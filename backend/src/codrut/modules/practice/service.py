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
from codrut.modules.companies.models import CompanyProject, ParticipantProfile, ProjectMembership
from codrut.modules.identity.models import User, UserRole
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
from codrut.modules.practice.prompts import (
    CODY_PROMPT_VERSION,
    CODY_SYSTEM_PROMPT,
    get_system_prompt_for_kind,
)
from codrut.modules.practice.quotas import (
    acquire_generation_lock,
    ensure_daily_session_limit,
    ensure_turn_length,
    is_session_turn_limit_reached,
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
        # 1. Load project and verify project_type is training
        stmt_proj = select(CompanyProject).where(CompanyProject.id == project_id)
        project = (await self.session.execute(stmt_proj)).scalar_one_or_none()
        if project is None:
            raise DomainError(f"Proiectul {project_id} nu a fost găsit", code="project_not_found")
        if project.project_type != "training":
            raise DomainError(
                "Exersarea nu este configurată pentru acest tip de proiect.",
                code="practice_not_configured_for_project_type",
            )

        # 2. Load practice program settings for project
        stmt_settings = select(PracticeProgramSettings).where(
            PracticeProgramSettings.project_id == project_id
        )
        program_settings = (await self.session.execute(stmt_settings)).scalar_one_or_none()
        if program_settings is None:
            raise DomainError(
                f"Practice is not configured for project {project_id}",
                code="practice_not_configured",
            )

        # 3. Load participant profile and project membership
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

        # 6. Create practice session with fixed active pack_id and prompt version
        practice_session = PracticeSession(
            program_settings_id=program_settings.id,
            participant_profile_id=profile.id,
            pack_id=program_settings.active_pack_id,
            scenario_id=scenario_id,
            kind=kind,
            state=SessionState.open,
            started_at=now,
            turn_count=0,
            prompt_version=CODY_PROMPT_VERSION,
        )
        self.session.add(practice_session)
        await self.session.flush()
        return practice_session

    async def start_trainer_session(
        self,
        principal: SessionPrincipal,
        project_id: uuid.UUID,
        kind: SessionKind,
        scenario_id: uuid.UUID | None = None,
    ) -> PracticeSession:
        """Start a direct practice session for a trainer without requiring invitations."""
        if not principal.can_access_workspace(UserRole.trainer):
            raise DomainError("Trainer access required", code="trainer_required")

        stmt_settings = select(PracticeProgramSettings).where(
            PracticeProgramSettings.project_id == project_id
        )
        program_settings = (await self.session.execute(stmt_settings)).scalar_one_or_none()
        if program_settings is None or program_settings.active_pack_id is None:
            raise DomainError(
                f"Practice is not configured for project {project_id}",
                code="practice_not_configured",
            )

        stmt_profile = select(ParticipantProfile).where(
            or_(
                ParticipantProfile.user_id == principal.user_id,
                ParticipantProfile.email == principal.email,
            )
        )
        profile = (await self.session.execute(stmt_profile)).scalar_one_or_none()
        if profile is None:
            stmt_proj = select(CompanyProject).where(CompanyProject.id == project_id)
            project = (await self.session.execute(stmt_proj)).scalar_one_or_none()
            if project is None:
                raise DomainError(f"Project not found: {project_id}", code="project_not_found")

            stmt_user = select(User).where(User.id == principal.user_id)
            user_exists = (await self.session.execute(stmt_user)).scalar_one_or_none() is not None

            profile = ParticipantProfile(
                id=uuid.uuid4(),
                company_id=project.company_id,
                user_id=principal.user_id if user_exists else None,
                full_name="Trainer",
                email=principal.email,
            )
            self.session.add(profile)
            await self.session.flush()

        now = datetime.now(UTC)
        practice_session = PracticeSession(
            program_settings_id=program_settings.id,
            participant_profile_id=profile.id,
            pack_id=program_settings.active_pack_id,
            scenario_id=scenario_id,
            kind=kind,
            state=SessionState.open,
            started_at=now,
            turn_count=0,
            prompt_version=CODY_PROMPT_VERSION,
        )
        self.session.add(practice_session)
        await self.session.flush()
        return practice_session

    async def get_session_history(
        self,
        principal: SessionPrincipal,
        session_id: uuid.UUID,
    ) -> tuple[PracticeSession, list[PracticeTurn]]:
        """Get a practice session and its conversation turns in order."""
        stmt_session = select(PracticeSession).where(PracticeSession.id == session_id)
        session_obj = (await self.session.execute(stmt_session)).scalar_one_or_none()
        profile = await self._resolve_participant_profile(principal)
        if session_obj is None or session_obj.participant_profile_id != profile.id:
            raise DomainError(
                f"Practice session not found: {session_id}",
                code="session_not_found",
            )

        stmt_turns = (
            select(PracticeTurn)
            .where(PracticeTurn.session_id == session_id)
            .order_by(PracticeTurn.ordinal.asc())
        )
        turns = list((await self.session.execute(stmt_turns)).scalars().all())
        return session_obj, turns

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
        profile = await self._resolve_participant_profile(principal)
        if session_obj is None or session_obj.participant_profile_id != profile.id:
            raise DomainError(
                f"Practice session not found: {session_id}",
                code="session_not_found",
            )
        if session_obj.state != SessionState.open:
            raise DomainError(
                f"Practice session is {session_obj.state.value}",
                code="session_closed",
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

            history_length = len(existing_turns) + 1
            is_actor_role = (session_obj.kind == SessionKind.roleplay)

            system_instruction = get_system_prompt_for_kind(
                kind=session_obj.kind,
                name=profile.full_name,
                history_length=history_length,
                is_actor_role=is_actor_role,
                biblioteca_path=self.settings.biblioteca_path,
            )

            request = GenerationRequest(
                messages=tuple(messages),
                system_instruction=system_instruction,
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
            cap_usd = Decimal(active_participants_count) * program_settings.usd_cap_per_participant

            reservation_id = await reserve(
                session=self.session,
                program_settings_id=program_settings.id,
                estimated_usd=estimated_usd,
                cap_usd=cap_usd,
                session_id=session_id,
            )

            # 8. Close transaction before calling model (frees DB connection)
            await self.session.commit()

            # 9. Invoke model generation provider
            try:
                result = await self.generation_provider.generate(request)
            except Exception:
                # 11. On failure: release budget, commit, participant turn remains saved in DB
                await release(self.session, reservation_id)
                await self.session.commit()
                raise

            # 10. New transaction: settle budget reservation with actual cost and record actor turn
            await settle(self.session, reservation_id, actual_usd=result.estimated_usd)

            actor_turn = PracticeTurn(
                session_id=session_id,
                ordinal=next_ordinal + 1,
                role=TurnRole.actor,
                text=result.text,
                prompt_tokens=result.usage.prompt_tokens,
                cached_tokens=result.usage.cached_tokens,
                output_tokens=result.usage.output_tokens,
                thought_tokens=result.usage.thought_tokens,
                expires_at=expires_at,
            )
            self.session.add(actor_turn)

            stmt_sess = select(PracticeSession).where(PracticeSession.id == session_id)
            current_session = (await self.session.execute(stmt_sess)).scalar_one()
            current_session.turn_count += 1

            await self.session.commit()

            return actor_turn

    async def submit_turn(
        self,
        principal: SessionPrincipal,
        session_id: uuid.UUID,
        text: str,
    ) -> tuple[PracticeTurn, PracticeTurn | None, SessionState]:
        """Submit participant turn, trigger actor reply, and return turns and session state."""
        actor_turn = await self.add_participant_turn(
            principal=principal,
            session_id=session_id,
            text=text,
        )
        stmt_pturn = (
            select(PracticeTurn)
            .where(
                PracticeTurn.session_id == session_id,
                PracticeTurn.role == TurnRole.participant,
            )
            .order_by(PracticeTurn.ordinal.desc())
            .limit(1)
        )
        p_turn = (await self.session.execute(stmt_pturn)).scalar_one()
        stmt_sess = select(PracticeSession).where(PracticeSession.id == session_id)
        sess = (await self.session.execute(stmt_sess)).scalar_one()
        return p_turn, actor_turn, sess.state

    async def end_session(
        self,
        principal: SessionPrincipal,
        session_id: uuid.UUID,
        outcome_kind: OutcomeKind = OutcomeKind.good,
        note: str | None = None,
    ) -> tuple[PracticeSession, str | None]:
        """Explicitly end a practice session, generate summary using SUMMARY_PROMPT, record outcome and persist evaluation data."""
        import json
        import logging
        import re

        from codrut.modules.practice.models import (
            CompetencyScore,
            InsightMoment,
            ParticipantMemory,
        )

        stmt = select(PracticeSession).where(PracticeSession.id == session_id)
        session_obj = (await self.session.execute(stmt)).scalar_one_or_none()
        profile = await self._resolve_participant_profile(principal)
        if session_obj is None or session_obj.participant_profile_id != profile.id:
            raise DomainError(
                f"Practice session not found: {session_id}",
                code="session_not_found",
            )

        summary_text: str | None = None

        # Fetch turns for summary generation
        stmt_turns = (
            select(PracticeTurn)
            .where(PracticeTurn.session_id == session_id)
            .order_by(PracticeTurn.ordinal.asc())
        )
        turns = list((await self.session.execute(stmt_turns)).scalars().all())

        if turns:
            history_lines = []
            for t in turns:
                speaker = profile.full_name if t.role == TurnRole.participant else "Codruț"
                history_lines.append(f"{speaker}: {t.text}")
            history_str = "\n\n".join(history_lines)
            from codrut.modules.practice.prompts import get_summary_prompt

            summary_content = get_summary_prompt(
                name=profile.full_name,
                opt_text=session_obj.kind.value,
                history=history_str,
            )
            req = GenerationRequest(
                messages=(GenerationMessage(role="user", text=summary_content),),
                system_instruction="Ești analizator de discurs.",
                purpose=GenerationPurpose.evaluator,
                max_output_tokens=self.settings.vertex_max_output_tokens_evaluator,
                temperature=0.2,
                thinking_budget=self.settings.thinking_budget_evaluator,
            )
            try:
                res = await self.generation_provider.generate(req)
                summary_text = res.text

                # 4-step closing flow persistence
                json_match = re.search(r"```json\s*(\{.*?\})\s*```", summary_text, re.DOTALL)
                if json_match:
                    try:
                        eval_data = json.loads(json_match.group(1))
                        scores_dict = eval_data.get("scores", {})
                        topic = eval_data.get("topic", "")
                        characters = eval_data.get("characters", [])

                        score_name_map = {
                            "questionsRatio": "Abilități de Coach și Întrebări",
                            "assertiveness": "Comunicare Asertivă",
                            "sbiFeedback": "Feedback Structurat (SBI)",
                            "conciseness": "Concizie și Echilibru",
                        }
                        for k, v in scores_dict.items():
                            if isinstance(v, (int, float)):
                                c_name = score_name_map.get(k, k)
                                normalized_score = int(round(float(v) * 10))
                                level = 1 if normalized_score < 50 else (2 if normalized_score < 80 else 3)
                                cs = CompetencyScore(
                                    user_id=profile.user_id or principal.user_id,
                                    score=min(100, max(0, normalized_score)),
                                    level=level,
                                    justification=f"Scor evaluat automat în modul {session_obj.kind.value}: {v}/10.",
                                    conversation_id=str(session_id),
                                    competency_name=c_name,
                                    source_type="session",
                                )
                                self.session.add(cs)

                        conclusion_part = summary_text.split("##Recomandări")[0].replace("##Concluzie", "").strip()
                        im = InsightMoment(
                            user_id=profile.user_id or principal.user_id,
                            conversation_id=str(session_id),
                            summary=conclusion_part[:500] if conclusion_part else "Sesiune finalizată.",
                        )
                        self.session.add(im)

                        numeric_scores = [float(x) for x in scores_dict.values() if isinstance(x, (int, float))]
                        avg_score = int(round(sum(numeric_scores) / max(1, len(numeric_scores)) * 10)) if numeric_scores else 50
                        pm = ParticipantMemory(
                            user_id=profile.user_id or principal.user_id,
                            session_id=str(session_id),
                            summary=conclusion_part[:1000] if conclusion_part else summary_text[:1000],
                            key_quotes=[],
                            evolution_signals=scores_dict,
                            personal_context={"topic": topic, "characters": characters},
                            relevant_competencies=list(score_name_map.values()),
                            source_type=session_obj.kind.value,
                            relevance_score=min(100, max(0, avg_score)),
                        )
                        self.session.add(pm)

                        profile.xp = (profile.xp or 0) + 10
                        profile.streak = (profile.streak or 0) + 1
                        stmt_u = select(User).where(User.id == (profile.user_id or principal.user_id))
                        user_obj = (await self.session.execute(stmt_u)).scalar_one_or_none()
                        if user_obj:
                            user_obj.xp = (user_obj.xp or 0) + 10
                            user_obj.streak = (user_obj.streak or 0) + 1

                    except Exception as parse_err:
                        logging.getLogger(__name__).warning(f"Failed to parse evaluation JSON in end_session: {parse_err}")
                else:
                    # Fara randul asta defectul e invizibil: raspunsul vine 200 OK,
                    # sesiunea se inchide, si tabloul ramane pe zero fara ca nimic
                    # sa se planga nicaieri. Asa a stat ascuns pana la plicul 28.
                    logging.getLogger(__name__).warning(
                        "end_session: evaluation JSON block missing from summary "
                        f"(session={session_id}, summary_len={len(summary_text or '')}). "
                        "No scores, insight moment or memory were persisted."
                    )

            except Exception as err:
                logging.getLogger(__name__).warning(f"Failed to generate session summary: {err}")

        # A DOUA chemare, portata la plicul 29 din app/api/evaluate/route.ts.
        # Aplicatia veche facea doua chemari la oprirea sesiunii, nu una: rezumatul
        # de mai sus (cele patru axe) SI evaluarea structurala de aici, care da
        # scoruri pe competentele PROIECTULUI, mostrele „asa ai spus / asa ar fi
        # sunat" si recomandarile pentru trainer. A doua nu fusese portata.
        if turns:
            try:
                from codrut.modules.practice.evaluator import (
                    PracticeEvaluator,
                    build_transcript,
                )
                from codrut.modules.practice.setup_service import (
                    competency_names_for_project,
                )

                # PracticeSession nu tine project_id direct; il are prin setarile
                # de program ale proiectului.
                setari = (await self.session.execute(
                    select(PracticeProgramSettings).where(
                        PracticeProgramSettings.id == session_obj.program_settings_id
                    )
                )).scalar_one_or_none()
                proiect_id = setari.project_id if setari else None
                competente = (
                    await competency_names_for_project(self.session, proiect_id)
                    if proiect_id else []
                )
                evaluator = PracticeEvaluator(
                    session=self.session,
                    generation_provider=self.generation_provider,
                    settings=self.settings,
                )
                await evaluator.evaluate_session(
                    session_id=session_id,
                    user_id=profile.user_id or principal.user_id,
                    project_id=proiect_id,
                    competencies=competente,
                    transcript=build_transcript(turns, profile.full_name),
                    source_type=session_obj.kind.value,
                )
            except Exception as eval_err:
                logging.getLogger(__name__).warning(
                    f"Structural evaluation failed in end_session: {eval_err}"
                )

        if session_obj.state != SessionState.closed:
            session_obj.state = SessionState.closed
            session_obj.ended_at = datetime.now(UTC)
            outcome = PracticeOutcome(
                session_id=session_id,
                kind=outcome_kind,
                note=note or (summary_text[:500] if summary_text else None),
            )
            self.session.add(outcome)
            await self.session.flush()

        return session_obj, summary_text

    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/webm",
    ) -> tuple[str, Decimal]:
        """Transcribe an audio recording and return text and estimated cost."""
        text, usage, cost_usd = await self.generation_provider.transcribe_audio(
            audio_bytes=audio_bytes,
            mime_type=mime_type,
        )
        return text, cost_usd

    async def get_stare_summary(self) -> dict[str, Any]:
        """Summary for the /stare dashboard."""
        from codrut.contracts.generation import TokenUsage
        from codrut.modules.practice.pricing import estimate_cost
        from codrut.modules.practice.prompts import CODY_PROMPT_VERSION, get_core_material

        _, material_bytes = get_core_material(self.settings.biblioteca_path)
        now = datetime.now(UTC)
        today_start = datetime(now.year, now.month, now.day, tzinfo=UTC)

        stmt_sess = select(func.count(PracticeSession.id)).where(PracticeSession.started_at >= today_start)
        sessions_today = (await self.session.execute(stmt_sess)).scalar_one() or 0

        stmt_turns = select(func.count(PracticeTurn.id)).where(PracticeTurn.created_at >= today_start)
        turns_today = (await self.session.execute(stmt_turns)).scalar_one() or 0

        stmt_cached_turns = select(func.count(PracticeTurn.id)).where(
            PracticeTurn.created_at >= today_start,
            PracticeTurn.cached_tokens > 0,
        )
        cached_turns = (await self.session.execute(stmt_cached_turns)).scalar_one() or 0

        # Cost exact calculation from usageMetadata on PracticeTurn
        stmt_turns_data = select(
            func.sum(PracticeTurn.prompt_tokens),
            func.sum(PracticeTurn.cached_tokens),
            func.sum(PracticeTurn.output_tokens),
            func.sum(PracticeTurn.thought_tokens),
        ).where(PracticeTurn.created_at >= today_start)
        row = (await self.session.execute(stmt_turns_data)).one()
        prompt_t = row[0] or 0
        cached_t = row[1] or 0
        output_t = row[2] or 0
        thought_t = row[3] or 0

        cache_percent = float(round((Decimal(cached_t) / Decimal(prompt_t) * 100), 1)) if prompt_t > 0 else 0.0

        usage_today = TokenUsage(
            prompt_tokens=prompt_t,
            cached_tokens=cached_t,
            output_tokens=output_t,
            thought_tokens=thought_t,
        )
        cost_usd = estimate_cost(usage_today, self.settings, model=self.settings.vertex_actor_model)

        return {
            "status": "normal",
            "status_text": "Sistemul funcționează normal",
            "prompt_version": CODY_PROMPT_VERSION,
            "material_bytes": material_bytes,
            "provider": self.settings.generation_provider,
            "model": self.settings.vertex_actor_model,
            "region": self.settings.vertex_region,
            "sessions_today": sessions_today,
            "turns_today": turns_today,
            "cached_turns": cached_turns,
            "cache_percent": cache_percent,
            "cost_today_usd": float(round(cost_usd, 6)),
            "last_error": None,
        }

