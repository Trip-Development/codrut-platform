import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
)
from codrut.modules.assignments.team_snapshot import AssessmentCycleTeamSnapshot
from codrut.modules.companies.hierarchy import HierarchyIssue
from codrut.modules.forms.models import SubmissionProcessingStatus
from codrut.modules.scoring.schemas import (
    DriverRankSummaryResponse,
    ReportDistributionResponse,
)
from codrut.modules.scoring.service import (
    DriverRowSelection,
    ReportDimensionAccumulator,
    ReportParticipant,
    _accumulate_scores,
    _averages_from_accumulators,
    _build_driver_rank_summary,
    _build_icare_cohort_summaries,
    _build_score_summary,
    _definition_report_score_scale,
    _distribution_count,
    _distribution_from_completed_pcm_assignments,
    _driver_feedback_by_dimension,
    _format_pcm_label,
    _get_pcm_color,
    _interpretation_from_rules,
    _leadership_ids_for_report,
    _leadership_member_lencioni_summary,
    _non_empty_string,
    _pcm_profile_key,
    _prettify_score_key,
    _private_definition_schema,
    _report_dimensions,
    _report_hierarchy_issue,
    _reportable_score_availability,
    _select_latest_completed_driver_rows,
    _valid_interpretation_rules,
)


def _definition(private_schema: object) -> SimpleNamespace:
    return SimpleNamespace(private_config={"schema": private_schema}, schema={})


def _result(scores: dict) -> SimpleNamespace:
    return SimpleNamespace(scores=scores)


