"""Notificarea zilnică a replicii zilei — plicul 252 (L3-P2).

Omul o pornește singur (butonul de pe pagina „O replică pe zi”), alege ora (7–21, ora
României) și o oprește oricând: oprirea ȘTERGE rândul. Serverul trimite, cel mult o dată pe zi,
un mesaj GOL prin serviciul de notificări al telefonului; textul e scris în `public/sw.js`.
Nu pleacă dacă omul a trimis deja replica de azi pe proiect, dacă nu mai are acord, nu mai e
membru activ sau dacă Cody e oprit pe proiect.

Modulul NU importă `replica_zilei.py` (care aduce promptul, ședințele și furnizorul de model):
cheamă direct funcțiile publice `profilul_in_proiect`, `ensure_participant_may_practice`,
`cere_acordul` și `are_acord`, cu aceleași coduri de refuz. În jurnal nu ajunge niciodată
adresa telefonului, id-ul omului sau o cheie.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

import httpx
from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.companies.models import ParticipantProfile, ProjectMembership
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.practice.acord import are_acord, cere_acordul, profilul_in_proiect
from codrut.modules.practice.models import (
    PracticeDailyReminder,
    PracticeDailyReply,
    PracticeProgramSettings,
)
from codrut.modules.practice.policies import ensure_participant_may_practice
from codrut.modules.practice.scoring import ZONA_ROMANIEI, ziua_in_romania
from codrut.modules.practice.web_push import (
    cheile,
    din_b64url,
    gazda_pentru_jurnal,
    gazda_permisa,
    semnatura_vapid,
    trimite_goala,
)

logger = logging.getLogger(__name__)

ORE = tuple(range(7, 22))
CEL_MULT_PE_RULARE = 200
CEL_MULT_TELEFOANE_PE_OM = 10
DEODATA = 2


def _refuz(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


# ---- cheile și „cine trimite” ----


def subiectul(settings: Settings) -> str | None:
    """Adresa aplicației din semnătură: numai `https://…` sau `mailto:…`, fără localhost."""
    subiect = settings.push_vapid_subject or settings.public_app_url
    if not subiect or not (subiect.startswith("https://") or subiect.startswith("mailto:")):
        return None
    if "localhost" in subiect or "127.0.0.1" in subiect:
        return None
    return subiect


def cheia_publica(settings: Settings) -> str | None:
    """Cheia publică, dacă e pusă, are forma bună și „cine trimite” e valid; altfel None."""
    publica = settings.push_vapid_public_key
    if not publica or subiectul(settings) is None:
        return None
    try:
        octeti = din_b64url(publica)
    except (ValueError, TypeError):
        return None
    if len(octeti) != 65 or octeti[0] != 4:
        return None
    return publica


def _vreo_cheie_pusa(settings: Settings) -> bool:
    """Un rând gol în mediu (`${…:-}`) nu e o cheie pusă."""
    privata = settings.push_vapid_private_key
    return bool(settings.push_vapid_public_key) or bool(
        privata is not None and privata.get_secret_value()
    )


def cheile_se_pot_citi(settings: Settings) -> bool:
    """Ambele chei puse, potrivite între ele, și „cine trimite” valid (worker-ul)."""
    privata = settings.push_vapid_private_key
    publica = settings.push_vapid_public_key
    if privata is None or not privata.get_secret_value() or not publica:
        return False
    if subiectul(settings) is None:
        return False
    try:
        cheile(privata.get_secret_value(), publica)
    except (ValueError, TypeError):
        return False
    return True


# ---- omul ----


async def _omul(
    session: AsyncSession, principal: SessionPrincipal, project_id: uuid.UUID
) -> ParticipantProfile:
    """Aceleași verificări ca la replica zilei (`_omul_si_setarile`), cu aceleași coduri."""
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
    return profil


def _verifica_adresa(endpoint: str) -> None:
    if gazda_permisa(endpoint) is None:
        # un singur rând, NUMAI gazda: se vede dacă un telefon folosește altă gazdă
        logger.info("notificarea zilnica: adresa refuzata, gazda %s", gazda_pentru_jurnal(endpoint))
        raise _refuz(422, "notificare_adresa_necunoscuta", "Adresa notificării nu e permisă.")


# ---- rutele ----


async def descrierea(
    session: AsyncSession, principal: SessionPrincipal, project_id: uuid.UUID, settings: Settings
) -> dict:
    await _omul(session, principal, project_id)
    publica = cheia_publica(settings)
    return {"disponibila": publica is not None, "cheie_publica": publica, "ore": list(ORE)}


async def starea(
    session: AsyncSession, principal: SessionPrincipal, project_id: uuid.UUID, endpoint: str
) -> dict:
    profil = await _omul(session, principal, project_id)
    rand = (await session.execute(
        select(PracticeDailyReminder).where(
            PracticeDailyReminder.endpoint == endpoint,
            PracticeDailyReminder.participant_profile_id == profil.id,
            PracticeDailyReminder.project_id == project_id,
        )
    )).scalar_one_or_none()
    if rand is None:
        return {"pornita": False, "ora": None}
    return {"pornita": True, "ora": rand.ora}


async def aboneaza(
    session: AsyncSession,
    principal: SessionPrincipal,
    project_id: uuid.UUID,
    endpoint: str,
    ora: int,
    settings: Settings,
) -> dict:
    profil = await _omul(session, principal, project_id)
    if cheia_publica(settings) is None:
        raise _refuz(503, "notificare_indisponibila", "Notificarea nu e disponibilă.")
    _verifica_adresa(endpoint)
    if ora not in ORE:
        raise _refuz(422, "notificare_ora", "Ora trebuie să fie între 7 și 21.")
    rand = (await session.execute(
        select(PracticeDailyReminder).where(PracticeDailyReminder.endpoint == endpoint)
    )).scalar_one_or_none()
    if rand is None:
        are_deja = (await session.execute(
            select(func.count()).select_from(PracticeDailyReminder).where(
                PracticeDailyReminder.participant_profile_id == profil.id
            )
        )).scalar_one()
        if are_deja >= CEL_MULT_TELEFOANE_PE_OM:
            raise _refuz(422, "notificare_prea_multe", "Prea multe telefoane cu notificarea.")
        session.add(PracticeDailyReminder(
            participant_profile_id=profil.id, project_id=project_id, endpoint=endpoint, ora=ora,
        ))
    else:
        # același telefon: notificarea e a ultimului care a pornit-o, pe proiectul de acum
        rand.participant_profile_id = profil.id
        rand.project_id = project_id
        rand.ora = ora
    await session.flush()
    return {"pornita": True, "ora": ora}


async def opreste(
    session: AsyncSession, principal: SessionPrincipal, project_id: uuid.UUID, endpoint: str
) -> None:
    """Șterge rândul dacă e al omului (pe oricare proiect al lui); altfel nu spune nimic."""
    profil = await _omul(session, principal, project_id)
    await session.execute(
        delete(PracticeDailyReminder).where(
            PracticeDailyReminder.endpoint == endpoint,
            PracticeDailyReminder.participant_profile_id == profil.id,
        )
    )


# ---- cine primește azi și trimiterea ----


def ora_in_romania(acum: datetime) -> int:
    return acum.astimezone(ZONA_ROMANIEI).hour


async def cei_de_anuntat(session: AsyncSession, acum: datetime) -> list[uuid.UUID]:
    """Id-urile rândurilor de anunțat acum (cel mult 200). Ce nu îndeplinește condițiile se sare."""
    azi = ziua_in_romania(acum)
    randuri = (await session.execute(
        select(PracticeDailyReminder.id, PracticeDailyReminder.participant_profile_id,
               PracticeDailyReminder.project_id)
        .join(
            PracticeProgramSettings,
            PracticeProgramSettings.project_id == PracticeDailyReminder.project_id,
        )
        .join(
            ProjectMembership,
            (ProjectMembership.project_id == PracticeDailyReminder.project_id)
            & (ProjectMembership.participant_profile_id
               == PracticeDailyReminder.participant_profile_id),
        )
        .where(
            PracticeDailyReminder.ora == ora_in_romania(acum),
            or_(
                PracticeDailyReminder.ultima_zi_trimisa.is_(None),
                PracticeDailyReminder.ultima_zi_trimisa != azi,
            ),
            PracticeProgramSettings.is_enabled.is_(True),
            ProjectMembership.active.is_(True),
            ~select(PracticeDailyReply.id).where(
                PracticeDailyReply.participant_profile_id
                == PracticeDailyReminder.participant_profile_id,
                PracticeDailyReply.project_id == PracticeDailyReminder.project_id,
                PracticeDailyReply.day == azi,
            ).exists(),
        )
        .order_by(PracticeDailyReminder.created_at, PracticeDailyReminder.id)
        .limit(CEL_MULT_PE_RULARE)
    )).all()
    alesi = []
    for rid, profil_id, project_id in randuri:
        if await are_acord(session, profil_id, project_id):
            alesi.append(rid)
    return alesi


@dataclass(frozen=True)
class _Luat:
    id: uuid.UUID
    endpoint: str


async def _ia_randurile(
    sesiuni: async_sessionmaker[AsyncSession], acum: datetime
) -> list[_Luat]:
    """Ia rândurile, fiecare o singură dată pe zi (UPDATE … RETURNING), apoi ÎNCHIDE sesiunea."""
    azi = ziua_in_romania(acum)
    luate: list[_Luat] = []
    async with sesiuni() as session:
        for rid in await cei_de_anuntat(session, acum):
            endpoint = (await session.execute(
                update(PracticeDailyReminder)
                .where(
                    PracticeDailyReminder.id == rid,
                    or_(
                        PracticeDailyReminder.ultima_zi_trimisa.is_(None),
                        PracticeDailyReminder.ultima_zi_trimisa != azi,
                    ),
                )
                .values(ultima_zi_trimisa=azi)
                .returning(PracticeDailyReminder.endpoint)
            )).scalar_one_or_none()
            await session.commit()
            if endpoint is not None:
                luate.append(_Luat(rid, endpoint))
    return luate


async def trimite_toate(
    settings: Settings,
    acum: datetime,
    sesiuni: async_sessionmaker[AsyncSession],
    client: httpx.AsyncClient,
) -> dict[str, int]:
    """O rulare: ia rândurile, trimite câte două deodată, apoi șterge abonările moarte."""
    gol = {"de_anuntat": 0, "trimise": 0, "sterse": 0, "respinse": 0}
    if not cheile_se_pot_citi(settings):
        if _vreo_cheie_pusa(settings):
            logger.warning("cheile notificarii nu se pot citi")
        return gol
    privata = settings.push_vapid_private_key.get_secret_value()  # type: ignore[union-attr]
    publica = settings.push_vapid_public_key or ""
    subiect = subiectul(settings) or ""
    luate = await _ia_randurile(sesiuni, acum)
    if not luate:
        return gol
    semafor = asyncio.Semaphore(DEODATA)

    async def unul(luat: _Luat) -> str:
        async with semafor:
            if gazda_permisa(luat.endpoint) is None:
                return "sterge"
            try:
                antet = semnatura_vapid(luat.endpoint, privata, publica, subiect, acum)
                cod = await trimite_goala(client, luat.endpoint, antet)
            except (httpx.HTTPError, ValueError):
                return "respinsa"
            if cod in (200, 201, 202):
                return "trimisa"
            if cod in (404, 410):
                return "sterge"
            return "respinsa"

    rezultate = await asyncio.gather(*(unul(luat) for luat in luate))
    de_sters = [luat.id for luat, r in zip(luate, rezultate, strict=True) if r == "sterge"]
    if de_sters:
        async with sesiuni() as session:
            await session.execute(
                delete(PracticeDailyReminder).where(PracticeDailyReminder.id.in_(de_sters))
            )
            await session.commit()
    numere = {
        "de_anuntat": len(luate),
        "trimise": sum(r == "trimisa" for r in rezultate),
        "sterse": len(de_sters),
        "respinse": sum(r == "respinsa" for r in rezultate),
    }
    logger.info(
        "notificarea zilnica de_anuntat=%d trimise=%d sterse=%d respinse=%d",
        numere["de_anuntat"], numere["trimise"], numere["sterse"], numere["respinse"],
    )
    return numere


def anunta_cheile(settings: Settings) -> bool:
    """Rândul de la pornirea worker-ului, fără nicio cheie în el."""
    citibile = cheile_se_pot_citi(settings)
    logger.info("notificarea zilnica: cheile se pot citi: %s", "da" if citibile else "nu")
    if _vreo_cheie_pusa(settings) and not citibile:
        logger.warning("cheile notificarii nu se pot citi")
    return citibile
