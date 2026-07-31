import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from codrut.core.database import SessionLocal, engine
from codrut.core.errors import DomainError
from codrut.core.security import hash_password
from codrut.modules.assignments.models import (
    AssessmentCycle,
    AssessmentCycleStatus,
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
    Team,
    TeamMembershipRole,
    TeamType,
)
from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.forms.models import (
    QuestionnaireDefinition,
    QuestionnaireResponse,
    QuestionnaireResponseStatus,
)
from codrut.modules.identity.models import User, UserRole
from codrut.modules.participants.service import (
    ParticipantWorkspaceService,
    _definition_scale_max,
    _definition_score_feedback,
    _definition_score_labels,
    _definition_score_scale,
)
from codrut.modules.scoring.models import (
    ResultPublication,
    ResultPublicationKind,
    ScoringResult,
)
from codrut.modules.scoring.publication import (
    ResultPublicationService,
    required_feedback_count,
)


def _feedback_definition() -> QuestionnaireDefinition:
    return QuestionnaireDefinition(
        id=uuid.uuid4(),
        key="boss_360",
        version=1_000_000 + int(uuid.uuid4().hex[:6], 16),
        title="Feedback sintetic",
        schema={"schema_version": "questionnaire.v1", "sections": []},
        private_config={
            "schema": {
                "scoring": {
                    "method": "average_statement_scores_by_section",
                    "scale_max": 5,
                    "score_unit": "grade_1_to_5",
                },
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


def test_received_feedback_threshold_is_always_two_distinct_reviewers() -> None:
    assert (
        required_feedback_count(
            eligible_count=1,
            minimum_completed=2,
            target_completed=3,
        )
        == 2
    )
    assert (
        required_feedback_count(
            eligible_count=2,
            minimum_completed=2,
            target_completed=3,
        )
        == 2
    )
    assert (
        required_feedback_count(
            eligible_count=3,
            minimum_completed=2,
            target_completed=3,
        )
        == 2
    )


def test_received_feedback_scale_uses_the_scoring_output_unit() -> None:
    definition = _feedback_definition()
    assert definition.private_config is not None
    scoring = definition.private_config["schema"]["scoring"]
    scoring["score_unit"] = "percent"

    assert _definition_scale_max(definition) == 100.0
    scoring["score_unit"] = "grade_1_to_5"
    assert _definition_scale_max(definition) == 5.0


@pytest.mark.asyncio
async def test_cycle_feedback_uses_persisted_cohorts_and_hides_ambiguous_rows() -> None:
    cycle_id = uuid.uuid4()
    target_id = uuid.uuid4()
    direct_id = uuid.uuid4()
    peer_id = uuid.uuid4()
    ambiguous_id = uuid.uuid4()
    service = ParticipantWorkspaceService(None)  # type: ignore[arg-type]
    profile = ParticipantProfile(
        id=target_id,
        company_id=uuid.uuid4(),
        full_name="Target",
    )
    assignments = [
        QuestionnaireAssignment(
            company_id=profile.company_id,
            assessment_cycle_id=cycle_id,
            respondent_profile_id=direct_id,
            questionnaire_key="boss_360",
            target_type=AssignmentTargetType.person,
            target_person_id=target_id,
            icare_cohort="direct_team",
        ),
        QuestionnaireAssignment(
            company_id=profile.company_id,
            assessment_cycle_id=cycle_id,
            respondent_profile_id=peer_id,
            questionnaire_key="boss_360",
            target_type=AssignmentTargetType.person,
            target_person_id=target_id,
            icare_cohort="leadership_peers",
        ),
        QuestionnaireAssignment(
            company_id=profile.company_id,
            assessment_cycle_id=cycle_id,
            respondent_profile_id=ambiguous_id,
            questionnaire_key="boss_360",
            target_type=AssignmentTargetType.person,
            target_person_id=target_id,
            icare_cohort=None,
        ),
    ]

    cohorts = await service._split_received_feedback_cohorts(
        profile,
        uuid.uuid4(),
        assignments,
    )

    assert [item.respondent_profile_id for item in cohorts["direct_team"]] == [direct_id]
    assert [item.respondent_profile_id for item in cohorts["leadership_peers"]] == [peer_id]


def test_lencioni_scale_sums_each_pinned_question_range() -> None:
    scale = [
        {"value": 1, "label": "Rareori"},
        {"value": 2, "label": "Uneori"},
        {"value": 3, "label": "De obicei"},
    ]
    definition = QuestionnaireDefinition(
        id=uuid.uuid4(),
        key="lencioni",
        version=1,
        title="Lencioni",
        schema={"schema_version": "questionnaire.v1"},
        private_config={
            "schema": {
                "sections": [
                    {
                        "questions": [
                            {"id": "q1", "scale": scale},
                            {"id": "q2", "scale": scale},
                            {"id": "q3", "scale": scale},
                        ]
                    }
                ],
                "scoring": {
                    "method": "sum_by_group",
                    "groups": [
                        {"id": "trust", "question_ids": ["q1", "q2", "q3"]},
                    ],
                },
            }
        },
        feedback_policy={"scale_min": 0, "scale_max": 10},
        content_checksum=uuid.uuid4().hex * 2,
        active=True,
    )

    assert _definition_score_scale(definition, dimension_ids={"trust"}) == (
        "score",
        3.0,
        9.0,
    )


def test_lencioni_heterogeneous_visible_group_ranges_are_unavailable() -> None:
    scale = [{"value": 1}, {"value": 2}, {"value": 3}]
    definition = QuestionnaireDefinition(
        id=uuid.uuid4(),
        key="lencioni",
        version=1,
        title="Lencioni",
        schema={"schema_version": "questionnaire.v1"},
        private_config={
            "schema": {
                "sections": [
                    {
                        "questions": [
                            {"id": "q1", "scale": scale},
                            {"id": "q2", "scale": scale},
                            {"id": "q3", "scale": scale},
                        ]
                    }
                ],
                "scoring": {
                    "method": "sum_by_group",
                    "groups": [
                        {"id": "trust", "question_ids": ["q1", "q2", "q3"]},
                        {"id": "conflict", "question_ids": ["q1", "q2"]},
                    ],
                },
            }
        },
        feedback_policy={},
        content_checksum=uuid.uuid4().hex * 2,
        active=True,
    )

    assert (
        _definition_score_scale(
            definition,
            dimension_ids={"trust", "conflict"},
        )
        is None
    )

def test_driver_feedback_is_read_from_the_pinned_questionnaire_definition() -> None:
    definition = QuestionnaireDefinition(
        id=uuid.uuid4(),
        key="distress_drivers",
        version=1,
        title="TA",
        schema={"schema_version": "questionnaire.v1"},
        private_config={
            "schema": {
                "scoring": {
                    "method": "sum_statement_scores_by_driver",
                    "drivers": [
                        {
                            "id": "be_perfect",
                            "label": "Fii perfect",
                            "feedback_above_50": "Verifică standardele imposibile.",
                        }
                    ],
                }
            }
        },
        active=True,
    )

    assert _definition_score_feedback(definition) == {
        "be_perfect": "Verifică standardele imposibile."
    }


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
        required_feedback_count(
            eligible_count=9,
            minimum_completed=2,
            target_completed=3,
        )
        == 2
    )


async def test_workspace_requires_context_for_multi_profile_account_and_scopes_cycle() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"multi-profile-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("participant-password-123"),
                role=UserRole.participant,
            )
            company_a = Company(id=uuid.uuid4(), name=f"Company A {uuid.uuid4()}")
            company_b = Company(id=uuid.uuid4(), name=f"Company B {uuid.uuid4()}")
            definition = QuestionnaireDefinition(
                id=uuid.uuid4(),
                key=f"synthetic-{uuid.uuid4().hex[:8]}",
                version=1,
                title="Synthetic questionnaire",
                schema={"schema_version": "questionnaire.v1", "sections": []},
                private_config={},
                feedback_policy={},
                active=True,
            )
            session.add_all([user, company_a, company_b, definition])
            await session.flush()

            profile_a = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company_a.id,
                user_id=user.id,
                full_name="Participant A",
                email=user.email,
            )
            profile_b = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company_b.id,
                user_id=user.id,
                full_name="Participant B",
                email=user.email,
            )
            project_a = CompanyProject(
                id=uuid.uuid4(),
                company_id=company_a.id,
                name="Program A",
                status=CompanyProjectStatus.active,
            )
            project_b = CompanyProject(
                id=uuid.uuid4(),
                company_id=company_b.id,
                name="Program B",
                status=CompanyProjectStatus.active,
            )
            session.add_all([profile_a, profile_b, project_a, project_b])
            await session.flush()
            cycle_a = AssessmentCycle(
                id=uuid.uuid4(),
                company_id=company_a.id,
                project_id=project_a.id,
                sequence=1,
                name="Evaluare inițială",
                status=AssessmentCycleStatus.active,
            )
            cycle_b = AssessmentCycle(
                id=uuid.uuid4(),
                company_id=company_b.id,
                project_id=project_b.id,
                sequence=2,
                name="Reevaluare 1",
                status=AssessmentCycleStatus.active,
            )
            previous_cycle_b = AssessmentCycle(
                id=uuid.uuid4(),
                company_id=company_b.id,
                project_id=project_b.id,
                sequence=1,
                name="Evaluare inițială",
                status=AssessmentCycleStatus.closed,
                closed_at=datetime.now(UTC) - timedelta(days=1),
            )
            session.add_all(
                [
                    ProjectMembership(
                        id=uuid.uuid4(),
                        company_id=company_a.id,
                        project_id=project_a.id,
                        participant_profile_id=profile_a.id,
                        active=True,
                    ),
                    ProjectMembership(
                        id=uuid.uuid4(),
                        company_id=company_b.id,
                        project_id=project_b.id,
                        participant_profile_id=profile_b.id,
                        active=True,
                    ),
                    cycle_a,
                    previous_cycle_b,
                    cycle_b,
                ]
            )
            await session.flush()
            assignment_a = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company_a.id,
                project_id=project_a.id,
                assessment_cycle_id=cycle_a.id,
                respondent_profile_id=profile_a.id,
                questionnaire_key=definition.key,
                questionnaire_definition_id=definition.id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.invited,
            )
            assignment_b = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company_b.id,
                project_id=project_b.id,
                assessment_cycle_id=cycle_b.id,
                respondent_profile_id=profile_b.id,
                questionnaire_key=definition.key,
                questionnaire_definition_id=definition.id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.invited,
            )
            previous_assignment_b = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company_b.id,
                project_id=project_b.id,
                assessment_cycle_id=previous_cycle_b.id,
                respondent_profile_id=profile_b.id,
                questionnaire_key=definition.key,
                questionnaire_definition_id=definition.id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.submitted,
            )
            session.add_all([assignment_a, previous_assignment_b, assignment_b])
            await session.flush()
            session.add(
                ResultPublication(
                    id=uuid.uuid4(),
                    publication_key=f"published-cycle-{uuid.uuid4().hex}",
                    participant_profile_id=profile_b.id,
                    company_id=company_b.id,
                    project_id=project_b.id,
                    assignment_round_id=previous_assignment_b.assignment_round_id,
                    assessment_cycle_id=previous_cycle_b.id,
                    questionnaire_definition_id=definition.id,
                    questionnaire_key=definition.key,
                    source_assignment_id=previous_assignment_b.id,
                    kind=ResultPublicationKind.individual,
                    source_count=1,
                    policy_snapshot={},
                    published_at=datetime.now(UTC),
                )
            )
            await session.flush()

            service = ParticipantWorkspaceService(session)
            selection = await service.get_workspace_summary(user.id)
            selected = await service.get_workspace_summary(
                user.id,
                participant_profile_id=profile_b.id,
                project_id=project_b.id,
            )

            assert selection.context_selection_required is True
            assert selection.participant_profile_id is None
            assert {context.participant_profile_id for context in selection.contexts} == {
                profile_a.id,
                profile_b.id,
            }
            assert {
                project.name: project.total_count
                for project in selection.questionnaire_projects
            } == {
                project_a.name: 1,
                project_b.name: 2,
            }
            program_b = next(
                project
                for project in selection.questionnaire_projects
                if project.id == project_b.id
            )
            assert {
                (task.cycleName, task.cycleSequence)
                for task in program_b.questionnaires
            } == {
                ("Evaluare inițială", 1),
                ("Reevaluare 1", 2),
            }
            assert {
                task.deadlineLabel for task in program_b.questionnaires
            } == {"finalul evaluării"}
            assert selected.context_selection_required is False
            assert selected.participant_profile_id == profile_b.id
            assert selected.project_id == project_b.id
            assert selected.assessment_cycle_id == cycle_b.id
            assert [task.assignmentId for task in selected.tasks] == [str(assignment_b.id)]
            assert selected.tasks[0].assessmentCycleId == cycle_b.id
            assert {cycle.id for cycle in selected.cycles} == {
                previous_cycle_b.id,
                cycle_b.id,
            }

            await session.rollback()
    finally:
        await engine.dispose()


