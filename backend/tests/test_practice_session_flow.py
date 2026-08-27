from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis
from sqlalchemy import select

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.identity.models import User, UserAccountType, UserRole  # noqa: F401
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import (
    BudgetReservationState,
    KnowledgePackState,
    OutcomeKind,
    PracticeBudgetReservation,
    PracticeKnowledgePack,
    PracticeOutcome,
    PracticeProgramSettings,
    PracticeSession,
    PracticeTheme,
    PracticeTurn,
    ProgramMode,
    SessionKind,
    SessionState,
    TurnRole,
)
from codrut.modules.practice.service import PracticeSessionService


async def create_test_context(
    session,
    is_enabled: bool = True,
    max_turns_per_session: int = 10,
    max_sessions_per_day: int = 5,
    max_chars_per_turn: int = 1200,
    usd_cap_per_participant: Decimal = Decimal("3.00"),
    membership_active: bool = True,
):
    suffix = uuid.uuid4().hex[:8]
    company = Company(name=f"Practice Co {suffix}")
    session.add(company)
    await session.flush()

    project = CompanyProject(
        company_id=company.id,
        name=f"Practice Project {suffix}",
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
        active=membership_active,
    )
    session.add(membership)
    await session.flush()

    theme = PracticeTheme(
        slug=f"theme-{suffix}",
        name=f"Theme {suffix}",
    )
    session.add(theme)
    await session.flush()

    pack = PracticeKnowledgePack(
        theme_id=theme.id,
        version=1,
        state=KnowledgePackState.approved,
        checksum="synthetic-checksum-12345",
        manifest={"title": "Approved Pack"},
        content_uri=f"pack://synthetic/{suffix}",
        word_count=500,
        approved_at=datetime.now(UTC),
    )
    session.add(pack)
    await session.flush()

    program_settings = PracticeProgramSettings(
        project_id=project.id,
        mode=ProgramMode.training,
        theme_id=theme.id,
        active_pack_id=pack.id,
        is_enabled=is_enabled,
        max_turns_per_session=max_turns_per_session,
        max_sessions_per_day=max_sessions_per_day,
        max_chars_per_turn=max_chars_per_turn,
        turn_retention_days=30,
        usd_cap_per_participant=usd_cap_per_participant,
    )
    session.add(program_settings)
    await session.flush()

    principal = SessionPrincipal(
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

    return {
        "company": company,
        "project": project,
        "profile": profile,
        "membership": membership,
        "theme": theme,
        "pack": pack,
        "program_settings": program_settings,
        "principal": principal,
    }


@pytest.mark.asyncio
async def test_ten_turn_practice_session_flow_local_provider() -> None:
    """Proba celor zece replici:

    1. Pornire sesiune cu pack_id fixat.
    2. 10 perechi de replici (participant + actor).
    3. Dupa fiecare replica: rezervare settled cu actual_usd scris.
    4. expires_at la 30 de zile pe fiecare replica.
    5. A 11-a replica inchide sesiunea cu turn_limit.
    6. Fara apeluri de retea.
    """
    settings = Settings(generation_provider="local")
    provider = LocalGenerationProvider(settings)

    async with SessionLocal() as session:
        ctx = await create_test_context(session, max_turns_per_session=10)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)

        service = PracticeSessionService(
            session=session,
            redis=redis,
            generation_provider=provider,
            settings=settings,
        )

        # 1. Start session
        practice_session = await service.start_session(
            principal=ctx["principal"],
            project_id=ctx["project"].id,
            kind=SessionKind.roleplay,
        )

        assert practice_session.id is not None
        assert practice_session.pack_id == ctx["pack"].id
        assert practice_session.state == SessionState.open
        assert practice_session.turn_count == 0

        # 2. Ten turns flow
        now = datetime.now(UTC)
        for turn_idx in range(1, 11):
            actor_turn = await service.add_participant_turn(
                principal=ctx["principal"],
                session_id=practice_session.id,
                text=f"Replica participant numarul {turn_idx}",
            )

            assert actor_turn is not None
            assert actor_turn.role == TurnRole.actor
            assert actor_turn.ordinal == turn_idx * 2
            assert practice_session.turn_count == turn_idx

            # Verify participant turn and actor turn retention expires_at
            stmt_turns = (
                select(PracticeTurn)
                .where(PracticeTurn.session_id == practice_session.id)
                .order_by(PracticeTurn.ordinal.desc())
                .limit(2)
            )
            latest_turns = (await session.execute(stmt_turns)).scalars().all()
            assert len(latest_turns) == 2
            for turn in latest_turns:
                # Retention ~30 days
                diff_days = (turn.expires_at - now).days
                assert 29 <= diff_days <= 31

            # 3. Verify settled reservation exists with actual_usd written
            stmt_reservations = (
                select(PracticeBudgetReservation)
                .where(PracticeBudgetReservation.session_id == practice_session.id)
                .order_by(PracticeBudgetReservation.created_at.desc())
            )
            reservations = (await session.execute(stmt_reservations)).scalars().all()
            assert len(reservations) == turn_idx
            latest_res = reservations[0]
            assert latest_res.state == BudgetReservationState.settled
            assert latest_res.actual_usd is not None
            assert latest_res.actual_usd >= Decimal("0.0000")

        # 4. 11th turn exceeds max_turns_per_session (10) -> closes session with turn_limit
        eleventh_result = await service.add_participant_turn(
            principal=ctx["principal"],
            session_id=practice_session.id,
            text="Replica participant 11 depaseste plafonul",
        )
        assert eleventh_result is None

        # Verify session is closed with turn_limit outcome
        assert practice_session.state == SessionState.closed
        stmt_outcome = select(PracticeOutcome).where(
            PracticeOutcome.session_id == practice_session.id
        )
        outcome = (await session.execute(stmt_outcome)).scalar_one()
        assert outcome.kind == OutcomeKind.turn_limit

        # 5. Verify local provider recorded exactly 10 requests without touching network
        assert len(provider.recorded_requests) == 10

        await redis.aclose()
        await session.rollback()


