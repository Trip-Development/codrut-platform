"""Adaptorul Claude pe Vertex: erorile și lanțul de motoare — plicul 234 (fișa L5, L5-P2).

Aceleași coduri ca motorul Gemini, ca lanțul din 233 să-l folosească fără să știe că e alt
furnizor. Codurile HTTP ale furnizorului sunt după documentația publică, NEVERIFICATE pe contul
nostru. Zero rețea; model și prețuri INVENTATE (prețuri inventate de test, nu prețul real).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from unittest.mock import MagicMock

import httpx
import pytest

from codrut.contracts.generation import (
    GenerationError,
    GenerationMessage,
    GenerationProviderKey,
    GenerationRequest,
    GenerationResult,
    TokenUsage,
)
from codrut.core.config import Settings

TOKEN_FALS = "token-fals-234-erori"  # noqa: S105
# prețuri inventate de test, nu prețul real
PRETURI_INVENTATE = '{"claude-model-de-test": ["3.00", "0.30", "15.00", "15.00"]}'
RASPUNS_BUN = {
    "content": [{"type": "text", "text": "A ajuns."}],
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 10, "output_tokens": 5},
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


@pytest.fixture
def pauze(monkeypatch):
    from codrut.modules.practice import motor_claude_vertex

    inregistrate: list[float] = []

    async def fara_asteptare(secunde: float) -> None:
        inregistrate.append(secunde)

    monkeypatch.setattr(motor_claude_vertex.asyncio, "sleep", fara_asteptare)
    return inregistrate


def setari() -> Settings:
    return Settings(
        generation_provider="vertex",
        vertex_project_id="test-project",
        claude_vertex_model="claude-model-de-test",
        claude_vertex_region="europe-west1",
        prices_by_model=PRETURI_INVENTATE,
    )


def acreditari_false() -> MagicMock:
    a = MagicMock()
    a.valid = True
    a.token = TOKEN_FALS
    return a


def cerere() -> GenerationRequest:
    return GenerationRequest(messages=(GenerationMessage(role="user", text="Salut."),))


def adaptor(client: httpx.AsyncClient):
    from codrut.modules.practice.motor_claude_vertex import ClaudeVertexGenerationProvider

    return ClaudeVertexGenerationProvider(setari(), acreditari_false(), client)


async def ruleaza(pasi: list, cereri: list):
    """Fiecare pas e un cod HTTP, un corp (dict → 200) sau o excepție de rețea."""

    def raspunde(req: httpx.Request) -> httpx.Response:
        cereri.append(req)
        pas = pasi[min(len(cereri) - 1, len(pasi) - 1)]
        if isinstance(pas, BaseException):
            raise pas
        if isinstance(pas, dict):
            return httpx.Response(200, json=pas)
        return httpx.Response(pas, json={"type": "error", "error": {"type": "x"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(raspunde)) as client:
        return await adaptor(client).generate(cerere())


async def test_1_aglomerat_apoi_raspunde(pauze) -> None:
    cereri: list = []
    r = await ruleaza([429, 529, RASPUNS_BUN], cereri)
    assert r.text == "A ajuns."
    assert len(cereri) == 3
    assert pauze == [2.0, 5.0]


@pytest.mark.parametrize("cod", [429, 503, 529])
async def test_2_aglomerat_de_trei_ori(pauze, cod) -> None:
    cereri: list = []
    with pytest.raises(GenerationError) as prins:
        await ruleaza([cod], cereri)
    assert prins.value.code == "vertex_rate_limited"
    assert prins.value.http_status == cod
    assert len(cereri) == 3


@pytest.mark.parametrize("cod", [400, 500])
async def test_3_alte_coduri_o_singura_cerere(pauze, cod) -> None:
    cereri: list = []
    with pytest.raises(GenerationError) as prins:
        await ruleaza([cod], cereri)
    assert prins.value.code == "vertex_http_error"
    assert prins.value.http_status == cod
    assert len(cereri) == 1
    assert pauze == []


@pytest.mark.parametrize("exc", [httpx.ConnectError("x"), httpx.ReadTimeout("x")])
async def test_4_reteaua(pauze, exc) -> None:
    with pytest.raises(GenerationError) as prins:
        await ruleaza([exc], [])
    assert prins.value.code == "vertex_network_error"


async def test_5_corpul_erorii_nu_ajunge_nicaieri(pauze, caplog) -> None:
    from codrut.modules.practice.motor_claude_vertex import ClaudeVertexGenerationProvider

    caplog.set_level(logging.DEBUG)
    text_din_corp = "TEXT-DIN-CORP-SECRET-234"

    def raspunde(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            529,
            json={"type": "error",
                  "error": {"type": "overloaded_error", "message": text_din_corp}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(raspunde)) as client:
        motor = ClaudeVertexGenerationProvider(setari(), acreditari_false(), client)
        with pytest.raises(GenerationError) as prins:
            await motor.generate(cerere())
    assert text_din_corp not in str(prins.value)
    assert text_din_corp not in repr(prins.value.details)
    assert text_din_corp not in caplog.text
    assert TOKEN_FALS not in str(prins.value)
    assert TOKEN_FALS not in caplog.text


COMUTA = [[429], [503], [529], [500], [502], [599],
          [httpx.ConnectError("x")]]
# Corecția 3 a controlorului: fără `content` → `vertex_no_candidates` → NU comută.
NU_COMUTA = [[400], [401], [404], [422], ["json-stricat"],
             [{"stop_reason": "end_turn"}], [{"content": [], "stop_reason": "refusal"}]]


@pytest.mark.parametrize("pasi", COMUTA)
async def test_6_comuta(pauze, pasi) -> None:
    from codrut.modules.practice import motoare

    with pytest.raises(GenerationError) as prins:
        await ruleaza(pasi, [])
    assert motoare.se_comuta(prins.value) is True


@pytest.mark.parametrize("pasi", NU_COMUTA)
async def test_6b_nu_comuta(pauze, pasi) -> None:
    from codrut.modules.practice import motoare

    if pasi == ["json-stricat"]:
        def raspunde(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"{stricat")

        async with httpx.AsyncClient(transport=httpx.MockTransport(raspunde)) as client:
            with pytest.raises(GenerationError) as prins:
                await adaptor(client).generate(cerere())
        assert prins.value.code == "vertex_invalid_json"
    else:
        with pytest.raises(GenerationError) as prins:
            await ruleaza(pasi, [])
    assert motoare.se_comuta(prins.value) is False


class VertexFals:
    """Motorul Gemini fals: dă 429 la scris; transcrie."""

    suporta_audio = True

    def __init__(self) -> None:
        self.audio: list[bytes] = []

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        raise GenerationError("x", code="vertex_rate_limited", http_status=429)

    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str = "audio/webm"):
        self.audio.append(audio_bytes)
        return "transcris", TokenUsage(), Decimal("0.000040")


async def test_7_in_lant_cade_vertex_raspunde_claude(caplog) -> None:
    from codrut.modules.practice import motoare

    caplog.set_level(logging.WARNING, logger="codrut.model")

    def raspunde(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": "Bună"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 54, "output_tokens": 34},
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(raspunde)) as client:
        lant = motoare.ComutareMotoare(
            [("vertex", VertexFals()), ("claude_vertex", adaptor(client))], setari()
        )
        r = await lant.generate(cerere())
    assert r.provider == GenerationProviderKey.claude_vertex
    assert r.model == "claude-model-de-test"
    assert r.estimated_usd == Decimal("0.000672")
    assert ("model_comutare de_la=vertex la=claude_vertex motiv=vertex_rate_limited http=429"
            in caplog.text)


async def test_8_transcrierea_nu_e_a_lui_claude() -> None:
    from codrut.modules.practice import motoare

    cereri: list = []

    def raspunde(req: httpx.Request) -> httpx.Response:
        cereri.append(req)
        return httpx.Response(200, json=RASPUNS_BUN)

    async with httpx.AsyncClient(transport=httpx.MockTransport(raspunde)) as client:
        claude = adaptor(client)
        assert claude.suporta_audio is False
        with pytest.raises(GenerationError) as prins:
            await claude.transcribe_audio(b"sunet")
        assert prins.value.code == "transcription_unsupported"
        assert cereri == []

        vertex = VertexFals()
        lant = motoare.ComutareMotoare([("claude_vertex", claude), ("vertex", vertex)], setari())
        text, _, _ = await lant.transcribe_audio(b"sunet")
    assert text == "transcris"
    assert vertex.audio == [b"sunet"]
    assert cereri == []
