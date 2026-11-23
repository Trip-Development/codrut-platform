"""„O replică pe zi”: situația zilei, replica omului și răspunsul profesorului — plicul 236 (L2-P1).

O dată pe zi, omul primește o situație scurtă (din obiectivul lui; fără obiectiv, din toată lista
proiectului), scrie O SINGURĂ replică, iar profesorul de la fiecare replică din jocul de rol îi
răspunde, cu instrucțiunea lui de azi, NESCHIMBATĂ. Nota o citește codul din răspuns.

Totul e al omului, pentru el însuși: nicio funcție de aici nu întoarce replica altcuiva, nimic
nu ajunge la trainer, HR sau șef, nu se scrie nimic în jurnalul serverului, nu se dau puncte pe
Tablou și nu se scrie nicio notă pe competență.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.contracts.generation import (
    GenerationMessage,
    GenerationPurpose,
    GenerationRequest,
)
from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.companies.models import ParticipantProfile, ProjectMembership
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.practice.acord import cere_acordul, profilul_in_proiect
from codrut.modules.practice.alias import codul_omului
from codrut.modules.practice.budget import plafonul_programului, release, reserve, settle
from codrut.modules.practice.generation_provider import GenerationProvider
from codrut.modules.practice.models import (
    PracticeDailyReply,
    PracticeDailySituation,
    PracticeObjective,
    PracticeObjectiveChoice,
    PracticeProgramSettings,
)
from codrut.modules.practice.policies import ensure_participant_may_practice
from codrut.modules.practice.pricing import estimate_pessimistic_cost
from codrut.modules.practice.prompts import (
    _NOTA_DIN_JOC,
    CODY_PROMPT_VERSION,
    cu_incheierea_replicii_zilei,
    get_prompts_pe_meserii,
)
from codrut.modules.practice.quotas import acquire_generation_lock, ensure_turn_length
from codrut.modules.practice.scoring import ziua_in_romania
from codrut.modules.practice.service import SCENA_CELUILALT

# peste pașii de pornire 1–2, deci fără regulile de salut și de confirmare; instrucțiunea
# profesorului e cea de la exersare, neschimbată, plus încheierea zilei la final (plicul 260)
PAS_DE_JOC = 3

# ---- funcțiile pure ----


def alege_situatia[T](candidati: Sequence[T], folosiri: Mapping[Any, int]) -> T | None:
    """Candidatul cu cele mai puține folosiri; la egalitate, primul în ordinea dată.

    Așa nu se repetă nimic până nu se termină lista, apoi se reia de la capăt.
    """
    ales: T | None = None
    minim = 0
    for c in candidati:
        n = folosiri.get(c.id, 0)  # type: ignore[attr-defined]
        if ales is None or n < minim:
            ales, minim = c, n
    return ales


def seria(zile: set[date], azi: date) -> int:
    """Seria iertătoare: o zi ratată pe săptămână ISO nu o rupe; a doua, da."""
    if not zile:
        return 0
    prima = min(zile)
    zi = azi if azi in zile else azi - timedelta(days=1)
    iertate: set[tuple[int, int]] = set()
    n = 0
    while zi >= prima:
        if zi in zile:
            n += 1
        else:
            saptamana = zi.isocalendar()[:2]
            if saptamana in iertate:
                break
            iertate.add(saptamana)
        zi -= timedelta(days=1)
    return n


def nota_din_text(text: str) -> Decimal | None:
    """Nota o citește codul (regula plicurilor 199/226): ultima potrivire, între 0 și 10."""
    potriviri = _NOTA_DIN_JOC.findall(text or "")
    if not potriviri:
        return None
    nota = Decimal(potriviri[-1].replace(",", ".")).quantize(Decimal("0.1"))
    if not Decimal("0") <= nota <= Decimal("10"):
        return None
    return nota


# ---- omul, proiectul, situațiile ----


async def _omul_si_setarile(
    session: AsyncSession, principal: SessionPrincipal, project_id: uuid.UUID
) -> tuple[ParticipantProfile, PracticeProgramSettings]:
    """Aceleași verificări ca la pornirea unei ședințe (`service.py`, `start_session`)."""
    profil = await profilul_in_proiect(session, principal, project_id)
    setari = (await session.execute(
        select(PracticeProgramSettings).where(PracticeProgramSettings.project_id == project_id)
    )).scalar_one_or_none()
    if setari is None:
        raise DomainError(
            f"Practice is not configured for project {project_id}",
            code="practice_not_configured",
        )
    membru = (await session.execute(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.participant_profile_id == profil.id,
        )
    )).scalar_one_or_none()
    ensure_participant_may_practice(
        principal,
        program_enabled=setari.is_enabled,
        membership_active=bool(membru is not None and membru.active),
    )
    await cere_acordul(session, profil.id, project_id)
    return profil, setari


async def _candidatii(
    session: AsyncSession, profil_id: uuid.UUID, project_id: uuid.UUID, catalog: str
) -> tuple[list[tuple[PracticeDailySituation, PracticeObjective]], bool]:
    """Situațiile din obiectivul ales de om; fără alegere, toate situațiile listei."""
    obiectiv_ales = (await session.execute(
        select(PracticeObjective)
        .join(PracticeObjectiveChoice, PracticeObjectiveChoice.objective_id == PracticeObjective.id)
        .where(
            PracticeObjectiveChoice.participant_profile_id == profil_id,
            PracticeObjectiveChoice.project_id == project_id,
            PracticeObjectiveChoice.replaced_at.is_(None),
            PracticeObjective.catalog == catalog,
            PracticeObjective.is_active.is_(True),
        )
    )).scalar_one_or_none()
    interogare = (
        select(PracticeDailySituation, PracticeObjective)
        .join(PracticeObjective, PracticeObjective.id == PracticeDailySituation.objective_id)
        .where(
            PracticeDailySituation.is_active.is_(True),
            PracticeObjective.is_active.is_(True),
            PracticeObjective.catalog == catalog,
        )
    )
    if obiectiv_ales is not None:
        randuri = (await session.execute(
            interogare.where(PracticeObjective.id == obiectiv_ales.id)
            .order_by(PracticeDailySituation.order_index)
        )).all()
        return [tuple(r) for r in randuri], True
    randuri = (await session.execute(
        interogare.order_by(PracticeDailySituation.order_index, PracticeObjective.order_index)
    )).all()
    return [tuple(r) for r in randuri], False


async def _folosirile(
    session: AsyncSession, profil_id: uuid.UUID, project_id: uuid.UUID
) -> dict[uuid.UUID, int]:
    randuri = (await session.execute(
        select(PracticeDailyReply.situation_id, func.count(PracticeDailyReply.id))
        .where(
            PracticeDailyReply.participant_profile_id == profil_id,
            PracticeDailyReply.project_id == project_id,
        )
        .group_by(PracticeDailyReply.situation_id)
    )).all()
    return {sid: n for sid, n in randuri}


async def _replica_din_ziua(
    session: AsyncSession, profil_id: uuid.UUID, project_id: uuid.UUID, zi: date
) -> PracticeDailyReply | None:
    return (await session.execute(
        select(PracticeDailyReply).where(
            PracticeDailyReply.participant_profile_id == profil_id,
            PracticeDailyReply.project_id == project_id,
            PracticeDailyReply.day == zi,
        )
    )).scalar_one_or_none()


async def _zilele(
    session: AsyncSession, profil_id: uuid.UUID, project_id: uuid.UUID
) -> set[date]:
    return set((await session.execute(
        select(PracticeDailyReply.day).where(
            PracticeDailyReply.participant_profile_id == profil_id,
            PracticeDailyReply.project_id == project_id,
        )
    )).scalars().all())


def _situatia(s: PracticeDailySituation, o: PracticeObjective) -> dict:
    return {"id": s.id, "text": s.text, "obiectiv_nr": o.order_index, "obiectiv_titlu": o.title}


def _azi(r: PracticeDailyReply) -> dict:
    return {
        "situatie_id": r.situation_id,
        "replica": r.reply_text,
        "raspuns": r.teacher_text,
        "nota": float(r.score) if r.score is not None else None,
        "trimisa_la": r.created_at,
    }


async def _situatia_zilei(
    session: AsyncSession,
    profil_id: uuid.UUID,
    project_id: uuid.UUID,
    setari: PracticeProgramSettings,
    replica_de_azi: PracticeDailyReply | None,
) -> tuple[tuple[PracticeDailySituation, PracticeObjective] | None, str | None, bool]:
    """(situația zilei, motivul când lipsește, dacă e din obiectivul omului)."""
    catalog = setari.objective_catalog
    if not catalog:
        return None, "fara_obiective", False
    candidati, din_obiectiv = await _candidatii(session, profil_id, project_id, catalog)
    if replica_de_azi is not None:
        # situația de azi e cea a replicii (nu se recalculează)
        s = await session.get(PracticeDailySituation, replica_de_azi.situation_id)
        o = await session.get(PracticeObjective, s.objective_id) if s is not None else None
        if s is not None and o is not None:
            return (s, o), None, din_obiectiv
    if not candidati:
        return None, "fara_situatii", din_obiectiv
    folosiri = await _folosirile(session, profil_id, project_id)
    ales = alege_situatia(
        [_Candidat(s, o) for s, o in candidati], folosiri
    )
    assert ales is not None
    return (ales.situatie, ales.obiectiv), None, din_obiectiv


class _Candidat:
    __slots__ = ("id", "obiectiv", "situatie")

    def __init__(self, situatie: PracticeDailySituation, obiectiv: PracticeObjective) -> None:
        self.id = situatie.id
        self.situatie = situatie
        self.obiectiv = obiectiv


async def _starea(
    session: AsyncSession,
    profil_id: uuid.UUID,
    project_id: uuid.UUID,
    setari: PracticeProgramSettings,
    azi: date,
) -> dict:
    replica = await _replica_din_ziua(session, profil_id, project_id, azi)
    perechea, motiv, din_obiectiv = await _situatia_zilei(
        session, profil_id, project_id, setari, replica
    )
    return {
        "situatie": _situatia(*perechea) if perechea is not None else None,
        "motiv": motiv,
        "din_obiectivul_meu": din_obiectiv,
        "azi": _azi(replica) if replica is not None else None,
        "serie": seria(await _zilele(session, profil_id, project_id), azi),
    }


async def starea_zilei(
    session: AsyncSession,
    principal: SessionPrincipal,
    project_id: uuid.UUID,
    *,
    acum: datetime,
) -> dict:
    """Situația zilei pentru om, replica lui de azi (dacă există) și seria."""
    profil, setari = await _omul_si_setarile(session, principal, project_id)
    return await _starea(session, profil.id, project_id, setari, ziua_in_romania(acum))


# ---- replica ----


async def trimite_replica(
    session: AsyncSession,
    principal: SessionPrincipal,
    project_id: uuid.UUID,
    situation_id: uuid.UUID,
    text: str,
    *,
    profesor: GenerationProvider,
    settings: Settings,
    redis: Redis,
    acum: datetime,
) -> dict:
    """Omul trimite replica zilei; profesorul de azi îi răspunde, o singură încercare."""
    # 1. omul
    profil, setari = await _omul_si_setarile(session, principal, project_id)
    profil_id, setari_id = profil.id, setari.id

    # 2. o singură replică pe zi
    azi = ziua_in_romania(acum)
    if await _replica_din_ziua(session, profil_id, project_id, azi) is not None:
        raise DomainError("Ai trimis deja replica de azi.", code="replica_zilei_facuta")

    # 3. situația zilei
    perechea, _, _ = await _situatia_zilei(session, profil_id, project_id, setari, None)
    if perechea is None:
        raise DomainError(
            "Pe acest proiect nu există încă replica zilei.",
            code="replica_zilei_indisponibila",
        )
    situatie, _obiectiv = perechea
    if situatie.id != situation_id:
        raise DomainError(
            "Situația de azi s-a schimbat. Reîncarcă pagina.", code="situatia_alta"
        )
    situatie_text = situatie.text

    # 4. replica
    if not (text or "").strip():
        raise DomainError("Scrie replica ta înainte să trimiți.", code="replica_goala")
    ensure_turn_length(text, setari.max_chars_per_turn)

    # 5. același lacăt ca la ședințe: omul nu poate trimite în paralel din două ferestre
    async with acquire_generation_lock(
        redis, profil_id, timeout_seconds=settings.vertex_timeout_evaluator_replica_seconds + 10
    ):
        # 6. cererea
        cod = await codul_omului(session, profil)
        _, instructiunea = get_prompts_pe_meserii(
            name=cod,
            history_length=PAS_DE_JOC,
            memories=None,
            biblioteca_path=settings.biblioteca_path,
            profil_rol=None,
        )
        instructiunea = cu_incheierea_replicii_zilei(instructiunea)  # plicul 260
        cerere = GenerationRequest(
            messages=(
                GenerationMessage(
                    role="user", text=f"{SCENA_CELUILALT}\n{situatie_text}\n\n{text}"
                ),
            ),
            system_instruction=instructiunea,
            purpose=GenerationPurpose.evaluator,
            max_output_tokens=settings.vertex_max_output_tokens_evaluator,
            temperature=0.2,
            thinking_budget=settings.thinking_budget_evaluator,
        )

        # 7. bugetul, ca la evaluatorul de la fiecare replică
        cuvinte = sum(len(m.text.split()) for m in cerere.messages)
        cuvinte += len(instructiunea.split())
        estimare = estimate_pessimistic_cost(
            prompt_tokens=max(1, cuvinte),
            max_output_tokens=settings.vertex_max_output_tokens_evaluator,
            thinking_budget=settings.thinking_budget_evaluator,
            settings=settings,
        )
        retentie = setari.turn_retention_days
        rezervare = await reserve(
            session,
            program_settings_id=setari_id,
            estimated_usd=estimare,
            cap_usd=await plafonul_programului(session, setari),
            session_id=None,
            participant_profile_id=profil_id,
        )
        await session.commit()

        # 8. apelul: o singură încercare
        try:
            rezultat = await asyncio.wait_for(
                profesor.generate(cerere),
                timeout=settings.vertex_timeout_evaluator_replica_seconds,
            )
        except TimeoutError:
            # apelul anulat la noi tot se plătește (lecția 101/210)
            await settle(session, rezervare, actual_usd=estimare)
            await session.commit()
            raise DomainError(
                "Cody nu poate răspunde acum. Replica ta nu s-a salvat; încearcă din nou.",
                code="profesor_indisponibil",
            ) from None
        except Exception:
            await release(session, rezervare)
            await session.commit()
            raise DomainError(
                "Cody nu poate răspunde acum. Replica ta nu s-a salvat; încearcă din nou.",
                code="profesor_indisponibil",
            ) from None

        # 9. reușit
        await settle(session, rezervare, actual_usd=rezultat.estimated_usd)
        session.add(PracticeDailyReply(
            participant_profile_id=profil_id,
            project_id=project_id,
            situation_id=situation_id,
            day=azi,
            reply_text=text,
            teacher_text=rezultat.text,
            score=nota_din_text(rezultat.text),
            cost_usd=rezultat.estimated_usd,
            prompt_version=CODY_PROMPT_VERSION,
            expires_at=acum + timedelta(days=retentie),
        ))
        await session.commit()

    return await _starea(session, profil_id, project_id, setari, azi)
