from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from codrut.contracts.generation import GenerationMessage, GenerationPurpose, GenerationRequest
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
from codrut.modules.practice.generation_provider import build_generation_provider
from codrut.modules.practice.models import (
    OutcomeKind,
    PracticeProgramSettings,
    PracticeTurn,
    ProgramMode,
    SessionKind,
    TurnRole,
)
from codrut.modules.practice.prompts import (
    CODY_PROMPT_VERSION,
    get_core_material,
    get_summary_prompt,
    get_system_prompt_for_kind,
)
from codrut.modules.practice.service import PracticeSessionService
from codrut.tools.seed_practice_test import seed_practice_test


async def run_dialog_probe_v4() -> None:
    settings = get_settings()
    print("=================================================================")
    print("   PLIC 23: PROBĂ DE DIALOG CU CREIERUL COMPLET DIN BIBLIOTECĂ   ")
    print(f"   Provider: {settings.generation_provider} | Regiune: {settings.vertex_region}")
    print(f"   Versiune Prompt: {CODY_PROMPT_VERSION}")
    print("=================================================================\n")

    # 1. Asigurare seed complet
    await seed_practice_test()

    material_text, material_bytes = get_core_material(settings.biblioteca_path)
    print(f"Material încărcat din BIBLIOTECA: {material_bytes:,} octeți.\n")

    async with SessionLocal() as db:
        # Asigurare proiect de tip training
        stmt_proj = (
            select(CompanyProject)
            .where(CompanyProject.name == "Exercitiu Raport Vineri")
            .limit(1)
        )
        project = (await db.execute(stmt_proj)).scalar_one()
        project.project_type = "training"
        await db.flush()

        email = "andrei@andreivacaru.ro"
        stmt_user = select(User).where(User.email == email)
        user = (await db.execute(stmt_user)).scalar_one_or_none()
        if not user:
            user = User(
                email=email,
                password_hash="not-used",
                role=UserRole.participant,
                account_type=UserAccountType.registered,
                terms_version=CURRENT_TERMS_VERSION,
                terms_accepted_at=datetime.now(UTC),
            )
            db.add(user)
            await db.flush()

        stmt_prof = select(ParticipantProfile).where(ParticipantProfile.email == email)
        profile = (await db.execute(stmt_prof)).scalar_one_or_none()
        if not profile:
            profile = ParticipantProfile(
                company_id=project.company_id,
                user_id=user.id,
                full_name="Andrei Vacaru",
                email=email,
            )
            db.add(profile)
            await db.flush()

        stmt_mem = (
            select(ProjectMembership)
            .where(ProjectMembership.project_id == project.id)
            .where(ProjectMembership.participant_profile_id == profile.id)
        )
        membership = (await db.execute(stmt_mem)).scalar_one_or_none()
        if not membership:
            membership = ProjectMembership(
                company_id=project.company_id,
                project_id=project.id,
                participant_profile_id=profile.id,
                active=True,
            )
            db.add(membership)
            await db.flush()

        stmt_settings = select(PracticeProgramSettings).where(
            PracticeProgramSettings.project_id == project.id
        )
        prog_settings = (await db.execute(stmt_settings)).scalar_one_or_none()
        if prog_settings:
            prog_settings.is_enabled = True
            prog_settings.max_turns_per_session = 30
            prog_settings.max_sessions_per_day = 50

        await db.commit()

        principal = SessionPrincipal(
            user_id=user.id,
            email=user.email,
            role=UserRole.participant,
            account_type=UserAccountType.registered,
            access_mode="account",
            terms_version=CURRENT_TERMS_VERSION,
            terms_accepted_at=datetime.now(UTC),
            consent_current=True,
            session_token="probe_v4_session_token_32bytes_ok",
        )

        service = PracticeSessionService(session=db, settings=settings)

        # -------------------------------------------------------------
        # PROBA 4: ROLE-PLAY 8 REPLICI CU PARTICIPANT PROST-INTENȚIONAT
        # -------------------------------------------------------------
        print(">>> ÎNCEPUT PROBA: Role-Play 8 replici cu participant dificil")
        rp_session, _ = await service.start_session(
            principal=principal,
            project_id=project.id,
            kind=SessionKind.roleplay,
        )
        await db.commit()
        print(f"Sesiune Role-Play creată: ID={rp_session.id} (prompt_version={rp_session.prompt_version})\n")

        rp_turns = [
            "Salut Cody, sunt gata să facem o simulare.",
            "Păi nu știu ce vrei de la mine, eu am trimis ce trebuia.",
            "Tu mereu găsești ceva să critici. Dacă nu-ți convine, fă-o tu!",
            "Nu mă interesează regulile tale. Eu lucrez cum vreau eu și nimeni nu s-a plâns până acum.",
            "Bine, dar problema e că tu nu știi să ceri clar ce vrei.",
            "Înțeleg că ești frustrat de întârziere, dar când îmi vorbești pe tonul ăsta nu putem colabora. Hai să stabilim exact ce lipsește din raport.",
            "Propun să ne uităm acum pe secțiunea 3 și să îți predau completările mâine până la ora 14:00. Ești de acord?",
            "Perfect, notez ora 14:00 și îți trimit pe email confirmarea termenului agreat.",
        ]

        for idx, text in enumerate(rp_turns, 1):
            print(f"--- [Role-Play Replica {idx}/8] Participant ---")
            print(text)
            start_t = datetime.now(UTC)
            p_turn, actor_turn, state = await service.submit_turn(
                principal=principal,
                session_id=rp_session.id,
                text=text,
            )
            await db.commit()
            dur = (datetime.now(UTC) - start_t).total_seconds()
            tokens_in = actor_turn.prompt_tokens if actor_turn else 0
            tokens_out = actor_turn.output_tokens if actor_turn else 0
            print(f"\n--- [Role-Play Replica {idx}/8] Cody ({dur:.2f}s | in:{tokens_in} out:{tokens_out}) ---")
            print(actor_turn.text if actor_turn else "[FĂRĂ RĂSPUNS]")
            print("-" * 65 + "\n")

        # -------------------------------------------------------------
        # PROBA 5: OPRIREA SESIUNII ȘI RĂSPUNSUL ÎNTREG CU JSON
        # -------------------------------------------------------------
        print(">>> ÎNCEPUT PROBA 5: Oprirea sesiunii și generare rezumat / scoring")
        closed_session, summary_text = await service.end_session(
            principal=principal,
            session_id=rp_session.id,
            outcome_kind=OutcomeKind.good,
            note="Proba de audit completă",
        )
        await db.commit()
        print("\n--- RĂSPUNSUL COMPLET DE SUMAR ȘI SCORING JSON ---")
        print(summary_text or "[FĂRĂ SUMAR]")
        print("=" * 65 + "\n")

        # -------------------------------------------------------------
        # PROBA 9: TESTARE COMPARATIVĂ PE CELE 4 MODELE GEMINI
        # -------------------------------------------------------------
        models_to_test = [
            "gemini-2.5-flash",
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite",
            "gemini-3-flash",
            "gemini-3.6-flash",
        ]
        print(">>> ÎNCEPUT PROBA 9: Testare comparativă modele Gemini pe Vertex AI")

        test_history_turns = [
            ("user", "Salut Cody, sunt gata să facem o simulare."),
            ("model", "Bună Andrei! Mă bucur să te aud. Cum îți merge ziua până acum?"),
            ("user", "Păi nu știu ce vrei de la mine, eu am trimis ce trebuia."),
        ]

        actor_sys_prompt = get_system_prompt_for_kind(
            kind="roleplay",
            name="Andrei",
            history_length=3,
            biblioteca_path=settings.biblioteca_path,
        )

        for mod in models_to_test:
            print(f"\n[Testare Model: {mod} | Regiune: {settings.vertex_region}]")
            from codrut.core.config import Settings
            override_settings = Settings(
                vertex_actor_model=mod,
                vertex_region=settings.vertex_region,
                generation_provider="vertex" if settings.generation_provider == "vertex" else "local",
            )
            provider = build_generation_provider(override_settings)

            req = GenerationRequest(
                messages=tuple(GenerationMessage(role=r, text=t) for r, t in test_history_turns),
                system_instruction=actor_sys_prompt,
                purpose=GenerationPurpose.actor,
                max_output_tokens=settings.vertex_max_output_tokens,
                temperature=0.7,
            )
            start_m = datetime.now(UTC)
            try:
                res = await provider.generate(req)
                dur_m = (datetime.now(UTC) - start_m).total_seconds()
                cost = (Decimal(res.usage.prompt_tokens) * Decimal("0.30") / Decimal(1_000_000)) + (
                    Decimal(res.usage.output_tokens) * Decimal("2.50") / Decimal(1_000_000)
                )
                print(f"  Status: SUCCES ({dur_m:.2f}s)")
                print(f"  Prompt tokens: {res.usage.prompt_tokens} | Output tokens: {res.usage.output_tokens}")
                print(f"  Cost estimat replică: ${float(cost):.6f}")
                print(f"  Text replica: {res.text[:150]}...")
            except Exception as e:
                dur_m = (datetime.now(UTC) - start_m).total_seconds()
                print(f"  Status: EȘUAT / NESUPORTAT în {settings.vertex_region} ({dur_m:.2f}s)")
                print(f"  Eroare: {e}")

    print("\n=================================================================")
    print("              TOATE PROBELE AU FOST FINALIZATE                   ")
    print("=================================================================")


if __name__ == "__main__":
    asyncio.run(run_dialog_probe_v4())