@pytest.mark.asyncio
async def test_refusal_practice_not_enabled() -> None:
    """Refusal 1: practica oprita pe proiect -> practice_not_enabled."""
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session, is_enabled=False)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(session=session, redis=redis, settings=settings)

        with pytest.raises(DomainError) as exc_info:
            await service.start_session(
                principal=ctx["principal"],
                project_id=ctx["project"].id,
                kind=SessionKind.roleplay,
            )

        assert exc_info.value.code == "practice_not_enabled"
        await redis.aclose()
        await session.rollback()


@pytest.mark.asyncio
async def test_refusal_not_project_member() -> None:
    """Refusal 2: nemembru sau membru inactiv -> not_project_member."""
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session, membership_active=False)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(session=session, redis=redis, settings=settings)

        with pytest.raises(DomainError) as exc_info:
            await service.start_session(
                principal=ctx["principal"],
                project_id=ctx["project"].id,
                kind=SessionKind.roleplay,
            )

        assert exc_info.value.code == "not_project_member"
        await redis.aclose()
        await session.rollback()


@pytest.mark.asyncio
async def test_refusal_secure_link_access() -> None:
    """Refusal 3: acces prin link securizat -> secure_link_practice_forbidden."""
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        # Modify principal to simulate secure link access
        secure_principal = ctx["principal"].model_copy(update={"access_mode": "secure_link"})

        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(session=session, redis=redis, settings=settings)

        with pytest.raises(DomainError) as exc_info:
            await service.start_session(
                principal=secure_principal,
                project_id=ctx["project"].id,
                kind=SessionKind.roleplay,
            )

        assert exc_info.value.code == "secure_link_practice_forbidden"
        await redis.aclose()
        await session.rollback()


@pytest.mark.asyncio
async def test_refusal_turn_too_long() -> None:
    """Refusal 4: replica depaseste max_chars_per_turn -> practice_turn_too_long."""
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session, max_chars_per_turn=50)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(session=session, redis=redis, settings=settings)

        practice_session = await service.start_session(
            principal=ctx["principal"],
            project_id=ctx["project"].id,
            kind=SessionKind.roleplay,
        )

        with pytest.raises(DomainError) as exc_info:
            await service.add_participant_turn(
                principal=ctx["principal"],
                session_id=practice_session.id,
                text=(
                    "Acesta este un text mult prea lung care depaseste "
                    "limita de 50 de caractere admisa in configurare."
                ),
            )

        assert exc_info.value.code == "practice_turn_too_long"
        await redis.aclose()
        await session.rollback()


