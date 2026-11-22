"""Harta echipei pentru HR — numai cifre de grup, cu pragul de 5 oameni (plicul 240, L4-P1).

Fișa `SPEC-CODY/FISE/L4-harta-echipei-pentru-hr.md`. Ce întoarce: câți au exersat din câți
invitați (și pe săptămâni), sesiunile și timpul, cele 7 competențe la început și acum (numai
role-play-ul ACESTUI proiect), cele 2 cele mai slabe, obiectivele alese. ORICE cifră apare numai
dacă vine de la cel puțin `PRAG_OAMENI` oameni distincți; altfel `valoare = None`,
`motiv = "prea_putini"`.

Fără nume, fără id-uri de oameni, fără liste pe om, fără clasament, fără textul conversațiilor
(la replici se citesc numai ședința, rolul și ora). Numai `select`: nu scrie nimic în bază și
nimic în jurnalul serverului. Replica zilei (236) nu intră.
"""

from __future__ import annotations

import math
import uuid
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.companies.models import ParticipantProfile, ProjectMembership
from codrut.modules.identity.models import User
from codrut.modules.practice.competency_aliases import match_comp
from codrut.modules.practice.conturi_test import fara_conturile_de_test
from codrut.modules.practice.models import (
    CompetencyScore,
    PracticeObjective,
    PracticeObjectiveChoice,
    PracticeProgramSettings,
    PracticeSession,
    PracticeTurn,
    SessionKind,
    TurnRole,
)
from codrut.modules.practice.pe_proiect import sedintele_proiectului
from codrut.modules.practice.scoring import e_nota_de_role_play, ziua_in_romania
from codrut.modules.practice.setup_service import competency_names_for_project

# fișa L4; întrebarea [harta-prag] la L4-P2
PRAG_OAMENI = 5
PREA_PUTINI = "prea_putini"
FARA_OBIECTIVE = "fara_obiective"
# o conversație lăsată deschisă sau continuată a doua zi nu umflă timpul
DURATA_MAXIMA = timedelta(minutes=60)
CELE_MAI_ALESE = 3
CELE_MAI_SLABE = 2


# ---------- funcțiile pure (fără bază) ----------


def cifra(valoare, oameni: int) -> dict:
    """O cifră a hărții: arătată numai dacă vine de la cel puțin `PRAG_OAMENI` oameni.

    0 e sub prag."""
    if valoare is None or oameni < PRAG_OAMENI:
        return {"valoare": None, "motiv": PREA_PUTINI}
    return {"valoare": valoare, "motiv": None}


def rotunjit(x: float) -> int:
    """La număr întreg, jumătatea în sus (corecția 1 a controlorului: și la început și acum)."""
    return math.floor(x + 0.5)


def luni_din(zi: date) -> date:
    return zi - timedelta(days=zi.weekday())


def saptamanile(
    porniri: Iterable[tuple[uuid.UUID, datetime]], acum: datetime,
) -> list[tuple[date, int]]:
    """(luni, câți oameni distincți au pornit o sesiune numărată în săptămâna aceea), din
    săptămâna primei sesiuni până la săptămâna lui `acum`, cu săptămânile goale.
    Fără sesiuni → listă goală."""
    pe_saptamana: dict[date, set] = defaultdict(set)
    for om, pornire in porniri:
        pe_saptamana[luni_din(ziua_in_romania(pornire))].add(om)
    if not pe_saptamana:
        return []
    zi = min(pe_saptamana)
    ultima = max(luni_din(ziua_in_romania(acum)), max(pe_saptamana))
    lista = []
    while zi <= ultima:
        lista.append((zi, len(pe_saptamana.get(zi, ()))))
        zi += timedelta(days=7)
    return lista


def durata(pornire: datetime, ultima_replica: datetime | None) -> timedelta:
    """De la pornire la ultima replică (a oricui), cel mult `DURATA_MAXIMA`, niciodată sub 0."""
    if ultima_replica is None:
        return timedelta(0)
    return max(timedelta(0), min(ultima_replica - pornire, DURATA_MAXIMA))


def minute_rotunjite(durate: Iterable[timedelta]) -> int:
    return rotunjit(sum((d.total_seconds() for d in durate), 0.0) / 60)


