import uuid
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from codrut.core.database import SessionLocal, engine
from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.forms.models import (
    QuestionnaireDefinition,
    QuestionnaireKey,
    QuestionnaireResponse,
    QuestionnaireResponseStatus,
)
from codrut.modules.identity import models as identity_models  # noqa: F401
from codrut.modules.scoring.models import ScoringResult
from codrut.modules.scoring.service import ScoringService
from codrut.tools.local_preview import build_preview_questionnaire_definitions

PREVIEW_DEFINITIONS = {
    definition.key: definition for definition in build_preview_questionnaire_definitions()
}


class FakeScoringRepository:
    def __init__(self) -> None:
        self.results: dict[uuid.UUID, ScoringResult] = {}

    async def get_by_assignment(self, assignment_id: uuid.UUID) -> ScoringResult | None:
        return self.results.get(assignment_id)

    async def add_scoring_result(self, result: ScoringResult) -> ScoringResult:
        self.results[result.assignment_id] = result
        return result

    async def delete_by_assignment(self, assignment_id: uuid.UUID) -> None:
        if assignment_id in self.results:
            del self.results[assignment_id]


@pytest.mark.asyncio
async def test_report_queries_enforce_company_project_scope_and_private_schema() -> None:
    service = ScoringService(session=None)  # type: ignore[arg-type]
    company_id = uuid.uuid4()
    project_id = uuid.uuid4()

    service.company_repository = SimpleNamespace(get_company=AsyncMock(return_value=None))
    with pytest.raises(DomainError) as missing_company_report:
        await service.get_company_report_aggregate(company_id)
    assert missing_company_report.value.code == "company_not_found"
    with pytest.raises(DomainError) as missing_company_review:
        await service.get_icare_answer_review(company_id)
    assert missing_company_review.value.code == "company_not_found"

    service.company_repository = SimpleNamespace(
        get_company=AsyncMock(return_value=SimpleNamespace(id=company_id)),
        get_project=AsyncMock(return_value=None),
    )
    with pytest.raises(DomainError) as missing_project_report:
        await service.get_company_report_aggregate(company_id, project_id)
    assert missing_project_report.value.code == "project_not_found"
    with pytest.raises(DomainError) as missing_project_review:
        await service.get_icare_answer_review(company_id, project_id)
    assert missing_project_review.value.code == "project_not_found"

    service.company_repository = SimpleNamespace(
        list_project_memberships=AsyncMock(return_value=[]),
        list_participants=AsyncMock(return_value=[]),
    )
    assert await service._list_report_participants(company_id, project_id) == []
    assert await service._list_report_participants(company_id, None) == []

    respondent = SimpleNamespace(id=uuid.uuid4(), full_name="Synthetic", email=None)
    assignment = SimpleNamespace(target_type="self", id=uuid.uuid4())
    definition = SimpleNamespace(
        schema={"sections": [{"id": "public"}]},
        private_config={"schema": {"sections": []}},
    )
    service.company_repository = SimpleNamespace(
        get_company=AsyncMock(return_value=SimpleNamespace(id=company_id)),
    )
    service.repository = SimpleNamespace(
        list_company_icare_answer_responses=AsyncMock(
            return_value=[
                (
                    assignment,
                    SimpleNamespace(answers={}),
                    respondent,
                    None,
                    definition,
                )
            ]
        )
    )

    review = await service.get_icare_answer_review(company_id)

    assert review.rows == []
    assert review.row_count == 0


@pytest.mark.asyncio
async def test_compute_and_save_score_rejects_missing_or_unsupported_metadata() -> None:
    service = ScoringService(session=None)  # type: ignore[arg-type]
    service.repository = FakeScoringRepository()

    for questionnaire_key in (QuestionnaireKey.lencioni, "custom"):
        with pytest.raises(DomainError) as missing_definition:
            await service.compute_and_save_score(
                assignment_id=uuid.uuid4(),
                questionnaire_key=questionnaire_key,
                answers={},
            )
        assert missing_definition.value.code == "scoring_not_supported"

        with pytest.raises(DomainError) as missing_metadata:
            await service.compute_and_save_score(
                assignment_id=uuid.uuid4(),
                questionnaire_key=questionnaire_key,
                answers={},
                definition_schema={},
            )
        assert missing_metadata.value.code == "scoring_metadata_missing"

    with pytest.raises(DomainError) as unsupported:
        await service.compute_and_save_score(
            assignment_id=uuid.uuid4(),
            questionnaire_key="custom",
            answers={},
            definition_schema={"scoring": {"method": "private_formula"}},
        )
    assert unsupported.value.code == "unsupported_scoring_method"


