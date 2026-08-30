from __future__ import annotations

import asyncio
import json
import time
import uuid
from decimal import Decimal

from sqlalchemy import select

from codrut.contracts.generation import GenerationMessage, GenerationPurpose, GenerationRequest, TokenUsage
from codrut.core.config import get_settings
from codrut.core.database import SessionLocal
from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.identity.models import User, UserAccountType, UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from codrut.modules.practice.models import (
    PracticeProgramSettings,
    PracticeTurn,
    ProgramMode,
    SessionKind,
    TurnRole,
)
from codrut.modules.practice.pricing import estimate_cost
from codrut.modules.practice.service import PracticeSessionService
from codrut.tools.seed_practice_test import seed_practice_test


async def run_5turn_cost_probe() -> dict:
    settings = get_settings()
    await seed_practice_test()

    async with SessionLocal() as db:
        stmt_user = select(User).where(User.email == "andrei@andreivacaru.ro")
        user = (await db.execute(stmt_user)).scalar_one()

        stmt_prof = select(ParticipantProfile).where(ParticipantProfile.user_id == user.id)
        prof = (await db.execute(stmt_prof)).scalar_one()

        stmt_proj = select(CompanyProject).where(
            CompanyProject.company_id == prof.company_id,
            CompanyProject.project_type == "training",
        )
        proj = (await db.execute(stmt_proj)).scalars().first()

        principal = SessionPrincipal(
            user_id=user.id,
            email=user.email,
            role=UserRole.participant,
            account_type=UserAccountType.registered,
            terms_accepted_at=user.terms_accepted_at,
            terms_version=user.terms_version or CURRENT_TERMS_VERSION,
        )

        service = PracticeSessionService(session=db, settings=settings)
        session_obj = await service.start_session(
            principal=principal,
            project_id=proj.id,
            kind=SessionKind.roleplay,
        )
        session_id = session_obj.id

    turns_input = [
        "Salut Cody, începem simularea de azi.",
        "Avem o problemă cu predarea raportului săptămânal.",
        "Colegul meu întârzie frecvent cu datele și ne blochează livrarea.",
        "Am încercat să discut calm, dar a devenit defensiv și a ridicat tonul.",
        "Vreau să aplicăm structura SBI ca să ajungem la un acord clar pentru vineri ora 14:00.",
    ]

    turn_results = []
    total_prompt_tokens = 0
    total_cached_tokens = 0
    total_output_tokens = 0
    total_thought_tokens = 0
    total_session_cost = Decimal("0")

    for i, user_text in enumerate(turns_input, start=1):
        async with SessionLocal() as db:
            service = PracticeSessionService(session=db, settings=settings)
            t0 = time.time()
            p_turn, a_turn, state = await service.submit_turn(
                principal=principal,
                session_id=session_id,
                text=user_text,
            )
            dur = time.time() - t0

            # Fetch turn metadata
            stmt_t = (
                select(PracticeTurn)
                .where(PracticeTurn.session_id == session_id, PracticeTurn.role == TurnRole.actor)
                .order_by(PracticeTurn.ordinal.desc())
                .limit(1)
            )
            act_turn = (await db.execute(stmt_t)).scalar_one()

            prompt_tok = act_turn.prompt_tokens or 0
            cached_tok = act_turn.cached_tokens or 0
            out_tok = act_turn.output_tokens or 0
            thought_tok = act_turn.thought_tokens or 0

            usage = TokenUsage(
                prompt_tokens=prompt_tok,
                cached_tokens=cached_tok,
                output_tokens=out_tok,
                thought_tokens=thought_tok,
            )
            turn_cost = estimate_cost(usage, settings, model=settings.vertex_actor_model)

            total_prompt_tokens += prompt_tok
            total_cached_tokens += cached_tok
            total_output_tokens += out_tok
            total_thought_tokens += thought_tok
            total_session_cost += turn_cost

            turn_results.append({
                "turn": i,
                "user_text": user_text,
                "actor_reply": (act_turn.text[:80] + "...") if len(act_turn.text) > 80 else act_turn.text,
                "duration_s": round(dur, 3),
                "prompt_tokens": prompt_tok,
                "cached_tokens": cached_tok,
                "output_tokens": out_tok,
                "thought_tokens": thought_tok,
                "turn_cost_usd": float(turn_cost),
            })

    # End session to run complete closing flow
    async with SessionLocal() as db:
        service = PracticeSessionService(session=db, settings=settings)
        closed_sess, summary_text = await service.end_session(
            principal=principal,
            session_id=session_id,
        )

        stare_summary = await service.get_stare_summary()

    probe_summary = {
        "session_id": str(session_id),
        "model": settings.vertex_actor_model,
        "region": settings.vertex_region,
        "turns": turn_results,
        "total_prompt_tokens": total_prompt_tokens,
        "total_cached_tokens": total_cached_tokens,
        "total_output_tokens": total_output_tokens,
        "total_thought_tokens": total_thought_tokens,
        "total_session_cost_usd": float(round(total_session_cost, 6)),
        "stare_page_cost_today_usd": stare_summary["cost_today_usd"],
        "stare_summary": stare_summary,
        "summary_text": summary_text,
    }

    with open("/tmp/02-session-5turns-cost.json", "w") as f:
        json.dump(probe_summary, f, indent=2, ensure_ascii=False)

    print("=== 5-TURN PROBE COMPLETED ===")
    print(f"Total Session Cost: ${total_session_cost:.6f} USD")
    print(f"Stare Page Cost Today: ${stare_summary['cost_today_usd']:.6f} USD")
    return probe_summary


if __name__ == "__main__":
    asyncio.run(run_5turn_cost_probe())
