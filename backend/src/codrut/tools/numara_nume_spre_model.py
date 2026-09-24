"""Câte nume de participanți ar pleca spre model — plicul 138, comanda pentru producție.

O scrie chatul Cody, o rulează chatul Aplicației, la repetiția pe copie:

    python -m codrut.tools.numara_nume_spre_model --proiect <uuid-ul proiectului de training>

Ce face, într-o singură tranzacție care se ÎNTOARCE la sfârșit (nu rămâne nimic în bază).
Serviciul aplicației face `commit` în mijlocul fiecărei replici, deci sesiunea e legată de o
tranzacție exterioară: fiecare `commit` al lui devine un punct intermediar, iar la sfârșit
tranzacția întreagă se întoarce.
  1. citește din bază numele participanților activi ai proiectului;
  2. ia primul dintre ei care poate exersa și îi face câte o ședință scurtă de role-play,
     strategie (și quiz, dacă e aprins), cu închidere — prin serviciul aplicației, dar cu
     furnizorul LOCAL: nimic nu pleacă spre Google, se prinde doar ce AR pleca;
  3. numără, în tot textul prins: (a) orice bucată din numele omului folosit la ședințe;
     (b) numele întregi ale tuturor participanților proiectului; (c) funcțiile lor întregi
     (plicul 142).

Nu afișează NICIUN nume. Scrie numai numerele. Ieșire 0 când totul e zero, 3 altfel.
Redis se atinge doar pentru lacătul de generare, de câteva milisecunde, care se eliberează.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.core.config import get_settings
from codrut.core.database import engine
from codrut.modules.companies.models import ParticipantProfile, ProjectMembership
from codrut.modules.identity.models import UserAccountType, UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.identity.terms import CURRENT_TERMS_VERSION
from codrut.modules.practice.alias import _fara_diacritice, _tipar_pentru_nume
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import PracticeProgramSettings, SessionKind
from codrut.modules.practice.service import PracticeSessionService

REPLICI = (
    "Da, hai.",
    "Înțeleg ce spui, dar raportul a întârziat a treia oară și echipa a rămas blocată.",
    "Aș vrea să stabilim împreună un termen clar, pe care să-l putem ține amândoi.",
    "Când se întâmplă asta, eu rămân fără timp pentru restul echipei.",
)


def _textul_prins(provider: LocalGenerationProvider) -> list[str]:
    texte = []
    for cerere in provider.recorded_requests:
        texte.append(cerere.system_instruction or "")
        texte.extend(m.text for m in cerere.messages)
    return [_fara_diacritice(t).lower() for t in texte]


def numara(texte: list[str], nume_om: str, nume_intregi: list[str]) -> tuple[int, int]:
    """(bucăți din numele omului folosit, nume întregi ale participanților) — numai numere."""
    tipar_om = _tipar_pentru_nume(nume_om)
    bucati = sum(len(tipar_om.findall(t)) for t in texte) if tipar_om else 0
    intregi = 0
    for nume in nume_intregi:
        curat = _fara_diacritice((nume or "").strip()).lower()
        if len(curat) < 5 or " " not in curat:
            continue
        tipar = re.compile(rf"(?<![\w]){re.escape(curat)}(?![\w])")
        intregi += sum(len(tipar.findall(t)) for t in texte)
    return bucati, intregi


async def masoara(proiect_id: uuid.UUID) -> tuple[int, int, int, int, int]:
    """(participanți citiți, cereri prinse, bucăți din numele omului, nume întregi, funcții)."""
    settings = get_settings().model_copy(update={"generation_provider": "local"})
    provider = LocalGenerationProvider(settings)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    conn = await engine.connect()
    exterioara = await conn.begin()
    s = AsyncSession(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        membri = (await s.execute(
            select(ParticipantProfile)
            .join(ProjectMembership,
                  ProjectMembership.participant_profile_id == ParticipantProfile.id)
            .where(ProjectMembership.project_id == proiect_id,
                   ProjectMembership.active.is_(True))
        )).scalars().all()
        setari = (await s.execute(
            select(PracticeProgramSettings)
            .where(PracticeProgramSettings.project_id == proiect_id)
        )).scalar_one_or_none()
        # scoase din obiecte ACUM: dupa un rollback, obiectele expira
        oameni = [(p.full_name, p.email, p.user_id) for p in membri]
        nume_intregi = [nume for nume, _, _ in oameni]
        # plicul 142: nici functia nu pleaca spre model
        functii = [p.position for p in membri if p.position]
        feluri = [SessionKind.roleplay, SessionKind.coaching]
        if setari is not None and setari.quiz_enabled:
            feluri.append(SessionKind.knowledge)
        service = PracticeSessionService(
            session=s, redis=redis, generation_provider=provider, settings=settings
        )
        nume_om = ""
        for nume, email, user_id in oameni:
            if not email:
                continue
            principal = SessionPrincipal(
                user_id=user_id or uuid.uuid4(),
                email=email,
                role=UserRole.participant,
                account_type=UserAccountType.registered,
                access_mode="account",
                consent_current=True,
                terms_accepted_at=datetime.now(UTC),
                terms_version=CURRENT_TERMS_VERSION,
                session_token="numara-nume-spre-model",  # noqa: S106 — nu e o parola
            )
            try:
                for fel in feluri:
                    sedinta, _ = await service.start_session(
                        principal=principal, project_id=proiect_id, kind=fel
                    )
                    for replica in REPLICI:
                        await service.add_participant_turn(
                            principal=principal, session_id=sedinta.id, text=replica
                        )
                    await service.end_session(principal=principal, session_id=sedinta.id)
            except Exception:  # noqa: BLE001 — omul ăsta nu poate exersa; următorul
                await s.rollback()
                provider.recorded_requests.clear()
                continue
            nume_om = nume
            break
    finally:
        await s.close()
        await exterioara.rollback()
        await conn.close()
        await redis.aclose()
    texte = _textul_prins(provider)
    bucati, intregi = numara(texte, nume_om, nume_intregi)
    _, functii_gasite = numara(texte, "", functii)
    return len(nume_intregi), len(provider.recorded_requests), bucati, intregi, functii_gasite


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--proiect", type=uuid.UUID, required=True)
    a = ap.parse_args(argv)
    citite, cereri, bucati, intregi, functii = asyncio.run(masoara(a.proiect))
    print(f"participanti cititi: {citite}")
    print(f"cereri spre model prinse (furnizor local, nimic trimis): {cereri}")
    print(f"bucati din numele omului folosit: {bucati}")
    print(f"nume intregi de participanti: {intregi}")
    print(f"functii intregi de participanti (plicul 142): {functii}")
    if cereri == 0:
        print("ATENTIE: nicio cerere prinsa — niciun participant nu a putut exersa.")
        return 2
    return 3 if (bucati or intregi or functii) else 0


if __name__ == "__main__":
    sys.exit(main())
