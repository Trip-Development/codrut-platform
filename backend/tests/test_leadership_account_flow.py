import uuid
from datetime import UTC, datetime, timedelta

import pytest

from codrut.core.config import get_settings
from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.modules.assignments.models import (
    AssignmentStatus,
    AssignmentTargetType,
    QuestionnaireAssignment,
    Team,
    TeamMembership,
    TeamMembershipRole,
    TeamType,
)
from codrut.modules.communications.task_links import TaskLinkClaims, create_task_token
from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.forms.models import QuestionnaireDefinition
from codrut.modules.forms.schemas import QuestionnaireResponseSaveRequest
from codrut.modules.forms.service import FormsService
from codrut.modules.identity.models import (
    SHADOW_ACCOUNT_PASSWORD_HASH,
    AssignmentInvite,
    Session,
    User,
    UserAccountType,
    UserRole,
)
from codrut.modules.identity.repository import hash_session_token
from codrut.modules.identity.schemas import LoginRequest, RegisterRequest
from codrut.modules.identity.service import IdentityService
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from codrut.modules.participants.service import ParticipantWorkspaceService


def create_mock_q_def() -> QuestionnaireDefinition:
    key = f"q_{uuid.uuid4().hex[:6]}"
    return QuestionnaireDefinition(
        id=uuid.uuid4(),
        key=key,
        version=1,
        title="Leadership 360",
        description="Evaluation",
        schema={
            "key": key,
            "version": 1,
            "title": "Leadership 360",
            "audience": "participant",
            "sections": [
                {
                    "id": "s1",
                    "title": "Secțiunea 1",
                    "questions": [
                        {
                            "id": "q1",
                            "text": "Întrebare 1",
                            "type": "rating",
                            "scale": [{"value": 1, "label": "1"}, {"value": 5, "label": "5"}],
                        }
                    ],
                }
            ],
        },
        feedback_policy={},
        trainer_visibility_policy={"raw_responses": "hidden"},
        content_checksum=uuid.uuid4().hex * 2,
        active=True,
    )


