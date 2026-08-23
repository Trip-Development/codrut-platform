import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.main import create_app
from codrut.modules.assignments.service import AssignmentService
from codrut.modules.companies.models import (
    Company,
    CompanyMembership,
    CompanyMembershipRole,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ParticipantViewAudit,
    ProjectMembership,
)
from codrut.modules.companies.router import (
    get_participant_workspace_preview,
    list_participant_view_audits,
)
from codrut.modules.companies.service import CompanyService
from codrut.modules.identity.models import User, UserRole
from codrut.modules.identity.schemas import SessionPrincipal


@pytest.fixture
async def preview_fixture():
    async with SessionLocal() as session:
        suffix = uuid.uuid4().hex[:6]
        # 1. Company A & B
        company_a = Company(id=uuid.uuid4(), name=f"Company Alpha {suffix}")
        company_b = Company(id=uuid.uuid4(), name=f"Company Beta {suffix}")
        session.add_all([company_a, company_b])
        await session.flush()

        # 2. Trainers
        trainer_a = User(
            id=uuid.uuid4(),
            email=f"trainer.alpha.{suffix}@example.com",
            password_hash="hash",  # noqa: S106
            role=UserRole.trainer,
        )
        trainer_b = User(
            id=uuid.uuid4(),
            email=f"trainer.beta.{suffix}@example.com",
            password_hash="hash",  # noqa: S106
            role=UserRole.trainer,
        )
        participant_user = User(
            id=uuid.uuid4(),
            email=f"participant.alpha.{suffix}@example.com",
            password_hash="hash",  # noqa: S106
            role=UserRole.participant,
        )
        session.add_all([trainer_a, trainer_b, participant_user])
        await session.flush()

        # Memberships
        membership_a = CompanyMembership(
            id=uuid.uuid4(),
            company_id=company_a.id,
            user_id=trainer_a.id,
            role=CompanyMembershipRole.owner,
        )
        membership_b = CompanyMembership(
            id=uuid.uuid4(),
            company_id=company_b.id,
            user_id=trainer_b.id,
            role=CompanyMembershipRole.owner,
        )
        session.add_all([membership_a, membership_b])
        await session.flush()

        # Participant Profile in Company A
        participant_profile_a = ParticipantProfile(
            id=uuid.uuid4(),
            company_id=company_a.id,
            user_id=participant_user.id,
            full_name="Radu Participant",
            email=participant_user.email,
        )
        session.add(participant_profile_a)
        await session.flush()

        # Project in Company A
        project_a = CompanyProject(
            id=uuid.uuid4(),
            company_id=company_a.id,
            name="Project Leadership",
            status=CompanyProjectStatus.active,
        )
        session.add(project_a)
        await session.flush()

        project_membership = ProjectMembership(
            id=uuid.uuid4(),
            company_id=company_a.id,
            project_id=project_a.id,
            participant_profile_id=participant_profile_a.id,
            active=True,
        )
        session.add(project_membership)
        await session.flush()
        await session.commit()

        return {
            "company_a_id": company_a.id,
            "company_b_id": company_b.id,
            "trainer_a_id": trainer_a.id,
            "trainer_a_email": trainer_a.email,
            "trainer_b_id": trainer_b.id,
            "trainer_b_email": trainer_b.email,
            "participant_user_id": participant_user.id,
            "participant_user_email": participant_user.email,
            "participant_profile_a_id": participant_profile_a.id,
            "project_a_id": project_a.id,
        }


@pytest.mark.asyncio
async def test_trainer_can_preview_participant_workspace_service(preview_fixture):
    data = preview_fixture
    async with SessionLocal() as session:
        service = CompanyService(session)
        summary = await service.get_participant_workspace_preview(
            trainer_user_id=data["trainer_a_id"],
            trainer_email=data["trainer_a_email"],
            company_id=data["company_a_id"],
            participant_id=data["participant_profile_a_id"],
        )
        assert summary.participant_profile_id == data["participant_profile_a_id"]
        assert summary.participant_full_name == "Radu Participant"
        assert summary.company_id == data["company_a_id"]

        # Check audit in DB
        result = await session.execute(
            select(ParticipantViewAudit).where(
                ParticipantViewAudit.company_id == data["company_a_id"],
                ParticipantViewAudit.participant_profile_id == data["participant_profile_a_id"],
            )
        )
        audits = list(result.scalars().all())
        assert len(audits) >= 1
        latest = audits[-1]
        assert latest.trainer_user_id == data["trainer_a_id"]
        assert latest.trainer_email == data["trainer_a_email"]
        assert latest.participant_name == "Radu Participant"
        assert latest.screen == "workspace"


@pytest.mark.asyncio
async def test_trainer_of_other_company_gets_403_service(preview_fixture):
    data = preview_fixture
    async with SessionLocal() as session:
        service = CompanyService(session)
        with pytest.raises(DomainError) as exc_info:
            await service.get_participant_workspace_preview(
                trainer_user_id=data["trainer_b_id"],
                trainer_email=data["trainer_b_email"],
                company_id=data["company_a_id"],
                participant_id=data["participant_profile_a_id"],
            )
        assert exc_info.value.code == "company_access_denied"


@pytest.mark.asyncio
async def test_trainer_preview_endpoint_router(preview_fixture):
    data = preview_fixture
    principal = SessionPrincipal(
        user_id=data["trainer_a_id"],
        email=data["trainer_a_email"],
        role=UserRole.trainer,
        terms_accepted_at=datetime.now(UTC),
        terms_version="privacy-2026-07-16",
        session_token="test-session",  # noqa: S106
    )

    async with SessionLocal() as session:
        summary = await get_participant_workspace_preview(
            company_id=data["company_a_id"],
            participant_id=data["participant_profile_a_id"],
            principal=principal,
            session=session,
        )
        assert summary.participant_profile_id == data["participant_profile_a_id"]
        assert summary.participant_full_name == "Radu Participant"


