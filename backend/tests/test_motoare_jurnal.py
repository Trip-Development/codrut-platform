"""Rândurile din jurnal ale comutării — plicul 233. Nimic din conversație, nici un nume."""

from __future__ import annotations

import re
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

SECRETE = ("INSTRUCTIUNE-SECRETA-233", "Ionela Test-Popovici", "întreabă ceva")


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


def bun(nume: str) -> GenerationResult:
    return GenerationResult(
        text="Răspuns.", usage=TokenUsage(), provider=GenerationProviderKey.local,
        model=f"model-{nume}", region="r", finish_reason="STOP", estimated_usd=Decimal("0"),
    )


class Motor:
    def __init__(self, urmeaza) -> None:
        self.urmeaza = urmeaza

    async def generate(self, request):
        if isinstance(self.urmeaza, BaseException):
            raise self.urmeaza
        return self.urmeaza


def cerere() -> GenerationRequest:
    return GenerationRequest(
        messages=(GenerationMessage(role="user", text="Ionela Test-Popovici întreabă ceva"),),
        system_instruction="INSTRUCTIUNE-SECRETA-233",
        purpose=GenerationPurpose.evaluator,
    )


def lant(a, b):
    from codrut.modules.practice import motoare

    return motoare.ComutareMotoare([("a", a), ("b", b)], Settings())


def _randuri(caplog, inceput: str) -> list[str]:
    return [r.getMessage() for r in caplog.records
            if r.name == "codrut.model" and r.getMessage().startswith(inceput)]


def _fara_secrete(caplog, exc: BaseException | None = None) -> None:
    for r in caplog.records:
        bucati = [r.getMessage(), str(r.args), r.exc_text or ""]
        for s in SECRETE:
            assert all(s not in b for b in bucati)
    if exc is not None:
        assert all(s not in str(exc) for s in SECRETE)


async def test_1_randurile_comutarii_ocolirii_revenirii_si_caderii(caplog) -> None:
    a, b = Motor(GenerationError("x", code="vertex_http_error", http_status=503)), Motor(bun("b"))
    ln = lant(a, b)
    with caplog.at_level("WARNING", logger="codrut.model"):
        await ln.generate(cerere())
        await ln.generate(cerere())
        await ln.generate(cerere())
    com = _randuri(caplog, "model_comutare")
    assert len(com) == 3
    assert re.fullmatch(
        r"model_comutare de_la=a la=b motiv=vertex_http_error http=503 secunde=\d+\.\d "
        r"scop=evaluator", com[0]), com[0]
    oc = _randuri(caplog, "model_ocolit")
    assert oc == ["model_ocolit motor=a caderi=3 secunde_ocolire=300"]

    from codrut.modules.practice import motoare

    motoare.STAREA.goleste()
    caplog.clear()
    a.urmeaza = GenerationError("x", code="vertex_network_error")
    with caplog.at_level("WARNING", logger="codrut.model"):
        await ln.generate(cerere())
    assert re.fullmatch(r"model_comutare de_la=a la=b motiv=vertex_network_error http=- "
                        r"secunde=\d+\.\d scop=evaluator", _randuri(caplog, "model_comutare")[0])

    caplog.clear()
    a.urmeaza = bun("a")
    with caplog.at_level("WARNING", logger="codrut.model"):
        await ln.generate(cerere())
    assert _randuri(caplog, "model_revenit") == ["model_revenit motor=a dupa_caderi=1"]

    caplog.clear()
    a.urmeaza = bun("a")
    gol = GenerationResult(text="", usage=TokenUsage(), provider=GenerationProviderKey.vertex,
                           model="m", region="r", finish_reason="STOP",
                           estimated_usd=Decimal("0"))
    a.urmeaza = gol
    with caplog.at_level("WARNING", logger="codrut.model"):
        await ln.generate(cerere())
    assert "motiv=raspuns_gol http=-" in _randuri(caplog, "model_comutare")[0]

    caplog.clear()
    a.urmeaza = GenerationError("x", code="vertex_network_error")
    b.urmeaza = GenerationError("x", code="vertex_rate_limited", http_status=429)
    with caplog.at_level("WARNING", logger="codrut.model"):
        with pytest.raises(GenerationError):
            await ln.generate(cerere())
    toate = _randuri(caplog, "model_toate_motoarele_au_cazut")
    assert len(toate) == 1
    assert re.fullmatch(r"model_toate_motoarele_au_cazut motoare=a,b motiv=vertex_rate_limited "
                        r"secunde=\d+\.\d scop=evaluator", toate[0]), toate[0]


async def test_2_nimic_din_conversatie_in_jurnal(caplog) -> None:
    a = Motor(GenerationError("x", code="vertex_network_error"))
    b = Motor(GenerationError("x", code="vertex_http_error", http_status=500))
    with caplog.at_level("DEBUG"):
        with pytest.raises(GenerationError) as prins:
            await lant(a, b).generate(cerere())
        b.urmeaza = bun("b")
        await lant(a, b).generate(cerere())
    assert caplog.records
    _fara_secrete(caplog, prins.value)


async def test_3_fara_comutare_fara_randuri(caplog) -> None:
    with caplog.at_level("DEBUG"):
        await lant(Motor(bun("a")), Motor(bun("b"))).generate(cerere())
    assert [r for r in caplog.records if r.name == "codrut.model"] == []