def _assignment(
    questionnaire_key: str,
    *,
    status: AssignmentStatus = AssignmentStatus.scored,
    respondent_profile_id: uuid.UUID | None = None,
    target_person_id: uuid.UUID | None = None,
    target_type: AssignmentTargetType = AssignmentTargetType.person,
    assignment_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
    target_team_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    respondent_id = respondent_profile_id or uuid.uuid4()
    return SimpleNamespace(
        id=assignment_id or uuid.uuid4(),
        created_at=created_at or datetime.now(UTC),
        questionnaire_key=questionnaire_key,
        status=status,
        respondent_profile_id=respondent_id,
        target_person_id=target_person_id or uuid.uuid4(),
        target_team_id=target_team_id,
        target_type=target_type,
    )


def _participant(
    participant_id: uuid.UUID,
    *,
    pcm_base: str | None = None,
    pcm_phase: str | None = None,
) -> ReportParticipant:
    return ReportParticipant(
        id=participant_id,
        full_name="Synthetic Participant",
        reports_to_name=None,
        role_group=None,
        pcm_base=pcm_base,
        pcm_phase=pcm_phase,
        user_id=None,
    )


def test_report_dimension_projection_rejects_private_or_malformed_metadata() -> None:
    assert _private_definition_schema(None) == {}
    assert _private_definition_schema(_definition([])) == {}  # type: ignore[arg-type]
    assert _valid_interpretation_rules(None) == ()
    assert _valid_interpretation_rules([{"min": 0}, "private"]) == ({"min": 0},)
    assert _non_empty_string(None) is None
    assert _non_empty_string("   ") is None
    assert _non_empty_string("  Visible  ") == "Visible"
    assert _prettify_score_key("") == ""


def test_report_dimensions_use_public_labels_rules_and_safe_fallbacks() -> None:
    group_definition = _definition(
        {
            "scoring": {
                "method": "sum_by_group",
                "interpretation": [{"min": 0, "max": 10, "label": "Global"}],
                "groups": [
                    "invalid",
                    {"label": "Missing ID"},
                    {"id": "team_signal", "label": "  Team signal  "},
                    {
                        "id": "team_fallback",
                        "interpretation": [{"min": 0, "max": 5, "label": "Specific"}],
                    },
                ],
            }
        }
    )
    dimensions = _report_dimensions(group_definition, {})  # type: ignore[arg-type]
    assert dimensions["team_signal"][0] == "Team signal"
    assert dimensions["team_signal"][1][0]["label"] == "Global"
    assert dimensions["team_fallback"][0] == "Team Fallback"
    assert dimensions["team_fallback"][1][0]["label"] == "Specific"

    driver_definition = _definition(
        {
            "scoring": {
                "method": "sum_statement_scores_by_driver",
                "drivers": [
                    None,
                    {"label": "Missing ID"},
                    {"id": "work_signal", "label": "Work signal"},
                ],
            }
        }
    )
    assert _report_dimensions(driver_definition, {}) == {  # type: ignore[arg-type]
        "work_signal": ("Work signal", ())
    }

    section_definition = _definition(
        {
            "scoring": {"method": "average_statement_scores_by_section"},
            "sections": [
                "invalid",
                {
                    "questions": [
                        "invalid",
                        {"id": "ignored", "type": "likert"},
                        {"type": "statement_score_set"},
                        {
                            "id": "feedback_signal",
                            "type": "statement_score_set",
                            "label": "Feedback signal",
                            "interpretation": [{"min": 1, "max": 5, "label": "Visible"}],
                        },
                    ]
                },
            ],
        }
    )
    assert _report_dimensions(section_definition, {}) == {  # type: ignore[arg-type]
        "feedback_signal": (
            "Feedback signal",
            ({"min": 1, "max": 5, "label": "Visible"},),
        )
    }

    assert _report_dimensions(  # type: ignore[arg-type]
        _definition({}), {"valid_score": "7", "private": None}
    ) == {"valid_score": ("Valid Score", ())}


def test_report_scale_is_derived_from_pinned_definition_scoring() -> None:
    lencioni = _definition(
        {
            "scoring": {
                "method": "sum_by_group",
                "interpretation": [
                    {"min": 0, "max": 4, "label": "Low"},
                    {"min": 5, "max": 12, "label": "High"},
                ],
            }
        }
    )
    drivers = _definition(
        {
            "scoring": {
                "method": "sum_statement_scores_by_driver",
                "normalize_to": 80,
            }
        }
    )
    percent_drivers = _definition(
        {
            "scoring": {
                "method": "sum_statement_scores_by_driver",
                "normalize_to": 100,
            }
        }
    )

    lencioni_scale = _definition_report_score_scale(lencioni)  # type: ignore[arg-type]
    driver_scale = _definition_report_score_scale(drivers)  # type: ignore[arg-type]
    percent_driver_scale = _definition_report_score_scale(  # type: ignore[arg-type]
        percent_drivers
    )
    assert lencioni_scale is not None
    assert (lencioni_scale.score_unit, lencioni_scale.scale_min, lencioni_scale.scale_max) == (
        "score",
        0,
        12,
    )
    assert driver_scale is not None
    assert (driver_scale.score_unit, driver_scale.scale_min, driver_scale.scale_max) == (
        "score",
        0,
        80,
    )
    assert percent_driver_scale is not None
    assert percent_driver_scale.score_unit == "percent"


def test_score_summary_suppresses_averages_from_incompatible_pinned_scales() -> None:
    ten_point = _definition(
        {
            "scoring": {
                "method": "sum_by_group",
                "scale_min": 0,
                "scale_max": 10,
            }
        }
    )
    five_point = _definition(
        {
            "scoring": {
                "method": "sum_by_group",
                "scale_min": 0,
                "scale_max": 5,
            }
        }
    )
    summary = _build_score_summary(  # type: ignore[arg-type]
        [
            (_assignment("lencioni"), _result({"trust": 8}), ten_point),
            (_assignment("lencioni"), _result({"trust": 4}), five_point),
        ]
    )

    assert summary.lencioni_count == 2
    assert summary.lencioni_averages == []
    assert summary.lencioni_scale.score_scale_compatible is False
    assert summary.lencioni_scale.unavailable_reason == "incompatible_score_scales"


def test_interpretation_and_average_helpers_ignore_invalid_rules() -> None:
    rules = (
        {"min": None, "max": 10, "label": "Missing minimum"},
        {"min": 0, "max": "bad", "label": "Invalid maximum"},
        {"min": 0, "max": 10, "label": "   "},
        {"min": 0, "max": 5, "label": "Low"},
        {
            "min": 6,
            "max": 10,
            "label": "High",
            "range_label": "Interval explicit",
        },
    )
    assert _interpretation_from_rules(4, rules) == ("Low", "0-5")
    assert _interpretation_from_rules(8, rules) == ("High", "Interval explicit")
    assert _interpretation_from_rules(20, rules) is None

    averages = _averages_from_accumulators(
        {
            "empty": ReportDimensionAccumulator(label="Empty"),
            "plain": ReportDimensionAccumulator(label="Plain", total=7, count=2),
            "interpreted": ReportDimensionAccumulator(
                label="Interpreted",
                total=16,
                count=2,
                interpretation_rules=rules,
            ),
        }
    )
    assert [item.id for item in averages] == ["interpreted", "plain"]
    assert averages[0].interpretation == "High"
    assert averages[1].interpretation is None


def test_score_accumulation_and_summary_exclude_unusable_results() -> None:
    accumulator: dict[str, ReportDimensionAccumulator] = {}
    assert (
        _accumulate_scores(  # type: ignore[arg-type]
            accumulator, _result({"invalid": True}), None
        )
        is False
    )
    assert _accumulate_scores(  # type: ignore[arg-type]
        accumulator, _result({"signal": {"score": "4.5"}}), None
    )
    assert _accumulate_scores(  # type: ignore[arg-type]
        accumulator, _result({"signal": 5.5}), None
    )
    assert accumulator["signal"].total == 10
    assert accumulator["signal"].count == 2

    rows = [
        (_assignment("lencioni", status=AssignmentStatus.assigned), _result({"a": 1}), None),
        (_assignment("lencioni"), None, None),
        (_assignment("lencioni"), _result({"a": 1}), None),
        (_assignment("distress_drivers"), _result({"b": 2, "c": 3}), None),
        (_assignment("boss_360"), _result({"c": 3}), None),
        (_assignment("unrelated"), _result({"d": 4}), None),
    ]
    summary = _build_score_summary(rows)  # type: ignore[arg-type]
    assert (summary.lencioni_count, summary.driver_count, summary.boss_360_count) == (
        1,
        1,
        1,
    )


def test_reportable_score_availability_distinguishes_queue_failure_and_orphan() -> None:
    scored = _assignment("lencioni")
    pending = _assignment("icare")
    failed = _assignment("distress_drivers")
    orphaned = _assignment("lencioni")
    response_derived = _assignment("pcm_base")
    rows = [
        (scored, _result({"signal": 1}), None),
        (pending, None, None),
        (failed, None, None),
        (orphaned, None, None),
        (response_derived, None, None),
    ]
    jobs = [
        SimpleNamespace(
            assignment_id=pending.id,
            status=SubmissionProcessingStatus.processing,
        ),
        SimpleNamespace(
            assignment_id=failed.id,
            status=SubmissionProcessingStatus.failed,
        ),
    ]

    availability = _reportable_score_availability(rows, jobs)  # type: ignore[arg-type]

    assert availability.scored == 1
    assert availability.pending == 1
    assert availability.failed == 1
    assert availability.orphaned == 1


def test_individual_lencioni_uses_target_team_and_top_leader_scope() -> None:
    chief_id = uuid.uuid4()
    leader_id = uuid.uuid4()
    member_one_id = uuid.uuid4()
    member_two_id = uuid.uuid4()
    leadership_team_id = uuid.uuid4()
    functional_team_id = uuid.uuid4()
    rows = [
        (
            _assignment(
                "lencioni",
                respondent_profile_id=chief_id,
                target_type=AssignmentTargetType.team,
                target_team_id=leadership_team_id,
            ),
            _result({"trust": 2}),
            None,
        ),
        (
            _assignment(
                "lencioni",
                respondent_profile_id=leader_id,
                target_type=AssignmentTargetType.team,
                target_team_id=leadership_team_id,
            ),
            _result({"trust": 4}),
            None,
        ),
        (
            _assignment(
                "lencioni",
                respondent_profile_id=member_one_id,
                target_type=AssignmentTargetType.team,
                target_team_id=functional_team_id,
            ),
            _result({"trust": 8}),
            None,
        ),
        (
            _assignment(
                "lencioni",
                respondent_profile_id=member_two_id,
                target_type=AssignmentTargetType.team,
                target_team_id=functional_team_id,
            ),
            _result({"trust": 10}),
            None,
        ),
    ]

    chief = _leadership_member_lencioni_summary(  # type: ignore[arg-type]
        rows,
        target_team_id=leadership_team_id,
    )
    leader = _leadership_member_lencioni_summary(  # type: ignore[arg-type]
        rows,
        target_team_id=functional_team_id,
    )

    assert chief.lencioni_count == 2
    assert chief.lencioni_averages[0].avg == 3
    assert leader.lencioni_count == 2
    assert leader.lencioni_averages[0].avg == 9


def test_ambiguous_hierarchy_keeps_explicit_leaders_for_individual_reports() -> None:
    explicit_leader_id = uuid.uuid4()
    inferred_leader_id = uuid.uuid4()
    participants = [
        ReportParticipant(
            id=explicit_leader_id,
            full_name="Explicit Leader",
            reports_to_name="Alex Dup",
            role_group="manager",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
        ReportParticipant(
            id=inferred_leader_id,
            full_name="Inferred Leader",
            reports_to_name=None,
            role_group=None,
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
    ]
    ambiguous_hierarchy = SimpleNamespace(
        ambiguous_name="Alex Dup",
        leadership_ids=set(),
    )

    assert _leadership_ids_for_report(ambiguous_hierarchy, participants) == {explicit_leader_id}


def test_driver_feedback_comes_from_the_pinned_definition() -> None:
    rows = [
        (
            _assignment("distress_drivers"),
            _result({"perfect": 62}),
            _definition(
                {
                    "scoring": {
                        "drivers": [
                            {
                                "id": "perfect",
                                "feedback_above_50": "Verifică dacă standardul te ajută.",
                            }
                        ]
                    }
                }
            ),
        )
    ]

    assert _driver_feedback_by_dimension(rows) == {  # type: ignore[arg-type]
        "perfect": "Verifică dacă standardul te ajută."
    }


def test_score_summary_excludes_icare_self_evaluation_from_external_aggregate() -> None:
    manager_id = uuid.uuid4()
    reviewer_id = uuid.uuid4()
    rows = [
        (
            _assignment(
                "boss_360",
                respondent_profile_id=manager_id,
                target_person_id=manager_id,
            ),
            _result({"clarity": 20}),
            None,
        ),
        (
            _assignment(
                "boss_360",
                respondent_profile_id=reviewer_id,
                target_person_id=manager_id,
            ),
            _result({"clarity": 80}),
            None,
        ),
    ]

    summary = _build_score_summary(rows)  # type: ignore[arg-type]

    assert summary.boss_360_count == 1
    assert summary.boss_360_averages[0].avg == 80


def test_icare_cohorts_keep_single_trainer_responses_visible_and_separate() -> None:
    chief_id = uuid.uuid4()
    leader_id = uuid.uuid4()
    direct_report_id = uuid.uuid4()
    participants = [
        ReportParticipant(
            id=chief_id,
            full_name="Ana Chief",
            reports_to_name=None,
            role_group="leadership",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
        ReportParticipant(
            id=leader_id,
            full_name="Bogdan Leader",
            reports_to_name="Ana Chief",
            role_group="leadership",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
        ReportParticipant(
            id=direct_report_id,
            full_name="Carmen Direct",
            reports_to_name="Bogdan Leader",
            role_group="individual",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
    ]
    rows = [
        (
            _assignment(
                "boss_360",
                respondent_profile_id=leader_id,
                target_person_id=leader_id,
            ),
            _result({"clarity": 70}),
            None,
        ),
        (
            _assignment(
                "boss_360",
                respondent_profile_id=chief_id,
                target_person_id=leader_id,
            ),
            _result({"clarity": 80}),
            None,
        ),
        (
            _assignment(
                "boss_360",
                respondent_profile_id=direct_report_id,
                target_person_id=leader_id,
            ),
            _result({"clarity": 90}),
            None,
        ),
    ]

    cohorts = _build_icare_cohort_summaries(rows, participants)  # type: ignore[arg-type]

    assert [(item.cohort, item.response_count) for item in cohorts] == [
        ("direct_team", 1),
        ("leadership_peers", 1),
        ("self", 1),
    ]
    assert [item.averages[0].avg for item in cohorts] == [90, 80, 70]


def test_icare_leadership_direct_report_is_a_peer_before_direct_team() -> None:
    chief_id = uuid.uuid4()
    leader_id = uuid.uuid4()
    participants = [
        ReportParticipant(
            id=chief_id,
            full_name="Ana Chief",
            reports_to_name=None,
            role_group="leadership",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
        ReportParticipant(
            id=leader_id,
            full_name="Bogdan Leader",
            reports_to_name="Ana Chief",
            role_group="leadership",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
    ]
    definition = _definition(
        {
            "scoring": {
                "method": "average_statement_scores_by_section",
                "score_unit": "grade_1_to_5",
                "scale_min": 1,
                "scale_max": 5,
            }
        }
    )
    rows = [
        (
            _assignment(
                "icare",
                respondent_profile_id=leader_id,
                target_person_id=chief_id,
            ),
            _result({"clarity": 4}),
            definition,
        )
    ]

    cohorts = _build_icare_cohort_summaries(rows, participants)  # type: ignore[arg-type]
    by_cohort = {item.cohort: item for item in cohorts}

    assert by_cohort["direct_team"].response_count == 0
    assert by_cohort["leadership_peers"].response_count == 1
    assert by_cohort["leadership_peers"].score_unit == "grade_1_to_5"
    assert by_cohort["leadership_peers"].scale_min == 1
    assert by_cohort["leadership_peers"].scale_max == 5


def test_icare_cycle_snapshot_ignores_current_organigram_changes() -> None:
    leader_id = uuid.uuid4()
    peer_id = uuid.uuid4()
    direct_report_id = uuid.uuid4()
    participants = [
        ReportParticipant(
            id=leader_id,
            full_name="Ana Leader",
            reports_to_name=None,
            role_group="individual",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
        ReportParticipant(
            id=peer_id,
            full_name="Bogdan Peer",
            reports_to_name=None,
            role_group="individual",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
        ReportParticipant(
            id=direct_report_id,
            full_name="Carmen Direct",
            reports_to_name="Alt manager",
            role_group="leadership",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
    ]
    snapshot = AssessmentCycleTeamSnapshot(
        leadership_ids=frozenset({leader_id, peer_id}),
        direct_report_ids_by_leader_id={leader_id: frozenset({direct_report_id})},
    )
    rows = [
        (
            _assignment(
                "icare",
                respondent_profile_id=leader_id,
                target_person_id=leader_id,
            ),
            _result({"clarity": 3}),
            None,
        ),
        (
            _assignment(
                "icare",
                respondent_profile_id=peer_id,
                target_person_id=leader_id,
            ),
            _result({"clarity": 4}),
            None,
        ),
        (
            _assignment(
                "icare",
                respondent_profile_id=direct_report_id,
                target_person_id=leader_id,
            ),
            _result({"clarity": 5}),
            None,
        ),
    ]

    cohorts = _build_icare_cohort_summaries(  # type: ignore[arg-type]
        rows,
        participants,
        team_snapshot=snapshot,
    )

    assert [(item.cohort, item.response_count) for item in cohorts] == [
        ("direct_team", 1),
        ("leadership_peers", 1),
        ("self", 1),
    ]
    assert [item.averages[0].avg for item in cohorts] == [5, 4, 3]


def test_icare_cohorts_suppress_incompatible_score_scales() -> None:
    chief_id = uuid.uuid4()
    leader_id = uuid.uuid4()
    member_id = uuid.uuid4()
    participants = [
        ReportParticipant(
            id=chief_id,
            full_name="Ana Chief",
            reports_to_name=None,
            role_group="leadership",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
        ReportParticipant(
            id=leader_id,
            full_name="Bogdan Leader",
            reports_to_name="Ana Chief",
            role_group="leadership",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
        ReportParticipant(
            id=member_id,
            full_name="Carmen Member",
            reports_to_name="Ana Chief",
            role_group="individual",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
    ]
    percent_definition = _definition(
        {
            "scoring": {
                "method": "average_statement_scores_by_section",
                "score_unit": "percent",
                "scale_min": 1,
                "scale_max": 4,
            }
        }
    )
    grade_definition = _definition(
        {
            "scoring": {
                "method": "average_statement_scores_by_section",
                "score_unit": "grade_1_to_5",
                "scale_min": 1,
                "scale_max": 5,
            }
        }
    )
    rows = [
        (
            _assignment(
                "icare",
                respondent_profile_id=leader_id,
                target_person_id=chief_id,
            ),
            _result({"clarity": 75}),
            percent_definition,
        ),
        (
            _assignment(
                "icare",
                respondent_profile_id=member_id,
                target_person_id=chief_id,
            ),
            _result({"clarity": 4}),
            grade_definition,
        ),
    ]

    cohorts = _build_icare_cohort_summaries(rows, participants)  # type: ignore[arg-type]

    assert all(item.response_count == 0 and item.averages == [] for item in cohorts)
    assert all(item.score_scale_compatible is False for item in cohorts)
    assert all(item.unavailable_reason == "incompatible_score_scales" for item in cohorts)


def test_icare_hierarchy_ambiguity_preserves_explicit_leadership_self_result() -> None:
    leader_id = uuid.uuid4()
    duplicate_one_id = uuid.uuid4()
    duplicate_two_id = uuid.uuid4()
    participants = [
        ReportParticipant(
            id=leader_id,
            full_name="Ana Leader",
            reports_to_name="Alex Dup",
            role_group="leadership",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
        ReportParticipant(
            id=duplicate_one_id,
            full_name="Alex Dup",
            reports_to_name=None,
            role_group="leadership",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
        ReportParticipant(
            id=duplicate_two_id,
            full_name="Alex Dup",
            reports_to_name=None,
            role_group="leadership",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
    ]
    rows = [
        (
            _assignment(
                "icare",
                respondent_profile_id=leader_id,
                target_person_id=leader_id,
            ),
            _result({"clarity": 80}),
            _definition(
                {
                    "scoring": {
                        "method": "average_statement_scores_by_section",
                        "score_unit": "percent",
                        "scale_min": 1,
                        "scale_max": 4,
                    }
                }
            ),
        ),
        (
            _assignment(
                "icare",
                respondent_profile_id=duplicate_one_id,
                target_person_id=leader_id,
            ),
            _result({"clarity": 60}),
            None,
        ),
    ]

    cohorts = _build_icare_cohort_summaries(rows, participants)  # type: ignore[arg-type]
    by_cohort = {item.cohort: item for item in cohorts}

    assert by_cohort["self"].response_count == 1
    assert by_cohort["self"].averages[0].avg == 80
    assert by_cohort["direct_team"].response_count == 0
    assert by_cohort["leadership_peers"].response_count == 0


def test_icare_cohorts_exclude_non_leadership_targets() -> None:
    chief_id = uuid.uuid4()
    leader_id = uuid.uuid4()
    member_id = uuid.uuid4()
    direct_report_id = uuid.uuid4()
    participants = [
        ReportParticipant(
            id=chief_id,
            full_name="Ana Chief",
            reports_to_name=None,
            role_group="leadership",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
        ReportParticipant(
            id=leader_id,
            full_name="Bogdan Leader",
            reports_to_name="Ana Chief",
            role_group="leadership",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
        ReportParticipant(
            id=member_id,
            full_name="Carmen Member",
            reports_to_name="Bogdan Leader",
            role_group="member",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
        ReportParticipant(
            id=direct_report_id,
            full_name="Dan Direct",
            reports_to_name="Carmen Member",
            role_group="member",
            pcm_base=None,
            pcm_phase=None,
            user_id=None,
        ),
    ]
    rows = [
        (
            _assignment(
                "boss_360",
                respondent_profile_id=member_id,
                target_person_id=member_id,
            ),
            _result({"clarity": 70}),
            None,
        ),
        (
            _assignment(
                "boss_360",
                respondent_profile_id=direct_report_id,
                target_person_id=member_id,
            ),
            _result({"clarity": 90}),
            None,
        ),
    ]

    cohorts = _build_icare_cohort_summaries(rows, participants)  # type: ignore[arg-type]

    assert [(item.cohort, item.response_count) for item in cohorts] == [
        ("direct_team", 0),
        ("leadership_peers", 0),
        ("self", 0),
    ]
    assert all(item.averages == [] for item in cohorts)


def _driver_definition() -> SimpleNamespace:
    return _definition(
        {
            "scoring": {
                "method": "sum_statement_scores_by_driver",
                "drivers": [
                    {"id": "be_perfect", "label": "Fii perfect"},
                    {"id": "hurry_up", "label": "Grăbește-te"},
                    {"id": "try_hard", "label": "Străduiește-te"},
                ],
            }
        }
    )


def _driver_selection_and_ranking(
    rows: list[tuple],
) -> tuple[DriverRowSelection, DriverRankSummaryResponse]:
    selection = _select_latest_completed_driver_rows(rows)  # type: ignore[arg-type]
    ranking = _build_driver_rank_summary(  # type: ignore[arg-type]
        selection.rankable_rows,
        insufficient_driver_score_count=selection.insufficient_driver_score_count,
    )
    return selection, ranking


def test_driver_rank_summary_counts_normal_primary_and_secondary_once() -> None:
    rows = [
        (
            _assignment("distress_drivers", respondent_profile_id=uuid.uuid4()),
            _result({"be_perfect": 90, "hurry_up": 70, "try_hard": 20}),
            _driver_definition(),
        ),
        (
            _assignment("distress_drivers", respondent_profile_id=uuid.uuid4()),
            _result({"be_perfect": 10, "hurry_up": 80, "try_hard": 70}),
            _driver_definition(),
        ),
    ]

    _selection, ranking = _driver_selection_and_ranking(rows)

    assert ranking.total_people == 2
    assert {item.id: item.value for item in ranking.first_rank} == {
        "be_perfect": 1,
        "hurry_up": 1,
    }
    assert {item.id: item.value for item in ranking.second_rank} == {
        "hurry_up": 1,
        "try_hard": 1,
    }
    assert ranking.first_rank_tie_breaks == 0
    assert ranking.second_rank_tie_breaks == 0
    assert ranking.insufficient_driver_score_count == 0


def test_driver_rank_summary_counts_one_participant_in_both_ranks() -> None:
    rows = [
        (
            _assignment("distress_drivers", respondent_profile_id=uuid.uuid4()),
            _result({"be_perfect": 10, "hurry_up": 20, "try_hard": 30}),
            _driver_definition(),
        )
    ]

    _selection, ranking = _driver_selection_and_ranking(rows)

    assert ranking.total_people == 1
    assert [(item.id, item.value) for item in ranking.first_rank] == [("try_hard", 1)]
    assert [(item.id, item.value) for item in ranking.second_rank] == [("hurry_up", 1)]
    assert ranking.insufficient_driver_score_count == 0


def test_driver_rank_summary_uses_definition_order_for_all_way_tie() -> None:
    rows = [
        (
            _assignment("distress_drivers", respondent_profile_id=uuid.uuid4()),
            _result({"try_hard": 60, "hurry_up": 60, "be_perfect": 60}),
            _driver_definition(),
        )
    ]

    _selection, ranking = _driver_selection_and_ranking(rows)

    assert [(item.id, item.value) for item in ranking.first_rank] == [("be_perfect", 1)]
    assert [(item.id, item.value) for item in ranking.second_rank] == [("hurry_up", 1)]
    assert ranking.first_rank_tie_breaks == 1
    assert ranking.second_rank_tie_breaks == 1


def test_driver_rank_summary_top_two_tie_only_counts_first_tie_break() -> None:
    rows = [
        (
            _assignment("distress_drivers", respondent_profile_id=uuid.uuid4()),
            _result({"try_hard": 40, "hurry_up": 60, "be_perfect": 60}),
            _driver_definition(),
        )
    ]

    _selection, ranking = _driver_selection_and_ranking(rows)

    assert [item.id for item in ranking.first_rank] == ["be_perfect"]
    assert [item.id for item in ranking.second_rank] == ["hurry_up"]
    assert ranking.first_rank_tie_breaks == 1
    assert ranking.second_rank_tie_breaks == 0


def test_driver_average_keeps_all_rows_while_pies_use_latest_person_result() -> None:
    participant_id = uuid.uuid4()
    same_created_at = datetime(2026, 7, 30, tzinfo=UTC)
    lower_id = uuid.UUID(int=1)
    higher_id = uuid.UUID(int=2)
    rows = [
        (
            _assignment(
                "distress_drivers",
                respondent_profile_id=participant_id,
                assignment_id=higher_id,
                created_at=same_created_at,
            ),
            _result({"be_perfect": 90, "hurry_up": 30, "try_hard": 10}),
            _driver_definition(),
        ),
        (
            _assignment(
                "distress_drivers",
                respondent_profile_id=participant_id,
                assignment_id=lower_id,
                created_at=same_created_at,
            ),
            _result({"be_perfect": 5, "hurry_up": 95, "try_hard": 10}),
            _driver_definition(),
        ),
    ]

    selection, ranking = _driver_selection_and_ranking(rows)
    summary = _build_score_summary(rows)  # type: ignore[arg-type]

    assert [row[0].id for row in selection.rankable_rows] == [higher_id]
    assert summary.driver_count == 2
    assert ranking.total_people == 1
    assert {item.id: item.avg for item in summary.driver_averages} == {
        "be_perfect": 47.5,
        "hurry_up": 62.5,
        "try_hard": 10,
    }
    assert [item.id for item in ranking.first_rank] == ["be_perfect"]
    assert [item.id for item in ranking.second_rank] == ["hurry_up"]


def test_latest_valid_driver_row_ignores_a_newer_malformed_result() -> None:
    participant_id = uuid.uuid4()
    older_id = uuid.UUID(int=1)
    newer_id = uuid.UUID(int=2)
    rows = [
        (
            _assignment(
                "distress_drivers",
                respondent_profile_id=participant_id,
                assignment_id=older_id,
                created_at=datetime(2026, 7, 29, tzinfo=UTC),
            ),
            _result({"be_perfect": 80, "hurry_up": 60, "try_hard": 20}),
            _driver_definition(),
        ),
        (
            _assignment(
                "distress_drivers",
                respondent_profile_id=participant_id,
                assignment_id=newer_id,
                created_at=datetime(2026, 7, 30, tzinfo=UTC),
            ),
            _result({"be_perfect": 99, "hurry_up": "invalid"}),
            _driver_definition(),
        ),
    ]

    selection, ranking = _driver_selection_and_ranking(rows)
    summary = _build_score_summary(rows)  # type: ignore[arg-type]

    assert [row[0].id for row in selection.rankable_rows] == [older_id]
    assert selection.insufficient_driver_score_count == 0
    assert summary.driver_count == 2
    assert ranking.total_people == 1
    assert {item.id: item.avg for item in summary.driver_averages} == {
        "be_perfect": 89.5,
        "hurry_up": 60,
        "try_hard": 20,
    }
    assert [item.id for item in ranking.first_rank] == ["be_perfect"]
    assert [item.id for item in ranking.second_rank] == ["hurry_up"]


def test_driver_exclusion_counts_people_without_any_valid_result_once() -> None:
    participant_id = uuid.uuid4()
    rows = [
        (
            _assignment(
                "distress_drivers",
                respondent_profile_id=participant_id,
                created_at=datetime(2026, 7, 29, tzinfo=UTC),
            ),
            _result({"be_perfect": "invalid"}),
            _driver_definition(),
        ),
        (
            _assignment(
                "distress_drivers",
                respondent_profile_id=participant_id,
                created_at=datetime(2026, 7, 30, tzinfo=UTC),
            ),
            _result({"hurry_up": 90}),
            _driver_definition(),
        ),
    ]

    selection, ranking = _driver_selection_and_ranking(rows)

    assert selection.rankable_rows == ()
    assert len(selection.average_rows) == 1
    assert selection.insufficient_driver_score_count == 1
    assert ranking.total_people == 0
    assert ranking.insufficient_driver_score_count == 1


def test_driver_rank_summary_reports_nonnumeric_and_one_driver_exclusions() -> None:
    rows = [
        (
            _assignment("distress_drivers", respondent_profile_id=uuid.uuid4()),
            _result({"be_perfect": "invalid", "hurry_up": None}),
            _driver_definition(),
        ),
        (
            _assignment("distress_drivers", respondent_profile_id=uuid.uuid4()),
            _result({"be_perfect": 50, "hurry_up": "invalid"}),
            _driver_definition(),
        ),
    ]

    selection, ranking = _driver_selection_and_ranking(rows)
    summary = _build_score_summary(rows)  # type: ignore[arg-type]

    assert summary.driver_count == 1
    assert {item.id: item.avg for item in summary.driver_averages} == {"be_perfect": 50}
    assert ranking.total_people == 0
    assert ranking.first_rank == []
    assert ranking.second_rank == []
    assert ranking.insufficient_driver_score_count == 2


def test_driver_rank_contract_rejects_distributions_that_do_not_sum_to_people() -> None:
    with pytest.raises(ValidationError, match="First-rank driver counts"):
        DriverRankSummaryResponse(
            total_people=1,
            first_rank=[],
            second_rank=[ReportDistributionResponse(id="perfect", label="Perfect", value=1)],
            first_rank_tie_breaks=0,
            second_rank_tie_breaks=0,
            insufficient_driver_score_count=0,
        )


def test_pcm_distribution_requires_completed_known_profiles() -> None:
    thinker_id = uuid.uuid4()
    alias_id = uuid.uuid4()
    blank_id = uuid.uuid4()
    missing_id = uuid.uuid4()
    participants = [
        _participant(thinker_id, pcm_base=" thinker "),
        _participant(alias_id, pcm_base="Gânditor"),
        _participant(blank_id, pcm_base="  "),
    ]
    assignments = [
        _assignment("pcm_base", respondent_profile_id=thinker_id),
        _assignment("pcm_base", respondent_profile_id=alias_id),
        _assignment("pcm_base", respondent_profile_id=blank_id),
        _assignment("pcm_base", respondent_profile_id=missing_id),
        _assignment(
            "pcm_base",
            status=AssignmentStatus.assigned,
            respondent_profile_id=thinker_id,
        ),
        _assignment("lencioni", respondent_profile_id=thinker_id),
    ]
    distribution = _distribution_from_completed_pcm_assignments(
        participants,
        assignments,  # type: ignore[arg-type]
        "pcm_base",
    )
    assert _distribution_count(distribution) == 2
    assert [item.label for item in distribution] == ["Gânditor", "Gânditor"]
    assert all(item.color == "#2563eb" for item in distribution)
    assert _pcm_profile_key(None) is None
    assert _pcm_profile_key("Gânditor") == "thinker"
    assert _pcm_profile_key("harmo_nizer") == "harmonizer"
    assert _format_pcm_label(None) == "Necompletată"
    assert _format_pcm_label("custom_profile") == "Custom Profile"
    assert _get_pcm_color("custom") is None


def test_hierarchy_issue_copy_is_specific_and_preserves_fallback() -> None:
    participant_id = uuid.uuid4()
    unresolved = _report_hierarchy_issue(
        HierarchyIssue(
            code="manager_unresolved",
            message="fallback",
            participant_id=participant_id,
            participant_name="Ana",
            reports_to_name="Bogdan",
        )
    )
    self_reference = _report_hierarchy_issue(
        HierarchyIssue(
            code="manager_self_reference",
            message="fallback",
            participant_id=participant_id,
            participant_name="Ana",
            reports_to_name="Ana",
        )
    )
    fallback = _report_hierarchy_issue(
        HierarchyIssue(
            code="other",
            message="Mesaj păstrat",
            participant_id=participant_id,
        )
    )
    assert '"Bogdan"' in unresolved.message
    assert "propriul manager" in self_reference.message
    assert fallback.message == "Mesaj păstrat"