@pytest.mark.asyncio
async def test_trainer_preview_other_company_router_403(preview_fixture):
    data = preview_fixture
    principal = SessionPrincipal(
        user_id=data["trainer_b_id"],
        email=data["trainer_b_email"],
        role=UserRole.trainer,
        terms_accepted_at=datetime.now(UTC),
        terms_version="privacy-2026-07-16",
        session_token="test-session",  # noqa: S106
    )

    async with SessionLocal() as session:
        with pytest.raises(DomainError) as exc_info:
            await get_participant_workspace_preview(
                company_id=data["company_a_id"],
                participant_id=data["participant_profile_a_id"],
                principal=principal,
                session=session,
            )
        assert exc_info.value.code == "company_access_denied"


@pytest.mark.asyncio
async def test_participant_role_cannot_call_preview_router(preview_fixture):
    data = preview_fixture
    principal = SessionPrincipal(
        user_id=data["participant_user_id"],
        email=data["participant_user_email"],
        role=UserRole.participant,
        terms_accepted_at=datetime.now(UTC),
        terms_version="privacy-2026-07-16",
        session_token="test-session",  # noqa: S106
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_participant_workspace_preview(
            company_id=data["company_a_id"],
            participant_id=data["participant_profile_a_id"],
            principal=principal,
            session=AsyncMock(),
        )
    assert exc_info.value.status_code == 403


def test_write_methods_on_preview_route_rejected(preview_fixture):
    data = preview_fixture
    app = create_app()

    client = TestClient(app)
    cid = data["company_a_id"]
    pid = data["participant_profile_a_id"]
    url = f"/api/companies/{cid}/participants/{pid}/workspace-preview"

    assert client.post(url, json={}).status_code == 405
    assert client.put(url, json={}).status_code == 405
    assert client.patch(url, json={}).status_code == 405
    assert client.delete(url).status_code == 405


@pytest.mark.asyncio
async def test_fail_closed_if_audit_fails(preview_fixture):
    data = preview_fixture
    principal = SessionPrincipal(
        user_id=data["trainer_a_id"],
        email=data["trainer_a_email"],
        role=UserRole.trainer,
        terms_accepted_at=datetime.now(UTC),
        terms_version="privacy-2026-07-16",
        session_token="test-session",  # noqa: S106
    )

    with patch.object(
        CompanyService,
        "get_participant_workspace_preview",
        side_effect=DomainError("Failed to record access audit log.", code="audit_log_failed"),
    ):
        with pytest.raises(DomainError) as exc_info:
            await get_participant_workspace_preview(
                company_id=data["company_a_id"],
                participant_id=data["participant_profile_a_id"],
                principal=principal,
                session=AsyncMock(),
            )
        assert exc_info.value.code == "audit_log_failed"


@pytest.mark.asyncio
async def test_participant_view_audits_endpoint_router(preview_fixture):
    data = preview_fixture
    async with SessionLocal() as session:
        audit = ParticipantViewAudit(
            id=uuid.uuid4(),
            company_id=data["company_a_id"],
            trainer_user_id=data["trainer_a_id"],
            trainer_email=data["trainer_a_email"],
            participant_profile_id=data["participant_profile_a_id"],
            participant_name="Radu Participant",
            screen="workspace",
        )
        session.add(audit)
        await session.commit()

    principal = SessionPrincipal(
        user_id=data["trainer_a_id"],
        email=data["trainer_a_email"],
        role=UserRole.trainer,
        terms_accepted_at=datetime.now(UTC),
        terms_version="privacy-2026-07-16",
        session_token="test-session",  # noqa: S106
    )

    async with SessionLocal() as session:
        audits = await list_participant_view_audits(
            company_id=data["company_a_id"],
            principal=principal,
            session=session,
        )
        assert len(audits) >= 1
        assert audits[0].trainer_email == data["trainer_a_email"]
        assert audits[0].participant_name == "Radu Participant"


@pytest.mark.asyncio
async def test_require_company_manager_shared_helper_non_regression(preview_fixture):
    data = preview_fixture
    async with SessionLocal() as session:
        assignment_service = AssignmentService(session)

        # 1. Trainer A on Company A succeeds
        await assignment_service._require_company_manager(
            data["trainer_a_id"],
            data["company_a_id"],
        )

        # 2. Trainer A on Company B fails with company_access_denied
        with pytest.raises(DomainError) as exc_info:
            await assignment_service._require_company_manager(
                data["trainer_a_id"],
                data["company_b_id"],
            )
        assert exc_info.value.code == "company_access_denied"

        # 3. Non-existent company fails with company_not_found
        with pytest.raises(DomainError) as exc_info:
            await assignment_service._require_company_manager(
                data["trainer_a_id"],
                uuid.uuid4(),
            )
        assert exc_info.value.code == "company_not_found"


@pytest.mark.asyncio
async def test_preview_privacy_threshold_and_unpublished_results(preview_fixture):
    data = preview_fixture
    async with SessionLocal() as session:
        service = CompanyService(session)
        summary = await service.get_participant_workspace_preview(
            trainer_user_id=data["trainer_a_id"],
            trainer_email=data["trainer_a_email"],
            company_id=data["company_a_id"],
            participant_id=data["participant_profile_a_id"],
            project_id=data["project_a_id"],
        )
        # Results are unpublished -> results list is empty or unavailable
        assert summary.results == []
        assert summary.received_feedback is None