@pytest.mark.asyncio
async def test_compute_and_save_score_replaces_existing_empty_group_result() -> None:
    repo = FakeScoringRepository()
    service = ScoringService(session=None)  # type: ignore[arg-type]
    service.repository = repo
    assignment_id = uuid.uuid4()
    existing = ScoringResult(
        assignment_id=assignment_id,
        scores={"stale": 99},
        primary_result="stale",
    )
    repo.results[assignment_id] = existing

    result = await service.compute_and_save_score(
        assignment_id=assignment_id,
        questionnaire_key="custom",
        answers={},
        definition_schema={
            "scoring": {
                "method": "sum_by_group",
                "groups": [],
                "interpretation": [],
            }
        },
    )

    assert result is existing
    assert result.scores == {}
    assert result.primary_result is None


@pytest.mark.asyncio
async def test_compute_and_save_score_handles_partial_rules_and_empty_dimensions() -> None:
    service = ScoringService(session=None)  # type: ignore[arg-type]
    service.repository = FakeScoringRepository()

    group_result = await service.compute_and_save_score(
        assignment_id=uuid.uuid4(),
        questionnaire_key="custom",
        answers={"signal": 3},
        definition_schema={
            "scoring": {
                "method": "sum_by_group",
                "groups": [{"id": "partial", "question_ids": ["signal"]}],
                "interpretation": [
                    {"min": None, "max": 5, "label": "Missing minimum"},
                    {"min": 10, "max": 20, "label": "Outside range"},
                ],
            }
        },
    )
    assert group_result.scores["partial"] == {"score": 3, "interpretation": ""}

    driver_result = await service.compute_and_save_score(
        assignment_id=uuid.uuid4(),
        questionnaire_key="custom",
        answers={},
        definition_schema={
            "scoring": {
                "method": "sum_statement_scores_by_driver",
                "drivers": [],
            },
            "sections": [],
        },
    )
    assert driver_result.scores == {}
    assert driver_result.primary_result is None

    average_result = await service.compute_and_save_score(
        assignment_id=uuid.uuid4(),
        questionnaire_key="custom",
        answers={},
        definition_schema={
            "scoring": {"method": "average_statement_scores_by_section"},
            "sections": [],
        },
    )
    assert average_result.scores == {}
    assert average_result.primary_result is None


@pytest.mark.asyncio
async def test_average_scoring_handles_empty_blocks_clamping_and_grade_output() -> None:
    service = ScoringService(session=None)  # type: ignore[arg-type]
    service.repository = FakeScoringRepository()
    schema = {
        "scoring": {
            "method": "average_statement_scores_by_section",
            "scale_min": 1,
            "scale_max": 5,
            "score_unit": "grade_1_to_5",
        },
        "sections": [
            {
                "id": "empty_section",
                "questions": [{"id": "ignored", "type": "likert"}],
            },
            {
                "id": "feedback_section",
                "questions": [
                    {
                        "id": "empty_signal",
                        "type": "statement_score_set",
                        "statements": [{"id": "boolean"}],
                    },
                    {
                        "id": "feedback_signal",
                        "type": "statement_score_set",
                        "statements": [
                            {"id": "low"},
                            {"id": "high"},
                            {"id": "middle"},
                        ],
                    },
                ],
            },
        ],
    }

    result = await service.compute_and_save_score(
        assignment_id=uuid.uuid4(),
        questionnaire_key="custom",
        answers={
            "empty_signal:boolean": True,
            "feedback_signal:low": 0,
            "feedback_signal:high": 6,
            "feedback_signal:middle": "3",
        },
        definition_schema=schema,
    )

    assert result.scores["empty_section"] == {"score": 0, "raw_avg": 0, "answered": 0}
    assert result.scores["empty_signal"] == {"score": 0, "raw_avg": 0, "answered": 0}
    assert result.scores["feedback_signal"] == {
        "score": 3.0,
        "raw_avg": 3.0,
        "answered": 3,
    }
    assert result.primary_result == "feedback_signal"