async def test_workspace_groups_active_and_historical_projects_and_hides_drafts() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"project-history-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("participant-password-123"),
                role=UserRole.participant,
            )
            company = Company(id=uuid.uuid4(), name=f"History Company {uuid.uuid4()}")
            profile = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user.id,
                full_name="History Participant",
                email=user.email,
            )
            projects = [
                CompanyProject(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    name="Current Program",
                    status=CompanyProjectStatus.active,
                ),
                CompanyProject(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    name="Completed Program",
                    status=CompanyProjectStatus.completed,
                ),
                CompanyProject(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    name="Archived Program",
                    status=CompanyProjectStatus.archived,
                ),
                CompanyProject(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    name="Draft Program",
                    status=CompanyProjectStatus.draft,
                ),
            ]
            session.add_all([user, company, profile, *projects])
            await session.flush()
            session.add_all(
                [
                    ProjectMembership(
                        id=uuid.uuid4(),
                        company_id=company.id,
                        project_id=project.id,
                        participant_profile_id=profile.id,
                        active=True,
                    )
                    for project in projects
                ]
            )
            await session.flush()

            selection = await ParticipantWorkspaceService(session).get_workspace_summary(
                user.id
            )
            visible_projects = selection.contexts[0].projects

            assert {
                project.name: (project.status, project.history_bucket)
                for project in visible_projects
            } == {
                "Archived Program": ("archived", "history"),
                "Completed Program": ("completed", "history"),
                "Current Program": ("active", "current"),
            }

            completed = await ParticipantWorkspaceService(session).get_workspace_summary(
                user.id,
                participant_profile_id=profile.id,
                project_id=projects[1].id,
            )
            assert completed.project_id == projects[1].id
            assert completed.project_name == "Completed Program"
            assert completed.tasks == []

            await session.rollback()
    finally:
        await engine.dispose()


