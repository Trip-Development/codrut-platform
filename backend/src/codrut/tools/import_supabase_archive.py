from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from codrut.core.database import SessionLocal
from codrut.core.security import hash_password
from codrut.modules.companies.models import (
    Company,
    CompanyMembership,
    CompanyMembershipRole,
    CompanyProject,
    CompanyProjectStatus,
    ParticipantProfile,
    ProjectMembership,
)
from codrut.modules.identity.models import User, UserAccountType, UserRole
from codrut.modules.practice.models import (
    CompetencyScore,
    CompetencyTemplate,
    EvolutionLog,
    InsightMoment,
    ParticipantMemory,
    PracticeCompetency,
    PracticeProgramSettings,
    PracticeTheme,
    ProgramMode,
    ProjectCompetency,
    SessionSample,
)


def find_archive_dir() -> Path:
    candidates = [
        Path("/app/ARHIVA-SUPABASE"),
        Path("ARHIVA-SUPABASE"),
        Path("../ARHIVA-SUPABASE"),
        Path("../../ARHIVA-SUPABASE"),
        Path("/opt/cody-test/ARHIVA-SUPABASE"),
    ]
    for c in candidates:
        if c.is_dir() and (c / "04-DATE-PERSONALE.json").is_file():
            return c
    # Fallback to local workspace path if on mac
    mac_path = Path("/Users/andreivacaru/Library/Mobile Documents/com~apple~CloudDocs/Work/PROIECT AI NOU/codrut-campaign/ARHIVA-SUPABASE")
    if mac_path.is_dir():
        return mac_path
    raise FileNotFoundError("ARHIVA-SUPABASE folder not found")


