"""Lista de motoare: setarea și construcția furnizorului — plicul 233 (fișa L5, L5-P1).

Cu un singur motor (implicit), `build_generation_provider` întoarce exact obiectul de azi.
Importurile din codul nou se fac în teste, ca roșul să fie din motivul potrivit.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.oauth2 import service_account
from pydantic import ValidationError

from codrut.contracts.generation import GenerationError
from codrut.core.config import Settings
from codrut.core.errors import DomainError, install_exception_handlers
from codrut.modules.practice.generation_provider import (
    LocalGenerationProvider,
    VertexGenerationProvider,
    build_generation_provider,
)


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
        acreditari.token = "token-fals-233"  # noqa: S105
        return acreditari

    monkeypatch.setattr(
        service_account.Credentials, "from_service_account_file", staticmethod(_din_fisier)
    )
    return str(fisier), citiri


def test_1_valorile_implicite_si_limitele() -> None:
    s = Settings()
    assert s.generation_engines == "vertex"
    assert s.generation_engine_skip_after_failures == 3
    assert s.generation_engine_skip_seconds == 300
    for gresit in ({"generation_engine_skip_after_failures": 0},
                   {"generation_engine_skip_after_failures": 21},
                   {"generation_engine_skip_seconds": 29},
                   {"generation_engine_skip_seconds": 3601}):
        with pytest.raises(ValidationError):
            Settings(**gresit)


@pytest.mark.parametrize("lista", ["vertex", " Vertex "])
def test_2_un_singur_motor_e_obiectul_de_azi(cheie_falsa, lista) -> None:
    cale, citiri = cheie_falsa
    s = Settings(generation_provider="vertex", vertex_credentials_path=cale,
                 generation_engines=lista)
    p = build_generation_provider(s)
    assert type(p) is VertexGenerationProvider
    assert len(citiri) == 1


@pytest.mark.parametrize("lista", ["vertex", "vertex,necunoscut", "", "vertex,vertex"])
def test_3_local_nu_citeste_lista(lista) -> None:
    s = Settings(generation_provider="local", generation_engines=lista)
    assert type(build_generation_provider(s)) is LocalGenerationProvider


@pytest.mark.parametrize("lista", ["vertex,vertex", "vertex,necunoscut", "", ",", "vertex,"])
def test_4_lista_gresita_e_refuzata_inainte_de_cheie(cheie_falsa, lista) -> None:
    from codrut.modules.practice import motoare

    cale, citiri = cheie_falsa
    s = Settings(generation_provider="vertex", vertex_credentials_path=cale,
                 generation_engines=lista)
    with pytest.raises(DomainError) as e1:
        motoare.citeste_lista(s)
    assert e1.value.code == "motoare_invalide"
    with pytest.raises(DomainError) as e2:
        build_generation_provider(s)
    assert e2.value.code == "motoare_invalide"
    assert citiri == []
    if lista == "vertex,necunoscut":
        assert "necunoscut" in e1.value.message
        assert "vertex" not in e1.value.message
        assert cale not in e1.value.message


def test_5_http_status_ramane_in_atribut_nu_in_raspuns() -> None:
    err = GenerationError("x", code="c", http_status=500)
    assert err.http_status == 500
    assert err.details is None
    assert GenerationError("y").http_status is None

    app = FastAPI()
    install_exception_handlers(app)

    @app.get("/cade")
    async def _cade() -> None:
        raise GenerationError("x", code="c", http_status=500)

    raspuns = TestClient(app).get("/cade")
    assert raspuns.json()["error"]["code"] == "c"
    assert "http_status" not in raspuns.text
    assert "500" not in raspuns.text
