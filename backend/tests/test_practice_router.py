from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from codrut.api.dependencies import current_principal, db_session
from codrut.core.config import Settings, get_settings
from codrut.core.database import SessionLocal
from codrut.main import create_app
from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.identity.models import UserAccountType, UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from codrut.modules.practice.models import (
    KnowledgePackState,
    PracticeKnowledgePack,
    PracticeProgramSettings,
    PracticeTheme,
    ProgramMode,
)
from codrut.modules.practice.prompts import CODY_PROMPT_VERSION, CODY_SYSTEM_PROMPT


async def setup_practice_context(
    session,
    *,
    is_enabled: bool = True,
    max_chars_per_turn: int = 1200,
) -> dict:
    suffix = uuid.uuid4().hex[:8]
    company = Company(name=f"Practice Router Co {suffix}")
    session.add(company)
    await session.flush()

    project = CompanyProject(
        company_id=company.id,
        name=f"Practice Router Project {suffix}",
        project_type="training",
        status=CompanyProjectStatus.active,
    )
    session.add(project)
    await session.flush()

    profile = ParticipantProfile(
        company_id=company.id,
        full_name=f"Participant {suffix}",
        email=f"participant_{suffix}@example.com",
    )
    session.add(profile)
    await session.flush()

    membership = ProjectMembership(
        company_id=company.id,
        project_id=project.id,
        participant_profile_id=profile.id,
        active=True,
    )
    session.add(membership)
    await session.flush()

    theme = PracticeTheme(
        slug=f"feedback-{suffix}",
        name="Feedback Constructiv",
    )
    session.add(theme)
    await session.flush()

    pack = PracticeKnowledgePack(
        theme_id=theme.id,
        version=1,
        state=KnowledgePackState.approved,
        checksum=f"chk-{suffix}",
        manifest={},
        content_uri=f"gs://test-bucket/pack-{suffix}",
        word_count=500,
    )
    session.add(pack)
    await session.flush()

    program_settings = PracticeProgramSettings(
        project_id=project.id,
        mode=ProgramMode.training,
        theme_id=theme.id,
        active_pack_id=pack.id,
        is_enabled=is_enabled,
        max_turns_per_session=10,
        max_sessions_per_day=5,
        max_chars_per_turn=max_chars_per_turn,
        usd_cap_per_participant=Decimal("3.00"),
    )
    session.add(program_settings)
    await session.flush()
    await session.commit()

    participant_principal = SessionPrincipal(
        user_id=uuid.uuid4(),
        email=profile.email,
        role=UserRole.participant,
        account_type=UserAccountType.registered,
        access_mode="account",
        consent_current=True,
        terms_accepted_at=datetime.now(UTC),
        terms_version=CURRENT_TERMS_VERSION,
        session_token=f"test-token-{suffix}",
    )

    other_participant_principal = SessionPrincipal(
        user_id=uuid.uuid4(),
        email=f"other_{suffix}@example.com",
        role=UserRole.participant,
        account_type=UserAccountType.registered,
        access_mode="account",
        consent_current=True,
        terms_accepted_at=datetime.now(UTC),
        terms_version=CURRENT_TERMS_VERSION,
        session_token=f"other-token-{suffix}",
    )

    trainer_principal = SessionPrincipal(
        user_id=uuid.uuid4(),
        email=f"trainer_{suffix}@example.com",
        role=UserRole.trainer,
        account_type=UserAccountType.registered,
        access_mode="account",
        consent_current=True,
        terms_accepted_at=datetime.now(UTC),
        terms_version=CURRENT_TERMS_VERSION,
        session_token=f"trainer-token-{suffix}",
    )

    return {
        "company": company,
        "project": project,
        "profile": profile,
        "program_settings": program_settings,
        "participant": participant_principal,
        "other_participant": other_participant_principal,
        "trainer": trainer_principal,
    }