@pytest.mark.asyncio
async def test_driver_scoring_ignores_unmapped_statements_and_invalid_scale_options() -> None:
    service = ScoringService(session=None)  # type: ignore[arg-type]
    service.repository = FakeScoringRepository()
    schema = {
        "scoring": {
            "method": "sum_statement_scores_by_driver",
            "drivers": [{"id": "known"}],
            "normalize_to": 0,
        },
        "sections": [
            {
                "questions": [
                    {"id": "ignored", "type": "likert"},
                    {
                        "id": "signals",
                        "type": "statement_score_set",
                        "scale": ["invalid", {"value": True}, {"value": 5}],
                        "statements": [
                            {"id": "unmapped", "scoring": {}},
                            {"id": "known", "scoring": {"driver": "known"}},
                            {"id": "new", "scoring": {"driver": "new"}, "scale": []},
                        ],
                    },
                ]
            }
        ],
    }

    result = await service.compute_and_save_score(
        assignment_id=uuid.uuid4(),
        questionnaire_key="custom",
        answers={"signals:known": 4, "signals:new": 2},
        definition_schema=schema,
    )

    assert result.scores == {"known": 4, "new": 2}
    assert result.primary_result == "known"


@pytest.mark.asyncio
async def test_compute_and_save_score_lencioni() -> None:
    repo = FakeScoringRepository()
    service = ScoringService(session=None)  # type: ignore
    service.repository = repo

    assignment_id = uuid.uuid4()

    schema = PREVIEW_DEFINITIONS["lencioni"].schema
    answers = {
        "team_sample_1": 3,
        "team_sample_2": 2,
        "team_sample_3": 1,
        "team_sample_4": 2,
        "team_sample_5": 3,
    }

    result = await service.compute_and_save_score(
        assignment_id=assignment_id,
        questionnaire_key=QuestionnaireKey.lencioni,
        answers=answers,
        definition_schema=schema,
    )

    assert result.assignment_id == assignment_id
    assert result.scores["team_signal_a"]["score"] == 3
    assert result.scores["team_signal_a"]["interpretation"] == "Rezultat demonstrativ."
    assert result.scores["team_signal_b"]["score"] == 2
    assert result.scores["team_signal_c"]["score"] == 1
    assert result.scores["team_signal_e"]["score"] == 3
    assert result.scores["team_signal_d"]["score"] == 2

    assert result.primary_result == "team_signal_c"


@pytest.mark.asyncio
async def test_compute_and_save_score_distress_drivers() -> None:
    repo = FakeScoringRepository()
    service = ScoringService(session=None)  # type: ignore
    service.repository = repo

    assignment_id = uuid.uuid4()

    schema = PREVIEW_DEFINITIONS["distress_drivers"].schema
    answers = {}
    for section in schema.get("sections", []):
        for question in section.get("questions", []):
            q_id = question["id"]
            for statement in question.get("statements", []):
                s_id = statement["id"]
                driver = statement["scoring"]["driver"]
                answers[f"{q_id}:{s_id}"] = 5 if driver == "work_signal_a" else 1

    result = await service.compute_and_save_score(
        assignment_id=assignment_id,
        questionnaire_key=QuestionnaireKey.distress_drivers,
        answers=answers,
        definition_schema=schema,
    )

    assert result.assignment_id == assignment_id
    assert result.scores["work_signal_a"] == 100
    assert result.scores["work_signal_b"] == 20
    assert result.primary_result == "work_signal_a"


