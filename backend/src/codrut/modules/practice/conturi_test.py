"""Contul de test al lui Andrei: fara limita pe zi, cu frana lui proprie.

Hotararea lui Andrei (1 oct 2026, STARE `[test-nelimitat]`): contul lui de test trebuie sa
poata porni oricate sedinte, ca sa poata incerca aplicatia oricand.

„Nelimitat" NU inseamna fara nicio frana. Contul de test primeste un plafon lunar PROPRIU,
pe fiecare server, ca un cont scapat sa nu poata arde bani fara capat. La ~0,05 USD pe
sedinta inseamna in jur de 500 de sedinte pe luna.

Doua lucruri se tin impreuna, si de asta stau aici, nu imprastiate:
  1. contul de test nu mai intra in punga proiectului — nici in numarul de membri dupa care
     se calculeaza punga, nici in ce s-a consumat din ea. Plafonul celorlalti nu creste si nu
     scade din cauza testelor lui;
  2. e UN SINGUR cont, pe adresa exacta. `andreyvacaru+lidera@gmail.com` si celelalte
     variante joaca oameni adevarati in probe si NU sunt conturi de test.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.modules.companies.models import ParticipantProfile
from codrut.modules.identity.models import User
from codrut.modules.practice.models import PracticeSession

# Adresele se scriu cu litere mici o singura data (plicul 81). Potrivirea e pe adresa
# intreaga, nu pe prefix: un `frozenset`, nu un `startswith`.
CONTURI_DE_TEST = frozenset({"andreyvacaru@gmail.com"})

# Frana proprie a contului de test, pe luna calendaristica UTC, peste toate proiectele.
PLAFON_LUNAR_CONT_TEST_USD = Decimal("25.00")


def e_cont_de_test(adresa: str | None) -> bool:
    """Adresa asta e a unui cont de test? Majusculele si spatiile nu conteaza."""
    if not adresa:
        return False
    return adresa.strip().lower() in CONTURI_DE_TEST


async def contul_de_test_al_sedintei(
    session: AsyncSession,
    session_id: uuid.UUID | None,
) -> str | None:
    """Adresa contului de test caruia ii apartine sedinta, sau `None`.

    Drumul e sedinta -> profilul participantului -> contul legat (`users.email`); daca
    profilul nu e legat de niciun cont, se ia adresa scrisa pe profil. Acelasi drum pentru
    sedintele obisnuite si pentru cele „ca trainer": si acolo rezervarea poarta `session_id`,
    iar profilul are adresa contului.
    """
    if session_id is None:
        return None
    adresa = (
        await session.execute(
            select(User.email)
            .select_from(PracticeSession)
            .join(
                ParticipantProfile,
                ParticipantProfile.id == PracticeSession.participant_profile_id,
            )
            .join(User, User.id == ParticipantProfile.user_id)
            .where(PracticeSession.id == session_id)
        )
    ).scalar_one_or_none()
    if adresa is None:
        # Profil nelegat de un cont: adresa scrisa pe profil.
        adresa = (
            await session.execute(
                select(ParticipantProfile.email)
                .select_from(PracticeSession)
                .join(
                    ParticipantProfile,
                    ParticipantProfile.id == PracticeSession.participant_profile_id,
                )
                .where(PracticeSession.id == session_id)
            )
        ).scalar_one_or_none()
    return adresa if e_cont_de_test(adresa) else None
