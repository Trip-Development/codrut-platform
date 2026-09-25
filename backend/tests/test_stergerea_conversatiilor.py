"""Ștergerea conversațiilor — plicul 149.

Acordul promite: conversațiile „sunt șterse la finalul [programului]" și „poți cere oricând
ștergerea lor mai devreme". Până la 149 nu exista nicio unealtă care să o facă.

Ce se dovedește aici, pe doi oameni inventați, fiecare cu text în TOATE locurile din inventar:
  · după ștergerea pe om: zero rânduri cu text de-al lui; ale celuilalt, amprentă identică;
  · acordul și costurile rămân; notele-cifre rămân, dacă nu se cere și ștergerea lor;
  · modul care numără nu schimbă nimic; fără cuvântul de confirmare nu se șterge nimic;
  · pe proiect: la fel, pentru toți oamenii proiectului.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from codrut.core.database import SessionLocal
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice.models import (
    CompetencyScore,
    CreatorNoteState,
    EvolutionLog,
    InsightMoment,
    OutcomeKind,
    ParticipantMemory,
    PracticeConsent,
    PracticeCreatorNote,
    PracticeFeedback,
    PracticeOutcome,
    PracticeSession,
    PracticeSessionSample,
    PracticeTurn,
    SessionKind,
    SessionSample,
    SessionState,
    TurnRole,
)
from codrut.tools.sterge_conversatii import CUVANTUL, Tinta, numara, ruleaza
from test_practice_session_flow import create_test_context


async def _om_cu_conversatie(s, eticheta: str) -> dict:
    """Un om inventat, cu o ședință închisă și text în fiecare loc din inventar."""
    ctx = await create_test_context(s)
    cont = User(id=uuid.uuid4(), email=ctx["profile"].email, password_hash="x",  # noqa: S106
                role=UserRole.participant)
    s.add(cont)
    await s.flush()
    ctx["profile"].user_id = cont.id
    acum = datetime.now(UTC)
    sed = PracticeSession(program_settings_id=ctx["program_settings"].id,
                          participant_profile_id=ctx["profile"].id, pack_id=ctx["pack"].id,
                          kind=SessionKind.roleplay, state=SessionState.closed, started_at=acum)
    s.add(sed)
    await s.flush()
    sid = str(sed.id)
    peste = acum + timedelta(days=30)
    s.add_all([
        PracticeTurn(session_id=sed.id, ordinal=1, role=TurnRole.participant,
                     text=f"{eticheta}: raportul a întârziat a treia oară", expires_at=peste,
                     cost_usd=Decimal("0.001")),
        PracticeTurn(session_id=sed.id, ordinal=2, role=TurnRole.actor,
                     text=f"{eticheta}: Cody răspunde", text_actor="actor", text_evaluator="ev",
                     expires_at=peste, cost_usd=Decimal("0.002")),
        PracticeOutcome(session_id=sed.id, kind=OutcomeKind.good, note=f"{eticheta}: sinteza"),
        PracticeFeedback(session_id=sed.id, criterion="criteriu", passed=True,
                         quote=f"{eticheta}: citat", suggestion="sugestie", expires_at=peste),
        PracticeSessionSample(session_id=sed.id, real_weak=f"{eticheta}: slab",
                              real_improved="mai bine", expires_at=peste),
        PracticeCreatorNote(author_user_id=cont.id, session_id=sed.id,
                            excerpt=f"{eticheta}: fragment", note="nota trainerului",
                            state=CreatorNoteState.new),
        ParticipantMemory(user_id=cont.id, session_id=sid, summary=f"{eticheta}: memoria",
                          key_quotes=["citat"], evolution_signals={}, personal_context={"t": 1},
                          relevant_competencies=[]),
        InsightMoment(user_id=cont.id, conversation_id=sid, summary=f"{eticheta}: moment"),
        InsightMoment(user_id=cont.id, conversation_id=sid,
                      summary=f"[TRAINER] {eticheta}: recomandare"),
        SessionSample(user_id=cont.id, conversation_id=sid, real_weak=f"{eticheta}: așa ai spus"),
        EvolutionLog(user_id=cont.id, session_id=sid, metrics={"a": 1},
                     qualitative_analysis=f"{eticheta}: analiza"),
        CompetencyScore(user_id=cont.id, project_id=ctx["project"].id, score=72, level=3,
                        justification=f"{eticheta}: a verificat înțelegerea",
                        conversation_id=sid, competency_name="Ascultare activă",
                        source_type="roleplay"),
    ])
    await s.flush()
    # id-urile ca valori simple: dupa `expire_all` obiectele nu se mai pot citi fara I/O
    ctx.update(sed=sed.id, cont_id=cont.id, profil=ctx["profile"].id, proiect=ctx["project"].id)
    return ctx


async def _amprenta(s, om: dict) -> str:
    """Tot ce e al omului, în toate tabelele din inventar, într-o singură amprentă."""
    s.expire_all()
    sed, cont = om["sed"], om["cont_id"]
    bucati = []
    for model, cond in (
        (PracticeTurn, PracticeTurn.session_id == sed),
        (PracticeOutcome, PracticeOutcome.session_id == sed),
        (PracticeFeedback, PracticeFeedback.session_id == sed),
        (PracticeSessionSample, PracticeSessionSample.session_id == sed),
        (PracticeCreatorNote, PracticeCreatorNote.session_id == sed),
        (ParticipantMemory, ParticipantMemory.user_id == cont),
        (InsightMoment, InsightMoment.user_id == cont),
        (SessionSample, SessionSample.user_id == cont),
        (EvolutionLog, EvolutionLog.user_id == cont),
        (CompetencyScore, CompetencyScore.user_id == cont),
        (PracticeConsent, PracticeConsent.participant_profile_id == om["profil"]),
    ):
        for r in (await s.execute(select(model).where(cond).order_by(model.id))).scalars():
            bucati.append(repr(sorted(
                (k, str(v)) for k, v in vars(r).items() if not k.startswith("_")
            )))
    return hashlib.sha256("\n".join(bucati).encode()).hexdigest()


async def _conn(s):
    return await s.connection()


@pytest.mark.asyncio
async def test_pe_om_zero_text_la_el_amprenta_neschimbata_la_celalalt() -> None:
    async with SessionLocal() as s:
        a = await _om_cu_conversatie(s, "OMUL-A")
        b = await _om_cu_conversatie(s, "OMUL-B")
        conn = await _conn(s)
        t_a = Tinta(sedinte=[a["sed"]], cont=a["cont_id"], proiect=None)
        inainte = await numara(conn, t_a)
        assert all(n > 0 for n in inainte.values()), inainte  # text în toate cele 10 locuri
        amprenta_b = await _amprenta(s, b)

        cod = await ruleaza(profil=a["profil"], proiect=None, de_sters=True,
                            confirmare=CUVANTUL, si_notele=False, conn=conn)

        assert cod == 0
        assert all(n == 0 for n in (await numara(conn, t_a)).values())
        # numaratoare INDEPENDENTA de unealta, scrisa direct pe tabele: un tabel uitat de ea
        # nu trebuie sa treaca doar fiindca unealta nu-l numara
        s.expire_all()
        sed, cont = a["sed"], a["cont_id"]
        for model, cond in (
            (PracticeFeedback, PracticeFeedback.session_id == sed),
            (PracticeSessionSample, PracticeSessionSample.session_id == sed),
            (ParticipantMemory, ParticipantMemory.user_id == cont),
            (InsightMoment, InsightMoment.user_id == cont),
            (SessionSample, SessionSample.user_id == cont),
            (EvolutionLog, EvolutionLog.user_id == cont),
            (PracticeOutcome, (PracticeOutcome.session_id == sed)
             & PracticeOutcome.note.is_not(None)),
            (PracticeCreatorNote, (PracticeCreatorNote.session_id == sed)
             & PracticeCreatorNote.excerpt.is_not(None)),
        ):
            n = (await s.execute(select(func.count()).select_from(model).where(cond))).scalar_one()
            assert n == 0, model.__tablename__
        text_ramas = (await s.execute(select(func.count()).select_from(PracticeTurn).where(
            PracticeTurn.session_id == sed,
            (PracticeTurn.text != "") | PracticeTurn.text_actor.is_not(None)
            | PracticeTurn.text_evaluator.is_not(None)))).scalar_one()
        assert text_ramas == 0
        assert await _amprenta(s, b) == amprenta_b
        # rămân: acordul, replicile ca rânduri (cu costul), notele-cifre fără justificare
        assert (await s.execute(select(func.count()).select_from(PracticeConsent).where(
            PracticeConsent.participant_profile_id == a["profil"]))).scalar_one() == 1
        replici = (await s.execute(select(PracticeTurn).where(
            PracticeTurn.session_id == a["sed"]))).scalars().all()
        assert [r.text for r in replici] == ["", ""]
        assert sum(r.cost_usd for r in replici) == Decimal("0.003")
        note = (await s.execute(select(CompetencyScore).where(
            CompetencyScore.user_id == a["cont_id"]))).scalars().all()
        assert [(n.score, n.justification) for n in note] == [(72, None)]
        nota_trainer = (await s.execute(select(PracticeCreatorNote.note).where(
            PracticeCreatorNote.session_id == a["sed"]))).scalar_one()
        assert nota_trainer == "nota trainerului"
        await s.rollback()


@pytest.mark.asyncio
async def test_si_notele_sterge_si_cifrele() -> None:
    async with SessionLocal() as s:
        a = await _om_cu_conversatie(s, "OMUL-A")
        conn = await _conn(s)
        assert await ruleaza(profil=a["profil"], proiect=None, de_sters=True,
                             confirmare=CUVANTUL, si_notele=True, conn=conn) == 0
        s.expire_all()
        assert (await s.execute(select(func.count()).select_from(CompetencyScore).where(
            CompetencyScore.user_id == a["cont_id"]))).scalar_one() == 0
        await s.rollback()


@pytest.mark.asyncio
async def test_modul_care_numara_nu_schimba_nimic() -> None:
    async with SessionLocal() as s:
        a = await _om_cu_conversatie(s, "OMUL-A")
        conn = await _conn(s)
        inainte = await _amprenta(s, a)
        assert await ruleaza(profil=a["profil"], proiect=None, de_sters=False,
                             confirmare=None, si_notele=False, conn=conn) == 0
        assert await _amprenta(s, a) == inainte
        await s.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("confirmare", [None, "", "sterg", "DA"])
async def test_fara_cuvantul_scris_nu_se_sterge_nimic(confirmare) -> None:
    async with SessionLocal() as s:
        a = await _om_cu_conversatie(s, "OMUL-A")
        conn = await _conn(s)
        inainte = await _amprenta(s, a)
        assert await ruleaza(profil=a["profil"], proiect=None, de_sters=True,
                             confirmare=confirmare, si_notele=True, conn=conn) == 2
        assert await _amprenta(s, a) == inainte
        await s.rollback()


@pytest.mark.asyncio
async def test_pe_proiect_zero_text_in_proiect_celalalt_proiect_neatins() -> None:
    async with SessionLocal() as s:
        a = await _om_cu_conversatie(s, "OMUL-A")
        b = await _om_cu_conversatie(s, "OMUL-B")  # alt proiect, altă firmă
        conn = await _conn(s)
        amprenta_b = await _amprenta(s, b)
        assert await ruleaza(profil=None, proiect=a["proiect"], de_sters=True,
                             confirmare=CUVANTUL, si_notele=False, conn=conn) == 0
        t_a = Tinta(sedinte=[a["sed"]], cont=None, proiect=a["proiect"])
        assert all(n == 0 for n in (await numara(conn, t_a)).values())
        assert await _amprenta(s, b) == amprenta_b
        await s.rollback()
