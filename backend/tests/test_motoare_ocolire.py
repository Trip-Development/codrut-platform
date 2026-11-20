"""Ocolirea temporară a motorului care cade la rând — plicul 233. Ceas fals, motoare false."""

from __future__ import annotations

from decimal import Decimal

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


CADE = GenerationError("x", code="vertex_network_error")


def cerere_gresita() -> GenerationError:
    return GenerationError("x", code="vertex_http_error", http_status=400)


def bun(nume: str) -> GenerationResult:
    return GenerationResult(
        text=f"Răspuns de la {nume}.", usage=TokenUsage(), provider=GenerationProviderKey.local,
        model=f"model-{nume}", region="r", finish_reason="STOP", estimated_usd=Decimal("0"),
    )


class Motor:
    def __init__(self, nume: str) -> None:
        self.nume = nume
        self.urmeaza: object = bun(nume)
        self.cereri = 0

    async def generate(self, request):
        self.cereri += 1
        if isinstance(self.urmeaza, BaseException):
            raise self.urmeaza
        return self.urmeaza


class Ceas:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def cerere() -> GenerationRequest:
    return GenerationRequest(messages=(GenerationMessage(role="user", text="Salut."),))


def lant(motoare_, ceas, **setari):
    from codrut.modules.practice import motoare

    return motoare.ComutareMotoare(motoare_, Settings(**setari), ceas=ceas)


async def _cereri(ln, n):
    for _ in range(n):
        await ln.generate(cerere())


async def test_1_trei_caderi_la_rand_ocolesc() -> None:
    a, b, ceas = Motor("a"), Motor("b"), Ceas()
    ln = lant([("a", a), ("b", b)], ceas)
    a.urmeaza = CADE
    await _cereri(ln, 3)
    assert a.cereri == 3 and b.cereri == 3
    r = await ln.generate(cerere())
    assert a.cereri == 3
    assert r.model == "model-b"


async def test_2_dupa_300_s_revine_si_reusita_goleste() -> None:
    from codrut.modules.practice import motoare

    a, b, ceas = Motor("a"), Motor("b"), Ceas()
    ln = lant([("a", a), ("b", b)], ceas)
    a.urmeaza = CADE
    await _cereri(ln, 3)
    ceas.t += 300
    a.urmeaza = bun("a")
    b_inainte = b.cereri
    r = await ln.generate(cerere())
    assert r.model == "model-a"
    assert b.cereri == b_inainte
    assert motoare.STAREA.caderi("a") == 0


async def test_3_dupa_300_s_o_cadere_ocoleste_imediat() -> None:
    a, b, ceas = Motor("a"), Motor("b"), Ceas()
    ln = lant([("a", a), ("b", b)], ceas)
    a.urmeaza = CADE
    await _cereri(ln, 3)
    ceas.t += 300
    await ln.generate(cerere())
    assert a.cereri == 4
    ceas.t += 299
    await ln.generate(cerere())
    assert a.cereri == 4
    ceas.t += 1
    await ln.generate(cerere())
    assert a.cereri == 5


async def test_4_reusita_intre_caderi_goleste_contorul() -> None:
    a, b, ceas = Motor("a"), Motor("b"), Ceas()
    ln = lant([("a", a), ("b", b)], ceas)
    for pas in (CADE, CADE, bun("a"), CADE, CADE):
        a.urmeaza = pas
        await ln.generate(cerere())
    a.urmeaza = bun("a")
    r = await ln.generate(cerere())
    assert r.model == "model-a"
    assert a.cereri == 6


async def test_5_un_400_nu_numara_si_nu_goleste() -> None:
    from codrut.modules.practice import motoare

    a, b, ceas = Motor("a"), Motor("b"), Ceas()
    ln = lant([("a", a), ("b", b)], ceas)
    a.urmeaza = CADE
    await _cereri(ln, 2)
    a.urmeaza = cerere_gresita()
    with pytest.raises(GenerationError):
        await ln.generate(cerere())
    assert motoare.STAREA.caderi("a") == 2
    a.urmeaza = CADE
    await ln.generate(cerere())
    assert motoare.STAREA.e_ocolit("a", ceas())


async def test_6_toate_ocolite_se_incearca_totusi_toate() -> None:
    a, b, c, ceas = Motor("a"), Motor("b"), Motor("c"), Ceas()
    ln = lant([("a", a), ("b", b), ("c", c)], ceas)
    a.urmeaza = CADE
    b.urmeaza = CADE
    c.urmeaza = CADE
    for _ in range(3):
        with pytest.raises(GenerationError):
            await ln.generate(cerere())
    # toate trei ocolite acum; „b” se întoarce, „c” rămâne ocolit
    ordine: list[str] = []
    for m in (a, b, c):
        orig = m.generate

        async def _g(request, _m=m, _o=orig):
            ordine.append(_m.nume)
            return await _o(request)

        m.generate = _g
    c.urmeaza = bun("c")
    r = await ln.generate(cerere())
    assert ordine == ["a", "b", "c"]
    assert r.model == "model-c"


async def test_6b_neocolitele_inaintea_ocolitelor() -> None:
    a, b, c, ceas = Motor("a"), Motor("b"), Motor("c"), Ceas()
    ln = lant([("a", a), ("b", b), ("c", c)], ceas)
    a.urmeaza = CADE
    await _cereri(ln, 3)  # „a” ocolit, „b” răspunde
    ordine: list[str] = []
    for m in (a, b, c):
        orig = m.generate

        async def _g(request, _m=m, _o=orig):
            ordine.append(_m.nume)
            return await _o(request)

        m.generate = _g
    b.urmeaza = CADE
    c.urmeaza = CADE
    with pytest.raises(GenerationError):
        await ln.generate(cerere())
    assert ordine == ["b", "c", "a"]


async def test_7_starea_e_a_procesului() -> None:
    a, b, ceas = Motor("a"), Motor("b"), Ceas()
    a.urmeaza = CADE
    for _ in range(3):
        await lant([("a", a), ("b", b)], ceas).generate(cerere())
    await lant([("a", a), ("b", b)], ceas).generate(cerere())
    assert a.cereri == 3


async def test_8_alte_valori_din_setare() -> None:
    a, b, ceas = Motor("a"), Motor("b"), Ceas()
    ln = lant([("a", a), ("b", b)], ceas, generation_engine_skip_after_failures=1,
              generation_engine_skip_seconds=30)
    a.urmeaza = CADE
    await ln.generate(cerere())
    await ln.generate(cerere())
    assert a.cereri == 1
    ceas.t += 30
    a.urmeaza = bun("a")
    r = await ln.generate(cerere())
    assert r.model == "model-a"
    assert a.cereri == 2
