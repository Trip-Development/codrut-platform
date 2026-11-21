"""Adaptorul Claude pe Vertex: citirea răspunsului — plicul 234 (fișa L5, L5-P2).

Forma răspunsului e după documentația publică, NEVERIFICATĂ pe contul nostru. Zero rețea;
model și prețuri INVENTATE (prețuri inventate de test, nu prețul real).
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import httpx
import pytest

from codrut.contracts.generation import (
    GenerationError,
    GenerationMessage,
    GenerationProviderKey,
    GenerationRequest,
    TokenUsage,
)
from codrut.core.config import Settings
from codrut.modules.practice.pricing import estimate_cost

# prețuri inventate de test, nu prețul real
PRETURI_INVENTATE = '{"claude-model-de-test": ["3.00", "0.30", "15.00", "15.00"]}'


@pytest.fixture(autouse=True)
def _starea_goala():
    try:
        from codrut.modules.practice import motoare
    except ImportError:  # codul vechi: roșul îl dă testul, nu pregătirea
        yield
        return
    motoare.STAREA.goleste()
    yield
    motoare.STAREA.goleste()


def setari() -> Settings:
    return Settings(
        generation_provider="vertex",
        vertex_project_id="test-project",
        claude_vertex_model="claude-model-de-test",
        claude_vertex_region="europe-west1",
        prices_by_model=PRETURI_INVENTATE,
    )


async def genereaza(corp=None, *, continut_brut: bytes | None = None):
    from codrut.modules.practice.motor_claude_vertex import ClaudeVertexGenerationProvider

    def raspunde(req: httpx.Request) -> httpx.Response:
        if continut_brut is not None:
            return httpx.Response(200, content=continut_brut)
        return httpx.Response(200, json=corp)

    acreditari = MagicMock()
    acreditari.valid = True
    acreditari.token = "token-fals-234-raspuns"  # noqa: S105
    async with httpx.AsyncClient(transport=httpx.MockTransport(raspunde)) as client:
        motor = ClaudeVertexGenerationProvider(setari(), acreditari, client)
        return await motor.generate(
            GenerationRequest(messages=(GenerationMessage(role="user", text="Salut."),))
        )


async def test_1_raspunsul_bun() -> None:
    r = await genereaza({
        "content": [{"type": "text", "text": "Bună"}, {"type": "text", "text": " ziua"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 54, "output_tokens": 34},
    })
    assert r.text == "Bună ziua"
    assert r.finish_reason == "STOP"
    assert r.usage == TokenUsage(54, 34, 0, 0)
    assert r.provider == GenerationProviderKey.claude_vertex
    assert r.model == "claude-model-de-test"
    assert r.region == "europe-west1"
    assert r.estimated_usd == Decimal("0.000672")
    assert r.estimated_usd == estimate_cost(r.usage, setari(), model="claude-model-de-test")


@pytest.mark.parametrize("stop,asteptat", [("end_turn", "STOP"), ("stop_sequence", "STOP"),
                                           ("max_tokens", "MAX_TOKENS")])
async def test_2_opririle_bune(stop, asteptat) -> None:
    r = await genereaza({"content": [{"type": "text", "text": "x"}], "stop_reason": stop,
                         "usage": {"input_tokens": 1, "output_tokens": 1}})
    assert r.finish_reason == asteptat


@pytest.mark.parametrize("stop", ["refusal", "tool_use", "pause_turn", None])
async def test_2b_alte_opriri_sunt_eroare(stop) -> None:
    corp = {"content": [{"type": "text", "text": "x"}], "usage": {}}
    if stop is not None:
        corp["stop_reason"] = stop
    with pytest.raises(GenerationError) as prins:
        await genereaza(corp)
    assert prins.value.code == "vertex_finish_reason_error"
    # mesajul are numai valoarea lui stop_reason, nimic din răspuns
    assert prins.value.message == f"Generation did not finish normally: {stop or ''}"


async def test_3_jetoanele_cu_cache() -> None:
    r = await genereaza({
        "content": [{"type": "text", "text": "x"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 54, "cache_read_input_tokens": 100,
                  "cache_creation_input_tokens": 10, "output_tokens": 34},
    })
    assert r.usage.prompt_tokens == 164
    assert r.usage.cached_tokens == 100
    assert r.usage.output_tokens == 34
    assert r.usage.thought_tokens == 0


async def test_4_numai_blocurile_text() -> None:
    r = await genereaza({
        "content": [{"type": "thinking", "thinking": "GANDIRE-ASCUNSA"},
                    {"type": "text", "text": "Vizibil."}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    })
    assert r.text == "Vizibil."


async def test_4b_continut_gol_e_text_gol_fara_eroare() -> None:
    r = await genereaza({"content": [], "stop_reason": "end_turn",
                         "usage": {"input_tokens": 1, "output_tokens": 0}})
    assert r.text == ""


@pytest.mark.parametrize("corp", [
    {"stop_reason": "end_turn", "usage": {}},
    {"content": "text", "stop_reason": "end_turn"},
    {"content": None, "stop_reason": "end_turn"},
    ["nu", "e", "obiect"],
])
async def test_4c_fara_content_lista(corp) -> None:
    with pytest.raises(GenerationError) as prins:
        await genereaza(corp)
    assert prins.value.code == "vertex_no_candidates"


async def test_5_corp_care_nu_e_json() -> None:
    with pytest.raises(GenerationError) as prins:
        await genereaza(continut_brut=b"<html>nu e json</html>")
    assert prins.value.code == "vertex_invalid_json"
