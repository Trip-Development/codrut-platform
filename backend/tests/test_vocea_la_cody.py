"""Vocea lui Andrei stă la Cody, nu la personaj — plicul 135 (măsurat la 134, varianta V1).

De la plicul 112, la role-play cu două apeluri, tot materialul cu vocea lui Andrei (profilul,
filozofia, conversațiile, tonul, mostrele) pleca la ACTOR — adică la omul dificil din scenă — iar
Cody-evaluatorul primea numai teoria. Invers față de ce hotărâse auditorul pe 13 septembrie.
Măsurat la 132 și 134: personajul îl striga pe om „Andrei” și se semna „— Cody”.

Ce se apără aici:

**A.** Feliile: actorul primește numai regulile de comportament; Cody primește tonul, mostrele de
voce și teoria, în ordinea din `CORE_SLOTS`. Profilul, filozofia și conversațiile nu pleacă nicăieri
la role-play. Drumul cu UN apel (strategie, quiz, role-play cu comutatorul stins) rămâne cu tot.

**B.** Pornirea scenei, cu comutatorul aprins, e un singur apel NUMAI la actor, cu promptul
actorului. Până acum se scria cu promptul de un apel — cu tot materialul — deci personajul se
năștea cu vocea lui Andrei și abia apoi o pierdea (găsit la 134). Evaluatorul tot nu se cheamă
acolo (plicul 119). Cu comutatorul stins, nimic nu se schimbă.

**C.** Semnătura „— Cody” de la finalul evaluării se scoate: pe ecran e deja sub numele lui Cody.

Biblioteca nu e în depozit și nici în CI, deci testele își fac una mică, cu câte un fișier pe
felie — altfel verificările de conținut ar trece pe nimic.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from redis.asyncio import Redis

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.practice import prompts
from codrut.modules.practice.generation_provider import (
    GenerationPurpose,
    GenerationRequest,
    GenerationResult,
    LocalGenerationProvider,
)
from codrut.modules.practice.models import SessionKind
from codrut.modules.practice.prompts import (
    COMANDA_DE_PORNIRE,
    CORE_SLOTS,
    FELII,
    get_prompts_pe_meserii,
    get_system_prompt_for_kind,
    scoate_semnatura_cody,
)
from codrut.modules.practice.service import SCENA_CELUILALT, PracticeSessionService
from test_practice_session_flow import create_test_context

LA_NIMENI = ("PROFIL-ANDREI", "FILOZOFIE", "FILOZOFIE-CONVERSATII")
CAP_DOUA_APELURI = "NU ești Cody-ca-profesor"
CAP_UN_APEL = "Ești simultan actor și Cody-ca-profesor."


def _eticheta(felie: str) -> str:
    return f"--- {felie} ---"


@pytest.fixture
def biblioteca(tmp_path: Path) -> str:
    """O bibliotecă mică, cu aceeași formă ca cea adevărată: un fișier pe fiecare felie."""
    miez = tmp_path / "02-pachete" / "comunicare-asertiva-si-feedback" / "00-miez"
    miez.mkdir(parents=True)
    for eticheta, fisiere in CORE_SLOTS:
        for f in fisiere:
            (miez / f).write_text(f"continutul lui {eticheta} din {f}", encoding="utf-8")
    prompts._MATERIAL_CACHE.clear()
    yield str(tmp_path)
    prompts._MATERIAL_CACHE.clear()


# --------------------------------------------------------------------------- A · feliile


def test_feliile_sunt_cele_masurate_la_134() -> None:
    assert FELII["actor"] == ("REGULI-COMPORTAMENT",)
    assert FELII["evaluator"] == ("TON-SI-COMPORTAMENT", "MOSTRE-DE-VOCE", "TEORIA-TEMEI")


def test_actorul_primeste_numai_regulile(biblioteca: str) -> None:
    actor, _ = get_prompts_pe_meserii(name="Ion", history_length=3, biblioteca_path=biblioteca)
    assert _eticheta("REGULI-COMPORTAMENT") in actor
    for felie in (*LA_NIMENI, "TON-SI-COMPORTAMENT", "MOSTRE-DE-VOCE", "TEORIA-TEMEI"):
        assert _eticheta(felie) not in actor, felie


def test_cody_primeste_tonul_si_mostrele_inaintea_teoriei(biblioteca: str) -> None:
    _, evaluator = get_prompts_pe_meserii(
        name="Ion", history_length=3, biblioteca_path=biblioteca
    )
    pozitii = [evaluator.index(_eticheta(f)) for f in FELII["evaluator"]]
    assert pozitii == sorted(pozitii), "partea constantă trebuie să rămână la început"
    for felie in (*LA_NIMENI, "REGULI-COMPORTAMENT"):
        assert _eticheta(felie) not in evaluator, felie


def test_nicio_felie_nu_pleaca_de_doua_ori() -> None:
    assert not set(FELII["actor"]) & set(FELII["evaluator"])


def test_drumul_cu_un_apel_pastreaza_tot_materialul(biblioteca: str) -> None:
    """Strategia, quizul și role-play-ul cu comutatorul stins nu se schimbă."""
    for mod in ("roleplay", "knowledge", "coaching"):
        prompt = get_system_prompt_for_kind(
            mod, name="Ion", history_length=3, biblioteca_path=biblioteca
        )
        for eticheta, _ in CORE_SLOTS:
            assert _eticheta(eticheta) in prompt, (mod, eticheta)


# --------------------------------------------------------------------------- B · pornirea


class FurnizorCuSemnatura(LocalGenerationProvider):
    """Furnizorul local, dar evaluatorul se semnează — ca la 134, în 12 din 16 evaluări."""

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        rez = await super().generate(request)
        if request.purpose == GenerationPurpose.evaluator:
            text = "Ai pasat vina, iar Cody vede asta. [🏆 Scor: 4/10]\n\n— Cody"
            return replace(rez, text=text)
        if request.purpose == GenerationPurpose.actor:
            # scena numai la pornire; salutul și replicile de joc sunt altceva, ca să nu se
            # confunde cu ea în istoricul evaluatorului
            if COMANDA_DE_PORNIRE["roleplay"] in (request.system_instruction or ""):
                return replace(rez, text="**Elena Marin:** Raportul?")
            return replace(rez, text="Salut. Ești gata să începem un joc de rol?")
        return rez


async def _pana_la_pornire(biblioteca: str, doua_apeluri: bool):
    settings = Settings(
        generation_provider="local", practice_two_calls=doua_apeluri, biblioteca_path=biblioteca
    )
    provider = FurnizorCuSemnatura(settings)
    session = SessionLocal()
    ctx = await create_test_context(session)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    service = PracticeSessionService(
        session=session, redis=redis, generation_provider=provider, settings=settings
    )
    sesiune, _ = await service.start_session(
        principal=ctx["principal"], project_id=ctx["project"].id, kind=SessionKind.roleplay
    )
    inainte = len(provider.recorded_requests)
    pornirea = await service.add_participant_turn(
        principal=ctx["principal"], session_id=sesiune.id, text="Da, hai."
    )
    cereri = provider.recorded_requests[inainte:]
    return session, redis, service, ctx, sesiune, provider, pornirea, cereri


@pytest.mark.asyncio
async def test_pornirea_la_doua_apeluri_e_numai_la_actor(biblioteca: str) -> None:
    session, redis, service, ctx, sesiune, provider, pornirea, cereri = await _pana_la_pornire(
        biblioteca, doua_apeluri=True
    )
    try:
        assert len(cereri) == 1, "la pornire evaluatorul nu se cheamă (plicul 119)"
        prompt = cereri[0].system_instruction
        assert cereri[0].purpose == GenerationPurpose.actor
        assert CAP_DOUA_APELURI in prompt and CAP_UN_APEL not in prompt
        assert COMANDA_DE_PORNIRE["roleplay"] in prompt
        for felie in (*LA_NIMENI, "MOSTRE-DE-VOCE", "TON-SI-COMPORTAMENT", "TEORIA-TEMEI"):
            assert _eticheta(felie) not in prompt, felie
        assert _eticheta("REGULI-COMPORTAMENT") in prompt

        # Scena se salvează ca bucata actorului, ca evaluatorul s-o primească la pasul
        # următor drept vorba celuilalt (plicul 118), nu ca propria lui replică.
        assert pornirea.text_actor == "**Elena Marin:** Raportul?"
        assert pornirea.text_evaluator is None

        inainte = len(provider.recorded_requests)
        await service.add_participant_turn(
            principal=ctx["principal"], session_id=sesiune.id, text="Ce anume te-a deranjat?"
        )
        (cerere_evaluator,) = [
            c for c in provider.recorded_requests[inainte:]
            if c.purpose == GenerationPurpose.evaluator
        ]
        ultima = cerere_evaluator.messages[-1]
        assert ultima.role == "user"
        assert SCENA_CELUILALT in ultima.text and "Raportul?" in ultima.text
        assert all(
            "Raportul?" not in m.text for m in cerere_evaluator.messages if m.role == "model"
        )
    finally:
        await session.rollback()
        await session.close()
        await redis.aclose()


@pytest.mark.asyncio
async def test_pornirea_cu_comutatorul_stins_nu_se_schimba(biblioteca: str) -> None:
    session, redis, *_rest, pornirea, cereri = await _pana_la_pornire(
        biblioteca, doua_apeluri=False
    )
    try:
        assert len(cereri) == 1
        prompt = cereri[0].system_instruction
        assert CAP_UN_APEL in prompt
        for eticheta, _ in CORE_SLOTS:
            assert _eticheta(eticheta) in prompt, eticheta
        assert pornirea.text_actor is None and pornirea.text_evaluator is None
    finally:
        await session.rollback()
        await session.close()
        await redis.aclose()


# --------------------------------------------------------------------------- C · semnătura


@pytest.mark.parametrize(
    "semnatura", ["— Cody", "- Cody", "–Cody", "  —   Cody  ", "—Cody"]
)
def test_semnatura_de_la_final_se_scoate(semnatura: str) -> None:
    text = f"Ai pasat vina. [🏆 Scor: 4/10]\n\nCe faci acum?\n\n{semnatura}\n"
    assert scoate_semnatura_cody(text) == "Ai pasat vina. [🏆 Scor: 4/10]\n\nCe faci acum?"


def test_cody_in_mijlocul_textului_ramane() -> None:
    text = "— Cody\nCody îți spune: ai pasat vina.\n\nCe faci acum, Mihai? — Cody știe."
    assert scoate_semnatura_cody(text) == text


def test_evaluarea_fara_semnatura_ramane_identica() -> None:
    text = "Ai pasat vina. [🏆 Scor: 4/10]\n\nCe faci acum?"
    assert scoate_semnatura_cody(text) == text
    assert scoate_semnatura_cody("") == ""


@pytest.mark.asyncio
async def test_aplicatia_salveaza_evaluarea_fara_semnatura(biblioteca: str) -> None:
    session, redis, service, ctx, sesiune, *_rest = await _pana_la_pornire(
        biblioteca, doua_apeluri=True
    )
    try:
        replica = await service.add_participant_turn(
            principal=ctx["principal"], session_id=sesiune.id, text="Păi nu e vina mea."
        )
        assert replica.text_evaluator == "Ai pasat vina, iar Cody vede asta. [🏆 Scor: 4/10]"
        assert not replica.text.rstrip().endswith("Cody")
        assert "iar Cody vede asta" in replica.text
    finally:
        await session.rollback()
        await session.close()
        await redis.aclose()
