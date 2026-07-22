import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select

from codrut.core.database import SessionLocal, engine
from codrut.modules.assignments.models import (
    AssessmentCycle,
    AssessmentCycleStatus,
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
)
from codrut.modules.companies.models import Company, CompanyProject, ParticipantProfile
from codrut.modules.forms.models import QuestionnaireDefinition
from codrut.modules.identity import models as identity_models  # noqa: F401
from codrut.modules.scoring.models import (
    ResultPublication,
    ResultPublicationKind,
    ScoringResult,
)
from codrut.modules.scoring.publication import ResultPublicationService


def _definition(*, key: str = "pilot_feedback") -> QuestionnaireDefinition:
    return QuestionnaireDefinition(
        id=uuid.uuid4(),
        key=key,
        version=1_000_000 + int(uuid.uuid4().hex[:6], 16),
        title="Feedback pilot",
        schema={"sections": []},
        private_config={
            "schema": {
                "scoring": {"method": "private_formula", "weights": [9, 4, 1]},
            }
        },
        feedback_policy={
            "publication": "aggregate",
            "minimum_completed": 2,
            "target_completed": 3,
            "dimension_ids": ["clarity"],
            "participant_results": {
                "publication": "scores",
                "dimension_ids": ["clarity"],
                "target_types": ["self"],
            },
        },
        content_checksum=uuid.uuid4().hex + uuid.uuid4().hex,
        active=True,
    )


async def test_individual_publication_is_idempotent_and_excludes_private_scoring() -> None:
    await engine.dispose()
    async with SessionLocal() as session:
        company = Company(id=uuid.uuid4(), name=f"Publication {uuid.uuid4()}")
        profile = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Ana Publicată",
            email=f"ana-{uuid.uuid4().hex[:8]}@example.com",
        )
        definition = _definition()
        assignment = QuestionnaireAssignment(
            id=uuid.uuid4(),
            company_id=company.id,
            respondent_profile_id=profile.id,
            questionnaire_key=definition.key,
            questionnaire_definition_id=definition.id,
            target_type=AssignmentTargetType.self_assessment,
            status=AssignmentStatus.scored,
        )
        session.add_all([company, definition])
        await session.flush()
        session.add(profile)
        await session.flush()
        session.add(assignment)
        await session.flush()
        session.add(
            ScoringResult(
                assignment_id=assignment.id,
                scores={"clarity": {"score": 4.2, "private_weight": 9}},
                primary_result="clarity",
            )
        )
        await session.flush()

        service = ResultPublicationService(session)
        await service.reconcile_assignment(assignment.id)
        await service.reconcile_assignment(assignment.id)
        publications = list(
            (
                await session.execute(
                    select(ResultPublication).where(
                        ResultPublication.source_assignment_id == assignment.id
                    )
                )
            ).scalars()
        )

        assert len(publications) == 1
        publication = publications[0]
        assert publication.kind == ResultPublicationKind.individual
        assert publication.participant_profile_id == profile.id
        assert publication.source_count == 1
        assert publication.revoked_at is None
        serialized_policy = json.dumps(publication.policy_snapshot)
        assert "private_formula" not in serialized_policy
        assert "weights" not in serialized_policy
        await session.rollback()
    await engine.dispose()


async def test_aggregate_publications_never_mix_assessment_cycles() -> None:
    await engine.dispose()
    async with SessionLocal() as session:
        company = Company(id=uuid.uuid4(), name=f"Cycle publication {uuid.uuid4()}")
        project = CompanyProject(
            id=uuid.uuid4(),
            company_id=company.id,
            name="Program longitudinal",
        )
        target = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Manager evaluat",
            email=f"manager-{uuid.uuid4().hex[:8]}@example.com",
        )
        reviewers = [
            ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name=f"Reviewer ciclu {index}",
                email=f"cycle-reviewer-{index}-{uuid.uuid4().hex[:8]}@example.com",
            )
            for index in range(2)
        ]
        definition = _definition(key="boss_360")
        cycles = [
            AssessmentCycle(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                sequence=1,
                name="Evaluare inițială",
                status=AssessmentCycleStatus.closed,
            ),
            AssessmentCycle(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                sequence=2,
                name="Reevaluare 1",
                status=AssessmentCycleStatus.active,
            ),
        ]
        session.add_all([company, definition])
        await session.flush()
        session.add_all([project, target, *reviewers])
        await session.flush()
        session.add_all(cycles)
        await session.flush()

        cycle_assignments: list[list[QuestionnaireAssignment]] = []
        for cycle in cycles:
            round_id = uuid.uuid4()
            assignments = [
                QuestionnaireAssignment(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    assessment_cycle_id=cycle.id,
                    assignment_round_id=round_id,
                    respondent_profile_id=reviewer.id,
                    questionnaire_key=definition.key,
                    questionnaire_definition_id=definition.id,
                    target_type=AssignmentTargetType.person,
                    target_person_id=target.id,
                    status=AssignmentStatus.scored,
                )
                for reviewer in reviewers
            ]
            cycle_assignments.append(assignments)
            session.add_all(assignments)
            await session.flush()
            session.add_all(
                [
                    ScoringResult(
                        assignment_id=assignment.id,
                        scores={"clarity": {"score": 3 + cycle.sequence}},
                        primary_result="clarity",
                    )
                    for assignment in assignments
                ]
            )
        await session.flush()

        service = ResultPublicationService(session)
        for assignments in cycle_assignments:
            await service.reconcile_assignment(assignments[-1].id)

        publications = list(
            (
                await session.execute(
                    select(ResultPublication)
                    .where(ResultPublication.kind == ResultPublicationKind.aggregate_360)
                    .where(ResultPublication.participant_profile_id == target.id)
                    .order_by(ResultPublication.assessment_cycle_id)
                )
            ).scalars()
        )
        assert len(publications) == 2
        assert {publication.assessment_cycle_id for publication in publications} == {
            cycle.id for cycle in cycles
        }
        assert all(publication.source_count == 2 for publication in publications)
        await session.rollback()
    await engine.dispose()


