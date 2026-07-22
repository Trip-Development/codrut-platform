import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from codrut.core.database import SessionLocal, engine
from codrut.core.security import hash_password
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
    Team,
    TeamType,
)
from codrut.modules.companies.models import Company, CompanyProject, ParticipantProfile
from codrut.modules.forms.models import QuestionnaireDefinition
from codrut.modules.identity.models import User, UserRole
from codrut.modules.participants.service import (
    ParticipantWorkspaceService,
    _definition_score_labels,
    _required_feedback_count,
)
from codrut.modules.scoring.models import (
    ResultPublication,
    ResultPublicationKind,
    ScoringResult,
)
from codrut.modules.scoring.publication import ResultPublicationService


def _feedback_definition() -> QuestionnaireDefinition:
    return QuestionnaireDefinition(
        id=uuid.uuid4(),
        key="boss_360",
        version=1_000_000 + int(uuid.uuid4().hex[:6], 16),
        title="Feedback sintetic",
        schema={"schema_version": "questionnaire.v1", "sections": []},
        private_config={
            "schema": {
                "scoring": {"method": "average_statement_scores_by_section"},
                "sections": [
                    {
                        "id": "feedback",
                        "questions": [
                            {
                                "id": "feedback_signal_a",
                                "label": "Claritate",
                                "type": "statement_score_set",
                            },
                            {
                                "id": "feedback_signal_b",
                                "label": "Sprijin",
                                "type": "statement_score_set",
                            },
                        ],
                    }
                ],
            }
        },
        feedback_policy={
            "publication": "aggregate",
            "minimum_completed": 2,
            "target_completed": 3,
            "dimension_ids": ["feedback_signal_a", "feedback_signal_b"],
            "participant_results": {
                "publication": "scores",
                "dimension_ids": ["feedback_signal_a", "feedback_signal_b"],
                "target_types": ["person"],
                "require_self_target": True,
            },
        },
        content_checksum=uuid.uuid4().hex * 2,
        active=True,
    )


def test_received_feedback_threshold_requires_two_or_three_reviewers() -> None:
    assert (
        _required_feedback_count(
            eligible_count=1,
            minimum_completed=2,
            target_completed=3,
        )
        == 2
    )
    assert (
        _required_feedback_count(
            eligible_count=2,
            minimum_completed=2,
            target_completed=3,
        )
        == 2
    )
    assert (
        _required_feedback_count(
            eligible_count=3,
            minimum_completed=2,
            target_completed=3,
        )
        == 3
    )


def test_result_labels_prefer_participant_schema_copy() -> None:
    definition = QuestionnaireDefinition(
        id=uuid.uuid4(),
        key="boss_360",
        version=1,
        title="Feedback sintetic",
        schema={
            "sections": [
                {
                    "id": "feedback",
                    "questions": [
                        {
                            "id": "feedback_signal_a",
                            "label": "Dezvoltare",
                            "type": "statement_score_set",
                        }
                    ],
                }
            ]
        },
        private_config={
            "schema": {
                "scoring": {
                    "groups": [
                        {"id": "feedback_signal_a", "label": "Internal label"},
                        {"id": "feedback_signal_b", "label": "Colaborare"},
                    ]
                }
            }
        },
        feedback_policy={},
        active=True,
    )

    assert _definition_score_labels(definition) == {
        "feedback_signal_a": "Dezvoltare",
        "feedback_signal_b": "Colaborare",
    }
    assert (
        _required_feedback_count(
            eligible_count=9,
            minimum_completed=2,
            target_completed=3,
        )
        == 3
    )


