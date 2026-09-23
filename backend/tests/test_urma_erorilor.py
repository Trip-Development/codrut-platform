"""Dacă ceva pică pe 28, rămâne o urmă — plicul 140.

Backendul pornește cu `--no-access-log` (și rămâne așa): o cerere care pica nu lăsa NICIO urmă pe
server. Pe 22 septembrie am aflat de ce pica spațiul lui Andrei numai fiindcă am putut reproduce pe
probă; pe 28, în fața oamenilor, n-am fi avut ce citi.

Acum: un rând pe fiecare cerere care NU reușește (4xx, 5xx) și un rând pe fiecare apel spre
model care nu reușește — numai ce trebuie ca să afli ce s-a întâmplat. Niciodată parametri, corp,
anteturi, cookie-uri, adrese de email, nume sau text scris de om.
"""

from __future__ import annotations

import logging
import uuid
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from codrut.contracts.generation import GenerationError, GenerationMessage, GenerationRequest
from codrut.core.config import Settings
from codrut.main import create_app
from codrut.modules.practice import generation_provider as modul
from codrut.modules.practice.generation_provider import VertexGenerationProvider

PERSONAL = ("ionela", "zavoianu", "zăvoianu", "exemplu.example", "@", "scris de om")


def _randuri(caplog, inceput: str) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith(inceput)]


def _fara_date_personale(rand: str) -> None:
    jos = rand.lower()
    for bucata in PERSONAL:
        assert bucata not in jos, f"„{bucata}” în rândul din jurnal: {rand}"
    assert "?" not in rand, f"parametri în rândul din jurnal: {rand}"


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


def test_o_cerere_care_pica_lasa_un_rand(client, caplog) -> None:
    with caplog.at_level(logging.INFO):
        r = client.get("/api/practice/dashboard?email=ionela@exemplu.example&nume=Ionela")
    assert r.status_code >= 400
    randuri = _randuri(caplog, "cerere_esuata")
    assert len(randuri) == 1, randuri
    rand = randuri[0]
    assert "metoda=GET" in rand
    assert "ruta=/api/practice/dashboard" in rand
    assert f"cod={r.status_code}" in rand
    assert f"ref={r.headers['X-Request-ID']}" in rand
    _fara_date_personale(rand)


def test_corpul_cererii_nu_intra_in_rand(client, caplog) -> None:
    with caplog.at_level(logging.INFO):
        r = client.post(
            f"/api/practice/sessions/{uuid.uuid4()}/turns",
            json={"text": "Ionela Zăvoianu a scris de om asta, ionela@exemplu.example"},
        )
    assert r.status_code >= 400
    (rand,) = _randuri(caplog, "cerere_esuata")
    # ruta, nu calea: fără identificatorul ședinței
    assert "ruta=/api/practice/sessions/{session_id}/turns" in rand
    _fara_date_personale(rand)


def test_un_parametru_codat_in_adresa_nu_scapa(client, caplog) -> None:
    """Un parametru de cale scris codat (`%40` în loc de `@`) se înlocuiește tot cu numele lui."""
    with caplog.at_level(logging.INFO):
        r = client.get("/api/practice/projects/ionela%40exemplu.example/room")
    assert r.status_code >= 400
    (rand,) = _randuri(caplog, "cerere_esuata")
    assert "/projects/{project_id}/room" in rand
    _fara_date_personale(rand)
    assert "%40" not in rand


def test_o_cale_necunoscuta_nu_se_scrie(client, caplog) -> None:
    """O cale fără rută poate conține orice a scris cineva în adresă — nu intră în jurnal."""
    with caplog.at_level(logging.INFO):
        r = client.get("/api/nu-exista/ionela@exemplu.example")
    assert r.status_code == 404
    (rand,) = _randuri(caplog, "cerere_esuata")
    assert "ruta=(fara ruta)" in rand
    _fara_date_personale(rand)


def test_codul_erorii_din_domeniu_intra_in_rand(client, caplog) -> None:
    with caplog.at_level(logging.INFO):
        r = client.post("/api/practice/sessions", json={"project_id": "nu-e-uuid"})
    assert r.status_code >= 400
    (rand,) = _randuri(caplog, "cerere_esuata")
    cod = r.json()["error"]["code"]
    assert f"eroare={cod}" in rand


def test_o_cerere_reusita_nu_lasa_niciun_rand(client, caplog) -> None:
    with caplog.at_level(logging.INFO):
        r = client.get("/api/health/live")
    assert r.status_code == 200
    assert _randuri(caplog, "cerere_esuata") == []


# ------------------------------------------------------------------ apelurile spre model


@pytest.mark.asyncio
async def test_un_apel_spre_model_care_pica_lasa_un_rand(monkeypatch, caplog) -> None:
    real = httpx.AsyncClient

    def client_aglomerat(*args, **kwargs):
        return real(
            *args, transport=httpx.MockTransport(lambda req: httpx.Response(429)), **kwargs
        )

    async def fara_pauza(_secunde):
        return None

    monkeypatch.setattr(modul.httpx, "AsyncClient", client_aglomerat)
    monkeypatch.setattr(modul.asyncio, "sleep", fara_pauza)
    cheie = MagicMock()
    cheie.valid = True
    cheie.token = "jeton-de-test"  # noqa: S105
    setari = Settings(
        generation_provider="vertex", vertex_project_id="codrut-cody", vertex_region="eu",
        vertex_actor_model="gemini-3.8-flash", vertex_evaluator_model="gemini-3.8-flash",
    )
    furnizor = VertexGenerationProvider(settings=setari, credentials=cheie)
    with caplog.at_level(logging.INFO), pytest.raises(GenerationError):
        await furnizor.generate(GenerationRequest(
            messages=(GenerationMessage(role="user", text="Ionela Zăvoianu a scris de om"),),
            system_instruction="proba",
        ))
    (rand,) = _randuri(caplog, "model_apel_esuat")
    assert "cod=vertex_rate_limited" in rand
    assert "http=429" in rand
    assert "incercari=3" in rand
    assert "model=gemini-3.8-flash" in rand
    _fara_date_personale(rand)