async def test_aggregate_publication_requires_threshold_and_is_revoked_when_it_drops() -> None:
    await engine.dispose()
    async with SessionLocal() as session:
        company = Company(id=uuid.uuid4(), name=f"Aggregate publication {uuid.uuid4()}")
        target = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Bianca Target",
            email=f"bianca-{uuid.uuid4().hex[:8]}@example.com",
        )
        reviewers = [
            ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name=f"Reviewer {index}",
                email=f"reviewer-{index}-{uuid.uuid4().hex[:8]}@example.com",
            )
            for index in range(2)
        ]
        definition = _definition(key="boss_360")
        definition.feedback_policy = {}
        definition.private_config = None
        definition.schema = {
            "sections": [
                {
                    "id": "feedback",
                    "questions": [
                        {
                            "id": "clarity",
                            "type": "statement_score_set",
                            "label": "Claritate",
                            "statements": [],
                        }
                    ],
                }
            ],
            "scoring": {"method": "average_statement_scores_by_section"},
        }
        round_id = uuid.uuid4()
        session.add_all([company, definition])
        await session.flush()
        session.add_all([target, *reviewers])
        await session.flush()
        assignments = [
            QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                assignment_round_id=uuid.uuid4(),
                respondent_profile_id=reviewer.id,
                questionnaire_key=definition.key,
                questionnaire_definition_id=definition.id,
                target_type=AssignmentTargetType.person,
                target_person_id=target.id,
                status=AssignmentStatus.scored,
            )
            for reviewer in reviewers
        ]
        self_assignment = QuestionnaireAssignment(
            id=uuid.uuid4(),
            company_id=company.id,
            assignment_round_id=round_id,
            respondent_profile_id=target.id,
            questionnaire_key=definition.key,
            questionnaire_definition_id=definition.id,
            target_type=AssignmentTargetType.person,
            target_person_id=target.id,
            status=AssignmentStatus.scored,
        )
        session.add_all([self_assignment, *assignments])
        await session.flush()
        results = [
            ScoringResult(
                assignment_id=assignment.id,
                scores={"clarity": {"score": 4 + index / 2}},
                primary_result="clarity",
            )
            for index, assignment in enumerate(assignments)
        ]
        session.add_all(
            [
                ScoringResult(
                    assignment_id=self_assignment.id,
                    scores={"clarity": {"score": 3.5}},
                    primary_result="clarity",
                ),
                *results,
            ]
        )
        await session.flush()

        service = ResultPublicationService(session)
        await service.reconcile_assignment(self_assignment.id)
        await service.reconcile_assignment(assignments[-1].id)
        individual_publication = (
            await session.execute(
                select(ResultPublication).where(
                    ResultPublication.kind == ResultPublicationKind.individual,
                    ResultPublication.source_assignment_id == self_assignment.id,
                )
            )
        ).scalar_one()
        publication = (
            await session.execute(
                select(ResultPublication).where(
                    ResultPublication.kind == ResultPublicationKind.aggregate_360,
                    ResultPublication.participant_profile_id == target.id,
                )
            )
        ).scalar_one()

        assert individual_publication.participant_profile_id == target.id
        assert individual_publication.policy_snapshot["require_self_target"] is True
        assert publication.source_count == 2
        assert publication.policy_snapshot["required_completed"] == 2
        assert publication.revoked_at is None

        assignments[0].status = AssignmentStatus.started
        await session.execute(
            delete(ScoringResult).where(ScoringResult.assignment_id == assignments[0].id)
        )
        await session.flush()
        await service.reconcile_assignment(assignments[0].id)
        await session.refresh(publication)

        assert publication.revoked_at is not None
        await session.rollback()
    await engine.dispose()