@pytest.mark.asyncio
async def test_compute_and_save_score_normalizes_short_distress_sample() -> None:
    repo = FakeScoringRepository()
    service = ScoringService(session=None)  # type: ignore
    service.repository = repo

    schema = deepcopy(PREVIEW_DEFINITIONS["distress_drivers"].schema)
    schema["scoring"]["normalize_to"] = 100
    answers = {}
    for question in schema["sections"][0]["questions"]:
        for statement in question["statements"]:
            answers[f"{question['id']}:{statement['id']}"] = (
                5 if statement["scoring"]["driver"] == "work_signal_a" else 2
            )

    result = await service.compute_and_save_score(
        assignment_id=uuid.uuid4(),
        questionnaire_key=QuestionnaireKey.distress_drivers,
        answers=answers,
        definition_schema=schema,
    )

    assert result.scores["work_signal_a"] == 100
    assert result.scores["work_signal_b"] == 40
    assert result.primary_result == "work_signal_a"


@pytest.mark.asyncio
async def test_compute_and_save_score_boss_360_averages_icare_sections() -> None:
    repo = FakeScoringRepository()
    service = ScoringService(session=None)  # type: ignore
    service.repository = repo

    assignment_id = uuid.uuid4()

    schema = PREVIEW_DEFINITIONS["boss_360"].schema
    answers = {}
    for section in schema.get("sections", []):
        for question in section.get("questions", []):
            for statement in question.get("statements", []):
                score = 1 if question["id"] == "feedback_signal_c" else 4
                answers[f"{question['id']}:{statement['id']}"] = score

    result = await service.compute_and_save_score(
        assignment_id=assignment_id,
        questionnaire_key=QuestionnaireKey.boss_360,
        answers=answers,
        definition_schema=schema,
    )

    assert result.assignment_id == assignment_id
    assert result.scores["feedback_signal_a"] == {
        "score": 100.0,
        "raw_avg": 4.0,
        "answered": 2,
    }
    assert result.scores["feedback_signal_c"] == {
        "score": 0.0,
        "raw_avg": 1.0,
        "answered": 2,
    }
    assert result.scores["feedback_section_3"]["score"] == 0.0
    assert result.primary_result == "feedback_signal_c"


