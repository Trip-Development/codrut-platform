from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.contracts.generation import (
    GenerationMessage,
    GenerationPurpose,
    GenerationRequest,
)
from codrut.core.config import Settings, get_settings
from codrut.core.errors import DomainError
from codrut.modules.companies.models import ParticipantProfile, ProjectMembership
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.practice.budget import release, reserve, settle
from codrut.modules.practice.generation_provider import (
    GenerationProvider,
    build_generation_provider,
)
from codrut.modules.practice.models import (
    OutcomeKind,
    PracticeOutcome,
    PracticeProgramSettings,
    PracticeSession,
    PracticeTurn,
    SessionKind,
    SessionState,
    TurnRole,
)
from codrut.modules.practice.policies import ensure_participant_may_practice
from codrut.modules.practice.pricing import estimate_pessimistic_cost
from codrut.modules.practice.quotas import (
    acquire_generation_lock,
    ensure_daily_session_limit,
    ensure_turn_length,
    is_session_turn_limit_reached,
)

PLACEHOLDER_SYSTEM_INSTRUCTION = (
    "Esti un partener de exercitiu. Raspunde scurt, in romana. "
    "TEMPORAR - se inlocuieste in Faza 2 cu persona reala."
)


class PracticeSessionService:
    def __init__(
        self,
        session: AsyncSession,
        redis: Redis | None = None,
        generation_provider: GenerationProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self._redis = redis
        self._generation_provider = generation_provider

    @property
    def redis(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(self.settings.redis_url, decode_responses=True)
        return self._redis

    @property
    def generation_provider(self) -> GenerationProvider:
        if self._generation_provider is None:
            self._generation_provider = build_generation_provider(self.settings)
        return self._generation_provider

    async def _resolve_participant_profile(
        self,
        principal: SessionPrincipal,
    ) -> ParticipantProfile:
        stmt = select(ParticipantProfile).where(
            or_(
                ParticipantProfile.user_id == principal.user_id,
                ParticipantProfile.email == principal.email,
            )
        )
        profile = (await self.session.execute(stmt)).scalar_one_or_none()
        if profile is None:
            raise DomainError(
                "Participant profile not found for principal",
                code="participant_profile_not_found",
            )
        return profile

    async def start_session(
        self,
        principal: SessionPrincipal,
        project_id: uuid.UUID,
        kind: SessionKind,
        scenario_id: uuid.UUID | None = None,
    ) -> PracticeSession:
        """Start a new practice session for a participant after policy and quota checks."""
        # 1. Load practice program settings for project
        stmt_settings = select(PracticeProgramSettings).where(
            PracticeProgramSettings.project_id == project_id
        )
        program_settings = (await self.session.execute(stmt_settings)).scalar_one_or_none()
        if program_settings is None:
            raise DomainError(
                f"Practice is not configured for project {project_id}",
                code="practice_not_configured",
            )

        # 2. Load participant profile and project membership
        stmt_profile = select(ParticipantProfile).where(
            or_(
                ParticipantProfile.user_id == principal.user_id,
                ParticipantProfile.email == principal.email,
            )
        )
        profile = (await self.session.execute(stmt_profile)).scalar_one_or_none()
        membership = None
        if profile is not None:
            stmt_membership = select(ProjectMembership).where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.participant_profile_id == profile.id,
            )
            membership = (await self.session.execute(stmt_membership)).scalar_one_or_none()

        membership_active = bool(membership is not None and membership.active)

        # 3. Authorization check
        ensure_participant_may_practice(
            principal,
            program_enabled=program_settings.is_enabled,
            membership_active=membership_active,
        )

        assert profile is not None

        # 4. Daily sessions limit
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        stmt_count = select(func.count(PracticeSession.id)).where(
            PracticeSession.participant_profile_id == profile.id,
            PracticeSession.started_at >= today_start,
        )
        sessions_today_count = (await self.session.execute(stmt_count)).scalar_one() or 0
        ensure_daily_session_limit(
            sessions_today_count=sessions_today_count,
            max_sessions_per_day=program_settings.max_sessions_per_day,
        )

        # 5. Check active knowledge pack
        if program_settings.active_pack_id is None:
            raise DomainError(
                "Active knowledge pack is missing for practice program",
                code="practice_pack_missing",
            )

        # 6. Create practice session with fixed active pack_id
        practice_session = PracticeSession(
            program_settings_id=program_settings.id,
            participant_profile_id=profile.id,
            pack_id=program_settings.active_pack_id,
            scenario_id=scenario_id,
            kind=kind,
            state=SessionState.open,
            started_at=now,
            turn_count=0,
        )
        self.session.add(practice_session)
        await self.session.flush()
        return practice_session

    async def add_participant_turn(
        self,
        principal: SessionPrincipal,
        session_id: uuid.UUID,
        text: str,
    ) -> PracticeTurn | None:
        """Add a participant turn and generate the actor's reply."""
        # 1. Verify session exists, is open, and belongs to principal
        stmt_session = select(PracticeSession).where(PracticeSession.id == session_id)
        session_obj = (await self.session.execute(stmt_session)).scalar_one_or_none()
        if session_obj is None:
            raise DomainError(
                f"Practice session not found: {session_id}",
                code="session_not_found",
            )
        if session_obj.state != SessionState.open:
            raise DomainError(
                f"Practice session is {session_obj.state.value}",
                code="session_closed",
            )

        profile = await self._resolve_participant_profile(principal)
        if session_obj.participant_profile_id != profile.id:
            raise DomainError(
                "Participant does not own this practice session",
                code="session_forbidden",
            )

        stmt_prog = select(PracticeProgramSettings).where(
            PracticeProgramSettings.id == session_obj.program_settings_id
        )
        program_settings = (await self.session.execute(stmt_prog)).scalar_one()

        # 2. Text length check
        ensure_turn_length(text, program_settings.max_chars_per_turn)

        # 3. Check turn count limit
        if is_session_turn_limit_reached(
            session_obj.turn_count, program_settings.max_turns_per_session
        ):
            session_obj.state = SessionState.closed
            session_obj.ended_at = datetime.now(UTC)
            outcome = PracticeOutcome(
                session_id=session_id,
                kind=OutcomeKind.turn_limit,
                note="Maximum turns reached for session",
            )
            self.session.add(outcome)
            await self.session.flush()
            return None

        # 4. Redis single-flight generation lock
        timeout_seconds = self.settings.vertex_timeout_seconds + 10
        async with acquire_generation_lock(
            redis=self.redis,
            participant_profile_id=profile.id,
            timeout_seconds=timeout_seconds,
        ):
            now = datetime.now(UTC)
            expires_at = now + timedelta(days=program_settings.turn_retention_days)

            # Query existing turns for this session
            stmt_turns = (
                select(PracticeTurn)
                .where(PracticeTurn.session_id == session_id)
                .order_by(PracticeTurn.ordinal.asc())
            )
            existing_turns = (await self.session.execute(stmt_turns)).scalars().all()
            next_ordinal = (existing_turns[-1].ordinal + 1) if existing_turns else 1

            # 5. Write participant turn
            p_turn = PracticeTurn(
                session_id=session_id,
                ordinal=next_ordinal,
                role=TurnRole.participant,
                text=text,
                expires_at=expires_at,
            )
            self.session.add(p_turn)
            await self.session.flush()

            # 6. Build GenerationRequest
            messages: list[GenerationMessage] = []
            for t in existing_turns:
                role_str = "user" if t.role == TurnRole.participant else "model"
                messages.append(GenerationMessage(role=role_str, text=t.text))
            messages.append(GenerationMessage(role="user", text=text))

            request = GenerationRequest(
                messages=tuple(messages),
                system_instruction=PLACEHOLDER_SYSTEM_INSTRUCTION,
                purpose=GenerationPurpose.actor,
                max_output_tokens=self.settings.vertex_max_output_tokens,
                temperature=0.7,
                thinking_budget=self.settings.thinking_budget_actor,
            )

            # 7. Estimate pessimistic cost and reserve budget
            prompt_words = sum(len(m.text.split()) for m in request.messages)
            if request.system_instruction:
                prompt_words += len(request.system_instruction.split())
            estimated_prompt_tokens = max(1, prompt_words)

            estimated_usd = estimate_pessimistic_cost(
                prompt_tokens=estimated_prompt_tokens,
                max_output_tokens=self.settings.vertex_max_output_tokens,
                thinking_budget=self.settings.thinking_budget_actor,
                settings=self.settings,
            )

            stmt_active_members = select(func.count(ProjectMembership.id)).where(
                ProjectMembership.project_id == program_settings.project_id,
                ProjectMembership.active.is_(True),
            )
            active_participants_count = (
                await self.session.execute(stmt_active_members)
            ).scalar_one() or 0
            cap_usd = (
                Decimal(active_participants_count)
                * program_settings.usd_cap_per_participant
            )

            reservation_id = await reserve(
                session=self.session,
                program_settings_id=program_settings.id,
                estimated_usd=estimated_usd,
                cap_usd=cap_usd,
                session_id=session_id,
            )

            # 8. Flush state before calling model
            await self.session.flush()

            # 9. Invoke model generation provider
            try:
                result = await self.generation_provider.generate(request)
            except Exception:
                # 11. On failure: release budget, participant turn remains
                await release(self.session, reservation_id)
                await self.session.flush()
                raise

            # 10. Settle budget reservation with actual cost and record actor turn
            await settle(self.session, reservation_id, actual_usd=result.estimated_usd)

            actor_turn = PracticeTurn(
                session_id=session_id,
                ordinal=next_ordinal + 1,
                role=TurnRole.actor,
                text=result.text,
                prompt_tokens=result.usage.prompt_tokens,
                output_tokens=result.usage.output_tokens,
                thought_tokens=result.usage.thought_tokens,
                expires_at=expires_at,
            )
            self.session.add(actor_turn)
            session_obj.turn_count += 1
            await self.session.flush()

            return actor_turn

    async def end_session(
        self,
        principal: SessionPrincipal,
        session_id: uuid.UUID,
        outcome_kind: OutcomeKind,
        note: str | None = None,
    ) -> None:
        """Explicitly end a practice session and record outcome idempotently."""
        stmt = select(PracticeSession).where(PracticeSession.id == session_id)
        session_obj = (await self.session.execute(stmt)).scalar_one_or_none()
        if session_obj is None:
            raise DomainError(
                f"Practice session not found: {session_id}",
                code="session_not_found",
            )

        profile = await self._resolve_participant_profile(principal)
        if session_obj.participant_profile_id != profile.id:
            raise DomainError(
                "Participant does not own this practice session",
                code="session_forbidden",
            )

        if session_obj.state == SessionState.closed:
            stmt_outcome = select(PracticeOutcome).where(
                PracticeOutcome.session_id == session_id
            )
            existing_outcome = (await self.session.execute(stmt_outcome)).scalar_one_or_none()
            if existing_outcome is None:
                outcome = PracticeOutcome(
                    session_id=session_id,
                    kind=outcome_kind,
                    note=note,
                )
                self.session.add(outcome)
                await self.session.flush()
            return

        session_obj.state = SessionState.closed
        session_obj.ended_at = datetime.now(UTC)
        outcome = PracticeOutcome(
            session_id=session_id,
            kind=outcome_kind,
            note=note,
        )
        self.session.add(outcome)
        await self.session.flush()