async def test_participant_results_require_active_matching_publication_snapshot() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"published-result-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("participant-password-123"),
                role=UserRole.participant,
            )
            company = Company(id=uuid.uuid4(), name=f"Published result {uuid.uuid4()}")
            profile = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user.id,
                full_name="Participant rezultat",
                email=user.email,
            )
            definition = _feedback_definition()
            definition.feedback_policy["participant_results"] = {
                "publication": "scores",
                "dimension_ids": ["feedback_signal_a"],
                "target_types": ["self"],
                "include_primary_result": True,
            }
            definition.content_checksum = None
            assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                respondent_profile_id=profile.id,
                questionnaire_key=definition.key,
                questionnaire_definition_id=definition.id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.scored,
            )
            session.add_all([user, company])
            await session.flush()
            session.add_all([profile, definition])
            await session.flush()
            session.add(assignment)
            await session.flush()
            session.add(
                ScoringResult(
                    assignment_id=assignment.id,
                    scores={"feedback_signal_a": {"score": 4.3}},
                    primary_result="feedback_signal_a",
                )
            )
            await session.flush()

            unpublished = await ParticipantWorkspaceService(session).get_workspace_summary(user.id)
            assert unpublished.results == []

            await ResultPublicationService(session).reconcile_assignment(assignment.id)
            published = await ParticipantWorkspaceService(session).get_workspace_summary(user.id)
            assert len(published.results) == 1
            assert published.results[0].scores["feedback_signal_a"]["score"] == 4.3

            publication = (
                await session.execute(
                    select(ResultPublication).where(
                        ResultPublication.source_assignment_id == assignment.id
                    )
                )
            ).scalar_one()
            publication.revoked_at = datetime.now(UTC)
            revoked = await ParticipantWorkspaceService(session).get_workspace_summary(user.id)
            assert revoked.results == []

            publication.revoked_at = None
            definition.content_checksum = uuid.uuid4().hex * 2
            checksum_mismatch = await ParticipantWorkspaceService(session).get_workspace_summary(
                user.id
            )
            assert checksum_mismatch.results == []

            await session.rollback()
    finally:
        await engine.dispose()


async def test_participant_workspace_summary_uses_persisted_profile_and_assignments(
    questionnaire_definition_factory,
) -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"workspace-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("participant-password-123"),
                role=UserRole.participant,
            )
            company = Company(
                id=uuid.uuid4(),
                name=f"Workspace Company {uuid.uuid4().hex[:8]}",
            )
            session.add_all([user, company])
            await session.flush()

            profile = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user.id,
                full_name="Ana Participant",
                email=user.email,
                pcm_base="harmonizer",
                pcm_phase="thinker",
            )
            manager = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Mara Manager",
                email=f"manager-{uuid.uuid4().hex[:8]}@example.com",
            )
            reviewer_one = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Reviewer One",
                email=f"reviewer-one-{uuid.uuid4().hex[:8]}@example.com",
            )
            reviewer_two = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Reviewer Two",
                email=f"reviewer-two-{uuid.uuid4().hex[:8]}@example.com",
            )
            project = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Leadership septembrie",
                due_at=datetime.now(UTC) + timedelta(days=21),
            )
            team = Team(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Leadership",
                type=TeamType.leadership,
            )
            feedback_definition = _feedback_definition()
            team_definition = questionnaire_definition_factory("lencioni")
            session.add_all(
                [
                    profile,
                    manager,
                    reviewer_one,
                    reviewer_two,
                    project,
                    team,
                    feedback_definition,
                    team_definition,
                ]
            )
            await session.flush()

            team_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=profile.id,
                questionnaire_key="lencioni",
                questionnaire_definition_id=team_definition.id,
                target_type=AssignmentTargetType.team,
                target_team_id=team.id,
                status=AssignmentStatus.invited,
            )
            received_feedback_round = uuid.uuid4()
            person_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=profile.id,
                questionnaire_key="boss_360",
                questionnaire_definition_id=feedback_definition.id,
                target_type=AssignmentTargetType.person,
                target_person_id=manager.id,
                status=AssignmentStatus.submitted,
            )
            received_assignment_one = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                assignment_round_id=received_feedback_round,
                respondent_profile_id=reviewer_one.id,
                questionnaire_key="boss_360",
                questionnaire_definition_id=feedback_definition.id,
                target_type=AssignmentTargetType.person,
                target_person_id=profile.id,
                status=AssignmentStatus.submitted,
            )
            received_assignment_two = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                assignment_round_id=received_feedback_round,
                respondent_profile_id=reviewer_two.id,
                questionnaire_key="boss_360",
                questionnaire_definition_id=feedback_definition.id,
                target_type=AssignmentTargetType.person,
                target_person_id=profile.id,
                status=AssignmentStatus.scored,
            )
            session.add_all(
                [
                    team_assignment,
                    person_assignment,
                    received_assignment_one,
                    received_assignment_two,
                ]
            )
            await session.flush()
            session.add_all(
                [
                    ScoringResult(
                        assignment_id=person_assignment.id,
                        scores={
                            "feedback_signal_a": {"score": 4.2, "answered": 3},
                            "feedback_signal_b": {
                                "score": 3.7,
                                "answered": 3,
                            },
                        },
                        primary_result="feedback_signal_b",
                    ),
                    ScoringResult(
                        assignment_id=received_assignment_one.id,
                        scores={
                            "feedback_signal_a": {"score": 4.0, "answered": 3},
                            "feedback_signal_b": {
                                "score": 3.0,
                                "answered": 3,
                            },
                            "not_published": {
                                "score": 1.0,
                                "answered": 3,
                            },
                            "section_total": {"score": 4.0, "answered": 9},
                        },
                        primary_result="feedback_signal_b",
                    ),
                    ScoringResult(
                        assignment_id=received_assignment_two.id,
                        scores={
                            "feedback_signal_a": {"score": 5.0, "answered": 3},
                            "feedback_signal_b": {
                                "score": 4.0,
                                "answered": 3,
                            },
                        },
                        primary_result="feedback_signal_b",
                    ),
                ]
            )
            await session.flush()
            await ResultPublicationService(session).reconcile_assignment(
                received_assignment_two.id
            )

            summary = await ParticipantWorkspaceService(session).get_workspace_summary(user.id)

            assert summary.participant_full_name == "Ana Participant"
            assert summary.participant_email == user.email
            assert summary.company_name == company.name
            assert summary.project_name == "Leadership septembrie"
            assert summary.pcm_base == "harmonizer"
            assert summary.pcm_phase == "thinker"
            assert [task.assignmentId for task in summary.tasks] == [
                str(team_assignment.id),
                str(person_assignment.id),
            ]
            assert summary.tasks[0].targetLabel == "Echipa ta"
            assert summary.tasks[0].status == "not_started"
            assert summary.tasks[1].targetLabel == "Mara Manager"
            assert summary.tasks[1].status == "completed"
            assert summary.results == []
            assert summary.received_feedback is not None
            assert summary.received_feedback.completed_count == 2
            assert summary.received_feedback.minimum_completed == 2
            assert summary.received_feedback.scale_max == 5.0
            assert summary.received_feedback.visible is True
            assert summary.received_feedback.overall_average == 4.0
            assert {dimension.id for dimension in summary.received_feedback.dimensions} == {
                "feedback_signal_a",
                "feedback_signal_b",
            }
            assert [
                dimension.model_dump() for dimension in summary.received_feedback.dimensions
            ] == [
                {
                    "id": "feedback_signal_a",
                    "label": "Claritate",
                    "average_score": 4.5,
                    "completed_count": 2,
                },
                {
                    "id": "feedback_signal_b",
                    "label": "Sprijin",
                    "average_score": 3.5,
                    "completed_count": 2,
                },
            ]

            publication = (
                await session.execute(
                    select(ResultPublication).where(
                        ResultPublication.kind == ResultPublicationKind.aggregate_360,
                        ResultPublication.participant_profile_id == profile.id,
                    )
                )
            ).scalar_one()
            publication.source_count = 3
            stale_publication = await ParticipantWorkspaceService(
                session
            ).get_workspace_summary(user.id)
            assert stale_publication.received_feedback is None
            assert stale_publication.received_feedback_groups == []

            await session.rollback()
    finally:
        await engine.dispose()