async def test_reconcile_reuses_and_revokes_backfilled_legacy_aggregate_publication() -> None:
    await engine.dispose()
    async with SessionLocal() as session:
        company = Company(id=uuid.uuid4(), name=f"Legacy aggregate {uuid.uuid4()}")
        project = CompanyProject(
            id=uuid.uuid4(),
            company_id=company.id,
            name="Program migrat",
        )
        target = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Manager migrat",
            email=f"legacy-target-{uuid.uuid4().hex[:8]}@example.com",
        )
        reviewers = [
            ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name=f"Reviewer migrat {index}",
                email=f"legacy-reviewer-{index}-{uuid.uuid4().hex[:8]}@example.com",
            )
            for index in range(2)
        ]
        definition = _definition(key="boss_360")
        cycle = AssessmentCycle(
            id=uuid.uuid4(),
            company_id=company.id,
            project_id=project.id,
            sequence=1,
            name="Evaluare inițială",
            status=AssessmentCycleStatus.active,
        )
        round_id = uuid.uuid4()
        session.add_all([company, definition])
        await session.flush()
        session.add_all([project, target, *reviewers])
        await session.flush()
        session.add(cycle)
        await session.flush()
        assignments = [
            QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                assessment_cycle_id=cycle.id,
                assignment_round_id=round_id,
                respondent_profile_id=reviewer.id,
                questionnaire_key=definition.key,
                questionnaire_definition_id=definition.id,
                target_type=AssignmentTargetType.person,
                target_person_id=target.id,
                status=AssignmentStatus.scored,
            )
            for reviewer in reviewers
        ]
        publication_key = ":".join(
            (
                "aggregate-360",
                str(target.id),
                str(project.id),
                str(cycle.id),
                str(round_id),
                str(definition.id),
            )
        )
        backfilled_publication = ResultPublication(
            id=uuid.uuid4(),
            publication_key=publication_key,
            participant_profile_id=target.id,
            company_id=company.id,
            project_id=project.id,
            assignment_round_id=round_id,
            assessment_cycle_id=cycle.id,
            questionnaire_definition_id=definition.id,
            questionnaire_key=definition.key,
            kind=ResultPublicationKind.aggregate_360,
            source_count=2,
            policy_snapshot={"publication": "aggregate"},
            published_at=datetime.now(UTC),
        )
        session.add_all([*assignments, backfilled_publication])
        await session.flush()
        session.add_all(
            [
                ScoringResult(
                    assignment_id=assignment.id,
                    scores={"clarity": {"score": 4}},
                    primary_result="clarity",
                )
                for assignment in assignments
            ]
        )
        await session.flush()

        service = ResultPublicationService(session)
        await service.reconcile_assignment(assignments[-1].id)
        publications = list(
            (
                await session.execute(
                    select(ResultPublication).where(
                        ResultPublication.kind == ResultPublicationKind.aggregate_360,
                        ResultPublication.participant_profile_id == target.id,
                    )
                )
            ).scalars()
        )
        assert [publication.id for publication in publications] == [backfilled_publication.id]
        assert publications[0].publication_key == publication_key
        assert publications[0].revoked_at is None

        assignments[0].status = AssignmentStatus.started
        await session.execute(
            delete(ScoringResult).where(ScoringResult.assignment_id == assignments[0].id)
        )
        await session.flush()
        await service.reconcile_assignment(assignments[0].id)
        await session.refresh(backfilled_publication)

        assert backfilled_publication.revoked_at is not None
        await session.rollback()
    await engine.dispose()


async def test_legacy_empty_policies_publish_known_individual_results() -> None:
    await engine.dispose()
    async with SessionLocal() as session:
        company = Company(id=uuid.uuid4(), name=f"Legacy results {uuid.uuid4()}")
        profile = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            full_name="Participant rezultat",
            email=f"legacy-{uuid.uuid4().hex[:8]}@example.com",
        )
        definition = _definition(key="distress_drivers")
        definition.feedback_policy = {}
        definition.private_config = None
        definition.schema = {
            "sections": [],
            "scoring": {
                "method": "sum_statement_scores_by_driver",
                "drivers": [{"id": "be_strong", "label": "Fii puternic"}],
            },
        }
        assignment = QuestionnaireAssignment(
            id=uuid.uuid4(),
            company_id=company.id,
            respondent_profile_id=profile.id,
            questionnaire_key=definition.key,
            questionnaire_definition_id=definition.id,
            target_type=AssignmentTargetType.self_assessment,
            status=AssignmentStatus.scored,
        )
        session.add_all([company, definition])
        await session.flush()
        session.add(profile)
        await session.flush()
        session.add(assignment)
        await session.flush()
        session.add(
            ScoringResult(
                assignment_id=assignment.id,
                scores={"be_strong": {"score": 72.0}},
                primary_result="be_strong",
            )
        )
        await session.flush()

        await ResultPublicationService(session).reconcile_assignment(assignment.id)
        publication = (
            await session.execute(
                select(ResultPublication).where(
                    ResultPublication.source_assignment_id == assignment.id
                )
            )
        ).scalar_one()

        assert publication.kind == ResultPublicationKind.individual
        assert publication.policy_snapshot == {
            "publication": "scores",
            "dimension_ids": ["be_strong"],
            "target_types": ["self"],
            "require_self_target": False,
            "include_primary_result": True,
        }
        await session.rollback()
    await engine.dispose()
