"""Tipul interlocutorului dintr-o ședință de role-play, dedus fără migrare — plicul 165, partea B.

Tipul (din echipă / coleg / șef / client) NU e salvat pe ședință. La pornire, aplicația îl alege
din rotație: al k-lea role-play al profilului (numărat de la 0, în ordinea pornirii) primește
`rotatie[k % len(rotatie)]`, cu `ROTATIE_CONDUCE` sau `ROTATIE_NU_CONDUCE` după `conduce_oameni`
(`service._profilul_de_rol`). Aici se face exact aceeași socoteală, înapoi, pentru punctajul pe
varietate.

LIMITA, scrisă pe față: dacă se șterg ședințe (unealta de la plicul 149) sau se schimbă
`role_group` al omului, tipurile deduse pentru trecut se pot muta — numărătoarea și rotația de
azi nu mai sunt cele de la pornire.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.companies.models import ParticipantProfile
from codrut.modules.practice.models import CompetencyScore, PracticeSession, SessionKind
from codrut.modules.practice.prompts import ROTATIE_CONDUCE, ROTATIE_NU_CONDUCE
from codrut.modules.practice.scoring import ScoreEntry

# ce înseamnă fiecare tip, pentru oameni
TIPURI_INTERLOCUTOR = {
    "jos": "din echipă",
    "lateral": "coleg",
    "sus": "șef",
    "client": "client",
}


def _conduce(profil: ParticipantProfile | None) -> bool:
    # aceeași verificare ca în `service._profilul_de_rol`
    grup = (profil.role_group or "") if profil else ""
    return grup.strip().casefold() in {"leadership", "manager"}


async def sedintele_notelor(
    session: AsyncSession,
    conversation_ids: Iterable[str],
) -> dict[str, tuple[str, str | None]]:
    """Pentru fiecare `conversation_id` care e o ședință: `(felul ei, tipul interlocutorului)`.

    Tipul e `None` la orice altceva decât role-play. Id-urile care nu sunt ședințe (arhiva,
    testele IN/OUT) lipsesc din rezultat.
    """
    ids: set[uuid.UUID] = set()
    for c in conversation_ids:
        try:
            ids.add(uuid.UUID(str(c)))
        except (TypeError, ValueError):
            continue
    if not ids:
        return {}
    sedinte = (await session.execute(
        select(PracticeSession).where(PracticeSession.id.in_(ids))
    )).scalars().all()
    profile_ids = {s.participant_profile_id for s in sedinte}
    profile = {
        p.id: p for p in (await session.execute(
            select(ParticipantProfile).where(ParticipantProfile.id.in_(profile_ids))
        )).scalars().all()
    }
    # toate role-play-urile acestor profiluri, în ordinea pornirii — numărătoarea de la pornire
    ordine: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for rand in (await session.execute(
        select(PracticeSession.id, PracticeSession.participant_profile_id)
        .where(
            PracticeSession.participant_profile_id.in_(profile_ids),
            PracticeSession.kind == SessionKind.roleplay,
        )
        .order_by(PracticeSession.started_at, PracticeSession.id)
    )).all():
        ordine[rand.participant_profile_id].append(rand.id)

    rezultat: dict[str, tuple[str, str | None]] = {}
    for s in sedinte:
        fel = s.kind.value if hasattr(s.kind, "value") else str(s.kind)
        tip = None
        if s.kind == SessionKind.roleplay:
            rotatie = (
                ROTATIE_CONDUCE if _conduce(profile.get(s.participant_profile_id))
                else ROTATIE_NU_CONDUCE
            )
            k = ordine[s.participant_profile_id].index(s.id)
            tip = rotatie[k % len(rotatie)]
        rezultat[str(s.id)] = (fel, tip)
    return rezultat


async def intrarile_de_punctaj(
    session: AsyncSession,
    scoruri: Sequence[CompetencyScore],
) -> dict[uuid.UUID, ScoreEntry]:
    """Notele care intră în punctaj, cu tipul interlocutorului — plicul 165.

    Regula 1: contează numai role-play-urile. Nota unei ședințe de alt fel (quiz, coaching) iese,
    oricum ar fi scris `source_type` (rezumatul de la închidere scrie „session" la orice fel).
    Notele fără ședință (arhiva) rămân, fără tip; `compute_competency_evidence` scoate în
    continuare quiz-ul și testele IN/OUT după `source_type`, ca până acum.
    """
    sedinte = await sedintele_notelor(session, {s.conversation_id for s in scoruri})
    intrari: dict[uuid.UUID, ScoreEntry] = {}
    for s in scoruri:
        fel, tip = sedinte.get(s.conversation_id, (None, None))
        if fel is not None and fel != SessionKind.roleplay.value:
            continue
        intrari[s.id] = ScoreEntry(
            score=s.score, created_at=s.created_at, source_type=s.source_type, interlocutor=tip,
        )
    return intrari
