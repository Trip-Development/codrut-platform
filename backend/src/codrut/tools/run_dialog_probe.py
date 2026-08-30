from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

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
    PracticeKnowledgePack,
    PracticeProgramSettings,
    PracticeScenario,
    PracticeTheme,
    ProgramMode,
    SessionKind,
)
from codrut.modules.practice.service import PracticeSessionService


async def run_dialog_probe() -> None:
    settings = get_settings()
    print("=================================================================")
    print("   PROBĂ DE DIALOG PRIN RUTELE ADEVĂRATE ALE APLICAȚIEI CODRUȚ   ")
    print(f"   Provider: {settings.generation_provider} | Regiune Vertex: {settings.vertex_region}")
    print("=================================================================\n")

    async with SessionLocal() as db:
        # 1. Obținere sau creare companie & proiect de test
        stmt_comp = select(Company).limit(1)
        company = (await db.execute(stmt_comp)).scalar_one_or_none()
        if not company:
            company = Company(name="Companie Proba Cody")
            db.add(company)
            await db.flush()

        stmt_proj = select(CompanyProject).where(CompanyProject.company_id == company.id).limit(1)
        project = (await db.execute(stmt_proj)).scalar_one_or_none()
        if not project:
            project = CompanyProject(
                company_id=company.id,
                name="Proiect Proba Cody",
                status=CompanyProjectStatus.active,
            )
            db.add(project)
            await db.flush()

        # 2. Obținere sau creare utilizator & profil participant
        email = "proba.participant@andreivacaru.ro"
        stmt_user = select(User).where(User.email == email)
        user = (await db.execute(stmt_user)).scalar_one_or_none()
        if not user:
            user = User(
                email=email,
                name="Participant Proba",
                password_hash="not-used",
                role=UserRole.participant,
                account_type=UserAccountType.user,
                accepted_terms_version=CURRENT_TERMS_VERSION,
            )
            db.add(user)
            await db.flush()

        stmt_prof = select(ParticipantProfile).where(ParticipantProfile.email == email)
        profile = (await db.execute(stmt_prof)).scalar_one_or_none()
        if not profile:
            profile = ParticipantProfile(
                company_id=company.id,
                user_id=user.id,
                full_name="Participant Proba",
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
                company_id=company.id,
                project_id=project.id,
                participant_profile_id=profile.id,
                active=True,
            )
            db.add(membership)
            await db.flush()

        # 3. Asigurare setări de program pentru practică
        stmt_settings = select(PracticeProgramSettings).where(
            PracticeProgramSettings.project_id == project.id
        )
        prog_settings = (await db.execute(stmt_settings)).scalar_one_or_none()
        if not prog_settings:
            prog_settings = PracticeProgramSettings(
                project_id=project.id,
                is_enabled=True,
                max_turns_per_session=10,
                max_sessions_per_day=50,
                max_chars_per_turn=2000,
            )
            db.add(prog_settings)
            await db.flush()
        else:
            prog_settings.is_enabled = True
            prog_settings.max_turns_per_session = 10
            prog_settings.max_sessions_per_day = 50

        await db.commit()

        principal = SessionPrincipal(
            user_id=user.id,
            email=user.email,
            name=user.name,
            role=UserRole.participant,
            account_type=UserAccountType.user,
            access_mode="session_cookie",
            accepted_terms_version=CURRENT_TERMS_VERSION,
        )

        service = PracticeSessionService(session=db, settings=settings)

        # -------------------------------------------------------------
        # PROBA 1: ROLE-PLAY (6 replici)
        # -------------------------------------------------------------
        print(">>> ÎNCEPUT PROBA 1: Modul Role-Play (6 replici)")
        rp_session = await service.start_session(
            principal=principal,
            project_id=project.id,
            kind=SessionKind.roleplay,
        )
        await db.commit()
        print(f"Sesiune Role-Play creată cu ID: {rp_session.id} (prompt_version={rp_session.prompt_version})\n")

        rp_turns = [
            "Am un coleg care întârzie de trei luni cu partea lui din proiect. De fiecare dată are un motiv. Eu îmi refac planurile în jurul lui și nu i-am spus niciodată nimic direct. Nu vreau să îl pun la zid.",
            "Nu e vorba de scuze, pur și simplu nu am vrut să creez tensiune în echipă când oricum aveam mult de lucru.",
            "Ai dreptate, am evitat discuția crezând că e mai simplu să fac eu. Dar acum mă încarcă prea mult.",
            "Vreau să stabilim un termen clar pentru fiecare etapă și să mă anunțe cu 24h înainte dacă apare un blocaj.",
            "Înțeleg că ai avut urgențe, dar când întârzii fără să anunți, eu trebuie să stau peste program ca să acopăr livrabilele.",
            "De luni vreau să avem un check-in de 5 minute dimineața ca să fim aliniați pe priorități.",
        ]

        for idx, text in enumerate(rp_turns, 1):
            print(f"--- [Role-Play Replica {idx}/6] Participant ---")
            print(text)
            start_t = datetime.now(UTC)
            p_turn, actor_turn, state = await service.submit_turn(
                principal=principal,
                session_id=rp_session.id,
                text=text,
            )
            await db.commit()
            dur = (datetime.now(UTC) - start_t).total_seconds()
            print(f"\n--- [Role-Play Replica {idx}/6] Cody ({dur:.2f}s) ---")
            print(actor_turn.text if actor_turn else "[FĂRĂ RĂSPUNS]")
            print("-" * 65 + "\n")

        # -------------------------------------------------------------
        # PROBA 2: STRATEGIE (4 replici)
        # -------------------------------------------------------------
        print("\n>>> ÎNCEPUT PROBA 2: Modul Strategie (4 replici)")
        strat_session = await service.start_session(
            principal=principal,
            project_id=project.id,
            kind=SessionKind.coaching,
        )
        await db.commit()
        print(f"Sesiune Strategie creată cu ID: {strat_session.id} (prompt_version={strat_session.prompt_version})\n")

        strat_turns = [
            "Vreau să îi spun unuia din echipă să fie mai implicat. Am tot amânat. Cum îi zic fără să îl demotivez?",
            "Păi nu vine la timp la ședințe și când vine, stă pe telefon și nu propune nicio idee.",
            "I-am zis data trecută «hai să fim mai activi», dar n-a schimbat nimic.",
            "O să îi spun concret că la ședința de analiză am nevoie de 2 propuneri scrise de la el cu o oră înainte.",
        ]

        for idx, text in enumerate(strat_turns, 1):
            print(f"--- [Strategie Replica {idx}/4] Participant ---")
            print(text)
            start_t = datetime.now(UTC)
            p_turn, actor_turn, state = await service.submit_turn(
                principal=principal,
                session_id=strat_session.id,
                text=text,
            )
            await db.commit()
            dur = (datetime.now(UTC) - start_t).total_seconds()
            print(f"\n--- [Strategie Replica {idx}/4] Cody ({dur:.2f}s) ---")
            print(actor_turn.text if actor_turn else "[FĂRĂ RĂSPUNS]")
            print("-" * 65 + "\n")

    print("=================================================================")
    print("              TOATE PROBELE AU FOST FINALIZATE                   ")
    print("=================================================================")


if __name__ == "__main__":
    asyncio.run(run_dialog_probe())