@pytest.mark.asyncio
async def test_refusal_daily_session_limit() -> None:
    """Refusal 5: limita zilnica de sesiuni depasita -> practice_daily_limit."""
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session, max_sessions_per_day=2)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(session=session, redis=redis, settings=settings)

        # Start session 1 -> OK
        s1 = await service.start_session(
            principal=ctx["principal"],
            project_id=ctx["project"].id,
            kind=SessionKind.roleplay,
        )
        assert s1 is not None

        # Start session 2 -> OK
        s2 = await service.start_session(
            principal=ctx["principal"],
            project_id=ctx["project"].id,
            kind=SessionKind.roleplay,
        )
        assert s2 is not None

        # Start session 3 -> Limit 2 reached -> practice_daily_limit
        with pytest.raises(DomainError) as exc_info:
            await service.start_session(
                principal=ctx["principal"],
                project_id=ctx["project"].id,
                kind=SessionKind.roleplay,
            )

        assert exc_info.value.code == "practice_daily_limit"
        await redis.aclose()
        await session.rollback()


@pytest.mark.asyncio
async def test_refusal_budget_exceeded_model_never_called() -> None:
    """Refusal 6: buget depasit -> budget_exceeded si verificat ca modelul NU e chemat."""
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        # Cap set to 0.00 USD per participant -> cap is 0.00 USD
        ctx = await create_test_context(session, usd_cap_per_participant=Decimal("0.00"))
        redis = Redis.from_url(settings.redis_url, decode_responses=True)

        mock_provider = AsyncMock()
        service = PracticeSessionService(
            session=session,
            redis=redis,
            generation_provider=mock_provider,
            settings=settings,
        )

        practice_session = await service.start_session(
            principal=ctx["principal"],
            project_id=ctx["project"].id,
            kind=SessionKind.roleplay,
        )

        with pytest.raises(DomainError) as exc_info:
            await service.add_participant_turn(
                principal=ctx["principal"],
                session_id=practice_session.id,
                text="Salut, incerc sa trimit o replica pe un program fara buget disponibil.",
            )

        assert exc_info.value.code == "budget_exceeded"

        # Explicit proof: model generation was NEVER called
        mock_provider.generate.assert_not_called()

        await redis.aclose()
        await session.rollback()


@pytest.mark.asyncio
async def test_generation_failure_releases_budget_and_persists_participant_turn() -> None:
    """Verifies that on model failure:

    1. Error is raised.
    2. Budget reservation is released and committed.
    3. Participant turn remains written and committed.
    4. Session remains open.
    5. Redis lock is freed.
    """
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)

        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = DomainError(
            "Vertex AI timeout", code="vertex_network_error"
        )

        service = PracticeSessionService(
            session=session,
            redis=redis,
            generation_provider=mock_provider,
            settings=settings,
        )

        practice_session = await service.start_session(
            principal=ctx["principal"],
            project_id=ctx["project"].id,
            kind=SessionKind.roleplay,
        )

        with pytest.raises(DomainError) as exc_info:
            await service.add_participant_turn(
                principal=ctx["principal"],
                session_id=practice_session.id,
                text="Aceasta replica va esua in timpul generarii",
            )

        assert exc_info.value.code == "vertex_network_error"

        # 1. Budget reservation is released in DB
        stmt_res = (
            select(PracticeBudgetReservation)
            .where(PracticeBudgetReservation.session_id == practice_session.id)
        )
        res_row = (await session.execute(stmt_res)).scalar_one()
        assert res_row.state == BudgetReservationState.released

        # 2. Participant turn remains written
        stmt_turns = (
            select(PracticeTurn)
            .where(PracticeTurn.session_id == practice_session.id)
        )
        turns = (await session.execute(stmt_turns)).scalars().all()
        assert len(turns) == 1
        assert turns[0].role == TurnRole.participant
        assert turns[0].text == "Aceasta replica va esua in timpul generarii"

        # 3. Session remains open
        stmt_sess = select(PracticeSession).where(PracticeSession.id == practice_session.id)
        sess_row = (await session.execute(stmt_sess)).scalar_one()
        assert sess_row.state == SessionState.open
        assert sess_row.turn_count == 0

        # 4. Redis lock is freed
        lock_key = f"codrut:practice:lock:{ctx['profile'].id}"
        assert await redis.get(lock_key) is None

        await redis.aclose()
        await session.rollback()