async def test_participant_workspace_received_feedback_hides_scores_below_threshold() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"workspace-threshold-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("participant-password-123"),
                role=UserRole.participant,
            )
            company = Company(
                id=uuid.uuid4(),
                name=f"Workspace Threshold Company {uuid.uuid4().hex[:8]}",
            )
            session.add_all([user, company])
            await session.flush()

            profile = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user.id,
                full_name="Ana Participant",
                email=user.email,
            )
            reviewer = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Reviewer One",
                email=f"reviewer-one-{uuid.uuid4().hex[:8]}@example.com",
            )
            feedback_definition = _feedback_definition()
            session.add_all([profile, reviewer, feedback_definition])
            await session.flush()

            received_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                respondent_profile_id=reviewer.id,
                questionnaire_key="boss_360",
                questionnaire_definition_id=feedback_definition.id,
                target_type=AssignmentTargetType.person,
                target_person_id=profile.id,
                status=AssignmentStatus.submitted,
            )
            session.add(received_assignment)
            await session.flush()
            session.add(
                ScoringResult(
                    assignment_id=received_assignment.id,
                    scores={
                        "feedback_signal_a": {"score": 5.0, "answered": 3},
                    },
                    primary_result="feedback_signal_a",
                )
            )
            await session.flush()

            summary = await ParticipantWorkspaceService(session).get_workspace_summary(user.id)

            assert summary.received_feedback is None
            assert summary.received_feedback_groups == []

            await session.rollback()
    finally:
        await engine.dispose()


