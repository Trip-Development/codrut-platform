"""Adaptorul Claude pe Vertex: setarea și pornirea — plicul 234 (fișa L5, L5-P2).

Numele modelului, regiunea și prețul NU au valoare implicită: fără ele motorul nu pornește,
nici din greșeală. Model și prețuri INVENTATE (prețuri inventate de test, nu prețul real).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from google.oauth2 import service_account

from codrut.core.config import Settings
from codrut.core.errors import DomainError
from codrut.modules.practice.generation_provider import (
    VertexGenerationProvider,
    build_generation_provider,
)

# prețuri inventate de test, nu prețul real
PRETURI_INVENTATE = '{"claude-model-de-test": ["3.00", "0.30", "15.00", "15.00"]}'

REGIUNI_UE = ["eu", "europe-west1", "europe-west3", "europe-west4", "europe-west8",
              "europe-west9", "europe-west10", "europe-west12", "europe-north1",
              "europe-central2", "europe-southwest1"]
REGIUNI_IN_AFARA = ["europe-west2", "europe-west6", "us-east5", "global", "europe",
                    "asia-southeast1"]


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
def cheie_falsa(tmp_path, monkeypatch):
    """Fișierul de cheie există, dar se citește printr-un înlocuitor; numărăm citirile."""
    fisier = tmp_path / "cheie-falsa.json"
    fisier.write_text("{}", encoding="utf-8")
    citiri: list[str] = []

    def _din_fisier(cale, scopes=None):
        citiri.append(cale)
        acreditari = MagicMock()
        acreditari.valid = True
        acreditari.token = "token-fals-234-setare"  # noqa: S105
        return acreditari

    monkeypatch.setattr(
        service_account.Credentials, "from_service_account_file", staticmethod(_din_fisier)
    )
    return str(fisier), citiri


def setari(cale: str, motoare_lista: str = "vertex,claude_vertex", **extra) -> Settings:
    valori = {
        "claude_vertex_model": "claude-model-de-test",
        "claude_vertex_region": "europe-west1",
        "prices_by_model": PRETURI_INVENTATE,
    }
    valori.update(extra)
    return Settings(generation_provider="vertex", vertex_credentials_path=cale,
                    generation_engines=motoare_lista, **valori)


def neconfigurat(s: Settings) -> DomainError:
    with pytest.raises(DomainError) as prins:
        build_generation_provider(s)
    assert prins.value.code == "claude_vertex_neconfigurat"
    return prins.value


def test_1_implicit_nimic_nu_se_schimba(cheie_falsa) -> None:
    s = Settings()
    assert s.claude_vertex_model == ""
    assert s.claude_vertex_region == ""
    assert s.generation_engines == "vertex"
    cale, _ = cheie_falsa
    p = build_generation_provider(Settings(generation_provider="vertex",
                                           vertex_credentials_path=cale))
    assert type(p) is VertexGenerationProvider


@pytest.mark.parametrize("lista", ["vertex,claude_vertex", "claude_vertex"])
def test_2_campurile_goale_opresc_pornirea(cheie_falsa, lista) -> None:
    cale, _ = cheie_falsa
    e = neconfigurat(setari(cale, lista, claude_vertex_model="", claude_vertex_region=""))
    assert "claude_vertex_model" in e.message and "claude_vertex_region" in e.message
    assert cale not in e.message

    e = neconfigurat(setari(cale, lista, claude_vertex_model=""))
    assert "claude_vertex_model" in e.message
    assert "claude_vertex_region" not in e.message
    assert "europe-west1" not in e.message

    e = neconfigurat(setari(cale, lista, claude_vertex_region=""))
    assert "claude_vertex_region" in e.message
    assert "claude-model-de-test" not in e.message


@pytest.mark.parametrize("regiune", REGIUNI_IN_AFARA)
def test_2b_regiunea_in_afara_ue(cheie_falsa, regiune) -> None:
    cale, _ = cheie_falsa
    e = neconfigurat(setari(cale, claude_vertex_region=regiune))
    assert "UE" in e.message


@pytest.mark.parametrize("preturi", [
    "",
    "nu e json",
    '{"alt-model": ["3.00", "0.30", "15.00", "15.00"]}',
    '{"claude-model-de-test": ["3.00", "0.30", "15.00"]}',
    '{"claude-model-de-test": ["3.00", "0.30", "15.00", "15.00", "1"]}',
    '{"claude-model-de-test": ["3.00", "abc", "15.00", "15.00"]}',
    '{"claude-model-de-test": ["3.00", null, "15.00", "15.00"]}',
    '{"claude-model-de-test": ["3.00", true, "15.00", "15.00"]}',
    '{"claude-model-de-test": ["3.00", "NaN", "15.00", "15.00"]}',
    '{"claude-model-de-test": "3.00"}',
    '["claude-model-de-test"]',
])
def test_2c_fara_pret_bun_nu_porneste(cheie_falsa, preturi) -> None:
    cale, _ = cheie_falsa
    neconfigurat(setari(cale, prices_by_model=preturi))


def test_3_configurat_complet_ordinea_din_lista(cheie_falsa) -> None:
    from codrut.modules.practice import motoare
    from codrut.modules.practice.motor_claude_vertex import ClaudeVertexGenerationProvider

    cale, citiri = cheie_falsa
    p = build_generation_provider(setari(cale, "vertex,claude_vertex"))
    assert type(p) is motoare.ComutareMotoare
    assert [n for n, _ in p._motoare] == ["vertex", "claude_vertex"]
    assert [type(m) for _, m in p._motoare] == [VertexGenerationProvider,
                                                ClaudeVertexGenerationProvider]
    assert len(citiri) == 1

    p = build_generation_provider(setari(cale, "claude_vertex,vertex"))
    assert [n for n, _ in p._motoare] == ["claude_vertex", "vertex"]
    assert [type(m) for _, m in p._motoare] == [ClaudeVertexGenerationProvider,
                                                VertexGenerationProvider]

    p = build_generation_provider(setari(cale, "claude_vertex"))
    assert type(p) is ClaudeVertexGenerationProvider
    assert len(citiri) == 3  # o citire pe construcție


@pytest.mark.parametrize("regiune", REGIUNI_UE)
def test_4_regiunile_admise(cheie_falsa, regiune) -> None:
    from codrut.modules.practice.motor_claude_vertex import ClaudeVertexGenerationProvider

    cale, _ = cheie_falsa
    p = build_generation_provider(setari(cale, "claude_vertex", claude_vertex_region=regiune))
    assert type(p) is ClaudeVertexGenerationProvider