async def test_icare_answer_review_returns_project_scoped_source_answers() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            company = Company(id=uuid.uuid4(), name=f"Icare Review {uuid.uuid4().hex[:8]}")
            session.add(company)
            await session.flush()

            project = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Leadership Review",
            )
            other_project = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Other Review",
            )
            respondent = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Respondent One",
                email=f"respondent-{uuid.uuid4().hex[:8]}@example.com",
            )
            target = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Target Leader",
                email=f"target-{uuid.uuid4().hex[:8]}@example.com",
            )
            definition_schema = deepcopy(PREVIEW_DEFINITIONS["boss_360"].schema)
            definition_version = 100_000 + uuid.uuid4().int % 100_000
            definition = QuestionnaireDefinition(
                id=uuid.uuid4(),
                key="boss_360",
                version=definition_version,
                title="Synthetic feedback review",
                description="",
                schema=definition_schema,
                trainer_visibility_policy={"raw_responses": "visible"},
                active=False,
            )
            hidden_definition = QuestionnaireDefinition(
                id=uuid.uuid4(),
                key="boss_360",
                version=definition_version + 1,
                title="Synthetic hidden feedback review",
                description="",
                schema=deepcopy(definition_schema),
                trainer_visibility_policy={"raw_responses": "hidden"},
                active=False,
            )
            controlled_definition = QuestionnaireDefinition(
                id=uuid.uuid4(),
                key="boss_360",
                version=definition_version + 2,
                title="Synthetic aggregate-only feedback review",
                description="",
                schema=deepcopy(definition_schema),
                trainer_visibility_policy={"raw_responses": "policy_controlled"},
                active=False,
            )
            session.add_all(
                [
                    project,
                    other_project,
                    respondent,
                    target,
                    definition,
                    hidden_definition,
                    controlled_definition,
                ]
            )
            await session.flush()

            first_question = definition_schema["sections"][0]["questions"][0]
            first_statement = first_question["statements"][0]
            answer_key = f"{first_question['id']}:{first_statement['id']}"
            assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=respondent.id,
                questionnaire_key="boss_360",
                questionnaire_definition_id=definition.id,
                target_type=AssignmentTargetType.person,
                target_person_id=target.id,
                status=AssignmentStatus.submitted,
            )
            other_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=other_project.id,
                respondent_profile_id=respondent.id,
                questionnaire_key="boss_360",
                questionnaire_definition_id=definition.id,
                target_type=AssignmentTargetType.person,
                target_person_id=target.id,
                status=AssignmentStatus.submitted,
            )
            hidden_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=respondent.id,
                questionnaire_key="boss_360",
                questionnaire_definition_id=hidden_definition.id,
                target_type=AssignmentTargetType.person,
                target_person_id=target.id,
                status=AssignmentStatus.submitted,
            )
            controlled_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=respondent.id,
                questionnaire_key="boss_360",
                questionnaire_definition_id=controlled_definition.id,
                target_type=AssignmentTargetType.person,
                target_person_id=target.id,
                status=AssignmentStatus.submitted,
            )
            session.add_all(
                [assignment, other_assignment, hidden_assignment, controlled_assignment]
            )
            await session.flush()

            session.add_all(
                [
                    QuestionnaireResponse(
                        id=uuid.uuid4(),
                        assignment_id=assignment.id,
                        questionnaire_key="boss_360",
                        questionnaire_version=definition_version,
                        status=QuestionnaireResponseStatus.submitted,
                        answers={answer_key: 1},
                    ),
                    QuestionnaireResponse(
                        id=uuid.uuid4(),
                        assignment_id=other_assignment.id,
                        questionnaire_key="boss_360",
                        questionnaire_version=definition_version,
                        status=QuestionnaireResponseStatus.submitted,
                        answers={answer_key: 4},
                    ),
                    QuestionnaireResponse(
                        id=uuid.uuid4(),
                        assignment_id=hidden_assignment.id,
                        questionnaire_key="boss_360",
                        questionnaire_version=hidden_definition.version,
                        status=QuestionnaireResponseStatus.submitted,
                        answers={answer_key: 5},
                    ),
                    QuestionnaireResponse(
                        id=uuid.uuid4(),
                        assignment_id=controlled_assignment.id,
                        questionnaire_key="boss_360",
                        questionnaire_version=controlled_definition.version,
                        status=QuestionnaireResponseStatus.submitted,
                        answers={answer_key: 3},
                    ),
                ]
            )
            await session.flush()

            review = await ScoringService(session).get_icare_answer_review(company.id, project.id)

            assert review.row_count == 1
            row = review.rows[0]
            assert row.assignment_id == assignment.id
            assert row.respondent_name == "Respondent One"
            assert row.target_name == "Target Leader"
            assert row.section_label == "Dezvoltare"
            assert row.measurement_label == "Dezvoltare"
            assert row.statement_label == "Comportament sintetic pentru dezvoltare"
            assert row.answer_value == 1
            assert row.answer_label == "Nu clarifică un comportament legat de dezvoltare"
            assert row.answer_description is None

            await session.rollback()
    finally:
        await engine.dispose()