async def test_received_feedback_is_never_combined_across_projects() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"feedback-projects-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("participant-password-123"),
                role=UserRole.participant,
            )
            company = Company(id=uuid.uuid4(), name="Feedback Projects Company")
            target = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user.id,
                email=user.email,
                full_name="Target Participant",
            )
            project_a = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Project Alpha",
            )
            project_b = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Project Beta",
            )
            definition = _feedback_definition()
            reviewers = [
                ParticipantProfile(
                    id=uuid.uuid4(),
                    company_id=company.id,
                        email=f"reviewer-{index}-{uuid.uuid4().hex[:6]}@example.com",
                    full_name=f"Reviewer {index}",
                )
                for index in range(4)
            ]
            session.add_all([user, company, target, project_a, project_b, definition, *reviewers])
            await session.flush()

            assignments: list[QuestionnaireAssignment] = []
            project_rounds = {
                project_a.id: uuid.uuid4(),
                project_b.id: uuid.uuid4(),
            }
            for index, reviewer in enumerate(reviewers):
                project = project_a if index < 2 else project_b
                assignment = QuestionnaireAssignment(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    assignment_round_id=project_rounds[project.id],
                    respondent_profile_id=reviewer.id,
                    questionnaire_key="boss_360",
                    questionnaire_definition_id=definition.id,
                    target_type=AssignmentTargetType.person,
                    target_person_id=target.id,
                    status=AssignmentStatus.scored,
                )
                assignments.append(assignment)
            session.add_all(assignments)
            await session.flush()
            session.add_all(
                [
                    ScoringResult(
                        assignment_id=assignment.id,
                        scores={
                            "feedback_signal_a": {
                                "score": 1.0 if assignment.project_id == project_a.id else 5.0
                            }
                        },
                        primary_result="feedback_signal_a",
                    )
                    for assignment in assignments
                ]
            )
            await session.flush()
            publication_service = ResultPublicationService(session)
            for assignment in assignments:
                await publication_service.reconcile_assignment(assignment.id)

            summary = await ParticipantWorkspaceService(session).get_workspace_summary(user.id)

            assert summary.received_feedback is None
            assert len(summary.received_feedback_groups) == 2
            by_project = {
                feedback.project_id: feedback for feedback in summary.received_feedback_groups
            }
            assert by_project[project_a.id].overall_average == 1.0
            assert by_project[project_b.id].overall_average == 5.0
            assert all(feedback.completed_count == 2 for feedback in by_project.values())

            await session.rollback()
    finally:
        await engine.dispose()


async def test_received_feedback_is_never_combined_across_rounds_in_one_project() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"feedback-rounds-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("participant-password-123"),
                role=UserRole.participant,
            )
            company = Company(id=uuid.uuid4(), name="Feedback Rounds Company")
            target = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user.id,
                email=user.email,
                full_name="Target Participant",
            )
            project = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Repeated Feedback Project",
            )
            definition = _feedback_definition()
            reviewers = [
                ParticipantProfile(
                    id=uuid.uuid4(),
                    company_id=company.id,
                        email=f"round-reviewer-{index}-{uuid.uuid4().hex[:6]}@example.com",
                    full_name=f"Round Reviewer {index}",
                )
                for index in range(2)
            ]
            session.add_all([user, company, target, project, definition, *reviewers])
            await session.flush()

            round_ids = (uuid.uuid4(), uuid.uuid4())
            assignments = [
                QuestionnaireAssignment(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    project_id=project.id,
                    assignment_round_id=round_id,
                    respondent_profile_id=reviewer.id,
                    questionnaire_key="boss_360",
                    questionnaire_definition_id=definition.id,
                    target_type=AssignmentTargetType.person,
                    target_person_id=target.id,
                    status=AssignmentStatus.scored,
                )
                for round_id in round_ids
                for reviewer in reviewers
            ]
            session.add_all(assignments)
            await session.flush()
            session.add_all(
                [
                    ScoringResult(
                        assignment_id=assignment.id,
                        scores={
                            "feedback_signal_a": {
                                "score": (
                                    1.0 if assignment.assignment_round_id == round_ids[0] else 5.0
                                )
                            }
                        },
                        primary_result="feedback_signal_a",
                    )
                    for assignment in assignments
                ]
            )
            await session.flush()
            publication_service = ResultPublicationService(session)
            for assignment in assignments:
                await publication_service.reconcile_assignment(assignment.id)

            summary = await ParticipantWorkspaceService(session).get_workspace_summary(user.id)

            assert summary.received_feedback is None
            assert len(summary.received_feedback_groups) == 2
            by_round = {
                feedback.assignment_round_id: feedback
                for feedback in summary.received_feedback_groups
            }
            assert by_round[round_ids[0]].overall_average == 1.0
            assert by_round[round_ids[1]].overall_average == 5.0
            assert all(feedback.completed_count == 2 for feedback in by_round.values())

            await session.rollback()
    finally:
        await engine.dispose()
