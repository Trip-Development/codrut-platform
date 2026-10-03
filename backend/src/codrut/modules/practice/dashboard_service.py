from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.companies.models import CompanyProject, ParticipantProfile
from codrut.modules.identity.models import User
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.practice.competency_aliases import (
    CANONICAL_COMPETENCIES,
    _strip_accents,
    match_comp,
    normalize_competency_name,
)
from codrut.modules.practice.evaluator import TRAINER_PREFIX
from codrut.modules.practice.interlocutor import intrarile_de_punctaj
from codrut.modules.practice.models import (
    CompetencyScore,
    InsightMoment,
    PracticeProgramSettings,
    PracticeSession,
    ProjectCompetency,
    SessionSample,
)
from codrut.modules.practice.scoring import (
    ZONA_ROMANIEI,
    ScoreEntry,
    compute_competency_evidence,
    compute_daily_xp,
    compute_streak,
    evidence_ceiling,
    streak_bonus_pct,
    ziua_in_romania,
)

# Textele lui Andrei, copiate ca atare — plicul 98. Cel pentru omul neinscris e cel de la
# plicul 78 (participants/service.py); cel pentru omul inscris care n-a exersat e din 19 sept.
NEEXERSAT_TITLU = "Încă nu ai exersat."
NEEXERSAT_DESCRIERE = (
    "După prima sesiune vei vedea aici cum cresc competențele tale în funcție de cât și cum "
    "ai exersat."
)




def _cheie(nume: str) -> str:
    """Numele unei competente, normalizat: litere mici, fara diacritice si punctuatie, fara spatii
    in plus — plicul 143. „rezolvarea  colaborativa" si „Rezolvarea colaborativă" sunt aceeasi."""
    return _strip_accents(normalize_competency_name(nume or ""))

class PracticeDashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _competentele_proiectului(self, project_id: uuid.UUID | None) -> list[str]:
        """Competentele alese de trainer pe proiect, in ordinea lui — plicul 143."""
        if project_id is None:
            return []
        return list((await self.session.execute(
            select(ProjectCompetency.name)
            .where(ProjectCompetency.project_id == project_id)
            .order_by(ProjectCompetency.order_index, ProjectCompetency.name)
        )).scalars().all())

    async def get_participant_dashboard_data(
        self,
        principal: SessionPrincipal,
        project_id: uuid.UUID | None = None,
        fara_sedinta: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Aggregate all participant metrics, competency evidence, moments, and samples for the dashboard."""  # noqa: E501
        # `fara_sedinta` — plicul 177: Tabloul fără notele acelei ședințe („+N puncte”).
        # 1. Resolve participant profile
        #
        # Aceeasi forma ca la plicul 30, pe drumul participantului — plicul 73. Aici ramasese
        # forma veche: dupa cont SAU adresa, fara companie, `scalar_one_or_none`, deci un om cu
        # profil in doua companii dadea MultipleResultsFound si tabloul crapa cu 500.
        #
        # Cand vine un proiect, cautam in compania lui. Cand nu vine, n-avem companie de care sa
        # ne legam: alegem determinist — profilul legat de cont inaintea celui doar cu adresa,
        # iar intre egali cel mai vechi — in loc sa crapam.
        stmt_prof = select(ParticipantProfile).where(
            or_(
                ParticipantProfile.user_id == principal.user_id,
                # plicul 79: dupa adresa, doar profilurile NELEGATE — ca la plicul 75
                and_(
                    ParticipantProfile.user_id.is_(None),
                    ParticipantProfile.email == principal.email,
                ),
            )
        )
        if project_id is not None:
            companie = (await self.session.execute(
                select(CompanyProject.company_id).where(CompanyProject.id == project_id)
            )).scalar_one_or_none()
            if companie is not None:
                stmt_prof = stmt_prof.where(ParticipantProfile.company_id == companie)
        stmt_prof = stmt_prof.order_by(
            ParticipantProfile.user_id.is_(None), ParticipantProfile.created_at
        )
        profile = (await self.session.execute(stmt_prof)).scalars().first()

        # Contul dupa id SAU adresa — plicul 73. N-are companie de care sa se lege; primeste
        # doar ordonare ferma si primul rand: intai contul cu id-ul exact, apoi cel mai vechi.
        stmt_u = (
            select(User)
            .where(
                or_(
                    User.id == principal.user_id,
                    User.email == principal.email,
                )
            )
            .order_by((User.id != principal.user_id), User.created_at)
        )
        user_obj = (await self.session.execute(stmt_u)).scalars().first()

        user_ids = [principal.user_id]
        if profile and profile.user_id and profile.user_id not in user_ids:
            user_ids.append(profile.user_id)
        if user_obj and user_obj.id not in user_ids:
            user_ids.append(user_obj.id)

        # 2. XP-ul vechi (neafișat de la plicul 165). `streak` nu se mai citește — plicul 166, C.
        total_xp = 0
        if profile:
            total_xp = profile.xp or 0
        elif user_obj:
            total_xp = user_obj.xp or 0

        # 3. Notele omului — NUMAI din proiectul deschis (plicul 184; Andrei, 30 sept:
        # „pe proiect”). Fără proiect deschis: numai notele care nu țin de niciun proiect.
        # Filtrul stă aici, înaintea oricărei socoteli: puncte, serie, nota de azi, textul
        # de gol și „+N” vin din același cuprins.
        stmt_scores = (
            select(CompetencyScore)
            .where(CompetencyScore.user_id.in_(user_ids))
            .where(
                CompetencyScore.project_id == project_id
                if project_id is not None
                else CompetencyScore.project_id.is_(None)
            )
            .order_by(CompetencyScore.created_at.desc())
        )
        all_scores = list((await self.session.execute(stmt_scores)).scalars().all())
        if fara_sedinta is not None:
            all_scores = [s for s in all_scores if s.conversation_id != str(fara_sedinta)]

        # Plicul 93: aici era o rezerva „daca omul n-are note, ia ultimele 150 din toata baza",
        # pusa pentru previzualizarea locala. Cine n-are note e fiecare om la prima intrare, deci
        # primul lui tablou era facut din notele altora. Fara note, tabloul ramane gol — ca la
        # momente si mostre, unde aceeasi rezerva a fost scoasa la plicul 29.

        # 4. Seria de zile — plicul 166, C: NUMAI zilele consecutive cu note, în ora României.
        #
        # Până acum era maximul dintre ele și `profile.streak`, un contor vechi care crește la
        # fiecare ședință ÎNCHISĂ, nu la fiecare zi: la contul C arăta 19, la liderul complet 2 după
        # două ședințe în aceeași zi. Contorul rămâne în bază, neafișat.
        activity_dates = [ziua_in_romania(s.created_at) for s in all_scores]
        effective_streak = compute_streak(
            activity_dates, reference_date=datetime.now(ZONA_ROMANIEI).date()
        )
        bonus_pct = streak_bonus_pct(effective_streak)

        # 5. Today's XP calculation (capped at 100)
        today_date = date.today()
        today_entries = [
            (s.source_type, s.score, s.created_at)
            for s in all_scores
            if s.created_at.date() == today_date
        ]
        xp_today = compute_daily_xp(today_entries)
        if xp_today == 0 and all_scores:
            # For demonstration on archived data, compute XP for the most active recent date
            recent_date = all_scores[0].created_at.date()
            recent_entries = [
                (s.source_type, s.score, s.created_at)
                for s in all_scores
                if s.created_at.date() == recent_date
            ]
            xp_today = compute_daily_xp(recent_entries)

        # 6. Notele, grupate pe competentele PROIECTULUI — plicul 143.
        #
        # Pana la 143 tabloul grupa pe o lista fixa de 7, din aplicatia veche („Reformulare
        # activa", „Verificarea intelegerii"…), nu pe competentele alese de trainer. Masurat la
        # 141: doua competente ale proiectului primeau note si nu apareau deloc, iar doua straine
        # apareau. Acum lista e a proiectului, in ordinea trainerului; nota se potriveste dupa nume
        # normalizat, iar aliasurile vechi raman numai a doua incercare, pentru notele din arhiva —
        # si niciodata nu adauga o competenta care nu e a proiectului.
        #
        # Fara proiect sau fara competente alese: lista fixa de azi, ca sa nu se strice nimic.
        competente = await self._competentele_proiectului(project_id)
        # plicul 165: numai notele role-play-urilor, fiecare cu tipul interlocutorului
        intrari = await intrarile_de_punctaj(self.session, all_scores)
        if competente:
            dupa_nume = {_cheie(n): n for n in competente}
            scores_by_comp: dict[str, list[ScoreEntry]] = {c: [] for c in competente}
            for s in all_scores:
                nume = dupa_nume.get(_cheie(s.competency_name or ""))
                if nume is None:
                    canonic = match_comp(s.competency_name)
                    nume = dupa_nume.get(_cheie(canonic)) if canonic else None
                if nume is None or s.id not in intrari:
                    continue
                scores_by_comp[nume].append(intrari[s.id])
        else:
            competente = list(CANONICAL_COMPETENCIES)
            scores_by_comp = {c: [] for c in CANONICAL_COMPETENCIES}
            for s in all_scores:
                matched_canonical = match_comp(s.competency_name)
                if not matched_canonical or s.id not in intrari:
                    continue
                scores_by_comp[matched_canonical].append(intrari[s.id])

        competency_results = []
        for name in competente:
            entries = scores_by_comp[name]
            ev = compute_competency_evidence(entries)
            competency_results.append({
                "name": name,
                "level": ev.level,
                "level_description": ev.level_description,
                "color": ev.color,
                "total_roleplays": ev.total_roleplays,
                "scores_70_count": ev.scores_70_count,
                "days_span_70": ev.days_span_70,
                "distinct_days_70": ev.distinct_days_70,
                "average_score": ev.average_score,
                "why_not_higher": ev.why_not_higher,
                "points": ev.points,
                "points_today": ev.points_today,
                "interlocutor_types": ev.interlocutor_types,
                "best_score_today": ev.best_score_today,
            })

        # 7. Insight moments
        #
        # DOUA REGULI, amandoua obligatorii:
        #
        # a) Momentele sunt de DOUA feluri. Cele cu prefixul `[TRAINER]` sunt notele
        #    pentru trainer — numele competentei, scorul, analiza — scrise la persoana
        #    a III-a. Ele NU ajung niciodata pe ecranul participantului. Cele fara
        #    prefix sunt ale lui, scrise pentru el, la persoana a II-a.
        #
        # b) NU exista rezerva „daca omul n-are momente, arata-le pe ale altcuiva".
        #    Pana la plicul 29 exista, ca sa se vada ceva pe datele de arhiva; cu date
        #    adevarate si mai multi participanti, ar fi insemnat ca unul citeste
        #    reflectiile altuia. Ecranul gol e raspunsul corect.
        stmt_moments = (
            select(InsightMoment)
            .where(
                InsightMoment.user_id.in_(user_ids),
                not_(InsightMoment.summary.startswith(TRAINER_PREFIX)),
            )
            .order_by(InsightMoment.created_at.desc())
            .limit(10)
        )
        moments = list((await self.session.execute(stmt_moments)).scalars().all())

        # 8. Session samples (real_weak / real_improved)
        #
        # Fara rezerva de la altcineva, din acelasi motiv ca la momente. Pana la plicul 94
        # intrau aici si mostrele fara stapan (`user_id` gol) — replici adevarate ale unui om,
        # pe tabloul oricui. Pe proba erau zero; le poate scrie doar importul arhivei.
        stmt_samples = (
            select(SessionSample)
            .where(SessionSample.user_id.in_(user_ids))
            .order_by(SessionSample.created_at.desc())
            .limit(10)
        )
        samples = list((await self.session.execute(stmt_samples)).scalars().all())

        rezultat = {
            "participant_name": profile.full_name if profile else (principal.email.split("@")[0]),
            "cody_alias": profile.cody_alias if profile else None,
            "xp_today": xp_today,
            "xp_daily_cap": 100,
            "xp_total": total_xp or sum(e.score for e in all_scores),
            "streak_days": effective_streak,
            "streak_bonus_pct": bonus_pct,
            "evidence_ceiling": evidence_ceiling(30),
            # punctajul nou — plicul 165: sume peste competențele arătate, fără plafon
            "points_today": sum(c["points_today"] for c in competency_results),
            "points_total": sum(c["points"] for c in competency_results),
            "competencies": competency_results,
            "insight_moments": [
                {
                    "id": str(m.id),
                    "summary": m.summary,
                    "competency_name": m.competency_name,
                    "created_at": m.created_at.isoformat(),
                }
                for m in moments
            ],
            "session_samples": [
                {
                    "id": str(s.id),
                    "real_weak": s.real_weak,
                    "real_improved": s.real_improved,
                    "invented_weak": s.invented_weak,
                    "invented_improved": s.invented_improved,
                    "created_at": s.created_at.isoformat(),
                }
                for s in samples
                if s.real_weak or s.real_improved or s.invented_weak or s.invented_improved
            ],
        }

        # Omul fara nicio nota afla DE CE e gol tabloul — plicul 98. Sunt doua situatii si un
        # singur text ar minti pe unul dintre ei: neinscris nicaieri, sau inscris dar fara
        # exersare. „Inscris" e definitia de la plicul 78, luata chiar de acolo. Cheia apare
        # numai la omul fara note: la cine are note, raspunsul ramane exact cum era.
        if not all_scores:
            from codrut.modules.participants.service import (
                NEINSCRIS_DESCRIERE,
                NEINSCRIS_TITLU,
                ParticipantWorkspaceService,
            )

            if await ParticipantWorkspaceService(self.session).are_legatura_reala(
                principal.user_id
            ):
                rezultat["empty_state"] = {
                    "kind": "neexersat",
                    "title": NEEXERSAT_TITLU,
                    "description": NEEXERSAT_DESCRIERE,
                }
            else:
                rezultat["empty_state"] = {
                    "kind": "neinscris",
                    "title": NEINSCRIS_TITLU,
                    "description": NEINSCRIS_DESCRIERE,
                }
        return rezultat

    async def puncte_castigate_in_sedinta(
        self,
        principal: SessionPrincipal,
        session_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Cât a crescut Tabloul datorită unei ședințe, pe competență — plicul 177 („+N puncte”).

        Tabloul proiectului ședinței cu notele ei minus același Tablou fără ele: aceeași socoteală
        care face Tabloul, deci „+N” e, prin construcție, exact creșterea pe care omul o vede acolo
        (bonusul de tip nou și „a doua ședință a zilei” incluse). Intră numai competențele cu N > 0.
        """
        proiect = (await self.session.execute(
            select(PracticeProgramSettings.project_id)
            .join(
                PracticeSession,
                PracticeSession.program_settings_id == PracticeProgramSettings.id,
            )
            .where(PracticeSession.id == session_id)
        )).scalar_one_or_none()
        dupa = await self.get_participant_dashboard_data(principal, proiect)
        inainte = await self.get_participant_dashboard_data(
            principal, proiect, fara_sedinta=session_id
        )
        puncte_inainte = {c["name"]: c["points"] for c in inainte["competencies"]}
        castig = []
        for c in dupa["competencies"]:
            n = c["points"] - puncte_inainte.get(c["name"], 0)
            if n > 0:
                castig.append({"competency": c["name"], "points": n})
        return castig