async def test_workspace_rejects_draft_cycles_and_hides_cancelled_tasks() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"cycle-visibility-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("participant-password-123"),
                role=UserRole.participant,
            )
            company = Company(id=uuid.uuid4(), name=f"Cycle visibility {uuid.uuid4()}")
            profile = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user.id,
                full_name="Participant visibility",
                email=user.email,
            )
            project = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Program visibility",
                status=CompanyProjectStatus.active,
            )
            definition = QuestionnaireDefinition(
                id=uuid.uuid4(),
                key=f"visibility-{uuid.uuid4().hex[:8]}",
                version=1,
                title="Visibility questionnaire",
                schema={"schema_version": "questionnaire.v1", "sections": []},
                private_config={},
                feedback_policy={},
                active=True,
            )
            draft_cycle = AssessmentCycle(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                sequence=1,
                name="Reevaluare draft",
                status=AssessmentCycleStatus.draft,
            )
            visible_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=profile.id,
                questionnaire_key=definition.key,
                questionnaire_definition_id=definition.id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.invited,
            )
            cancelled_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                respondent_profile_id=profile.id,
                questionnaire_key=definition.key,
                questionnaire_definition_id=definition.id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.cancelled,
            )
            session.add_all([user, company])
            await session.flush()
            session.add_all([profile, project, definition])
            await session.flush()
            session.add_all(
                [
                    draft_cycle,
                    ProjectMembership(
                        id=uuid.uuid4(),
                        company_id=company.id,
                        project_id=project.id,
                        participant_profile_id=profile.id,
                        active=True,
                    ),
                    visible_assignment,
                    cancelled_assignment,
                ]
            )
            await session.flush()

            service = ParticipantWorkspaceService(session)
            workspace = await service.get_workspace_summary(
                user.id,
                participant_profile_id=profile.id,
                project_id=project.id,
            )

            assert workspace.assessment_cycle_id is None
            assert workspace.cycles == []
            assert [task.assignmentId for task in workspace.tasks] == [str(visible_assignment.id)]

            with pytest.raises(DomainError) as exc_info:
                await service.get_workspace_summary(
                    user.id,
                    participant_profile_id=profile.id,
                    project_id=project.id,
                    cycle_id=draft_cycle.id,
                )

            assert exc_info.value.code == "participant_cycle_forbidden"
            await session.rollback()
    finally:
        await engine.dispose()


