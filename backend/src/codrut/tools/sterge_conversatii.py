"""Ștergerea conversațiilor cu Cody — plicul 149.

Acordul pe care îl bifează omul promite, cuvânt cu cuvânt: „Conversațiile tale sunt păstrate în
aplicație pe durata programului și sunt șterse la finalul acestuia. […] Poți cere oricând
ștergerea lor mai devreme." Unealta asta ține promisiunea.

Două feluri:

    python -m codrut.tools.sterge_conversatii --profil <uuid>     # la cererea omului
    python -m codrut.tools.sterge_conversatii --proiect <uuid>    # la finalul programului

Fără `--sterge`, NUMAI NUMĂRĂ ce ar șterge, pe tabele, într-o tranzacție care se întoarce.
Cu `--sterge`, șterge numai dacă primește și `--confirmare STERG`, cuvântul scris de mână.

CE ȘTERGE — tot textul din conversație (inventarul plicului 149, căutat pe baza probei):
  · practice_turns.text / text_actor / text_evaluator — replicile; rândul RĂMÂNE, cu textul gol,
    ca să rămână costul și numărătoarea replicilor;
  · practice_outcomes.note — sinteza ședinței (golită);
  · practice_feedback, practice_session_samples — citate și sugestii (rânduri șterse);
  · practice_creator_notes.excerpt — citatul din conversație (golit; nota trainerului rămâne);
  · participant_memory — ce ține minte Cody (rânduri șterse);
  · insight_moments — momentele, inclusiv recomandările pentru trainer (rânduri șterse);
  · session_samples — „așa ai spus / așa ar fi sunat" (rânduri șterse);
  · evolution_logs — analiza calitativă (rânduri șterse);
  · competency_scores.justification — fraza evaluatorului despre conversație (golită).
CE NU ȘTERGE: acordul (dovada că omul a fost întrebat), costurile (rezervările de bani și
costurile de pe replici), ședințele ca fapt (data, felul, starea — fără text), XP-ul.
NOTELE PE COMPETENȚE (cifrele): rămân, dacă nu se dă `--si-notele`. Fără ele tabloul omului se
golește; cu ele, tabloul rămâne cum era, dar fără nicio frază despre conversație.

NU se pot șterge de aici, și de aceea sunt scrise: jurnalul serverului (până la plicul 149 scria
primele 80 de semne din ultima replică a omului, `service.py`) și copiile de siguranță ale bazei.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from codrut.core.database import engine
from codrut.modules.companies.models import ParticipantProfile
from codrut.modules.practice.models import (
    CompetencyScore,
    EvolutionLog,
    InsightMoment,
    ParticipantMemory,
    PracticeCreatorNote,
    PracticeFeedback,
    PracticeOutcome,
    PracticeProgramSettings,
    PracticeSession,
    PracticeSessionSample,
    PracticeTurn,
    SessionSample,
)

CUVANTUL = "STERG"


@dataclass(frozen=True)
class Tinta:
    """Ce ședințe și ce cont intră în ștergere."""

    sedinte: list[uuid.UUID]
    cont: uuid.UUID | None
    proiect: uuid.UUID | None

    @property
    def sedinte_text(self) -> list[str]:
        return [str(s) for s in self.sedinte]


async def tinta(conn: AsyncConnection, *, profil: uuid.UUID | None,
                proiect: uuid.UUID | None) -> Tinta:
    if profil is not None:
        cont = (await conn.execute(
            select(ParticipantProfile.user_id).where(ParticipantProfile.id == profil)
        )).scalar_one_or_none()
        if cont is None and (await conn.execute(
            select(func.count()).select_from(ParticipantProfile)
            .where(ParticipantProfile.id == profil)
        )).scalar_one() == 0:
            raise SystemExit(f"Profilul {profil} nu există.")
        sedinte = list((await conn.execute(
            select(PracticeSession.id).where(PracticeSession.participant_profile_id == profil)
        )).scalars())
        return Tinta(sedinte=sedinte, cont=cont, proiect=None)
    sedinte = list((await conn.execute(
        select(PracticeSession.id)
        .join(PracticeProgramSettings,
              PracticeProgramSettings.id == PracticeSession.program_settings_id)
        .where(PracticeProgramSettings.project_id == proiect)
    )).scalars())
    return Tinta(sedinte=sedinte, cont=None, proiect=proiect)


def _pe_conversatie(coloana, t: Tinta, coloana_cont=None):
    """Rândurile legate de ședințele țintei; pe om, și tot ce e al contului lui."""
    conditii = [coloana.in_(t.sedinte_text)] if t.sedinte else []
    if t.cont is not None and coloana_cont is not None:
        conditii.append(coloana_cont == t.cont)
    return or_(*conditii) if conditii else None


def filtre(t: Tinta) -> dict[str, tuple]:
    """Tabel -> (modelul, condiția rândurilor cu text de-al țintei, felul: șterge / golește)."""
    replici = PracticeTurn.session_id.in_(t.sedinte) if t.sedinte else None
    pe_sedinta = (lambda col: col.in_(t.sedinte)) if t.sedinte else (lambda col: None)
    note = _pe_conversatie(CompetencyScore.conversation_id, t, CompetencyScore.user_id)
    if t.proiect is not None:
        note = or_(*(c for c in (note, CompetencyScore.project_id == t.proiect) if c is not None))
    memorie = _pe_conversatie(ParticipantMemory.session_id, t, ParticipantMemory.user_id)
    if t.proiect is not None:
        memorie = or_(*(c for c in (memorie, ParticipantMemory.project_id == t.proiect)
                        if c is not None))
    return {
        "practice_turns (replicile)": (
            PracticeTurn, replici, "goleste",
            or_(PracticeTurn.text != "", PracticeTurn.text_actor.is_not(None),
                PracticeTurn.text_evaluator.is_not(None))),
        "practice_outcomes (sinteza)": (
            PracticeOutcome, pe_sedinta(PracticeOutcome.session_id), "goleste",
            PracticeOutcome.note.is_not(None)),
        "practice_feedback": (
            PracticeFeedback, pe_sedinta(PracticeFeedback.session_id), "sterge", None),
        "practice_session_samples": (
            PracticeSessionSample, pe_sedinta(PracticeSessionSample.session_id), "sterge", None),
        "practice_creator_notes (citatul)": (
            PracticeCreatorNote, pe_sedinta(PracticeCreatorNote.session_id), "goleste",
            PracticeCreatorNote.excerpt.is_not(None)),
        "participant_memory (memoria lui Cody)": (ParticipantMemory, memorie, "sterge", None),
        "insight_moments (momentele)": (
            InsightMoment,
            _pe_conversatie(InsightMoment.conversation_id, t, InsightMoment.user_id),
            "sterge", None),
        "session_samples (mostrele)": (
            SessionSample,
            _pe_conversatie(SessionSample.conversation_id, t, SessionSample.user_id),
            "sterge", None),
        "evolution_logs": (
            EvolutionLog, _pe_conversatie(EvolutionLog.session_id, t, EvolutionLog.user_id),
            "sterge", None),
        "competency_scores (justificarea)": (
            CompetencyScore, note, "goleste", CompetencyScore.justification.is_not(None)),
    }


async def numara(conn: AsyncConnection, t: Tinta) -> dict[str, int]:
    """Câte rânduri CU TEXT de-al țintei are fiecare tabel."""
    out = {}
    for nume, (model, cond, _fel, are_text) in filtre(t).items():
        if cond is None:
            out[nume] = 0
            continue
        q = select(func.count()).select_from(model).where(cond)
        if are_text is not None:
            q = q.where(are_text)
        out[nume] = (await conn.execute(q)).scalar_one()
    return out


async def note_ale_tintei(conn: AsyncConnection, t: Tinta) -> int:
    cond = filtre(t)["competency_scores (justificarea)"][1]
    if cond is None:
        return 0
    return (await conn.execute(select(func.count()).select_from(CompetencyScore).where(cond))
            ).scalar_one()


async def sterge(conn: AsyncConnection, t: Tinta, *, si_notele: bool) -> None:
    for _nume, (model, cond, fel, _are_text) in filtre(t).items():
        if cond is None:
            continue
        if model is CompetencyScore and si_notele:
            await conn.execute(delete(CompetencyScore).where(cond))
        elif fel == "sterge":
            await conn.execute(delete(model).where(cond))
        elif model is PracticeTurn:
            await conn.execute(update(PracticeTurn).where(cond).values(
                text="", text_actor=None, text_evaluator=None))
        elif model is PracticeOutcome:
            await conn.execute(update(PracticeOutcome).where(cond).values(note=None))
        elif model is PracticeCreatorNote:
            await conn.execute(update(PracticeCreatorNote).where(cond).values(excerpt=None))
        elif model is CompetencyScore:
            await conn.execute(update(CompetencyScore).where(cond).values(justification=None))


async def ruleaza(*, profil: uuid.UUID | None, proiect: uuid.UUID | None, de_sters: bool,
                  confirmare: str | None, si_notele: bool, conn: AsyncConnection | None = None
                  ) -> int:
    """0 = gata (sau numărat) · 2 = fără confirmare, nimic șters · 3 = a rămas text, întors."""
    if de_sters and confirmare != CUVANTUL:
        print(f"NIMIC ȘTERS: pentru ștergere trebuie scris `--confirmare {CUVANTUL}`.")
        return 2
    proprie = conn is None
    if proprie:
        conn = await engine.connect()
    tranzactie = await conn.begin_nested() if conn.in_transaction() else await conn.begin()
    try:
        t = await tinta(conn, profil=profil, proiect=proiect)
        inainte = await numara(conn, t)
        note = await note_ale_tintei(conn, t)
        print(f"ținta: {'profilul ' + str(profil) if profil else 'proiectul ' + str(proiect)} · "
              f"ședințe: {len(t.sedinte)} · notele pe competențe: {note} "
              f"({'se șterg' if si_notele else 'rămân, fără justificare'})")
        for nume, n in inainte.items():
            print(f"  {nume}: {n} rânduri cu text")
        if not de_sters:
            print("NUMAI NUMĂRAT — nimic atins.")
            await tranzactie.rollback()
            return 0
        await sterge(conn, t, si_notele=si_notele)
        dupa = await numara(conn, t)
        ramas = {k: v for k, v in dupa.items() if v}
        if ramas:
            print(f"OPRIT: a rămas text {ramas} — totul se întoarce.")
            await tranzactie.rollback()
            return 3
        await tranzactie.commit()
        tabele = sum(1 for v in inainte.values() if v)
        print(f"ȘTERS: {sum(inainte.values())} rânduri cu text, în {tabele} tabele. "
              "Acordul și costurile au rămas.")
        return 0
    except BaseException:
        if tranzactie.is_active:
            await tranzactie.rollback()
        raise
    finally:
        if proprie:
            await conn.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    cine = ap.add_mutually_exclusive_group(required=True)
    cine.add_argument("--profil", type=uuid.UUID, help="la cererea omului")
    cine.add_argument("--proiect", type=uuid.UUID, help="la finalul programului")
    ap.add_argument("--sterge", action="store_true", help="altfel numai numără")
    ap.add_argument("--confirmare", help=f"cuvântul {CUVANTUL}, scris de mână")
    ap.add_argument("--si-notele", action="store_true",
                    help="șterge și notele pe competențe (implicit rămân)")
    a = ap.parse_args(argv)
    return asyncio.run(ruleaza(profil=a.profil, proiect=a.proiect, de_sters=a.sterge,
                               confirmare=a.confirmare, si_notele=a.si_notele))


if __name__ == "__main__":
    sys.exit(main())