def inceput_si_acum(note_pe_om: dict) -> tuple[int | None, int | None, int]:
    """`note_pe_om` = {om: [(moment, scor), …]}. Intră numai omul cu note în cel puțin 2 zile
    diferite (ora României): început = media lui din prima zi, acum = media lui din ultima zi.
    Grupul = media pe oameni (fiecare cântărește la fel), rotunjită la întreg."""
    inceputuri, acumuri = [], []
    for note in note_pe_om.values():
        pe_zi: dict[date, list[int]] = defaultdict(list)
        for moment, scor in note:
            pe_zi[ziua_in_romania(moment)].append(scor)
        if len(pe_zi) < 2:
            continue
        prima, ultima = pe_zi[min(pe_zi)], pe_zi[max(pe_zi)]
        inceputuri.append(sum(prima) / len(prima))
        acumuri.append(sum(ultima) / len(ultima))
    if not inceputuri:
        return None, None, 0
    oameni = len(inceputuri)
    return rotunjit(sum(inceputuri) / oameni), rotunjit(sum(acumuri) / oameni), oameni


def cele_mai_slabe(competente: list[dict]) -> dict:
    """Dintre competențele cu `acum` arătat, cele două cu `acum` cel mai mic; la egalitate,
    ordinea competențelor din proiect."""
    aratate = [
        (c["acum"]["valoare"], i, c["nume"])
        for i, c in enumerate(competente) if c["acum"]["valoare"] is not None
    ]
    if not aratate:
        return {"nume": None, "motiv": PREA_PUTINI}
    return {"nume": [nume for _, _, nume in sorted(aratate)[:CELE_MAI_SLABE]], "motiv": None}


def obiectivele(alegeri: dict[uuid.UUID, tuple[int, str]]) -> dict:
    """`alegeri` = {om: (nr, titlu)} (alegerea curentă a fiecăruia). Cele mai alese =
    obiectivele alese de cel puțin `PRAG_OAMENI` oameni, după număr (descrescător), apoi după
    `nr`; cel mult 3."""
    pe_obiectiv: dict[tuple[int, str], int] = defaultdict(int)
    for nr_titlu in alegeri.values():
        pe_obiectiv[nr_titlu] += 1
    alese = sorted(
        ((nr, titlu, cati) for (nr, titlu), cati in pe_obiectiv.items() if cati >= PRAG_OAMENI),
        key=lambda t: (-t[2], t[0]),
    )[:CELE_MAI_ALESE]
    si_au_ales = len(alegeri)
    return {
        "si_au_ales": cifra(si_au_ales, si_au_ales),
        "cele_mai_alese": [
            {"nr": nr, "titlu": titlu, "oameni": cati} for nr, titlu, cati in alese
        ],
        "motiv": None if si_au_ales >= PRAG_OAMENI and alese else PREA_PUTINI,
    }


# ---------- interogările (numai select) ----------


async def _oamenii(
    session: AsyncSession, project_id: uuid.UUID,
) -> dict[uuid.UUID, uuid.UUID | None]:
    """{profil: contul lui sau None} — oamenii proiectului (toate apartenențele), fără contul de
    test; contul = `profil.user_id`, altfel după adresă (ca în Evoluție)."""
    randuri = (await session.execute(
        select(ParticipantProfile, ProjectMembership)
        .join(
            ProjectMembership,
            ProjectMembership.participant_profile_id == ParticipantProfile.id,
        )
        .where(ProjectMembership.project_id == project_id)
    )).all()
    randuri, _ = await fara_conturile_de_test(session, randuri)
    adrese = {p.email.lower() for p, _ in randuri if p.email and not p.user_id}
    dupa_adresa = {}
    if adrese:
        dupa_adresa = {
            adresa.lower(): uid for uid, adresa in (await session.execute(
                select(User.id, User.email).where(func.lower(User.email).in_(adrese))
            )).all()
        }
    return {
        p.id: p.user_id or (dupa_adresa.get(p.email.lower()) if p.email else None)
        for p, _ in randuri
    }


async def notele_pe_competenta(
    session: AsyncSession,
    project_id: uuid.UUID,
    conturi: set[uuid.UUID] | None = None,
) -> dict[str, list[tuple[uuid.UUID, datetime, int]]]:
    """{competența proiectului: [(cont, moment, scor), …]} — numai notele de role-play din
    ședințele de role-play ale ACESTUI proiect, ale oamenilor lui. Potrivirea numelui ca în
    Evoluție (numele canonic și numele brut)."""
    if conturi is None:
        conturi = {u for u in (await _oamenii(session, project_id)).values() if u}
    competente = await competency_names_for_project(session, project_id)
    note = []
    if conturi:
        sedinte_role_play = sedintele_proiectului(project_id).where(
            PracticeSession.kind == SessionKind.roleplay
        )
        note = (await session.execute(
            select(
                CompetencyScore.user_id, CompetencyScore.competency_name,
                CompetencyScore.score, CompetencyScore.created_at, CompetencyScore.source_type,
            ).where(
                CompetencyScore.user_id.in_(conturi),
                CompetencyScore.conversation_id.in_(sedinte_role_play),
            )
        )).all()
    pe_nume: dict[str, list] = defaultdict(list)
    for cont, nume_nota, scor, moment, sursa in note:
        if not nume_nota or not e_nota_de_role_play(sursa):
            continue
        canonic = match_comp(nume_nota)
        if canonic:
            pe_nume[canonic].append((cont, moment, scor))
        if canonic != nume_nota:
            pe_nume[nume_nota].append((cont, moment, scor))
    rezultat = {}
    for nume in competente or sorted(pe_nume):
        canonic = match_comp(nume)
        rezultat[nume] = pe_nume.get(nume) or (pe_nume.get(canonic, []) if canonic else [])
    return rezultat


