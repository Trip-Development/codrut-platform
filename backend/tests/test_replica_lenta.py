"""Plicul 96: o replica buna care vine incet nu mai e aruncata de noi.

La masuratoarea de referinta a plicului 82, 9 replici din 250 au fost pierdute, toate taiate de
aplicatie la 60 de secunde; cea mai lenta replica primita a venit la 80,5 secunde. Pe proba
pragul urca la 120, ca setare a serverului, nu in cod (productia e o hotarare separata).

Fara retea si fara asteptare adevarata: furnizorul prefacut citeste limita pe care aplicatia o
pune cererii si „raspunde la 90 de secunde" — adica taie daca limita e sub 90.
"""

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import yaml

from codrut.contracts.generation import (
    GenerationError,
    GenerationMessage,
    GenerationPurpose,
    GenerationRequest,
)
from codrut.core.config import Settings
from codrut.modules.practice import generation_provider as modul
from codrut.modules.practice.generation_provider import VertexGenerationProvider

RASPUNS_DUPA_SECUNDE = 90
COMPOSE_PROBA = Path(__file__).resolve().parents[2] / "infra" / "test" / "compose.test.yaml"


def _raspunde_incet(req: httpx.Request) -> httpx.Response:
    limita = req.extensions["timeout"]["read"]
    if limita is not None and limita < RASPUNS_DUPA_SECUNDE:
        raise httpx.ReadTimeout("modelul inca scrie", request=req)
    return httpx.Response(200, json={
        "candidates": [{"finishReason": "STOP",
                        "content": {"parts": [{"text": "Replica care a venit greu."}]}}],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
    })


async def _genereaza(monkeypatch, prag: int):
    real = httpx.AsyncClient

    def client_cu_retea_prefacuta(*args, **kwargs):
        return real(*args, transport=httpx.MockTransport(_raspunde_incet), **kwargs)

    # furnizorul isi face singur clientul, cu limita din setari — exact drumul aplicatiei
    monkeypatch.setattr(modul.httpx, "AsyncClient", client_cu_retea_prefacuta)
    cheie = MagicMock()
    cheie.valid = True
    cheie.token = "jeton-de-test"  # noqa: S105
    setari = Settings(
        generation_provider="vertex", vertex_project_id="codrut-cody", vertex_region="eu",
        vertex_actor_model="gemini-3.8-flash", vertex_evaluator_model="gemini-3.8-flash",
        vertex_timeout_seconds=prag,
    )
    furnizor = VertexGenerationProvider(settings=setari, credentials=cheie)
    return await furnizor.generate(GenerationRequest(
        messages=(GenerationMessage(role="user", text="Salut"),),
        system_instruction="proba",
        purpose=GenerationPurpose.actor,
        max_output_tokens=256,
    ))


@pytest.mark.asyncio
async def test_cu_pragul_de_60_replica_de_90_de_secunde_se_pierde(monkeypatch) -> None:
    with pytest.raises(GenerationError) as eroare:
        await _genereaza(monkeypatch, 60)
    assert eroare.value.code == "vertex_network_error"


@pytest.mark.asyncio
async def test_cu_pragul_de_120_replica_de_90_de_secunde_ajunge(monkeypatch) -> None:
    rezultat = await _genereaza(monkeypatch, 120)
    assert rezultat.text == "Replica care a venit greu."


def test_pragul_ajunge_din_setarile_probei_in_container() -> None:
    """compose.test.yaml trece setarea; fara ea, valoarea din .env nu ajunge nicaieri."""
    servicii = yaml.safe_load(COMPOSE_PROBA.read_text(encoding="utf-8"))["services"]
    mediu = servicii["testbackend"]["environment"]
    assert "CODRUT_VERTEX_TIMEOUT_SECONDS" in mediu
