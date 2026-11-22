"""Notificarea zilnică a replicii zilei: rutele omului — plicul 252 (L3-P2), §6.1.

Clientul HTTP din proces; cheile de test sunt făcute aici, cu `cryptography`. Nicio cerere nu
pleacă spre Google/Apple/Mozilla: rutele doar țin minte abonarea.
"""

from __future__ import annotations

import base64
import logging
import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from codrut.api.dependencies import current_principal, db_session
from codrut.core.config import Settings, get_settings
from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.main import create_app
from codrut.modules.practice.models import PracticeConsent, PracticeDailyReminder
from test_practice_router import setup_practice_context
from test_replica_zilei_profesor import ACUM, al_doilea_om, proiect_legat

ADRESA_APLICATIEI = "https://test.cody.example"


def _b64(octeti: bytes) -> str:
    return base64.urlsafe_b64encode(octeti).rstrip(b"=").decode()


def chei_de_test() -> tuple[str, str]:
    cheie = ec.generate_private_key(ec.SECP256R1())
    n = cheie.public_key().public_numbers()
    privata = cheie.private_numbers().private_value.to_bytes(32, "big")
    return _b64(privata), _b64(b"\x04" + n.x.to_bytes(32, "big") + n.y.to_bytes(32, "big"))


def setari(cu_chei: bool = True) -> Settings:
    if not cu_chei:
        return Settings(generation_provider="local", public_app_url=ADRESA_APLICATIEI)
    privata, publica = chei_de_test()
    return Settings(
        generation_provider="local", public_app_url=ADRESA_APLICATIEI,
        push_vapid_public_key=publica, push_vapid_private_key=privata,
    )


def client(principal, settings: Settings | None = None) -> AsyncClient:
    app = create_app()

    async def baza():
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[db_session] = baza
    app.dependency_overrides[current_principal] = lambda: principal
    s = settings or setari()
    app.dependency_overrides[get_settings] = lambda: s
    app.state.settings = s
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def adrese() -> dict[str, str]:
    x = uuid.uuid4().hex
    return {
        "google": f"https://fcm.googleapis.com/fcm/send/{x}",
        "apple": f"https://web.push.apple.com/{x}",
        "mozilla": f"https://updates.push.services.mozilla.com/wpush/v2/{x}",
        "windows": f"https://wns2-par02p.notify.windows.com/w/?token={x}",
    }


RELE = (
    "http://fcm.googleapis.com/fcm/send/x",
    "https://fcm.googleapis.com:8443/fcm/send/x",
    "https://fcm.googleapis.com:443/x",
    "https://user:parola@fcm.googleapis.com/x",
    "https://fcm.googleapis.com@rau.ro/x",
    "https://rau.ro\\@fcm.googleapis.com/x",
    "https://fcm.googleapis.com.rau.ro/x",
    "https://fcm.googleapis.com./x",
    "https://FCM.googleapis.com/x",
    "https://xn--fcm-0na.googleapis.com/x",
    "https://localhost/x",
    "https://169.254.169.254/latest",
    "https://notify.windows.com/x",
    "https://necunoscut.example/x",
)


def url(ctx) -> str:
    return f"/api/practice/projects/{ctx['project'].id}/notificare-zilnica"


async def randurile(profil_id) -> list[PracticeDailyReminder]:
    async with SessionLocal() as s:
        return list((await s.execute(
            select(PracticeDailyReminder)
            .where(PracticeDailyReminder.participant_profile_id == profil_id)
        )).scalars())


async def ctx_nou(**kw) -> dict:
    async with SessionLocal() as session:
        ctx = await proiect_legat(session, **kw)
        await session.commit()
    return ctx