async def harta_echipei(
    session: AsyncSession, project_id: uuid.UUID, *, acum: datetime,
) -> dict:
    """Cifrele grupului pentru proiect, la momentul `acum`.

    Ruta dă ora de acum, testele una fixă."""
    oameni = await _oamenii(session, project_id)
    profiluri = list(oameni)
    setari = (await session.execute(
        select(PracticeProgramSettings.id, PracticeProgramSettings.objective_catalog)
        .where(PracticeProgramSettings.project_id == project_id)
    )).first()

    # --- sesiunile numărate: cu cel puțin o replică a omului ---
    sedinte = []
    if setari is not None and profiluri:
        sedinte = (await session.execute(
            select(PracticeSession.id, PracticeSession.participant_profile_id,
                   PracticeSession.started_at)
            .where(PracticeSession.program_settings_id == setari.id,
                   PracticeSession.participant_profile_id.in_(profiluri))
        )).all()
    cu_omul: set[uuid.UUID] = set()
    ultima: dict[uuid.UUID, datetime] = {}
    if sedinte:
        for sid, rol, moment in (await session.execute(
            select(PracticeTurn.session_id, PracticeTurn.role, PracticeTurn.created_at)
            .where(PracticeTurn.session_id.in_([s[0] for s in sedinte]))
        )).all():
            if rol == TurnRole.participant:
                cu_omul.add(sid)
            if sid not in ultima or moment > ultima[sid]:
                ultima[sid] = moment
    numarate = [(sid, om, pornire) for sid, om, pornire in sedinte if sid in cu_omul]
    au_exersat = len({om for _, om, _ in numarate})

    # --- competențele ---
    pe_competenta = await notele_pe_competenta(
        session, project_id, {u for u in oameni.values() if u}
    )
    competente = []
    for nume, note in pe_competenta.items():
        pe_om: dict[uuid.UUID, list] = defaultdict(list)
        for cont, moment, scor in note:
            pe_om[cont].append((moment, scor))
        inceput, acum_val, cati = inceput_si_acum(pe_om)
        competente.append({
            "nume": nume, "oameni": cifra(cati, cati),
            "inceput": cifra(inceput, cati), "acum": cifra(acum_val, cati),
        })

    # --- obiectivele: alegerile curente, din catalogul proiectului, obiective active ---
    if setari is None or not setari.objective_catalog:
        obiective = {"si_au_ales": cifra(None, 0), "cele_mai_alese": [], "motiv": FARA_OBIECTIVE}
    else:
        alegeri = {}
        if profiluri:
            alegeri = {
                om: (nr, titlu) for om, nr, titlu in (await session.execute(
                    select(PracticeObjectiveChoice.participant_profile_id,
                           PracticeObjective.order_index, PracticeObjective.title)
                    .join(
                        PracticeObjective,
                        PracticeObjective.id == PracticeObjectiveChoice.objective_id,
                    )
                    .where(
                        PracticeObjectiveChoice.project_id == project_id,
                        PracticeObjectiveChoice.replaced_at.is_(None),
                        PracticeObjectiveChoice.participant_profile_id.in_(profiluri),
                        PracticeObjective.catalog == setari.objective_catalog,
                        PracticeObjective.is_active.is_(True),
                    )
                )).all()
            }
        obiective = obiectivele(alegeri)

    invitati = len(oameni)
    return {
        "project_id": project_id,
        "calculat_la": acum,
        "prag_oameni": PRAG_OAMENI,
        "invitati": cifra(invitati, invitati),
        "au_exersat": cifra(au_exersat, au_exersat),
        "pe_saptamani": [
            {"saptamana": luni.isoformat(), "au_exersat": cifra(cati, cati)}
            for luni, cati in saptamanile(((om, p) for _, om, p in numarate), acum)
        ],
        "sesiuni": cifra(len(numarate), au_exersat),
        "minute": cifra(
            minute_rotunjite(durata(p, ultima.get(sid)) for sid, _, p in numarate), au_exersat
        ),
        "competente": competente,
        "cele_mai_slabe": cele_mai_slabe(competente),
        "obiective": obiective,
    }