async def test_company_report_aggregate_is_scoped_and_uses_only_scored_results(
    questionnaire_definition_factory,
) -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            company = Company(id=uuid.uuid4(), name=f"Aggregate {uuid.uuid4().hex[:8]}")
            other_company = Company(id=uuid.uuid4(), name=f"Other Aggregate {uuid.uuid4().hex[:8]}")
            session.add_all([company, other_company])
            await session.flush()

            participant = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Ana Aggregate",
                email=f"ana-{uuid.uuid4().hex[:8]}@example.com",
            )
            other_participant = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=other_company.id,
                full_name="Other Aggregate",
                email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            )
            session.add_all([participant, other_participant])
            await session.flush()

            project = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Leadership Septembrie",
            )
            other_project = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Vânzări Octombrie",
            )
            session.add_all([project, other_project])
            await session.flush()

            definitions = {
                key: questionnaire_definition_factory(key)
                for key in ("lencioni", "distress_drivers", "boss_360")
            }
            session.add_all(definitions.values())
            await session.flush()

            lencioni_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=participant.id,
                questionnaire_key="lencioni",
                questionnaire_definition_id=definitions["lencioni"].id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.scored,
            )
            driver_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=participant.id,
                questionnaire_key="distress_drivers",
                questionnaire_definition_id=definitions["distress_drivers"].id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.scored,
            )
            submitted_without_score = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=participant.id,
                questionnaire_key="boss_360",
                questionnaire_definition_id=definitions["boss_360"].id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.submitted,
            )
            boss_360_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=participant.id,
                questionnaire_key="boss_360",
                questionnaire_definition_id=definitions["boss_360"].id,
                target_type=AssignmentTargetType.person,
                target_person_id=participant.id,
                status=AssignmentStatus.scored,
            )
            other_company_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=other_company.id,
                respondent_profile_id=other_participant.id,
                questionnaire_key="lencioni",
                questionnaire_definition_id=definitions["lencioni"].id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.scored,
            )
            other_project_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=other_project.id,
                respondent_profile_id=participant.id,
                questionnaire_key="lencioni",
                questionnaire_definition_id=definitions["lencioni"].id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.scored,
            )
            session.add_all(
                [
                    lencioni_assignment,
                    driver_assignment,
                    submitted_without_score,
                    boss_360_assignment,
                    other_company_assignment,
                    other_project_assignment,
                ]
            )
            await session.flush()

            session.add_all(
                [
                    ScoringResult(
                        assignment_id=lencioni_assignment.id,
                        primary_result="team_signal_a",
                        scores={
                            "team_signal_a": {"score": 6},
                            "team_signal_b": {"score": 9},
                            "team_signal_c": {"score": 8},
                            "team_signal_d": {"score": 7},
                            "team_signal_e": {"score": 5},
                        },
                    ),
                    ScoringResult(
                        assignment_id=driver_assignment.id,
                        primary_result="work_signal_d",
                        scores={
                            "work_signal_a": 10,
                            "work_signal_b": "20",
                            "work_signal_c": 30,
                            "work_signal_d": 60,
                            "work_signal_e": 50,
                        },
                    ),
                    ScoringResult(
                        assignment_id=boss_360_assignment.id,
                        primary_result="feedback_signal_c",
                        scores={
                            "feedback_signal_a": {"score": 80},
                            "feedback_signal_b": {"score": 75},
                            "feedback_signal_c": {"score": 60},
                            "feedback_signal_d": {"score": 90},
                            "feedback_signal_e": {"score": 85},
                        },
                    ),
                    ScoringResult(
                        assignment_id=other_company_assignment.id,
                        primary_result="team_signal_b",
                        scores={
                            "team_signal_a": {"score": 1},
                            "team_signal_b": {"score": 1},
                            "team_signal_c": {"score": 1},
                        },
                    ),
                    ScoringResult(
                        assignment_id=other_project_assignment.id,
                        primary_result="team_signal_a",
                        scores={
                            "team_signal_a": {"score": 15},
                            "team_signal_b": {"score": 15},
                            "team_signal_c": {"score": 15},
                            "team_signal_d": {"score": 15},
                            "team_signal_e": {"score": 15},
                        },
                    ),
                ]
            )
            await session.flush()

            aggregate = await ScoringService(session).get_company_report_aggregate(company.id)

            assert aggregate.total_assigned == 5
            assert aggregate.total_completed == 5
            assert aggregate.completion_rate == 100
            assert aggregate.lencioni_count == 2
            assert aggregate.driver_count == 1
            assert aggregate.boss_360_count == 1
            assert {result.assignment_id for result in aggregate.results} == {
                lencioni_assignment.id,
                driver_assignment.id,
                boss_360_assignment.id,
                other_project_assignment.id,
            }
            assert aggregate.lencioni_averages[0].avg == 10.5
            assert [item.id for item in aggregate.driver_averages] == [
                "work_signal_a",
                "work_signal_b",
                "work_signal_c",
                "work_signal_d",
                "work_signal_e",
            ]
            assert [item.avg for item in aggregate.driver_averages] == [10, 20, 30, 60, 50]
            assert all(item.interpretation is None for item in aggregate.driver_averages)
            assert aggregate.pcm_base_count == 0
            assert aggregate.pcm_phase_count == 0
            assert aggregate.pcm_base_distribution == []
            assert aggregate.pcm_phase_distribution == []
            boss_scores = {item.id: item.avg for item in aggregate.boss_360_averages}
            assert boss_scores["feedback_signal_c"] == 60
            assert boss_scores["feedback_signal_d"] == 90

            project_aggregate = await ScoringService(session).get_company_report_aggregate(
                company.id,
                project.id,
            )

            assert project_aggregate.total_assigned == 4
            assert {result.assignment_id for result in project_aggregate.results} == {
                lencioni_assignment.id,
                driver_assignment.id,
                boss_360_assignment.id,
            }

            await session.rollback()
    finally:
        await engine.dispose()


