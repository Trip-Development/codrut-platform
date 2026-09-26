"""Acordul la prima intrare în exersare — plicul 139.

Hotărârea lui Andrei și a auditorului: niciun om nu vorbește cu Cody până nu a văzut și a bifat
acordul. E condiție de aprindere pe producție.

Textul e al lui Andrei, cuvânt cu cuvânt (refăcut pe 23 septembrie, seara). Stă AICI, într-un
singur loc: ecranul îl primește de la server, iar amprenta lui intră în rândul acordului. Dacă
textul se schimbă vreodată, amprenta se schimbă și acordul se cere din nou.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.errors import DomainError
from codrut.modules.companies.models import CompanyProject, ParticipantProfile
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.practice.alias import codul_omului
from codrut.modules.practice.models import PracticeConsent

LOC_COD = "[codul omului]"

TITLU = "Exersează cu Cody"
PARAGRAFE: tuple[str, ...] = (
    "Cody e un asistent de exersare construit de Andrei Văcaru. Funcționează cu un sistem de "
    "inteligență artificială (serviciul Google, cu datele păstrate în Uniunea Europeană).",
    f"Aici intri sub un cod: {LOC_COD}. Numele tău nu e trimis sistemului AI.",
    "Ce scrii în conversație e trimis sistemului AI, ca să-ți poată răspunde. Nu scrie nume de "
    "colegi, de clienți sau alte date personale.",
    "Conversațiile tale sunt păstrate în aplicație pe durata programului și sunt șterse la "
    "finalul acestuia. Până atunci, în aplicație le poate consulta doar trainerul tău. Poți cere "
    "oricând ștergerea lor mai devreme.",
    "Compania ta nu vede nimic individual, doar rezultate de grup, fără nume.",
)
BIFA = "Am înțeles și vreau să încep."

# Amprenta textului, cu locul codului necompletat: aceeași pentru toată lumea.
AMPRENTA = hashlib.sha256(
    "\n\n".join((TITLU, *PARAGRAFE, BIFA)).encode("utf-8")
).hexdigest()


def paragrafele_pentru(cod: str) -> list[str]:
    return [p.replace(LOC_COD, cod) for p in PARAGRAFE]


async def profilul_in_proiect(
    session: AsyncSession, principal: SessionPrincipal, proiect_id: uuid.UUID
) -> ParticipantProfile:
    """Profilul omului în compania proiectului — aceeași căutare ca la pornirea ședinței."""
    proiect = (await session.execute(
        select(CompanyProject).where(CompanyProject.id == proiect_id)
    )).scalar_one_or_none()
    if proiect is None:
        raise DomainError(f"Proiectul {proiect_id} nu a fost găsit", code="project_not_found")
    profil = (await session.execute(
        select(ParticipantProfile)
        .where(
            ParticipantProfile.company_id == proiect.company_id,
            or_(
                ParticipantProfile.user_id == principal.user_id,
                and_(
                    ParticipantProfile.user_id.is_(None),
                    ParticipantProfile.email == principal.email,
                ),
            ),
        )
        .order_by(ParticipantProfile.user_id.is_(None), ParticipantProfile.created_at)
    )).scalars().first()
    if profil is None:
        raise DomainError("Nu faci parte din acest proiect.", code="participant_not_found")
    return profil


async def are_acord(
    session: AsyncSession, profil_id: uuid.UUID, proiect_id: uuid.UUID
) -> bool:
    """Și-a dat omul acordul, pe proiectul ăsta, pentru textul de AZI?"""
    return (await session.execute(
        select(PracticeConsent.id).where(
            PracticeConsent.participant_profile_id == profil_id,
            PracticeConsent.project_id == proiect_id,
            PracticeConsent.text_hash == AMPRENTA,
        )
    )).first() is not None


async def cere_acordul(
    session: AsyncSession, profil_id: uuid.UUID, proiect_id: uuid.UUID
) -> None:
    """Refuzul serverului: fără acord, nicio ședință. Ecranul ascuns nu e o ușă închisă."""
    if not await are_acord(session, profil_id, proiect_id):
        raise DomainError(
            "Înainte de prima conversație cu Cody trebuie să citești și să bifezi acordul.",
            code="acord_lipsa",
        )


async def starea_acordului(
    session: AsyncSession, principal: SessionPrincipal, proiect_id: uuid.UUID
) -> dict:
    """Ce arată ecranul: textul, cu codul omului în el, și dacă a bifat deja.

    Codul se dă aici, dacă omul nu-l are încă: textul îi spune sub ce cod intră.
    """
    profil = await profilul_in_proiect(session, principal, proiect_id)
    cod = await codul_omului(session, profil)
    return {
        "acordat": await are_acord(session, profil.id, proiect_id),
        "cod": cod,
        "titlu": TITLU,
        "paragrafe": paragrafele_pentru(cod),
        "bifa": BIFA,
        "amprenta": AMPRENTA,
    }


async def da_acordul(
    session: AsyncSession, principal: SessionPrincipal, proiect_id: uuid.UUID, amprenta: str
) -> dict:
    """Omul a bifat. Se ține minte cine, ce proiect, când și ce text (amprenta)."""
    if amprenta != AMPRENTA:
        # omul a văzut alt text decât cel de azi (ecran vechi, deschis de dinainte)
        raise DomainError(
            "Textul acordului s-a schimbat. Reîncarcă pagina și citește-l din nou.",
            code="acord_text_schimbat",
        )
    profil = await profilul_in_proiect(session, principal, proiect_id)
    if not await are_acord(session, profil.id, proiect_id):
        session.add(PracticeConsent(
            participant_profile_id=profil.id,
            project_id=proiect_id,
            text_hash=AMPRENTA,
            accepted_at=datetime.now(UTC),
        ))
        await session.flush()
    return await starea_acordului(session, principal, proiect_id)
