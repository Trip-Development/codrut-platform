import uuid
from types import SimpleNamespace

from codrut.modules.assignments.models import AssignmentStatus, AssignmentTargetType
from codrut.modules.companies.hierarchy import HierarchyIssue
from codrut.modules.scoring.service import (
    ReportDimensionAccumulator,
    ReportParticipant,
    _accumulate_scores,
    _averages_from_accumulators,
    _build_driver_rank_summary,
    _build_icare_cohort_summaries,
    _build_score_summary,
    _distribution_count,
    _distribution_from_completed_pcm_assignments,
    _driver_feedback_by_dimension,
    _format_pcm_label,
    _get_pcm_color,
    _interpretation_from_rules,
    _non_empty_string,
    _pcm_profile_key,
    _prettify_score_key,
    _private_definition_schema,
    _report_dimensions,
    _report_hierarchy_issue,
    _valid_interpretation_rules,
)


def _definition(private_schema: object) -> SimpleNamespace:
    return SimpleNamespace(private_config={"schema": private_schema})


def _result(scores: dict) -> SimpleNamespace:
    return SimpleNamespace(scores=scores)


def _assignment(
    questionnaire_key: str,
    *,
    status: AssignmentStatus = AssignmentStatus.scored,
    respondent_profile_id: uuid.UUID | None = None,
    target_person_id: uuid.UUID | None = None,
    target_type: AssignmentTargetType = AssignmentTargetType.person,
) -> SimpleNamespace:
    respondent_id = respondent_profile_id or uuid.uuid4()
    return SimpleNamespace(
        questionnaire_key=questionnaire_key,
        status=status,
        respondent_profile_id=respondent_id,
        target_person_id=target_person_id or uuid.uuid4(),
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
    ) == {
        "valid_score": ("Valid Score", ())
    }


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
    assert _accumulate_scores(  # type: ignore[arg-type]
        accumulator, _result({"invalid": True}), None
    ) is False
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
        (_assignment("distress_drivers"), _result({"b": 2}), None),
        (_assignment("boss_360"), _result({"c": 3}), None),
        (_assignment("unrelated"), _result({"d": 4}), None),
    ]
    summary = _build_score_summary(rows)  # type: ignore[arg-type]
    assert (summary.lencioni_count, summary.driver_count, summary.boss_360_count) == (
        1,
        1,
        1,
    )


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


def test_driver_rank_summary_uses_definition_order_for_ties_and_exact_totals() -> None:
    first_participant = uuid.uuid4()
    second_participant = uuid.uuid4()
    definition = _definition(
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
    rows = [
        (
            _assignment(
                "distress_drivers",
                respondent_profile_id=first_participant,
            ),
            _result({"try_hard": 60, "hurry_up": 60, "be_perfect": 60}),
            definition,
        ),
        (
            _assignment(
                "distress_drivers",
                respondent_profile_id=second_participant,
            ),
            _result({"try_hard": 20, "hurry_up": 70, "be_perfect": 80}),
            definition,
        ),
    ]

    ranking = _build_driver_rank_summary(rows)  # type: ignore[arg-type]

    assert ranking.total_people == 2
    assert sum(item.value for item in ranking.first_rank) == 2
    assert sum(item.value for item in ranking.second_rank) == 2
    assert {item.id: item.value for item in ranking.first_rank} == {"be_perfect": 2}
    assert {item.id: item.value for item in ranking.second_rank} == {"hurry_up": 2}
    assert ranking.first_rank_tie_breaks == 1
    assert ranking.second_rank_tie_breaks == 1


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