@pytest.mark.asyncio
async def test_fara_sesiune_401_pe_toate_cele_patru() -> None:
    app = create_app()

    async def fara_baza():
        yield None

    app.dependency_overrides[db_session] = fara_baza
    p = f"/api/practice/projects/{uuid.uuid4()}/notificare-zilnica"
    corp = {"endpoint": "https://fcm.googleapis.com/x"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        for metoda, cale, j in (
            ("GET", p, None), ("POST", f"{p}/stare", corp),
            ("PUT", p, {**corp, "ora": 9}), ("POST", f"{p}/opreste", corp),
        ):
            r = await c.request(metoda, cale, json=j)
            assert r.status_code == 401, (metoda, cale)


@pytest.mark.asyncio
async def test_trainerul_si_omul_fara_profil_sunt_refuzati() -> None:
    async with SessionLocal() as session:
        ctx = await setup_practice_context(session)
    corp = {"endpoint": adrese()["google"]}
    for cine in ("other_participant", "trainer"):
        async with client(ctx[cine]) as c:
            for metoda, cale, j in (
                ("GET", url(ctx), None), ("POST", f"{url(ctx)}/stare", corp),
                ("PUT", url(ctx), {**corp, "ora": 9}), ("POST", f"{url(ctx)}/opreste", corp),
            ):
                r = await c.request(metoda, cale, json=j)
                assert r.status_code == 400, (cine, metoda, cale)
                assert r.json()["error"]["code"] == "participant_not_found"


async def _codurile(ctx) -> tuple[list[str], list[str]]:
    from codrut.modules.practice import notificare_zilnica as nz
    from codrut.modules.practice import replica_zilei as rz

    e = adrese()["google"]
    nz_coduri = []
    async with SessionLocal() as s:
        for f in (
            lambda: nz.descrierea(s, ctx["principal"], ctx["project"].id, setari()),
            lambda: nz.starea(s, ctx["principal"], ctx["project"].id, e),
            lambda: nz.aboneaza(s, ctx["principal"], ctx["project"].id, e, 9, setari()),
            lambda: nz.opreste(s, ctx["principal"], ctx["project"].id, e),
        ):
            with pytest.raises(DomainError) as err:
                await f()
            nz_coduri.append(err.value.code)
        with pytest.raises(DomainError) as err:
            await rz.starea_zilei(s, ctx["principal"], ctx["project"].id, acum=ACUM)
    return nz_coduri, [err.value.code] * 4


@pytest.mark.asyncio
async def test_membru_inactiv_cody_oprit_fara_acord_aceleasi_coduri_ca_replica_zilei() -> None:
    ctx = await ctx_nou(membership_active=False)
    noi, rz = await _codurile(ctx)
    assert noi == rz == ["not_project_member"] * 4
    ctx = await ctx_nou(is_enabled=False)
    noi, rz = await _codurile(ctx)
    assert noi == rz == ["practice_not_enabled"] * 4
    ctx = await ctx_nou()
    async with SessionLocal() as s:
        await s.execute(delete(PracticeConsent).where(
            PracticeConsent.participant_profile_id == ctx["profile"].id
        ))
        await s.commit()
    noi, rz = await _codurile(ctx)
    assert noi == rz == ["acord_lipsa"] * 4
    assert await randurile(ctx["profile"].id) == []


@pytest.mark.asyncio
async def test_fara_chei_nu_e_disponibila_si_nu_se_salveaza_nimic() -> None:
    ctx = await ctx_nou()
    async with client(ctx["principal"], setari(cu_chei=False)) as c:
        r = await c.get(url(ctx))
        assert r.status_code == 200
        assert r.json() == {"disponibila": False, "cheie_publica": None, "ore": list(range(7, 22))}
        r = await c.put(url(ctx), json={"endpoint": adrese()["google"], "ora": 9})
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "notificare_indisponibila"
    assert await randurile(ctx["profile"].id) == []


@pytest.mark.asyncio
async def test_adresa_aplicatiei_locala_inseamna_indisponibila() -> None:
    ctx = await ctx_nou()
    privata, publica = chei_de_test()
    s = Settings(generation_provider="local", public_app_url="http://localhost:3000",
                 push_vapid_public_key=publica, push_vapid_private_key=privata)
    async with client(ctx["principal"], s) as c:
        assert (await c.get(url(ctx))).json()["disponibila"] is False


@pytest.mark.asyncio
async def test_cu_chei_e_disponibila_cu_cheia_publica_si_orele() -> None:
    ctx = await ctx_nou()
    s = setari()
    async with client(ctx["principal"], s) as c:
        r = await c.get(url(ctx))
    assert r.status_code == 200
    assert r.json() == {
        "disponibila": True, "cheie_publica": s.push_vapid_public_key, "ore": list(range(7, 22)),
    }


@pytest.mark.asyncio
async def test_adresele_serviciilor_cunoscute_trec_celelalte_nu(caplog) -> None:
    ctx = await ctx_nou()
    async with client(ctx["principal"]) as c:
        for nume, e in adrese().items():
            r = await c.put(url(ctx), json={"endpoint": e, "ora": 9})
            assert r.status_code == 200, nume
            assert r.json() == {"pornita": True, "ora": 9}
        assert len(await randurile(ctx["profile"].id)) == 4
        caplog.set_level(logging.INFO)
        for e in RELE:
            caplog.clear()
            r = await c.put(url(ctx), json={"endpoint": e, "ora": 9})
            assert r.status_code == 422, e
            assert r.json()["error"]["code"] == "notificare_adresa_necunoscuta", e
            jurnal = "\n".join(m.getMessage() for m in caplog.records)
            assert "/x" not in jurnal and "latest" not in jurnal, jurnal
        assert len(await randurile(ctx["profile"].id)) == 4
        for ora in (6, 22):
            r = await c.put(url(ctx), json={"endpoint": adrese()["google"], "ora": ora})
            assert r.status_code == 422
            assert r.json()["error"]["code"] == "notificare_ora"
        r = await c.put(url(ctx), json={"endpoint": adrese()["google"], "ora": 9, "nume": "x"})
        assert r.status_code == 422
        r = await c.post(f"{url(ctx)}/stare", json={"endpoint": adrese()["google"], "x": 1})
        assert r.status_code == 422
    assert len(await randurile(ctx["profile"].id)) == 4


@pytest.mark.asyncio
async def test_refuzul_adresei_scrie_in_jurnal_numai_gazda(caplog) -> None:
    ctx = await ctx_nou()
    caplog.set_level(logging.INFO)
    cale = f"/drum-secret-{uuid.uuid4().hex}"
    async with client(ctx["principal"]) as c:
        r = await c.put(url(ctx), json={"endpoint": f"https://alta.gazda.example{cale}", "ora": 9})
    assert r.status_code == 422
    jurnal = "\n".join(m.getMessage() for m in caplog.records)
    assert "alta.gazda.example" in jurnal
    assert cale not in jurnal


@pytest.mark.asyncio
async def test_a_doua_pornire_schimba_ora_si_telefonul_trece_la_ultimul_om() -> None:
    ctx = await ctx_nou()
    e = adrese()["google"]
    async with client(ctx["principal"]) as c:
        assert (await c.put(url(ctx), json={"endpoint": e, "ora": 9})).status_code == 200
        r = await c.put(url(ctx), json={"endpoint": e, "ora": 18})
        assert r.json() == {"pornita": True, "ora": 18}
    [rand] = await randurile(ctx["profile"].id)
    assert rand.ora == 18
    async with SessionLocal() as s:
        profil2, om2 = await al_doilea_om(s, ctx)
        await s.commit()
    async with client(om2) as c:
        r = await c.put(url(ctx), json={"endpoint": e, "ora": 7})
        assert r.json() == {"pornita": True, "ora": 7}
    assert await randurile(ctx["profile"].id) == []
    [rand2] = await randurile(profil2.id)
    assert rand2.id == rand.id and rand2.ora == 7
    async with client(ctx["principal"]) as c:
        r = await c.post(f"{url(ctx)}/stare", json={"endpoint": e})
        assert r.json() == {"pornita": False, "ora": None}


@pytest.mark.asyncio
async def test_starea_si_oprirea_pe_telefonul_altui_om_nu_spun_si_nu_sterg_nimic() -> None:
    ctx = await ctx_nou()
    async with SessionLocal() as s:
        profil2, om2 = await al_doilea_om(s, ctx)
        await s.commit()
    e2 = adrese()["apple"]
    async with client(om2) as c:
        await c.put(url(ctx), json={"endpoint": e2, "ora": 20})
    async with client(ctx["principal"]) as c:
        r = await c.post(f"{url(ctx)}/stare", json={"endpoint": e2})
        assert r.status_code == 200
        assert r.json() == {"pornita": False, "ora": None}
        r = await c.post(f"{url(ctx)}/opreste", json={"endpoint": e2})
        assert r.status_code == 204
    assert len(await randurile(profil2.id)) == 1


@pytest.mark.asyncio
async def test_oprirea_sterge_randul_si_a_doua_oara_tot_204() -> None:
    ctx = await ctx_nou()
    e = adrese()["mozilla"]
    async with client(ctx["principal"]) as c:
        await c.put(url(ctx), json={"endpoint": e, "ora": 9})
        r = await c.post(f"{url(ctx)}/stare", json={"endpoint": e})
        assert r.json() == {"pornita": True, "ora": 9}
        assert (await c.post(f"{url(ctx)}/opreste", json={"endpoint": e})).status_code == 204
        assert await randurile(ctx["profile"].id) == []
        assert (await c.post(f"{url(ctx)}/opreste", json={"endpoint": e})).status_code == 204


@pytest.mark.asyncio
async def test_cel_mult_zece_telefoane_pe_om() -> None:
    ctx = await ctx_nou()
    async with client(ctx["principal"]) as c:
        for _ in range(10):
            r = await c.put(url(ctx), json={"endpoint": adrese()["google"], "ora": 9})
            assert r.status_code == 200
        r = await c.put(url(ctx), json={"endpoint": adrese()["google"], "ora": 9})
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "notificare_prea_multe"
        [primul] = (await randurile(ctx["profile"].id))[:1]
        r = await c.put(url(ctx), json={"endpoint": primul.endpoint, "ora": 12})
        assert r.status_code == 200
    assert len(await randurile(ctx["profile"].id)) == 10


@pytest.mark.asyncio
async def test_raspunsurile_nu_contin_nume_email_sau_id_de_om() -> None:
    ctx = await ctx_nou()
    e = adrese()["google"]
    async with client(ctx["principal"]) as c:
        texte = [
            (await c.get(url(ctx))).text,
            (await c.put(url(ctx), json={"endpoint": e, "ora": 9})).text,
            (await c.post(f"{url(ctx)}/stare", json={"endpoint": e})).text,
        ]
    for t in texte:
        assert ctx["profile"].full_name not in t
        assert ctx["profile"].email not in t
        assert str(ctx["profile"].id) not in t
        assert "participant_profile_id" not in t


def test_coloanele_tabelei_sunt_exact_cele_din_plic() -> None:
    coloane = [c.name for c in PracticeDailyReminder.__table__.columns]
    assert sorted(coloane) == sorted([
        "id", "participant_profile_id", "project_id", "endpoint", "ora",
        "ultima_zi_trimisa", "created_at", "updated_at",
    ])
    for interzis in ("name", "email", "p256dh", "auth", "ip", "user_agent"):
        assert interzis not in coloane


def test_fisierele_noi_nu_aduc_modelul_nici_in_worker() -> None:
    import subprocess
    import sys
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src" / "codrut"
    for f in (src / "modules/practice/notificare_zilnica.py", src / "modules/practice/web_push.py",
              src / "tools/chei_notificare.py"):
        text = f.read_text(encoding="utf-8")
        for interzis in ("generation_provider", "practice.prompts", "evaluator", "replica_zilei"):
            assert f"import {interzis}" not in text, (f, interzis)
            assert f".{interzis} import" not in text, (f, interzis)
    iesire = subprocess.run(
        [sys.executable, "-c",
         "import codrut.workers.main, sys; print([m for m in ("
         "'codrut.modules.practice.prompts', 'codrut.modules.practice.generation_provider', "
         "'codrut.modules.practice.evaluator', 'codrut.modules.practice.replica_zilei') "
         "if m in sys.modules])"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert iesire == "[]"