@pytest.mark.asyncio
async def test_leadership_account_registration_and_flow() -> None:
    """1. Leadership participant registers, accesses dashboard, and submits response."""
    settings = get_settings()
    async with SessionLocal() as session:
        # 1. Independent roots
        company = Company(id=uuid.uuid4(), name=f"Test Company {uuid.uuid4().hex[:6]}")
        session.add(company)
        project = CompanyProject(
            id=uuid.uuid4(),
            company_id=company.id,
            name="Leadership Program",
            status=CompanyProjectStatus.active,
        )
        session.add(project)
        user = User(
            id=uuid.uuid4(),
            email=f"leader.{uuid.uuid4().hex[:6]}@example.com",
            role=UserRole.participant,
            account_type=UserAccountType.guest,
            password_hash=SHADOW_ACCOUNT_PASSWORD_HASH,
        )
        session.add(user)
        q_def = create_mock_q_def()
        session.add(q_def)
        await session.flush()

        # 2. Profiles and Teams
        profile = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            user_id=user.id,
            email=user.email,
            full_name="Elena Director",
        )
        session.add(profile)
        team = Team(
            id=uuid.uuid4(),
            company_id=company.id,
            name=f"Leadership Team {uuid.uuid4().hex[:6]}",
            type=TeamType.leadership,
        )
        session.add(team)
        await session.flush()

        # 3. Memberships, Assignments, and Invites
        membership = ProjectMembership(
            id=uuid.uuid4(),
            company_id=company.id,
            project_id=project.id,
            participant_profile_id=profile.id,
            active=True,
        )
        session.add(membership)
        team_member = TeamMembership(
            id=uuid.uuid4(),
            team_id=team.id,
            participant_profile_id=profile.id,
            role=TeamMembershipRole.leader,
        )
        session.add(team_member)

        assignment = QuestionnaireAssignment(
            id=uuid.uuid4(),
            project_id=project.id,
            company_id=company.id,
            respondent_profile_id=profile.id,
            questionnaire_key=q_def.key,
            questionnaire_definition_id=q_def.id,
            target_type=AssignmentTargetType.self_assessment,
            status=AssignmentStatus.assigned,
        )
        session.add(assignment)

        claims = TaskLinkClaims(
            company_id=company.id,
            project_id=project.id,
            respondent_profile_id=profile.id,
            assignment_ids=(assignment.id,),
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        token = create_task_token(claims, settings)

        invite = AssignmentInvite(
            id=uuid.uuid4(),
            token=token,
            company_id=company.id,
            respondent_profile_id=profile.id,
            project_id=project.id,
            expires_at=claims.expires_at,
        )
        session.add(invite)
        await session.commit()

        # Step 1: Verify invite as unregistered leadership
        identity_service = IdentityService(session)
        verify_res = await identity_service.verify_invite_token(token)
        assert verify_res.is_leadership is True
        assert verify_res.already_registered is False
        assert verify_res.email == profile.email

        # Step 2: Register account
        auth_res = await identity_service.register(
            RegisterRequest(
                email=profile.email,
                password="A-Very-Secure-Password-1234!",  # noqa: S106
                token=token,
                terms_accepted=True,
                terms_version=CURRENT_TERMS_VERSION,
            )
        )
        assert auth_res.response.email == profile.email
        assert auth_res.response.account_type == UserAccountType.registered
        assert auth_res.response.role == UserRole.participant
        assert auth_res.session_token is not None

        # Verify password hash updated
        await session.refresh(user)
        assert user.account_type == UserAccountType.registered
        assert user.password_hash != SHADOW_ACCOUNT_PASSWORD_HASH

        # Step 3: Verify invite now recognizes user as already registered
        verify_res_after = await identity_service.verify_invite_token(token)
        assert verify_res_after.is_leadership is True
        assert verify_res_after.already_registered is True

        # Step 4: Exchange session with the newly created session
        exchange_res = await identity_service.verify_invite_token_and_create_session(
            token,
            existing_session_token=auth_res.session_token,
        )
        assert exchange_res.response.action == "dashboard_ready"
        assert f"profile={profile.id}" in exchange_res.response.destination

        # Step 5: Authenticated participant accesses tasks & submits questionnaire
        part_service = ParticipantWorkspaceService(session)
        summary = await part_service.get_workspace_summary(
            user_id=user.id,
            participant_profile_id=profile.id,
        )
        assert len(summary.tasks) == 1
        assert summary.tasks[0].id == str(assignment.id)

        forms_service = FormsService(session)
        submit_res = await forms_service.save_assignment_response(
            user_id=user.id,
            assignment_id=assignment.id,
            payload=QuestionnaireResponseSaveRequest(answers={"q1": 5}),
            submit=True,
            participant_profile_id=profile.id,
        )
        assert submit_res is not None
        assert submit_res.status.value == "submitted"

        # Confirm assignment completed
        await session.refresh(assignment)
        assert assignment.status == AssignmentStatus.submitted


@pytest.mark.asyncio
async def test_leadership_login_later() -> None:
    """2. Same leadership participant later authenticates with password and accesses tasks."""
    settings = get_settings()
    async with SessionLocal() as session:
        # 1. Roots
        company = Company(id=uuid.uuid4(), name=f"Company {uuid.uuid4().hex[:6]}")
        session.add(company)
        project = CompanyProject(
            id=uuid.uuid4(),
            company_id=company.id,
            name="Leadership Project",
            status=CompanyProjectStatus.active,
        )
        session.add(project)
        user = User(
            id=uuid.uuid4(),
            email=f"leader.login.{uuid.uuid4().hex[:6]}@example.com",
            role=UserRole.participant,
            account_type=UserAccountType.guest,
            password_hash=SHADOW_ACCOUNT_PASSWORD_HASH,
        )
        session.add(user)
        q_def = create_mock_q_def()
        session.add(q_def)
        await session.flush()

        # 2. Profiles and Teams
        profile = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            user_id=user.id,
            email=user.email,
            full_name="Andrei Manager",
        )
        session.add(profile)
        team = Team(
            id=uuid.uuid4(),
            company_id=company.id,
            name=f"Leadership Team {uuid.uuid4().hex[:6]}",
            type=TeamType.leadership,
        )
        session.add(team)
        await session.flush()

        # 3. Memberships, Assignments, and Invites
        membership = ProjectMembership(
            id=uuid.uuid4(),
            company_id=company.id,
            project_id=project.id,
            participant_profile_id=profile.id,
            active=True,
        )
        session.add(membership)
        team_member = TeamMembership(
            id=uuid.uuid4(),
            team_id=team.id,
            participant_profile_id=profile.id,
            role=TeamMembershipRole.leader,
        )
        session.add(team_member)

        assignment = QuestionnaireAssignment(
            id=uuid.uuid4(),
            project_id=project.id,
            company_id=company.id,
            respondent_profile_id=profile.id,
            questionnaire_key=q_def.key,
            questionnaire_definition_id=q_def.id,
            target_type=AssignmentTargetType.self_assessment,
            status=AssignmentStatus.assigned,
        )
        session.add(assignment)

        claims = TaskLinkClaims(
            company_id=company.id,
            project_id=project.id,
            respondent_profile_id=profile.id,
            assignment_ids=(assignment.id,),
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        token = create_task_token(claims, settings)

        invite = AssignmentInvite(
            id=uuid.uuid4(),
            token=token,
            company_id=company.id,
            respondent_profile_id=profile.id,
            project_id=project.id,
            expires_at=claims.expires_at,
        )
        session.add(invite)
        await session.commit()

        identity_service = IdentityService(session)
        # Register
        await identity_service.register(
            RegisterRequest(
                email=profile.email,
                password="My-Safe-Password-1234!",  # noqa: S106
                token=token,
                terms_accepted=True,
                terms_version=CURRENT_TERMS_VERSION,
            )
        )

        # Later: Login with credentials
        login_res = await identity_service.login(
            LoginRequest(
                email=profile.email,
                password="My-Safe-Password-1234!",  # noqa: S106
            )
        )
        assert login_res.response.email == profile.email
        assert login_res.session_token is not None

        # Exchange invite with logged in session
        exchange_res = await identity_service.verify_invite_token_and_create_session(
            token,
            existing_session_token=login_res.session_token,
        )
        assert exchange_res.response.action == "dashboard_ready"


@pytest.mark.asyncio
async def test_member_secure_link_flow_without_account() -> None:
    """3. Non-leadership member uses secure link directly without creating an account."""
    settings = get_settings()
    async with SessionLocal() as session:
        # 1. Roots
        company = Company(id=uuid.uuid4(), name=f"Company {uuid.uuid4().hex[:6]}")
        session.add(company)
        project = CompanyProject(
            id=uuid.uuid4(),
            company_id=company.id,
            name="Team Evaluation",
            status=CompanyProjectStatus.active,
        )
        session.add(project)
        user = User(
            id=uuid.uuid4(),
            email=f"member.{uuid.uuid4().hex[:6]}@example.com",
            role=UserRole.participant,
            account_type=UserAccountType.guest,
            password_hash=SHADOW_ACCOUNT_PASSWORD_HASH,
        )
        session.add(user)
        q_def = create_mock_q_def()
        session.add(q_def)
        await session.flush()

        # 2. Profiles and Teams
        profile = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            user_id=user.id,
            email=user.email,
            full_name="Radu Membru",
        )
        session.add(profile)
        # Regular member team (type=functional)
        team = Team(
            id=uuid.uuid4(),
            company_id=company.id,
            name=f"Member Team {uuid.uuid4().hex[:6]}",
            type=TeamType.functional,
        )
        session.add(team)
        await session.flush()

        # 3. Memberships, Assignments, and Invites
        membership = ProjectMembership(
            id=uuid.uuid4(),
            company_id=company.id,
            project_id=project.id,
            participant_profile_id=profile.id,
            active=True,
        )
        session.add(membership)
        team_member = TeamMembership(
            id=uuid.uuid4(),
            team_id=team.id,
            participant_profile_id=profile.id,
            role=TeamMembershipRole.member,
        )
        session.add(team_member)

        assignment = QuestionnaireAssignment(
            id=uuid.uuid4(),
            project_id=project.id,
            company_id=company.id,
            respondent_profile_id=profile.id,
            questionnaire_key=q_def.key,
            questionnaire_definition_id=q_def.id,
            target_type=AssignmentTargetType.self_assessment,
            status=AssignmentStatus.assigned,
        )
        session.add(assignment)

        claims = TaskLinkClaims(
            company_id=company.id,
            project_id=project.id,
            respondent_profile_id=profile.id,
            assignment_ids=(assignment.id,),
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        token = create_task_token(claims, settings)

        invite = AssignmentInvite(
            id=uuid.uuid4(),
            token=token,
            company_id=company.id,
            respondent_profile_id=profile.id,
            project_id=project.id,
            expires_at=claims.expires_at,
        )
        session.add(invite)
        await session.commit()

        identity_service = IdentityService(session)
        verify_res = await identity_service.verify_invite_token(token)
        assert verify_res.is_leadership is False
        assert verify_res.already_registered is False

        # Member exchange produces guest session & secure_link_ready
        exchange_res = await identity_service.verify_invite_token_and_create_session(token)
        assert exchange_res.response.action == "secure_link_ready"
        assert exchange_res.session_token is not None


@pytest.mark.asyncio
async def test_edge_cases() -> None:
    """4. All edge cases: abandonment, expiration, cross-device, forwarded link, wrong session."""
    settings = get_settings()
    async with SessionLocal() as session:
        # 1. Roots
        company = Company(id=uuid.uuid4(), name=f"Company {uuid.uuid4().hex[:6]}")
        session.add(company)
        project = CompanyProject(
            id=uuid.uuid4(),
            company_id=company.id,
            name="Edge Cases Project",
            status=CompanyProjectStatus.active,
        )
        session.add(project)
        user = User(
            id=uuid.uuid4(),
            email=f"edge.lead.{uuid.uuid4().hex[:6]}@example.com",
            role=UserRole.participant,
            account_type=UserAccountType.guest,
            password_hash=SHADOW_ACCOUNT_PASSWORD_HASH,
        )
        session.add(user)
        q_def = create_mock_q_def()
        session.add(q_def)
        await session.flush()

        # 2. Profiles and Teams
        profile = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company.id,
            user_id=user.id,
            email=user.email,
            full_name="Edge Leader",
        )
        session.add(profile)
        team = Team(
            id=uuid.uuid4(),
            company_id=company.id,
            name=f"Leadership Team {uuid.uuid4().hex[:6]}",
            type=TeamType.leadership,
        )
        session.add(team)
        await session.flush()

        # 3. Memberships, Assignments, and Invites
        membership = ProjectMembership(
            id=uuid.uuid4(),
            company_id=company.id,
            project_id=project.id,
            participant_profile_id=profile.id,
            active=True,
        )
        session.add(membership)
        team_member = TeamMembership(
            id=uuid.uuid4(),
            team_id=team.id,
            participant_profile_id=profile.id,
            role=TeamMembershipRole.leader,
        )
        session.add(team_member)

        assignment = QuestionnaireAssignment(
            id=uuid.uuid4(),
            project_id=project.id,
            company_id=company.id,
            respondent_profile_id=profile.id,
            questionnaire_key=q_def.key,
            questionnaire_definition_id=q_def.id,
            target_type=AssignmentTargetType.self_assessment,
            status=AssignmentStatus.assigned,
        )
        session.add(assignment)

        claims = TaskLinkClaims(
            company_id=company.id,
            project_id=project.id,
            respondent_profile_id=profile.id,
            assignment_ids=(assignment.id,),
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        token = create_task_token(claims, settings)

        invite = AssignmentInvite(
            id=uuid.uuid4(),
            token=token,
            company_id=company.id,
            respondent_profile_id=profile.id,
            project_id=project.id,
            expires_at=claims.expires_at,
        )
        session.add(invite)
        await session.commit()

        identity_service = IdentityService(session)

        # Edge case A: Abandons halfway and reopens same link
        verify_1 = await identity_service.verify_invite_token(token)
        assert verify_1.already_registered is False
        verify_2 = await identity_service.verify_invite_token(token)
        assert verify_2.already_registered is False

        # Edge case B: Forwarded to someone else (trying to register different email)
        with pytest.raises(DomainError) as exc_info:
            await identity_service.register(
                RegisterRequest(
                    email="intruder@example.com",  # Wrong email
                    password="Password-123456789!",  # noqa: S106
                    token=token,
                    terms_accepted=True,
                    terms_version=CURRENT_TERMS_VERSION,
                )
            )
        assert "email" in str(exc_info.value).lower() or exc_info.value.code == "email_mismatch"

        # Edge case C: Link expires in the meantime
        expired_claims = TaskLinkClaims(
            company_id=company.id,
            project_id=project.id,
            respondent_profile_id=profile.id,
            assignment_ids=(assignment.id,),
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        expired_token = create_task_token(expired_claims, settings)
        invite.token = expired_token
        invite.expires_at = expired_claims.expires_at
        await session.commit()

        with pytest.raises(DomainError) as exc_exp:
            await identity_service.verify_invite_token(expired_token)
        assert exc_exp.value.code == "task_link_expired"

        with pytest.raises(DomainError) as exc_exp_reg:
            await identity_service.register(
                RegisterRequest(
                    email=profile.email,
                    password="Password-123456789!",  # noqa: S106
                    token=expired_token,
                    terms_accepted=True,
                    terms_version=CURRENT_TERMS_VERSION,
                )
            )
        assert exc_exp_reg.value.code == "task_link_expired"

        # Restore valid expiration for remaining edge cases
        invite.token = token
        invite.expires_at = claims.expires_at
        await session.commit()

        # Perform valid registration
        reg_res = await identity_service.register(
            RegisterRequest(
                email=profile.email,
                password="Password-123456789!",  # noqa: S106
                token=token,
                terms_accepted=True,
                terms_version=CURRENT_TERMS_VERSION,
            )
        )
        reg_session_token = reg_res.session_token

        # Edge case D: Opens link on another device (without session cookie)
        exchange_no_session = await identity_service.verify_invite_token_and_create_session(token)
        assert exchange_no_session.response.action == "login_required"
        assert f"returnTo=%2Finvite%2F{token}" in exchange_no_session.response.destination

        # Edge case E: Already has account and is logged in with a DIFFERENT account
        other_user = User(
            id=uuid.uuid4(),
            email=f"other.{uuid.uuid4().hex[:6]}@example.com",
            role=UserRole.participant,
            account_type=UserAccountType.registered,
            password_hash="some-hash",  # noqa: S106
        )
        session.add(other_user)
        await session.flush()

        other_session_token = f"other-session-{uuid.uuid4().hex}"
        other_session = Session(
            id=uuid.uuid4(),
            user_id=other_user.id,
            token_hash=hash_session_token(other_session_token),
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        session.add(other_session)
        await session.commit()

        exchange_other_session = await identity_service.verify_invite_token_and_create_session(
            token,
            existing_session_token=other_session_token,
        )
        assert exchange_other_session.response.action == "account_switch_required"
        assert f"returnTo=%2Finvite%2F{token}" in exchange_other_session.response.destination

        # Edge case F: Clicks link twice in a row (idempotent)
        res_first = await identity_service.verify_invite_token_and_create_session(
            token,
            existing_session_token=reg_session_token,
        )
        res_second = await identity_service.verify_invite_token_and_create_session(
            token,
            existing_session_token=reg_session_token,
        )
        assert res_first.response.action == "dashboard_ready"
        assert res_second.response.action == "dashboard_ready"
        assert res_first.response.destination == res_second.response.destination
