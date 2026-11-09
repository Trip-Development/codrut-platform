"""Profesorul are 15 secunde la fiecare replică — plicul 210 (P58, 9 nov).

Măsurat pe live: omul așteaptă cel mai lent dintre actor (2 s) și evaluatorul de pe replică
(46 s, 132,7 s, pe 6 nov 240 s). Limita e numai a evaluatorului de pe replică; raportul de la
închidere rămâne cu limita lui de 120 s.
"""

import asyncio
import time
from unittest.mock import MagicMock

import pytest
from redis.asyncio import Redis

from codrut.contracts.generation import (
    GenerationError,
    GenerationMessage,
    GenerationPurpose,
    GenerationRequest,
)
from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.practice import service as modul_service
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import SessionKind
from codrut.modules.practice.pricing import estimate_pessimistic_cost
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context

LIMITA_DE_TEST = 0.2
DOARME_PREA_MULT = 1.0


def _setari(**altele) -> Settings:
    # `model_copy` ca să putem pune sub minimul de 5 s, fără ca suita să aștepte
    return Settings(generation_provider="local", **altele).model_copy(
        update={"vertex_timeout_evaluator_replica_seconds": LIMITA_DE_TEST}
    )


CERERE = GenerationRequest(
    messages=(GenerationMessage(role="user", text="Salut"),),
    system_instruction="proba",
    purpose=GenerationPurpose.evaluator,
    max_output_tokens=256,
)


class Profesor:
    """Furnizorul local, cu purtarea evaluatorului pusă de test."""

    def __init__(self, settings: Settings, purtare) -> None:
        self._local = LocalGenerationProvider(settings)
        self._purtare = purtare
        self.apeluri_evaluator = 0
        self.cereri_evaluator: list[GenerationRequest] = []
        self.cost_actor = None

    async def generate(self, cerere: GenerationRequest):
        if cerere.purpose != GenerationPurpose.evaluator:
            rezultat = await self._local.generate(cerere)
            self.cost_actor = rezultat.estimated_usd
            return rezultat
        self.apeluri_evaluator += 1
        self.cereri_evaluator.append(cerere)
        await self._purtare(self.apeluri_evaluator)
        return await self._local.generate(cerere)


async def _doarme_apoi_pica(_apel: int) -> None:
    # exact ce face azi depășirea: cererea stă, apoi httpx renunță și iese o eroare
    await asyncio.sleep(DOARME_PREA_MULT)
    raise GenerationError("Vertex AI network request failed", code="vertex_network_error")


def _serviciu(provider, settings) -> PracticeSessionService:
    return PracticeSessionService(
        session=MagicMock(), redis=MagicMock(), generation_provider=provider, settings=settings
    )


@pytest.mark.asyncio
async def test_t1_la_depasire_nu_mai_e_a_doua_incercare(caplog) -> None:
    settings = _setari()
    profesor = Profesor(settings, _doarme_apoi_pica)
    inceput = time.monotonic()

    with caplog.at_level("WARNING"):
        rezultat = await _serviciu(profesor, settings)._evaluatorul(CERERE, "sesiune-test")

    durata = time.monotonic() - inceput
    assert rezultat is None
    assert profesor.apeluri_evaluator == 1
    assert durata < LIMITA_DE_TEST * 2
    assert "motiv=timp" in caplog.text


@pytest.mark.asyncio
async def test_t2_sub_limita_rezultatul_e_neschimbat() -> None:
    async def raspunde(_apel: int) -> None:
        return None

    settings = _setari()
    profesor = Profesor(settings, raspunde)
    rezultat = await _serviciu(profesor, settings)._evaluatorul(CERERE, "sesiune-test")

    assert rezultat is not None
    assert profesor.apeluri_evaluator == 1


@pytest.mark.asyncio
async def test_t3_la_o_eroare_obisnuita_a_doua_incercare_ramane() -> None:
    async def pica_prima_data(apel: int) -> None:
        if apel == 1:
            raise GenerationError("eroare obișnuită", code="vertex_http_error")

    settings = _setari()
    profesor = Profesor(settings, pica_prima_data)
    rezultat = await _serviciu(profesor, settings)._evaluatorul(CERERE, "sesiune-test")

    assert rezultat is not None
    assert profesor.apeluri_evaluator == 2


def test_t4_setarea_are_15_implicit_si_se_citeste_din_mediu(monkeypatch) -> None:
    monkeypatch.delenv("CODRUT_VERTEX_TIMEOUT_EVALUATOR_REPLICA_SECONDS", raising=False)
    assert Settings().vertex_timeout_evaluator_replica_seconds == 15

    monkeypatch.setenv("CODRUT_VERTEX_TIMEOUT_EVALUATOR_REPLICA_SECONDS", "20")
    assert Settings().vertex_timeout_evaluator_replica_seconds == 20


@pytest.mark.asyncio
async def test_t5_apelul_anulat_tot_se_plateste_in_buget(monkeypatch) -> None:
    decontate = []
    decontul_real = modul_service.settle

    async def settle_spion(session, reservation_id, actual_usd):
        decontate.append(actual_usd)
        return await decontul_real(session, reservation_id, actual_usd=actual_usd)

    monkeypatch.setattr(modul_service, "settle", settle_spion)
    settings = _setari(practice_two_calls=True)
    profesor = Profesor(settings, _doarme_apoi_pica)

    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(
            session=session, redis=redis, generation_provider=profesor, settings=settings
        )
        sedinta, _ = await service.start_session(
            principal=ctx["principal"], project_id=ctx["project"].id, kind=SessionKind.roleplay
        )
        # prima replică e confirmarea (numai actorul); a doua cheamă și evaluatorul
        await service.add_participant_turn(
            principal=ctx["principal"], session_id=sedinta.id, text="Da, hai."
        )
        decontate.clear()
        replica = await service.add_participant_turn(
            principal=ctx["principal"], session_id=sedinta.id, text="Replica omului."
        )

        cerere = profesor.cereri_evaluator[-1]
        cuvinte = sum(len(m.text.split()) for m in cerere.messages) + len(
            cerere.system_instruction.split()
        )
        estimare = estimate_pessimistic_cost(
            prompt_tokens=max(1, cuvinte),
            max_output_tokens=settings.vertex_max_output_tokens_evaluator,
            thinking_budget=settings.thinking_budget_evaluator,
            settings=settings,
        )
        assert estimare > 0
        assert decontate == [profesor.cost_actor + estimare]
        assert "Evaluare nelivrată" in replica.text

        await redis.aclose()
        await session.rollback()
