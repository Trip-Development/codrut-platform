"""Comutarea pe motorul următor — plicul 233 (fișa L5, L5-P1). Numai motoare false, zero rețea."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from codrut.contracts.generation import (
    GenerationError,
    GenerationMessage,
    GenerationProviderKey,
    GenerationPurpose,
    GenerationRequest,
    GenerationResult,
    TokenUsage,
)
from codrut.core.config import Settings


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


def rezultat(nume: str, text: str = "Răspuns bun.", usd: str = "0.001000") -> GenerationResult:
    return GenerationResult(
        text=text,
        usage=TokenUsage(prompt_tokens=10, output_tokens=3),
        provider=GenerationProviderKey.vertex if nume == "a" else GenerationProviderKey.local,
        model=f"model-{nume}",
        region=f"regiune-{nume}",
        finish_reason="STOP",
        estimated_usd=Decimal(usd),
    )


class MotorFals:
    """Întoarce, pe rând, ce e în `pasi` (ultimul se repetă); numără cererile."""

    def __init__(self, *pasi, suporta_audio: bool | None = None) -> None:
        self.pasi = list(pasi)
        self.cereri: list[GenerationRequest] = []
        self.audio: list[bytes] = []
        if suporta_audio is not None:
            self.suporta_audio = suporta_audio

    def _urmatorul(self):
        return self.pasi.pop(0) if len(self.pasi) > 1 else self.pasi[0]

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        self.cereri.append(request)
        pas = self._urmatorul()
        if isinstance(pas, BaseException):
            raise pas
        if callable(pas):
            return await pas()
        return pas

    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str = "audio/webm"):
        self.audio.append(audio_bytes)
        pas = self._urmatorul()
        if isinstance(pas, BaseException):
            raise pas
        return pas


def cerere() -> GenerationRequest:
    return GenerationRequest(
        messages=(GenerationMessage(role="user", text="Bună ziua."),),
        system_instruction="instrucțiune",
        purpose=GenerationPurpose.actor,
    )


def lant(a, b):
    from codrut.modules.practice import motoare

    return motoare.ComutareMotoare([("a", a), ("b", b)], Settings())


async def test_1_primul_raspunde_al_doilea_nu_e_intrebat() -> None:
    ra = rezultat("a")
    a, b = MotorFals(ra), MotorFals(rezultat("b"))
    assert await lant(a, b).generate(cerere()) is ra
    assert len(b.cereri) == 0


def eroare(cod: str, http: int | None = None) -> GenerationError:
    """Construită în test, nu la colectare: pe codul vechi roșul vine din `http_status`."""
    if http is None:
        return GenerationError("x", code=cod)
    return GenerationError("x", code=cod, http_status=http)


COMUTA = [
    ("vertex_rate_limited", 429),
    ("vertex_rate_limited", 503),
    ("vertex_http_error", 500),
    ("vertex_http_error", 502),
    ("vertex_http_error", 503),
    ("vertex_http_error", 504),
    ("vertex_network_error", None),
    ("gol", ""),
    ("gol", "  \n"),
]


@pytest.mark.parametrize("cod,http", COMUTA)
async def test_2_comuta(cod, http) -> None:
    pas = rezultat("a", text=http) if cod == "gol" else eroare(cod, http)
    a, b = MotorFals(pas), MotorFals(rezultat("b"))
    c = cerere()
    r = await lant(a, b).generate(c)
    assert r.model == "model-b"
    assert r.provider == GenerationProviderKey.local
    assert len(a.cereri) == 1 and len(b.cereri) == 1
    assert b.cereri[0] is c


NU_COMUTA = [
    ("vertex_http_error", 400),
    ("vertex_http_error", 401),
    ("vertex_http_error", 403),
    ("vertex_http_error", 404),
    ("vertex_http_error", 422),
    ("vertex_http_error", None),
    ("vertex_invalid_json", None),
    ("vertex_no_candidates", None),
    ("vertex_finish_reason_error", None),
    ("token_acquisition_failed", None),
    ("ValueError", None),
]


@pytest.mark.parametrize("cod,http", NU_COMUTA)
async def test_3_nu_comuta(cod, http) -> None:
    from codrut.modules.practice import motoare

    exc = ValueError("eroare a noastră") if cod == "ValueError" else eroare(cod, http)
    a, b = MotorFals(exc), MotorFals(rezultat("b"))
    with pytest.raises(type(exc)) as prins:
        await lant(a, b).generate(cerere())
    assert prins.value is exc
    assert len(b.cereri) == 0
    assert motoare.STAREA.caderi("a") == 0


async def test_4_toate_cad_se_ridica_ultima_eroare() -> None:
    ea = eroare("vertex_network_error")
    eb = eroare("vertex_rate_limited", 429)
    a, b = MotorFals(ea), MotorFals(eb)
    with pytest.raises(GenerationError) as prins:
        await lant(a, b).generate(cerere())
    assert prins.value is eb
    assert prins.value.code == "vertex_rate_limited"
    assert len(a.cereri) == 1 and len(b.cereri) == 1


async def test_5_anularea_nu_e_cadere() -> None:
    from codrut.modules.practice import motoare

    async def _incet():
        await asyncio.sleep(10)
        return rezultat("a")

    a, b = MotorFals(_incet), MotorFals(rezultat("b"))
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(lant(a, b).generate(cerere()), 0.01)
    assert len(b.cereri) == 0
    assert motoare.STAREA.caderi("a") == 0


async def test_6_costul_raspunsului_gol_se_aduna() -> None:
    a = MotorFals(rezultat("a", text="", usd="0.001000"))
    rb = rezultat("b", usd="0.002000")
    b = MotorFals(rb)
    r = await lant(a, b).generate(cerere())
    assert r.estimated_usd == Decimal("0.003000")
    for camp in ("usage", "model", "provider", "region", "finish_reason", "text"):
        assert getattr(r, camp) == getattr(rb, camp)


async def test_6b_amandoua_goale_se_intoarce_ultimul_cu_costul_adunat() -> None:
    a = MotorFals(rezultat("a", text="", usd="0.001000"))
    b = MotorFals(rezultat("b", text=" ", usd="0.002000"))
    r = await lant(a, b).generate(cerere())
    assert r.model == "model-b"
    assert r.text == " "
    assert r.estimated_usd == Decimal("0.003000")


async def test_7_transcrierea_merge_la_primul_cu_audio() -> None:
    from codrut.modules.practice import motoare

    t = ("text", TokenUsage(), Decimal("0.000040"))
    a, b = MotorFals(t, suporta_audio=False), MotorFals(t)
    assert await lant(a, b).transcribe_audio(b"sunet") == t
    assert a.audio == [] and b.audio == [b"sunet"]

    e = GenerationError("x", code="transcription_failed")
    a2, b2 = MotorFals(e), MotorFals(t)
    with pytest.raises(GenerationError) as prins:
        await lant(a2, b2).transcribe_audio(b"sunet")
    assert prins.value is e
    assert b2.audio == []

    fara = motoare.ComutareMotoare(
        [("a", MotorFals(t, suporta_audio=False)), ("b", MotorFals(t, suporta_audio=False))],
        Settings(),
    )
    with pytest.raises(GenerationError) as niciunul:
        await fara.transcribe_audio(b"sunet")
    assert niciunul.value.code == "transcription_failed"