async def test_workspace_pcm_values_are_scoped_to_selected_cycle() -> None:
    await engine.dispose()
    try:
        async with SessionLocal() as session:
            user = User(
                id=uuid.uuid4(),
                email=f"cycle-pcm-{uuid.uuid4().hex[:8]}@example.com",
                password_hash=hash_password("participant-password-123"),
                role=UserRole.participant,
            )
            company = Company(id=uuid.uuid4(), name=f"PCM Company {uuid.uuid4()}")
            profile = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user.id,
                full_name="Participant PCM",
                email=user.email,
                pcm_base="thinker",
                pcm_phase="promoter",
            )
            project = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Program PCM",
                status=CompanyProjectStatus.active,
            )
            definition = QuestionnaireDefinition(
                id=uuid.uuid4(),
                key="pcm_base",
                version=1_000_000 + int(uuid.uuid4().hex[:6], 16),
                title="Profil PCM sintetic",
                schema={"schema_version": "questionnaire.v1", "sections": []},
                private_config={},
                feedback_policy={},
                active=True,
            )
            session.add_all([user, company, profile, project, definition])
            await session.flush()
            baseline_cycle = AssessmentCycle(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                sequence=1,
                name="Evaluare inițială",
                status=AssessmentCycleStatus.closed,
                closed_at=datetime.now(UTC) - timedelta(days=1),
            )
            current_cycle = AssessmentCycle(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                sequence=2,
                name="Reevaluare 1",
                status=AssessmentCycleStatus.active,
            )
            session.add_all([baseline_cycle, current_cycle])
            await session.flush()
            baseline_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                assessment_cycle_id=baseline_cycle.id,
                respondent_profile_id=profile.id,
                questionnaire_key="pcm_base",
                questionnaire_definition_id=definition.id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.submitted,
            )
            current_assignment = QuestionnaireAssignment(
                id=uuid.uuid4(),
                company_id=company.id,
                project_id=project.id,
                assessment_cycle_id=current_cycle.id,
                respondent_profile_id=profile.id,
                questionnaire_key="pcm_base",
                questionnaire_definition_id=definition.id,
                target_type=AssignmentTargetType.self_assessment,
                status=AssignmentStatus.submitted,
            )
            session.add_all([baseline_assignment, current_assignment])
            await session.flush()
            session.add(
                ResultPublication(
                    id=uuid.uuid4(),
                    publication_key=f"pcm-history-{uuid.uuid4().hex}",
                    participant_profile_id=profile.id,
                    company_id=company.id,
                    project_id=project.id,
                    assignment_round_id=baseline_assignment.assignment_round_id,
                    assessment_cycle_id=baseline_cycle.id,
                    questionnaire_definition_id=definition.id,
                    questionnaire_key=definition.key,
                    source_assignment_id=baseline_assignment.id,
                    kind=ResultPublicationKind.individual,
                    source_count=1,
                    policy_snapshot={},
                    published_at=datetime.now(UTC),
                )
            )
            session.add_all(
                [
                    QuestionnaireResponse(
                        id=uuid.uuid4(),
                        assignment_id=baseline_assignment.id,
                        questionnaire_key="pcm_base",
                        questionnaire_version=definition.version,
                        status=QuestionnaireResponseStatus.submitted,
                        answers={"pcm_base": "harmonizer", "pcm_phase": "rebel"},
                        submitted_at=datetime.now(UTC) - timedelta(days=2),
                    ),
                    QuestionnaireResponse(
                        id=uuid.uuid4(),
                        assignment_id=current_assignment.id,
                        questionnaire_key="pcm_base",
                        questionnaire_version=definition.version,
                        status=QuestionnaireResponseStatus.submitted,
                        answers={"pcm_base": "thinker", "pcm_phase": "promoter"},
                        submitted_at=datetime.now(UTC),
                    ),
                ]
            )
            await session.flush()

            service = ParticipantWorkspaceService(session)
            baseline = await service.get_workspace_summary(
                user.id,
                participant_profile_id=profile.id,
                project_id=project.id,
                cycle_id=baseline_cycle.id,
            )
            current = await service.get_workspace_summary(
                user.id,
                participant_profile_id=profile.id,
                project_id=project.id,
                cycle_id=current_cycle.id,
            )

            assert (baseline.pcm_base, baseline.pcm_phase) == ("harmonizer", "rebel")
            assert (current.pcm_base, current.pcm_phase) == ("thinker", "promoter")

            await session.rollback()
    finally:
        await engine.dispose()


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
            assert published.results[0].score_unit == "grade_1_to_5"
            assert published.results[0].scale_min == 1.0
            assert published.results[0].scale_max == 5.0
            assert published.results[0].score_scale_compatible is True

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
                reports_to_name="Mara Manager",
                role_group="leadership",
            )
            manager = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Mara Manager",
                email=f"manager-{uuid.uuid4().hex[:8]}@example.com",
                role_group="leadership",
            )
            reviewer_one = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Reviewer One",
                email=f"reviewer-one-{uuid.uuid4().hex[:8]}@example.com",
                reports_to_name="Ana Participant",
                role_group="leadership",
            )
            reviewer_two = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Reviewer Two",
                email=f"reviewer-two-{uuid.uuid4().hex[:8]}@example.com",
                reports_to_name="Ana Participant",
                role_group="leadership",
            )
            project = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Leadership septembrie",
                status=CompanyProjectStatus.active,
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
            assert summary.received_feedback.cohort == "leadership_peers"
            assert summary.received_feedback.completed_count == 2
            assert summary.received_feedback.minimum_completed == 2
            assert summary.received_feedback.score_unit == "grade_1_to_5"
            assert summary.received_feedback.scale_min == 1.0
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

            reviewer_two.role_group = "individual"
            await session.flush()
            privacy_split = await ParticipantWorkspaceService(
                session
            ).get_workspace_summary(user.id)
            assert len(privacy_split.received_feedback_groups) == 2
            assert all(
                feedback.visible is False
                and feedback.unavailable_reason == "privacy_threshold"
                for feedback in privacy_split.received_feedback_groups
            )
            reviewer_two.role_group = "leadership"
            await session.flush()

            participant_service = ParticipantWorkspaceService(session)
            no_dimensions = await participant_service._build_received_feedback_cohort_summary(
                [received_assignment_one, received_assignment_two],
                publication=publication,
                project_id=project.id,
                project_name=project.name,
                cohort="leadership_peers",
                minimum_completed=2,
                allowed_dimensions=set(),
                labels=_definition_score_labels(feedback_definition),
                questionnaire_title=feedback_definition.title,
                score_unit="grade_1_to_5",
                scale_min=1,
                scale_max=5,
            )
            assert no_dimensions is not None
            assert no_dimensions.visible is False
            assert no_dimensions.unavailable_reason == "no_eligible_dimensions"

            missing_score = (
                await session.execute(
                    select(ScoringResult).where(
                        ScoringResult.assignment_id == received_assignment_one.id
                    )
                )
            ).scalar_one()
            await session.delete(missing_score)
            await session.flush()
            scoring_unavailable = (
                await participant_service._build_received_feedback_cohort_summary(
                    [received_assignment_one, received_assignment_two],
                    publication=publication,
                    project_id=project.id,
                    project_name=project.name,
                    cohort="leadership_peers",
                    minimum_completed=2,
                    allowed_dimensions={"feedback_signal_a", "feedback_signal_b"},
                    labels=_definition_score_labels(feedback_definition),
                    questionnaire_title=feedback_definition.title,
                    score_unit="grade_1_to_5",
                    scale_min=1,
                    scale_max=5,
                )
            )
            assert scoring_unavailable is not None
            assert scoring_unavailable.visible is False
            assert scoring_unavailable.unavailable_reason == "scoring_unavailable"

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

            director = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Director",
                email=f"director-{uuid.uuid4().hex[:8]}@example.com",
                role_group="leadership",
            )
            profile = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                user_id=user.id,
                full_name="Ana Participant",
                email=user.email,
                role_group="leadership",
                reports_to_name=director.full_name,
            )
            reviewer = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=company.id,
                full_name="Reviewer One",
                email=f"reviewer-one-{uuid.uuid4().hex[:8]}@example.com",
                reports_to_name=profile.full_name,
                role_group="individual",
            )
            feedback_definition = _feedback_definition()
            session.add_all([director, profile, reviewer, feedback_definition])
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

            await ResultPublicationService(session).reconcile_assignment(
                received_assignment.id
            )

            summary = await ParticipantWorkspaceService(session).get_workspace_summary(user.id)

            assert summary.received_feedback is not None
            assert summary.received_feedback.cohort == "direct_team"
            assert summary.received_feedback.completed_count == 1
            assert summary.received_feedback.minimum_completed == 2
            assert summary.received_feedback.visible is False
            assert summary.received_feedback.unavailable_reason == "privacy_threshold"
            assert summary.received_feedback.overall_average is None
            assert summary.received_feedback.dimensions == []
            assert summary.received_feedback_groups == [summary.received_feedback]

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
                status=CompanyProjectStatus.active,
            )
            project_b = CompanyProject(
                id=uuid.uuid4(),
                company_id=company.id,
                name="Project Beta",
                status=CompanyProjectStatus.active,
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
                status=CompanyProjectStatus.active,
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
