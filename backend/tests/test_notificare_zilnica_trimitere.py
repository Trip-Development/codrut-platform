"""Notificarea zilnică: cine primește și trimiterea — plicul 252 (L3-P2), §6.2.

Numai `httpx.MockTransport`: nicio cerere nu iese din proces. Un test pune
`build_generation_provider` să ridice, ca dovadă că nimic de aici nu cheamă modelul.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from sqlalchemy import delete, select

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.companies.models import CompanyProject, CompanyProjectStatus
from codrut.modules.practice import notificare_zilnica as nz
from codrut.modules.practice.models import (
    PracticeConsent,
    PracticeDailyReminder,
    PracticeDailyReply,
    PracticeDailySituation,
)
from codrut.modules.practice.web_push import din_b64url
from test_notificare_zilnica_api import ADRESA_APLICATIEI, chei_de_test, setari
from test_replica_zilei_profesor import proiect_legat

IARNA = datetime(2026, 1, 14, 8, 5, tzinfo=UTC)  # 10:05 în România
VARA = datetime(2026, 7, 15, 7, 5, tzinfo=UTC)  # 10:05 în România


@pytest.fixture(autouse=True)
async def tabela_goala():
    async with SessionLocal() as s:
        await s.execute(delete(PracticeDailyReminder))
        await s.commit()
    yield
    async with SessionLocal() as s:
        await s.execute(delete(PracticeDailyReminder))
        await s.commit()


class Serviciu:
    """Serviciul telefonului, prefăcut: ține minte cererile și răspunde cu codul cerut."""

    def __init__(self, cod: int | None = 201, eroare: bool = False) -> None:
        self.cod, self.eroare, self.cereri = cod, eroare, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.cereri.append(request)
        if self.eroare:
            raise httpx.ConnectError("fara retea", request=request)
        if self.cod == 301:
            return httpx.Response(301, headers={"Location": "https://rau.example/x"})
        return httpx.Response(self.cod)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.MockTransport(self), timeout=10, follow_redirects=False
        )


def adresa() -> str:
    return f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}"


async def om_cu_notificare(ora: int = 10, **kw) -> tuple[dict, PracticeDailyReminder]:
    async with SessionLocal() as s:
        ctx = await proiect_legat(s, **kw)
        rand = PracticeDailyReminder(
            participant_profile_id=ctx["profile"].id, project_id=ctx["project"].id,
            endpoint=adresa(), ora=ora,
        )
        s.add(rand)
        await s.commit()
    return ctx, rand


async def ruleaza(serviciu: Serviciu, acum: datetime, settings: Settings | None = None):
    async with serviciu.client() as c:
        return await nz.trimite_toate(settings or setari(), acum, SessionLocal, c)


async def randul(rid) -> PracticeDailyReminder | None:
    async with SessionLocal() as s:
        return await s.get(PracticeDailyReminder, rid)


async def replica_de_azi(profil_id, project_id, zi) -> None:
    async with SessionLocal() as s:
        situatie = (await s.execute(select(PracticeDailySituation.id).limit(1))).scalar_one()
        s.add(PracticeDailyReply(
            participant_profile_id=profil_id, project_id=project_id, situation_id=situatie,
            day=zi, reply_text="Ceva.", teacher_text="Bine.",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        ))
        await s.commit()


@pytest.mark.asyncio
async def test_numai_ora_potrivita_primeste_o_cerere(monkeypatch) -> None:
    import codrut.modules.practice.generation_provider as gp

    def nu(*_a, **_k):
        raise AssertionError("modelul nu are ce căuta aici")

    monkeypatch.setattr(gp, "build_generation_provider", nu)
    _, zece = await om_cu_notificare(10)
    await om_cu_notificare(9)
    await om_cu_notificare(11)
    serviciu = Serviciu()
    numere = await ruleaza(serviciu, IARNA)
    assert [str(r.url) for r in serviciu.cereri] == [zece.endpoint]
    assert numere == {"de_anuntat": 1, "trimise": 1, "sterse": 0, "respinse": 0}


@pytest.mark.asyncio
async def test_o_data_pe_zi_si_a_doua_zi_din_nou() -> None:
    _, rand = await om_cu_notificare(10)
    serviciu = Serviciu()
    await ruleaza(serviciu, IARNA)
    await ruleaza(serviciu, IARNA + timedelta(minutes=10))
    assert len(serviciu.cereri) == 1
    await ruleaza(serviciu, IARNA + timedelta(days=1))
    assert len(serviciu.cereri) == 2
    assert (await randul(rand.id)).ultima_zi_trimisa == (IARNA + timedelta(days=1)).date()


@pytest.mark.asyncio
async def test_doua_rulari_deodata_pe_acelasi_rand_dau_o_singura_cerere() -> None:
    await om_cu_notificare(10)
    serviciu = Serviciu()
    async with serviciu.client() as c1, serviciu.client() as c2:
        await asyncio.gather(
            nz.trimite_toate(setari(), IARNA, SessionLocal, c1),
            nz.trimite_toate(setari(), IARNA, SessionLocal, c2),
        )
    assert len(serviciu.cereri) == 1


@pytest.mark.asyncio
async def test_replica_de_azi_pe_proiect_opreste_notificarea_alt_proiect_nu() -> None:
    ctx, rand = await om_cu_notificare(10)
    async with SessionLocal() as s:
        alt = CompanyProject(
            company_id=ctx["company"].id, name=f"Alt proiect {uuid.uuid4().hex[:6]}",
            project_type="training", status=CompanyProjectStatus.active,
        )
        s.add(alt)
        await s.commit()
    await replica_de_azi(ctx["profile"].id, alt.id, IARNA.date())
    serviciu = Serviciu()
    await ruleaza(serviciu, IARNA)
    assert len(serviciu.cereri) == 1
    ctx2, _ = await om_cu_notificare(10)
    await replica_de_azi(ctx2["profile"].id, ctx2["project"].id, IARNA.date())
    serviciu2 = Serviciu()
    await ruleaza(serviciu2, IARNA)
    assert serviciu2.cereri == []


@pytest.mark.asyncio
async def test_fara_acord_membru_inactiv_cody_oprit_nimic_si_randul_ramane() -> None:
    _, r1 = await om_cu_notificare(10, membership_active=False)
    _, r2 = await om_cu_notificare(10, is_enabled=False)
    ctx3, r3 = await om_cu_notificare(10)
    async with SessionLocal() as s:
        await s.execute(delete(PracticeConsent).where(
            PracticeConsent.participant_profile_id == ctx3["profile"].id
        ))
        await s.commit()
    serviciu = Serviciu()
    await ruleaza(serviciu, IARNA)
    assert serviciu.cereri == []
    for r in (r1, r2, r3):
        ramas = await randul(r.id)
        assert ramas is not None and ramas.ultima_zi_trimisa is None


@pytest.mark.asyncio
async def test_cererea_e_goala_si_semnata_cu_afirmatiile_exacte() -> None:
    _, rand = await om_cu_notificare(10)
    s = setari()
    serviciu = Serviciu()
    await ruleaza(serviciu, IARNA, s)
    [cerere] = serviciu.cereri
    assert cerere.method == "POST"
    assert cerere.content == b""
    assert cerere.headers["content-length"] == "0"
    assert cerere.headers["ttl"] == "3600"
    assert cerere.headers["urgency"] == "normal"
    antet = cerere.headers["authorization"]
    assert antet.startswith("vapid t=")
    jwt, k = antet[len("vapid t="):].split(", k=")
    assert k == s.push_vapid_public_key
    cap, corp, semn = jwt.split(".")
    assert json.loads(din_b64url(cap)) == {"typ": "JWT", "alg": "ES256"}
    afirmatii = json.loads(din_b64url(corp))
    assert set(afirmatii) == {"aud", "exp", "sub"}
    assert afirmatii["aud"] == "https://fcm.googleapis.com"
    assert afirmatii["sub"] == ADRESA_APLICATIEI
    assert afirmatii["exp"] == int((IARNA + timedelta(hours=12)).timestamp())
    rs = din_b64url(semn)
    assert len(rs) == 64 and "=" not in semn
    publica = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), din_b64url(k))
    publica.verify(
        encode_dss_signature(int.from_bytes(rs[:32], "big"), int.from_bytes(rs[32:], "big")),
        f"{cap}.{corp}".encode(), ec.ECDSA(hashes.SHA256()),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("cod", [410, 404])
async def test_abonarea_moarta_se_sterge(cod) -> None:
    _, rand = await om_cu_notificare(10)
    numere = await ruleaza(Serviciu(cod), IARNA)
    assert await randul(rand.id) is None
    assert numere["sterse"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("cod,eroare", [(500, False), (None, True), (301, False)])
async def test_respinsa_ramane_marcata_azi_fara_reincercare(cod, eroare) -> None:
    _, rand = await om_cu_notificare(10)
    serviciu = Serviciu(cod, eroare)
    numere = await ruleaza(serviciu, IARNA)
    assert numere == {"de_anuntat": 1, "trimise": 0, "sterse": 0, "respinse": 1}
    assert len(serviciu.cereri) == 1  # nici redirecționarea nu e urmată
    ramas = await randul(rand.id)
    assert ramas is not None and ramas.ultima_zi_trimisa == IARNA.date()
    await ruleaza(serviciu, IARNA + timedelta(minutes=20))
    assert len(serviciu.cereri) == 1


@pytest.mark.asyncio
async def test_gazda_straina_pusa_direct_in_baza_nicio_cerere_si_randul_sters() -> None:
    _, rand = await om_cu_notificare(10)
    async with SessionLocal() as s:
        r = await s.get(PracticeDailyReminder, rand.id)
        r.endpoint = "https://rau.example/fura"
        await s.commit()
    serviciu = Serviciu()
    await ruleaza(serviciu, IARNA)
    assert serviciu.cereri == []
    assert await randul(rand.id) is None


@pytest.mark.asyncio
async def test_fara_chei_sau_cu_cheie_stricata_nimic(caplog) -> None:
    await om_cu_notificare(10)
    serviciu = Serviciu()
    gol = {"de_anuntat": 0, "trimise": 0, "sterse": 0, "respinse": 0}
    assert await ruleaza(serviciu, IARNA, setari(cu_chei=False)) == gol
    privata, publica = chei_de_test()
    caplog.set_level(logging.INFO)
    stricata = Settings(generation_provider="local", public_app_url=ADRESA_APLICATIEI,
                        push_vapid_public_key=publica, push_vapid_private_key="A" * 43)
    assert await ruleaza(serviciu, IARNA, stricata) == gol
    assert serviciu.cereri == []
    jurnal = "\n".join(m.getMessage() for m in caplog.records)
    assert "cheile notificarii nu se pot citi" in jurnal
    assert "A" * 43 not in jurnal and publica not in jurnal and privata not in jurnal


@pytest.mark.asyncio
async def test_jurnalul_nu_are_adresa_sau_id_de_om(caplog) -> None:
    ctx, rand = await om_cu_notificare(10)
    caplog.set_level(logging.DEBUG)
    await ruleaza(Serviciu(), IARNA)
    jurnal = "\n".join(m.getMessage() for m in caplog.records)
    assert "de_anuntat=1" in jurnal
    assert rand.endpoint not in jurnal
    assert str(ctx["profile"].id) not in jurnal
    assert "fcm.googleapis.com/fcm" not in jurnal


@pytest.mark.asyncio
async def test_ora_de_vara() -> None:
    _, rand = await om_cu_notificare(10)
    serviciu = Serviciu()
    await ruleaza(serviciu, VARA)
    assert [str(r.url) for r in serviciu.cereri] == [rand.endpoint]


def test_cronul_e_la_zece_minute_unic_cu_timeout() -> None:
    from codrut.workers import main as worker

    [job] = [j for j in worker.WorkerSettings.cron_jobs
             if j.coroutine is worker.trimite_notificarile_zilnice]
    assert job.minute == {0, 10, 20, 30, 40, 50}
    assert job.second == 0
    assert job.unique is True and job.run_at_startup is False
    assert job.timeout_s == 240


@pytest.mark.asyncio
async def test_worker_anunta_la_pornire_daca_cheile_se_pot_citi(caplog) -> None:
    caplog.set_level(logging.INFO)
    assert nz.anunta_cheile(setari()) is True
    assert nz.anunta_cheile(setari(cu_chei=False)) is False
    randuri = [m.getMessage() for m in caplog.records if "se pot citi" in m.getMessage()]
    assert randuri == [
        "notificarea zilnica: cheile se pot citi: da",
        "notificarea zilnica: cheile se pot citi: nu",
    ]
