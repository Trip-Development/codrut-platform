"""Adaptorul Claude pe Vertex: forma cererii — plicul 234 (fișa L5, L5-P2).

Forma e după documentația publică, NEVERIFICATĂ pe contul nostru (se probează la L5-P3/P4).
Numai `httpx.MockTransport` și acreditări false: zero rețea. Modelul și prețurile sunt
INVENTATE (prețuri inventate de test, nu prețul real). Importurile din codul nou se fac în
teste, ca roșul să fie din motivul potrivit.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock

import httpx
import pytest

from codrut.contracts.generation import (
    GenerationMessage,
    GenerationPurpose,
    GenerationRequest,
)
from codrut.core.config import Settings

TOKEN_FALS = "token-fals-234-cerere"  # noqa: S105
# prețuri inventate de test, nu prețul real
PRETURI_INVENTATE = '{"claude-model-de-test": ["3.00", "0.30", "15.00", "15.00"]}'

RASPUNS_BUN = {
    "content": [{"type": "text", "text": "Bună ziua"}],
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 54, "output_tokens": 34},
}


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


def setari(regiune: str = "europe-west1") -> Settings:
    return Settings(
        generation_provider="vertex",
        vertex_project_id="test-project",
        claude_vertex_model="claude-model-de-test",
        claude_vertex_region=regiune,
        prices_by_model=PRETURI_INVENTATE,
    )


def acreditari_false() -> MagicMock:
    a = MagicMock()
    a.valid = True
    a.token = TOKEN_FALS
    return a


async def trimite(request: GenerationRequest, regiune: str = "europe-west1"):
    from codrut.modules.practice.motor_claude_vertex import ClaudeVertexGenerationProvider

    cereri: list[httpx.Request] = []

    def raspunde(req: httpx.Request) -> httpx.Response:
        cereri.append(req)
        return httpx.Response(200, json=RASPUNS_BUN)

    async with httpx.AsyncClient(transport=httpx.MockTransport(raspunde)) as client:
        motor = ClaudeVertexGenerationProvider(setari(regiune), acreditari_false(), client)
        rezultat = await motor.generate(request)
    assert len(cereri) == 1
    return cereri[0], rezultat


def cerere_simpla(**extra) -> GenerationRequest:
    return GenerationRequest(
        messages=(GenerationMessage(role="user", text="Bună ziua."),),
        system_instruction="Instrucțiune de test.",
        purpose=GenerationPurpose.actor,
        max_output_tokens=512,
        temperature=0.5,
        **extra,
    )


@pytest.mark.parametrize(
    "regiune,adresa",
    [
        (
            "europe-west1",
            "https://europe-west1-aiplatform.googleapis.com/v1/projects/test-project/"
            "locations/europe-west1/publishers/anthropic/models/claude-model-de-test:rawPredict",
        ),
        (
            "eu",
            "https://aiplatform.eu.rep.googleapis.com/v1/projects/test-project/"
            "locations/eu/publishers/anthropic/models/claude-model-de-test:rawPredict",
        ),
    ],
)
async def test_1_adresa_si_metoda(regiune, adresa) -> None:
    req, _ = await trimite(cerere_simpla(), regiune)
    assert req.method == "POST"
    assert str(req.url) == adresa


async def test_2_corpul_are_exact_cheile_cerute() -> None:
    c = cerere_simpla()
    req, _ = await trimite(c)
    corp = json.loads(req.content)
    assert set(corp) == {"anthropic_version", "messages", "max_tokens", "temperature", "system"}
    assert corp["anthropic_version"] == "vertex-2023-10-16"
    assert corp["max_tokens"] == c.max_output_tokens == 512
    assert corp["temperature"] == c.temperature == 0.5
    assert corp["system"] == c.system_instruction
    for interzis in ("model", "thinking", "contents", "generationConfig", "systemInstruction"):
        assert interzis not in corp


async def test_2b_fara_instructiune_nu_exista_system() -> None:
    c = GenerationRequest(messages=(GenerationMessage(role="user", text="Salut."),))
    req, _ = await trimite(c)
    corp = json.loads(req.content)
    assert set(corp) == {"anthropic_version", "messages", "max_tokens", "temperature"}


async def test_3_rolurile_si_textele_neschimbate() -> None:
    texte = (
        "Bună ziua, eu sunt Ioana — șefa de tură.",
        "Aș vrea să vorbim «deschis» despre „termen”.\nAl doilea rând.",
        "Înțeleg; țin minte și ăsta.",
        "Mulțumesc — ne auzim mâine.",
    )
    roluri = ("model", "user", "model", "user")
    c = GenerationRequest(
        messages=tuple(
            GenerationMessage(role=r, text=t) for r, t in zip(roluri, texte, strict=True)
        ),
        system_instruction="Instrucțiune.",
    )
    req, _ = await trimite(c)
    mesaje = json.loads(req.content)["messages"]
    assert [m["role"] for m in mesaje] == ["assistant", "user", "assistant", "user"]
    assert [m["content"] for m in mesaje] == list(texte)
    assert all(set(m) == {"role", "content"} for m in mesaje)
    assert all(isinstance(m["content"], str) for m in mesaje)


async def test_4_antetele_si_tokenul_nu_ajunge_in_jurnal(caplog) -> None:
    caplog.set_level(logging.DEBUG)
    req, _ = await trimite(cerere_simpla())
    assert req.headers["Authorization"] == f"Bearer {TOKEN_FALS}"
    assert req.headers["Content-Type"] == "application/json"
    assert TOKEN_FALS not in caplog.text


async def test_5_gandirea_si_json_nu_se_trimit() -> None:
    fara, _ = await trimite(cerere_simpla())
    cu, _ = await trimite(
        cerere_simpla(thinking_budget=1024, response_mime_type="application/json")
    )
    assert json.loads(cu.content) == json.loads(fara.content)
