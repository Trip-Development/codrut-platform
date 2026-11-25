"""Plicul 271: notificarea zilnică scrie în jurnal răspunsul serviciului și rezumatul
fiecărei rulări.


Un rând pe trimitere (gazda, codul, rezultatul, motivul curățat, cel mult 80 de caractere) și un
rând rezumat la fiecare rulare, și cu zero. În jurnal nu ajunge nimic despre om: nici adresa
telefonului (nici bucăți din ea), nici id-uri, nici cheile, nici antetul `Authorization`.
Fără rețea și fără model: serviciul telefonului e un `httpx.MockTransport`.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.practice import notificare_zilnica as nz
from codrut.modules.practice.models import PracticeDailyReminder
from test_notificare_zilnica_api import ADRESA_APLICATIEI, chei_de_test, setari
from test_notificare_zilnica_trimitere import (  # noqa: F401 — tabela_goala e fixture autouse
    IARNA,
    om_cu_notificare,
    randul,
    tabela_goala,
)
from test_replica_zilei_profesor import proiect_legat

BACKEND = Path(__file__).resolve().parents[1]
REZUMAT = "notificarea zilnica de_anuntat="


def jeton() -> str:
    """64 de caractere base64url, ca o adresă Apple adevărată (inventată)."""
    return secrets.token_urlsafe(48)[:64]


async def om_cu_apple(ora: int = 10) -> tuple[dict, PracticeDailyReminder, str]:
    tok = jeton()
    async with SessionLocal() as s:
        ctx = await proiect_legat(s)
        rand = PracticeDailyReminder(
            participant_profile_id=ctx["profile"].id, project_id=ctx["project"].id,
            endpoint=f"https://web.push.apple.com/{tok}", ora=ora,
        )
        s.add(rand)
        await s.commit()
    return ctx, rand, tok


class Apple:
    """Serviciul telefonului, prefăcut: răspunde cu `cod` și `corp` (corpul poate fi o funcție
    de cerere, ca să repete adresa sau antetul primit)."""

    def __init__(self, cod: int = 201, corp=b"", eroare: str | None = None, pe_adresa=None) -> None:
        self.cod, self.corp, self.eroare, self.pe_adresa = cod, corp, eroare, pe_adresa or {}
        self.cereri: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.cereri.append(request)
        if self.eroare is not None:
            mesaj = self.eroare.replace("{url}", str(request.url))
            raise httpx.ConnectError(mesaj, request=request)
        cod = self.pe_adresa.get(str(request.url), self.cod)
        corp = self.corp(request) if callable(self.corp) else self.corp
        if isinstance(corp, str):
            corp = corp.encode("utf-8")
        return httpx.Response(cod, content=corp)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(self), timeout=10, follow_redirects=False
        )


async def ruleaza(serviciu: Apple, settings: Settings | None = None, acum=IARNA):
    async with serviciu.client() as c:
        return await nz.trimite_toate(settings or setari(), acum, SessionLocal, c)


def jurnalul(caplog) -> str:
    return "\n".join(r.getMessage() for r in caplog.records)


def trimiteri(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if "notificarea zilnica: trimitere " in r.getMessage()]


def rezumate(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith(REZUMAT)]


def motivul(rand: str) -> str:
    return rand.split(" motiv=", 1)[1]


def setari_cu_chei() -> tuple[Settings, str, str]:
    privata, publica = chei_de_test()
    s = Settings(
        generation_provider="local", public_app_url=ADRESA_APLICATIEI,
        push_vapid_public_key=publica, push_vapid_private_key=privata,
    )
    return s, privata, publica


@pytest.mark.asyncio
async def test_refuz_apple_403_scrie_gazda_codul_si_motivul(caplog) -> None:
    await om_cu_apple()
    caplog.set_level(logging.DEBUG)
    numere = await ruleaza(Apple(403, b'{"reason":"BadJwtToken"}'))
    [r] = trimiteri(caplog)
    assert r.getMessage() == (
        "notificarea zilnica: trimitere gazda=web.push.apple.com cod=403 rezultat=respinsa "
        'motiv={"reason":"BadJwtToken"}'
    )
    assert r.levelno == logging.WARNING
    assert numere == {"de_anuntat": 1, "trimise": 0, "sterse": 0, "respinse": 1}


@pytest.mark.asyncio
async def test_trimisa_201_scrie_un_rand_cu_motiv_gol(caplog) -> None:
    await om_cu_apple()
    caplog.set_level(logging.DEBUG)
    await ruleaza(Apple(201))
    [r] = trimiteri(caplog)
    assert r.getMessage() == (
        "notificarea zilnica: trimitere gazda=web.push.apple.com cod=201 rezultat=trimisa motiv=-"
    )
    assert r.levelno == logging.INFO


@pytest.mark.asyncio
async def test_motivul_se_taie_la_80(caplog) -> None:
    await om_cu_apple()
    caplog.set_level(logging.DEBUG)
    corp = ("abc def " * 40)[:300]
    await ruleaza(Apple(400, corp))
    [r] = trimiteri(caplog)
    assert len(motivul(r.getMessage())) == 80


@pytest.mark.asyncio
async def test_adresa_intreaga_si_cheia_nu_ajung_in_jurnal(caplog) -> None:
    ctx, rand, tok = await om_cu_apple()
    settings, privata, publica = setari_cu_chei()
    antete: list[str] = []

    def corp_rau(request: httpx.Request) -> str:
        antet = request.headers["Authorization"]
        antete.append(antet)
        return json.dumps({
            "reason": "BadJwtToken", "url": str(request.url), "tok": tok,
            "auth": antet, "k": publica, "alt": "https://alt.example/x",
        })

    caplog.set_level(logging.DEBUG)
    await ruleaza(Apple(400, corp_rau), settings)
    [r] = trimiteri(caplog)
    assert " cod=400 " in r.getMessage()
    jurnal = jurnalul(caplog)
    [antet] = antete
    bucata_t = re.search(r"t=([^,\s]+)", antet).group(1)
    for interzis in (
        rand.endpoint, tok, "web.push.apple.com/", publica, privata, bucata_t,
        str(ctx["profile"].id), str(ctx["project"].id), str(rand.id), "alt.example",
    ):
        assert interzis not in jurnal, interzis
    assert "vapid" not in jurnal.lower()


@pytest.mark.asyncio
async def test_jetonul_de_la_margine_nu_ajunge_in_jurnal(caplog) -> None:
    """Corecția 3: jetonul tăiat la margine și adresa scrisă `https:\\/\\/…` (JSON)."""
    caplog.set_level(logging.DEBUG)
    _, _, tok1 = await om_cu_apple()
    await ruleaza(Apple(400, lambda req: " " * 500 + req.url.path.lstrip("/")))
    _, _, tok2 = await om_cu_apple()
    await ruleaza(Apple(400, lambda req: str(req.url).replace("/", "\\/")))
    randuri = trimiteri(caplog)
    assert len(randuri) == 2 and all(" cod=400 " in r.getMessage() for r in randuri)
    jurnal = jurnalul(caplog)
    assert tok1[:16] not in jurnal
    assert tok2[:16] not in jurnal
    assert "web.push.apple.com\\/" not in jurnal


@pytest.mark.asyncio
async def test_eroare_de_retea_scrie_numai_numele_erorii(caplog) -> None:
    _, _, tok = await om_cu_apple()
    caplog.set_level(logging.DEBUG)
    await ruleaza(Apple(eroare="nu merge {url}"))
    [r] = trimiteri(caplog)
    assert r.getMessage().endswith(" cod=eroare rezultat=respinsa motiv=ConnectError")
    assert tok not in jurnalul(caplog)


@pytest.mark.asyncio
async def test_rezumat_si_cand_nu_e_nimeni_de_anuntat(caplog) -> None:
    caplog.set_level(logging.DEBUG)
    assert await ruleaza(Apple()) == {"de_anuntat": 0, "trimise": 0, "sterse": 0, "respinse": 0}
    assert rezumate(caplog) == ["notificarea zilnica de_anuntat=0 trimise=0 sterse=0 respinse=0"]


@pytest.mark.asyncio
async def test_rezumat_si_fara_chei(caplog) -> None:
    await om_cu_apple()
    caplog.set_level(logging.DEBUG)
    serviciu = Apple()
    await ruleaza(serviciu, setari(cu_chei=False))
    assert serviciu.cereri == []
    assert rezumate(caplog) == ["notificarea zilnica de_anuntat=0 trimise=0 sterse=0 respinse=0"]


async def trei_randuri() -> tuple[Apple, PracticeDailyReminder]:
    _, a1, _ = await om_cu_apple()
    _, a2, _ = await om_cu_apple()
    _, g = await om_cu_notificare(10)
    return Apple(pe_adresa={a1.endpoint: 201, a2.endpoint: 410, g.endpoint: 500}), a2


@pytest.mark.asyncio
async def test_un_rand_pe_trimitere_si_un_singur_rezumat(caplog) -> None:
    serviciu, _ = await trei_randuri()
    caplog.set_level(logging.DEBUG)
    await ruleaza(serviciu)
    randuri = [r.getMessage() for r in trimiteri(caplog)]
    assert sorted(re.search(r"rezultat=(\w+)", m).group(1) for m in randuri) == [
        "respinsa", "sterge", "trimisa",
    ]
    assert rezumate(caplog) == ["notificarea zilnica de_anuntat=3 trimise=1 sterse=1 respinse=1"]


def test_jurnalul_workerului_iese_pe_stderr() -> None:
    cod = (
        "import asyncio, logging\n"
        "from codrut.workers import main as w\n"
        "asyncio.run(w.WorkerSettings.on_startup({}))\n"
        "logging.getLogger('codrut.modules.practice.notificare_zilnica').info('proba 271')\n"
        "r = logging.getLogger()\n"
        "print(len(r.handlers), logging.getLevelName(r.level),"
        " logging.getLogger('httpx').isEnabledFor(logging.INFO))\n"
    )
    iesire = subprocess.run(  # noqa: S603 - python-ul testelor și cod scris aici
        [sys.executable, "-c", cod], cwd=BACKEND, env=os.environ.copy(),
        capture_output=True, text=True, timeout=120,
    )
    assert iesire.returncode == 0, iesire.stderr
    assert iesire.stderr.count("notificarea zilnica: cheile se pot citi:") == 1, iesire.stderr
    assert iesire.stderr.count("proba 271") == 1, iesire.stderr
    assert iesire.stdout.strip().splitlines()[-1] == "0 WARNING False"


@pytest.mark.asyncio
async def test_paza_refuzul_nu_schimba_numerele_si_randul_ramane() -> None:
    _, rand, _ = await om_cu_apple()
    serviciu = Apple(403, b'{"reason":"BadJwtToken"}')
    assert await ruleaza(serviciu) == {"de_anuntat": 1, "trimise": 0, "sterse": 0, "respinse": 1}
    ramas = await randul(rand.id)
    assert ramas is not None and ramas.ultima_zi_trimisa == IARNA.date()
    assert len(serviciu.cereri) == 1


@pytest.mark.asyncio
async def test_paza_trimite_goala_intoarce_tot_codul() -> None:
    from codrut.modules.practice import web_push

    async with Apple(201).client() as c:
        adresa = f"https://web.push.apple.com/{jeton()}"
        cod = await web_push.trimite_goala(c, adresa, "vapid t=x, k=y")
    assert cod == 201 and type(cod) is int


@pytest.mark.asyncio
async def test_paza_jurnalul_stricat_nu_schimba_trimiterea(monkeypatch) -> None:
    def stricat(*_a, **_k):
        raise RuntimeError("jurnal stricat")

    monkeypatch.setattr(nz, "motiv_pentru_jurnal", stricat, raising=False)
    serviciu, a410 = await trei_randuri()
    assert await ruleaza(serviciu) == {"de_anuntat": 3, "trimise": 1, "sterse": 1, "respinse": 1}
    assert await randul(a410.id) is None