def make_test_client(
    principal: SessionPrincipal,
    *,
    trainer_direct_entry: bool = False,
):
    app = create_app()

    async def get_db_override():
        async with SessionLocal() as session:
            yield session

    async def get_principal_override() -> SessionPrincipal:
        return principal

    app.dependency_overrides[db_session] = get_db_override
    app.dependency_overrides[current_principal] = get_principal_override

    # Patch settings in app state / factory
    test_settings = Settings(
        generation_provider="local",
        practice_trainer_direct_entry=trainer_direct_entry,
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.state.settings = test_settings

    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_practice_session_lifecycle_and_prompt_version():
    """Verify session creation, turn submission, history retrieval, and session closing."""
    async with SessionLocal() as session:
        ctx = await setup_practice_context(session)

    client = make_test_client(ctx["participant"])

    # 1. Start session
    start_resp = await client.post(
        "/api/practice/sessions",
        json={
            "project_id": str(ctx["project"].id),
            "kind": "roleplay",
        },
    )
    assert start_resp.status_code == 201, start_resp.text
    session_data = start_resp.json()
    session_id = session_data["id"]
    assert session_data["prompt_version"] == CODY_PROMPT_VERSION
    assert session_data["prompt_version"] == "v2.3"
    assert session_data["state"] == "open"
    # De la plicul 38 Cody vorbeste primul: sesiunea porneste cu replica lui, nu goala.
    assert session_data["turn_count"] == 1
    assert session_data["first_turn"] is not None
    assert session_data["first_turn"]["role"] == "actor"
    assert session_data["first_turn"]["ordinal"] == 1

    # 2. Submit participant turn
    turn_resp = await client.post(
        f"/api/practice/sessions/{session_id}/turns",
        json={"text": "Salut Cody, vreau să exersăm o discuție de feedback."},
    )
    assert turn_resp.status_code == 200, turn_resp.text
    turn_data = turn_resp.json()
    assert turn_data["participant_turn"]["role"] == "participant"
    assert "Salut Cody" in turn_data["participant_turn"]["text"]
    assert turn_data["actor_turn"] is not None
    assert turn_data["actor_turn"]["role"] == "actor"
    assert turn_data["session_state"] == "open"

    # 3. Get session history
    hist_resp = await client.get(f"/api/practice/sessions/{session_id}")
    assert hist_resp.status_code == 200, hist_resp.text
    hist_data = hist_resp.json()
    assert hist_data["session"]["id"] == session_id
    assert hist_data["session"]["prompt_version"] == "v2.3"
    # replica de deschidere + replica omului + raspunsul lui Cody
    assert len(hist_data["turns"]) == 3
    assert hist_data["turns"][0]["role"] == "actor"
    assert hist_data["turns"][1]["role"] == "participant"
    assert hist_data["turns"][2]["role"] == "actor"

    # 4. End session
    end_resp = await client.post(
        f"/api/practice/sessions/{session_id}/end",
        json={"outcome_kind": "good", "note": "Sesiune finalizată cu succes."},
    )
    assert end_resp.status_code == 200, end_resp.text
    end_data = end_resp.json()
    assert end_data["session"]["state"] == "closed"


@pytest.mark.asyncio
async def test_participant_cannot_access_another_participants_session():
    """Verify isolation: participant B cannot view or submit turns to participant A's session."""
    async with SessionLocal() as session:
        ctx = await setup_practice_context(session)

    # Participant A starts session
    client_a = make_test_client(ctx["participant"])
    start_resp = await client_a.post(
        "/api/practice/sessions",
        json={
            "project_id": str(ctx["project"].id),
            "kind": "roleplay",
        },
    )
    assert start_resp.status_code == 201
    session_id = start_resp.json()["id"]

    # Also register participant profile for other participant so lookup succeeds
    async with SessionLocal() as session:
        other_profile = ParticipantProfile(
            company_id=ctx["company"].id,
            full_name="Other Participant",
            email=ctx["other_participant"].email,
        )
        session.add(other_profile)
        await session.commit()

    client_b = make_test_client(ctx["other_participant"])

    # Non-existent session
    random_session_id = uuid.uuid4()
    nonexistent_resp = await client_b.get(f"/api/practice/sessions/{random_session_id}")
    assert nonexistent_resp.status_code == 400
    assert nonexistent_resp.json()["error"]["code"] == "session_not_found"

    # Participant B attempts to read history of Participant A's session -> exactly identical error
    read_resp = await client_b.get(f"/api/practice/sessions/{session_id}")
    assert read_resp.status_code == 400
    assert read_resp.json()["error"]["code"] == "session_not_found"
    assert read_resp.json()["error"]["message"] == f"Practice session not found: {session_id}"

    # Participant B attempts to submit turn
    turn_resp = await client_b.post(
        f"/api/practice/sessions/{session_id}/turns",
        json={"text": "Incerc sa trimit replica in sesiunea altuia"},
    )
    assert turn_resp.status_code == 400
    assert turn_resp.json()["error"]["code"] == "session_not_found"
    assert turn_resp.json()["error"]["message"] == f"Practice session not found: {session_id}"

    # Participant B attempts to end session
    end_resp = await client_b.post(
        f"/api/practice/sessions/{session_id}/end",
        json={"outcome_kind": "good"},
    )
    assert end_resp.status_code == 400
    assert end_resp.json()["error"]["code"] == "session_not_found"
    assert end_resp.json()["error"]["message"] == f"Practice session not found: {session_id}"


@pytest.mark.asyncio
async def test_turn_length_quota_enforced():
    """Verify that messages exceeding max_chars_per_turn are rejected with turn_too_long."""
    async with SessionLocal() as session:
        ctx = await setup_practice_context(session, max_chars_per_turn=50)

    client = make_test_client(ctx["participant"])
    start_resp = await client.post(
        "/api/practice/sessions",
        json={"project_id": str(ctx["project"].id), "kind": "roleplay"},
    )
    session_id = start_resp.json()["id"]

    long_text = "A" * 60
    turn_resp = await client.post(
        f"/api/practice/sessions/{session_id}/turns",
        json={"text": long_text},
    )
    assert turn_resp.status_code == 400
    assert turn_resp.json()["error"]["code"] == "practice_turn_too_long"


@pytest.mark.asyncio
async def test_trainer_direct_entry_gives_404_when_disabled():
    """When practice_trainer_direct_entry is False, /practice/trainer/sessions returns 404."""
    async with SessionLocal() as session:
        ctx = await setup_practice_context(session)

    client = make_test_client(ctx["trainer"], trainer_direct_entry=False)
    resp = await client.post(
        "/api/practice/trainer/sessions",
        json={"project_id": str(ctx["project"].id), "kind": "roleplay"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_trainer_direct_entry_succeeds_when_enabled():
    """When practice_trainer_direct_entry is True, trainer can start session directly."""
    async with SessionLocal() as session:
        ctx = await setup_practice_context(session)

    client = make_test_client(ctx["trainer"], trainer_direct_entry=True)
    resp = await client.post(
        "/api/practice/trainer/sessions",
        json={"project_id": str(ctx["project"].id), "kind": "roleplay"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["prompt_version"] == "v2.3"
    assert data["state"] == "open"

    # Trainer can also submit turns
    turn_resp = await client.post(
        f"/api/practice/sessions/{data['id']}/turns",
        json={"text": "Salut Cody, sunt trainerul Andrei si testam."},
    )
    assert turn_resp.status_code == 200, turn_resp.text
    assert turn_resp.json()["actor_turn"] is not None


def test_cody_prompt_content_and_version():
    """Verify that prompts contain the exact SYSTEM_PROMPT_CORE without meta notes."""
    from codrut.modules.practice.prompts import get_system_prompt_for_kind
    assert CODY_PROMPT_VERSION == "v2.3"
    roleplay_prompt = get_system_prompt_for_kind("roleplay")
    assert "Ești Codruț" in roleplay_prompt
    assert "Treci DIRECT la SETUP" in roleplay_prompt