async def test_company_report_aggregate_includes_team_lenses_and_hierarchy_warnings(
    questionnaire_definition_factory,
) -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            company = Company(id=uuid.uuid4(), name=f"Hierarchy {uuid.uuid4().hex[:8]}")
            session.add(company)
            await session.flush()

            project = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Leadership canonical",
            )
            session.add(project)
            await session.flush()

            ceo = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Ana Maria",
                email=f"ana-{uuid.uuid4().hex[:8]}@example.com",
                pcm_base="harmonizer",
                pcm_phase="thinker",
            )
            manager = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Bogdan Manager",
                email=f"bogdan-{uuid.uuid4().hex[:8]}@example.com",
                pcm_base="ganditor",
                pcm_phase="persister",
            )
            member = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Clara Member",
                email=f"clara-{uuid.uuid4().hex[:8]}@example.com",
                pcm_base="promoter",
                pcm_phase="rebel",
            )
            external = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Dorin External",
                email=f"dorin-{uuid.uuid4().hex[:8]}@example.com",
                pcm_base="imaginer",
                pcm_phase="harmonizer",
            )
            session.add_all([ceo, manager, member, external])
            await session.flush()

            definitions = {
                key: questionnaire_definition_factory(key)
                for key in ("pcm_base", "phase", "distress_drivers", "lencioni")
            }
            session.add_all(definitions.values())
            await session.flush()

            session.add_all(
                [
                    ProjectMembership(
                        id=uuid.uuid4(),
                        company_id=company.id,
                        project_id=project.id,
                        participant_profile_id=ceo.id,
                        reports_to_name="1",
                        role_group="leadership",
                    ),
                    ProjectMembership(
                        id=uuid.uuid4(),
                        company_id=company.id,
                        project_id=project.id,
                        participant_profile_id=manager.id,
                        reports_to_name="AnaMaria",
                        role_group="manager",
                    ),
                    ProjectMembership(
                        id=uuid.uuid4(),
                        company_id=company.id,
                        project_id=project.id,
                        participant_profile_id=member.id,
                        reports_to_name="Bogdan Manager",
                        role_group="member",
                    ),
                    ProjectMembership(
                        id=uuid.uuid4(),
                        company_id=company.id,
                        project_id=project.id,
                        participant_profile_id=external.id,
                        reports_to_name="Outside Lead",
                        role_group="member",
                    ),
                ]
            )
            await session.flush()

            assignments = [
                QuestionnaireAssignment(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    respondent_profile_id=ceo.id,
                    questionnaire_key="pcm_base",
                    questionnaire_definition_id=definitions["pcm_base"].id,
                    target_type=AssignmentTargetType.self_assessment,
                    status=AssignmentStatus.submitted,
                ),
                QuestionnaireAssignment(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    respondent_profile_id=manager.id,
                    questionnaire_key="pcm_base",
                    questionnaire_definition_id=definitions["pcm_base"].id,
                    target_type=AssignmentTargetType.self_assessment,
                    status=AssignmentStatus.submitted,
                ),
                QuestionnaireAssignment(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    respondent_profile_id=member.id,
                    questionnaire_key="phase",
                    questionnaire_definition_id=definitions["phase"].id,
                    target_type=AssignmentTargetType.self_assessment,
                    status=AssignmentStatus.submitted,
                ),
                QuestionnaireAssignment(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    respondent_profile_id=external.id,
                    questionnaire_key="pcm_base",
                    questionnaire_definition_id=definitions["pcm_base"].id,
                    target_type=AssignmentTargetType.self_assessment,
                    status=AssignmentStatus.submitted,
                ),
                QuestionnaireAssignment(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    respondent_profile_id=manager.id,
                    questionnaire_key="distress_drivers",
                    questionnaire_definition_id=definitions["distress_drivers"].id,
                    target_type=AssignmentTargetType.self_assessment,
                    status=AssignmentStatus.scored,
                ),
                QuestionnaireAssignment(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    respondent_profile_id=member.id,
                    questionnaire_key="lencioni",
                    questionnaire_definition_id=definitions["lencioni"].id,
                    target_type=AssignmentTargetType.self_assessment,
                    status=AssignmentStatus.scored,
                ),
            ]
            session.add_all(assignments)
            await session.flush()

            session.add_all(
                [
                    ScoringResult(
                        assignment_id=assignments[4].id,
                        primary_result="work_signal_d",
                        scores={
                            "work_signal_a": 10,
                            "work_signal_b": 20,
                            "work_signal_c": 30,
                            "work_signal_d": 70,
                            "work_signal_e": 40,
                        },
                    ),
                    ScoringResult(
                        assignment_id=assignments[5].id,
                        primary_result="team_signal_a",
                        scores={
                            "team_signal_a": {"score": 4},
                            "team_signal_b": {"score": 5},
                            "team_signal_c": {"score": 6},
                            "team_signal_d": {"score": 7},
                            "team_signal_e": {"score": 8},
                        },
                    ),
                ]
            )
            await session.flush()

            aggregate = await ScoringService(session).get_company_report_aggregate(
                company.id,
                project.id,
            )

            assert aggregate.pcm_base_count == 4
            assert aggregate.pcm_phase_count == 4
            base_distribution = [
                (item.id, item.label, item.value) for item in aggregate.pcm_base_distribution
            ]
            assert base_distribution == [
                ("harmonizer", "Armonizator", 1),
                ("ganditor", "Gânditor", 1),
                ("imaginer", "Imaginator", 1),
                ("promoter", "Promotor", 1),
            ]
            assert aggregate.hierarchy_ambiguous is False
            assert [issue.code for issue in aggregate.hierarchy_issues] == ["manager_unresolved"]
            assert aggregate.hierarchy_issues[0].reports_to_name == "Outside Lead"

            team_by_id = {team.id: team for team in aggregate.team_lenses}
            assert team_by_id["leadership"].member_count == 2
            manager_team = next(
                team for team in aggregate.team_lenses if team.name == "Echipa Bogdan Manager"
            )
            assert manager_team.member_count == 2
            assert manager_team.assigned_count == 4
            assert manager_team.completed_count == 4
            assert manager_team.driver_count == 1
            assert manager_team.lencioni_count == 1
            assert manager_team.pcm_base_count == 2
            assert manager_team.pcm_phase_count == 2

            await session.rollback()
    finally:
        await engine.dispose()


async def test_company_report_aggregate_flags_ambiguous_referenced_manager_names() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            company = Company(id=uuid.uuid4(), name=f"Ambiguous {uuid.uuid4().hex[:8]}")
            session.add(company)
            await session.flush()

            first_manager = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Alex Dup",
                email=f"alex-one-{uuid.uuid4().hex[:8]}@example.com",
            )
            second_manager = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Alex Dup",
                email=f"alex-two-{uuid.uuid4().hex[:8]}@example.com",
            )
            member = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Mara Member",
                email=f"mara-{uuid.uuid4().hex[:8]}@example.com",
                reports_to_name="AlexDup",
            )
            session.add_all([first_manager, second_manager, member])
            await session.flush()

            aggregate = await ScoringService(session).get_company_report_aggregate(company.id)

            assert aggregate.hierarchy_ambiguous is True
            assert aggregate.team_lenses == []
            assert aggregate.hierarchy_issues[0].code == "manager_ambiguous"
            assert "Alex Dup" in (aggregate.hierarchy_ambiguity_message or "")

            await session.rollback()
    finally:
        await engine.dispose()