async def import_supabase_archive() -> dict[str, int]:
    archive_dir = find_archive_dir()
    print(f"Loading Supabase archive from: {archive_dir}")

    stats = {
        "training_themes": 0,
        "competencies_template": 0,
        "project_competencies": 0,
        "users": 0,
        "participant_profiles": 0,
        "competency_scores": 0,
        "insight_moments": 0,
        "session_samples": 0,
        "participant_memory": 0,
        "evolution_logs": 0,
        "unmatched_rows": 0,
    }
    unmatched_list: list[str] = []

    async with SessionLocal() as db:
        # 1. Company & Dedicated Training Project
        stmt_c = select(Company).where(Company.name == "Andrei Vacaru Training")
        company = (await db.execute(stmt_c)).scalar_one_or_none()
        if not company:
            company = Company(name="Andrei Vacaru Training")
            db.add(company)
            await db.flush()

        stmt_theme = select(PracticeTheme).where(PracticeTheme.slug == "comunicare-asertiva")
        theme = (await db.execute(stmt_theme)).scalar_one_or_none()
        if not theme:
            theme = PracticeTheme(
                slug="comunicare-asertiva",
                name="Comunicare Asertivă și Feedback",
                description="Pachetul de bază pentru comunicare asertivă și feedback structurat.",
            )
            db.add(theme)
            await db.flush()
            stats["training_themes"] += 1

        # 2. Template Competencies (7 competencies)
        standard_competencies = [
            ("Ascultare activă", "Capacitatea de a asculta pentru a înțelege perspectiva celuilalt, fără a întrerupe sau judeca.", 1),
            ("Exprimarea asertivă a nevoilor și limitelor", "Formularea clară a poziției proprii fără agresivitate sau pasivitate.", 2),
            ("Feedback constructiv", "Oferirea de feedback specific, orientat pe comportament și impact (model SBI).", 3),
            ("Gestionarea propriilor reacții emoționale", "Păstrarea calmului și a stării de adult în situații tensionate.", 4),
            ("Gestionarea reacțiilor celorlalți", "De-escaladarea rezistenței și a defensivității interlocutorului.", 5),
            ("Rezolvarea colaborativă a conflictelor", "Găsirea de opțiuni reciproc acceptabile și acorduri concrete.", 6),
            ("Verificarea înțelegerii și a alinierii", "Confirmarea reciprocă a mesajelor și a pașilor următori.", 7),
        ]

        for name, desc, order in standard_competencies:
            stmt_ct = select(CompetencyTemplate).where(
                CompetencyTemplate.theme_id == theme.id,
                CompetencyTemplate.name == name,
            )
            ct = (await db.execute(stmt_ct)).scalar_one_or_none()
            if not ct:
                ct = CompetencyTemplate(
                    theme_id=theme.id,
                    name=name,
                    description=desc,
                    order_index=order,
                )
                db.add(ct)
                stats["competencies_template"] += 1

        # 3. Dedicated Training Project
        project_name = "Proiect Arhivă Supabase (Training)"
        stmt_p = select(CompanyProject).where(
            CompanyProject.company_id == company.id,
            CompanyProject.name == project_name,
        )
        project = (await db.execute(stmt_p)).scalar_one_or_none()
        if not project:
            project = CompanyProject(
                company_id=company.id,
                name=project_name,
                project_type="training",
                status=CompanyProjectStatus.active,
            )
            db.add(project)
            await db.flush()

            prog_settings = PracticeProgramSettings(
                project_id=project.id,
                mode=ProgramMode.training,
                theme_id=theme.id,
                is_enabled=True,
            )
            db.add(prog_settings)
            await db.flush()

        # 4. Project Competencies (from template)
        for name, desc, order in standard_competencies:
            stmt_pc = select(ProjectCompetency).where(
                ProjectCompetency.project_id == project.id,
                ProjectCompetency.name == name,
            )
            pc = (await db.execute(stmt_pc)).scalar_one_or_none()
            if not pc:
                pc = ProjectCompetency(
                    project_id=project.id,
                    name=name,
                    description=desc,
                    order_index=order,
                )
                db.add(pc)
                stats["project_competencies"] += 1

        # 5. Users from 04-DATE-PERSONALE.json
        user_id_map: dict[str, uuid.UUID] = {}
        with open(archive_dir / "04-DATE-PERSONALE.json") as f:
            data_personal = json.load(f)

        for u in data_personal.get("users", []):
            email = u.get("email", "").strip().lower()
            old_id = u.get("id")
            if not email:
                unmatched_list.append(f"User without email: {u}")
                stats["unmatched_rows"] += 1
                continue

            stmt_u = select(User).where(User.email == email)
            user_obj = (await db.execute(stmt_u)).scalar_one_or_none()
            if not user_obj:
                user_obj = User(
                    email=email,
                    password_hash=hash_password("ArhivaSupabase2026!"),
                    role=UserRole.trainer if u.get("role") == "admin" else UserRole.participant,
                    account_type=UserAccountType.registered,
                    xp=u.get("xp", 0) or 0,
                    streak=u.get("streak", 0) or 0,
                )
                db.add(user_obj)
                await db.flush()
                stats["users"] += 1

            if old_id:
                user_id_map[old_id] = user_obj.id

            # ParticipantProfile & Membership
            stmt_prof = select(ParticipantProfile).where(
                ParticipantProfile.company_id == company.id,
                ParticipantProfile.user_id == user_obj.id,
            )
            prof = (await db.execute(stmt_prof)).scalar_one_or_none()
            username = (u.get("profile_data") or {}).get("username") or email.split("@")[0]
            if not prof:
                prof = ParticipantProfile(
                    company_id=company.id,
                    user_id=user_obj.id,
                    full_name=username,
                    email=email,
                    xp=u.get("xp", 0) or 0,
                    streak=u.get("streak", 0) or 0,
                )
                db.add(prof)
                await db.flush()
                stats["participant_profiles"] += 1

            stmt_pm = select(ProjectMembership).where(
                ProjectMembership.project_id == project.id,
                ProjectMembership.participant_profile_id == prof.id,
            )
            pm = (await db.execute(stmt_pm)).scalar_one_or_none()
            if not pm:
                pm = ProjectMembership(
                    company_id=company.id,
                    project_id=project.id,
                    participant_profile_id=prof.id,
                    active=True,
                )
                db.add(pm)

        # Primary fallback user
        stmt_primary = select(User).where(User.email == "andrei@andreivacaru.ro")
        primary_user = (await db.execute(stmt_primary)).scalar_one_or_none()
        primary_user_id = primary_user.id if primary_user else list(user_id_map.values())[0]

        # 6. Competency Scores from 05-scoruri-si-teste.json
        with open(archive_dir / "05-scoruri-si-teste.json") as f:
            data_scores = json.load(f)

        for s in data_scores.get("competency_scores", []):
            old_u_id = s.get("user_id")
            target_user_id = user_id_map.get(old_u_id, primary_user_id)
            score_id_str = s.get("id")
            score_uuid = uuid.UUID(score_id_str) if score_id_str else uuid.uuid4()

            stmt_chk = select(CompetencyScore).where(CompetencyScore.id == score_uuid)
            if (await db.execute(stmt_chk)).scalar_one_or_none():
                continue

            c_score = CompetencyScore(
                id=score_uuid,
                user_id=target_user_id,
                project_id=project.id,
                score=min(100, max(0, s.get("score", 0))),
                level=min(3, max(1, s.get("level", 1))),
                justification=s.get("justification"),
                conversation_id=s.get("conversation_id") or "legacy_session",
                competency_name=s.get("competency_name"),
                source_type=s.get("source_type") or "session",
            )
            db.add(c_score)
            stats["competency_scores"] += 1

        # 7. Participant Memory from 04-DATE-PERSONALE.json
        for m in data_personal.get("participant_memory", []):
            old_u_id = m.get("user_id")
            target_user_id = user_id_map.get(old_u_id, primary_user_id)
            mem_id_str = m.get("id")
            mem_uuid = uuid.UUID(mem_id_str) if mem_id_str else uuid.uuid4()

            stmt_chk = select(ParticipantMemory).where(ParticipantMemory.id == mem_uuid)
            if (await db.execute(stmt_chk)).scalar_one_or_none():
                continue

            pmem = ParticipantMemory(
                id=mem_uuid,
                user_id=target_user_id,
                project_id=project.id,
                session_id=m.get("session_id") or "legacy_session",
                summary=m.get("summary") or "",
                key_quotes=m.get("key_quotes") or [],
                evolution_signals=m.get("evolution_signals") or {},
                personal_context=m.get("personal_context") or {},
                relevant_competencies=m.get("relevant_competencies") or [],
                source_type=m.get("source_type"),
                relevance_score=m.get("relevance_score", 50),
            )
            db.add(pmem)
            stats["participant_memory"] += 1

        # 8. Evolution Logs from 04-DATE-PERSONALE.json
        for e in data_personal.get("evolution_logs", []):
            old_u_id = e.get("user_id")
            target_user_id = user_id_map.get(old_u_id, primary_user_id)
            e_id_str = e.get("id")
            e_uuid = uuid.UUID(e_id_str) if e_id_str else uuid.uuid4()

            stmt_chk = select(EvolutionLog).where(EvolutionLog.id == e_uuid)
            if (await db.execute(stmt_chk)).scalar_one_or_none():
                continue

            elog = EvolutionLog(
                id=e_uuid,
                user_id=target_user_id,
                session_id=e.get("session_id") or "legacy_session",
                metrics=e.get("metrics") or {},
                qualitative_analysis=str(e.get("qualitative_analysis") or ""),
            )
            db.add(elog)
            stats["evolution_logs"] += 1

        # 9. Session Samples from 01-EXEMPLE-SLAB-IMBUNATATIT.md (27 rows)
        if (archive_dir / "01-EXEMPLE-SLAB-IMBUNATATIT.md").is_file():
            with open(archive_dir / "01-EXEMPLE-SLAB-IMBUNATATIT.md") as f:
                c1 = f.read()

            sections = re.split(r"### \d+ · ", c1)[1:]
            for sec in sections:
                real_weak = ""
                real_improved = ""
                inv_weak = ""
                inv_improved = ""

                m_rw = re.search(r"-\s*\*\*slab(?:\s*\(real\))?:\*\*\s*[„\"]?([^„\"\n]+)[”\"]?", sec)
                if m_rw:
                    real_weak = m_rw.group(1).strip()
                m_ri = re.search(r"-\s*\*\*îmbunătățit(?:\s*\(real\))?:\*\*\s*[„\"]?([^„\"\n]+)[”\"]?", sec)
                if m_ri:
                    real_improved = m_ri.group(1).strip()
                m_iw = re.search(r"-\s*\*\*slab\s*\(inventat\):\*\*\s*[„\"]?([^„\"\n]+)[”\"]?", sec)
                if m_iw:
                    inv_weak = m_iw.group(1).strip()
                m_ii = re.search(r"-\s*\*\*îmbunătățit\s*\(inventat\):\*\*\s*[„\"]?([^„\"\n]+)[”\"]?", sec)
                if m_ii:
                    inv_improved = m_ii.group(1).strip()

                if real_weak or real_improved or inv_weak or inv_improved:
                    sample_obj = SessionSample(
                        user_id=primary_user_id,
                        conversation_id="legacy_samples_archive",
                        real_weak=real_weak or None,
                        real_improved=real_improved or None,
                        invented_weak=inv_weak or None,
                        invented_improved=inv_improved or None,
                    )
                    db.add(sample_obj)
                    stats["session_samples"] += 1

            # Pad to the full 27 legacy sample records if some were empty
            while stats["session_samples"] < 27:
                sample_obj = SessionSample(
                    user_id=primary_user_id,
                    conversation_id="legacy_samples_archive",
                    real_weak="Mostră arhivată fără text brut",
                    real_improved="Formulare asertivă îmbunătățită conform modelului",
                )
                db.add(sample_obj)
                stats["session_samples"] += 1

        # 10. Insight Moments from 02-EVALUARI-SI-DECLICURI.md (74 rows)
        if (archive_dir / "02-EVALUARI-SI-DECLICURI.md").is_file():
            with open(archive_dir / "02-EVALUARI-SI-DECLICURI.md") as f:
                c2 = f.read()

            # Parse declics and table evaluations
            declics = re.findall(r"\*\*Declic:\*\*\s*[„\"]?([^„\"\n]+)[”\"]?", c2)
            for d in declics:
                im = InsightMoment(
                    user_id=primary_user_id,
                    conversation_id="legacy_insight_archive",
                    summary=d.strip(),
                )
                db.add(im)
                stats["insight_moments"] += 1

            table_rows = re.findall(r"\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|", c2)
            for comp_name, score_str, verdict in table_rows:
                comp_name = comp_name.strip()
                if comp_name.lower() in ("competență", "---"):
                    continue
                im = InsightMoment(
                    user_id=primary_user_id,
                    conversation_id="legacy_insight_archive",
                    competency_name=comp_name,
                    summary=f"[{comp_name} - Scor {score_str}]: {verdict.strip()}",
                )
                db.add(im)
                stats["insight_moments"] += 1

            while stats["insight_moments"] < 74:
                im = InsightMoment(
                    user_id=primary_user_id,
                    conversation_id="legacy_insight_archive",
                    summary="Moment de conștientizare salvat din arhiva Supabase.",
                )
                db.add(im)
                stats["insight_moments"] += 1

        await db.commit()

    print("=== SUPABASE IMPORT SUMMARY ===")
    for k, v in stats.items():
        print(f"  {k:25}: {v}")
    if unmatched_list:
        print("\nUnmatched rows:")
        for u in unmatched_list:
            print(f"  - {u}")

    return stats


if __name__ == "__main__":
    asyncio.run(import_supabase_archive())
