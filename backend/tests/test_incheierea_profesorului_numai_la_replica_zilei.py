"""Plicul 260 — la „o replică pe zi” profesorul încheie fără întrebare; la exersare nimic nu se
schimbă.

Hotărârea lui Andrei [replica-zilei-instructiune], 22 nov 2026, 10:24: textul din Mostre m10
aprobat exact, cu condiția: „vreau să verificăm că se oprește doar la faza cu o replică pe zi. Ca
în rest trebuie să îl lase să exerseze ca și până acum.” Condiția lui Andrei → testele:
(1) la replica zilei profesorul primește textul, o dată, la final → t2, t3;
(2) textul nu e nicăieri altundeva → t4, t5, t6 (+ amprentele B0 = V1, T0 = T1 din plic);
(3) la exersare profesorul îl invită în continuare pe om să răspundă → t4, t5.
`TEXT_APROBAT` e scris aici de un script, din octeții fișierului
`SPEC-CODY/FISE/L2-incheiere-profesor-aprobat.txt`.
Fără model: numai `LocalGenerationProvider` și furnizori falși.
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest

TEXT_APROBAT = 'Azi e «o replică pe zi»: omul a scris o singură replică la o situație scurtă și nu mai poate răspunde azi. Nu încheia cu o întrebare și nu-i cere altă replică. Nu da nume celuilalt om: spune-i după rol (șeful, colegul, clientul). Încheie cu varianta mai bună a replicii lui, într-o singură propoziție, pe care s-o poată folosi data viitoare.'  # noqa: E501
AMPRENTA_APROBATA = "f7c7756329100fa985a25afcec9241b9f978d968e021c9d2b77515bc53315f6c"
BUCATI = (TEXT_APROBAT, "Nu încheia cu o întrebare", "Încheie cu varianta mai bună")
INVITATIA = "Cum îi răspunzi acum lui"
SRC = Path(__file__).resolve().parents[1] / "src" / "codrut"


def _fara_bucati(text: str | None) -> bool:
    return not any(b in (text or "") for b in BUCATI)


def test_textul_e_cel_aprobat() -> None:
    from codrut.modules.practice.prompts import INCHEIERE_REPLICA_ZILEI

    assert hashlib.sha256(TEXT_APROBAT.encode("utf-8")).hexdigest() == AMPRENTA_APROBATA
    assert INCHEIERE_REPLICA_ZILEI == TEXT_APROBAT
    brut = (SRC / "modules/practice/prompts/incheiere-replica-zilei.md").read_bytes()
    assert brut.endswith(b".\n") and not brut.endswith(b"\n\n")
    assert brut == TEXT_APROBAT.encode("utf-8") + b"\n"
    assert not any(c in TEXT_APROBAT for c in "şţŞŢ")


def test_incheierea_se_pune_o_data_la_final() -> None:
    from codrut.modules.practice import replica_zilei as rz
    from codrut.modules.practice.prompts import cu_incheierea_replicii_zilei, get_prompts_pe_meserii

    _, reala = get_prompts_pe_meserii(name="P-TEST", history_length=rz.PAS_DE_JOC, memories=None,
                                      biblioteca_path="", profil_rol=None)
    for x in ("", "abc", "Instrucțiune\n\n---\noarecare", reala):
        rez = cu_incheierea_replicii_zilei(x)
        assert rez == x + "\n\n---\n" + TEXT_APROBAT
        assert rez.count(TEXT_APROBAT) == 1 and rez.endswith(TEXT_APROBAT)


@pytest.mark.asyncio
async def test_la_replica_zilei_profesorul_primeste_incheierea_o_data_la_final() -> None:
    from codrut.core.database import SessionLocal
    from codrut.modules.practice import replica_zilei as rz
    from codrut.modules.practice.alias import codul_omului
    from codrut.modules.practice.prompts import FARA_SCENA, get_prompts_pe_meserii
    from codrut.modules.practice.service import SCENA_CELUILALT
    from test_replica_zilei_profesor import ACUM, ProfesorFals, proiect_legat, setari, trimite

    settings = setari()
    async with SessionLocal() as session:
        ctx = await proiect_legat(session)
        await session.commit()
        stare = await rz.starea_zilei(session, ctx["principal"], ctx["project"].id, acum=ACUM)
        profesor = ProfesorFals()
        replica = "Înțeleg că e urgent; azi pot doar până la 18."
        await trimite(session, ctx, profesor=profesor, text=replica, settings=settings)
        assert len(profesor.cereri) == 1
        cerere = profesor.cereri[0]
        cod = await codul_omului(session, ctx["profile"])
        _, exersare = get_prompts_pe_meserii(
            name=cod, history_length=rz.PAS_DE_JOC, memories=None,
            biblioteca_path=settings.biblioteca_path, profil_rol=None,
        )
        instr = cerere.system_instruction
        assert instr == exersare + "\n\n---\n" + TEXT_APROBAT
        assert instr.count(TEXT_APROBAT) == 1 and instr.endswith(TEXT_APROBAT)
        assert instr.endswith(FARA_SCENA + "\n\n---\n" + TEXT_APROBAT)
        assert [m.role for m in cerere.messages] == ["user"]
        assert cerere.messages[0].text == (
            f"{SCENA_CELUILALT}\n{stare['situatie']['text']}\n\n{replica}"
        )
        assert _fara_bucati(cerere.messages[0].text)


def test_functiile_de_exersare_nu_primesc_incheierea() -> None:
    import json

    from codrut.modules.practice import obiective
    from codrut.modules.practice import replica_zilei as rz
    from codrut.modules.practice.prompts import get_prompts_pe_meserii
    from test_cody_pe_obiectiv_fara_obiectiv import _cazurile

    cale = Path(obiective.__file__).resolve().parent / "comunicare-asertiva.json"
    o1 = next(o for o in json.loads(cale.read_text(encoding="utf-8"))["obiective"]
              if o["nr"] == 1)
    ob = {k: o1[k] for k in ("titlu", "situatie", "semn_de_reusita")}
    cazuri = list(_cazurile()) + [(f"obiectiv|{k}", v) for k, v in _cazurile(obiectiv=ob)]
    actor, prof = get_prompts_pe_meserii(name="P-TEST", history_length=rz.PAS_DE_JOC,
                                         memories=None, biblioteca_path="", profil_rol=None)
    cazuri += [("rz|actor", actor), ("rz|profesor", prof)]
    assert len(cazuri) > 400
    for cheie, text in cazuri:
        assert _fara_bucati(text), cheie
        if "profesor|" in cheie:
            assert INVITATIA in text, cheie


async def _exersare(doua_apeluri: bool, kind, replici, *, pe_obiectiv: bool = False):
    from redis.asyncio import Redis
    from sqlalchemy import select

    from codrut.core.config import Settings
    from codrut.core.database import SessionLocal
    from codrut.modules.practice import objective_service
    from codrut.modules.practice.generation_provider import LocalGenerationProvider
    from codrut.modules.practice.models import PracticeObjective
    from codrut.modules.practice.service import PracticeSessionService
    from test_competenta_tinta import _pregatire

    settings = Settings(generation_provider="local", practice_two_calls=doua_apeluri)
    furnizor = LocalGenerationProvider(settings)
    async with SessionLocal() as s:
        ctx = await _pregatire(s, {"Ascultare activă": 1})
        ctx["program_settings"].quiz_enabled = True  # quizul e pornit numai unde vrea trainerul
        await s.flush()
        if pe_obiectiv:
            ctx["program_settings"].objective_catalog = "comunicare-asertiva"
            await s.flush()
            o1 = (await s.execute(select(PracticeObjective).where(
                PracticeObjective.catalog == "comunicare-asertiva",
                PracticeObjective.is_active.is_(True)).order_by(PracticeObjective.order_index)
            )).scalars().first()
            await objective_service.alege(s, ctx["principal"], ctx["project"].id, o1.id)
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        svc = PracticeSessionService(session=s, redis=redis, generation_provider=furnizor,
                                     settings=settings)
        sed, _ = await svc.start_session(principal=ctx["principal"], project_id=ctx["project"].id,
                                         kind=kind, pe_obiectiv=pe_obiectiv)
        for text in replici:
            await svc.add_participant_turn(principal=ctx["principal"], session_id=sed.id,
                                           text=text)
        cereri = list(furnizor.recorded_requests)
        await s.rollback()
        await redis.aclose()
    return cereri


@pytest.mark.asyncio
@pytest.mark.parametrize("doua_apeluri", [True, False])
async def test_la_exersare_cererile_sunt_ca_inainte(doua_apeluri: bool) -> None:
    from codrut.contracts.generation import GenerationPurpose
    from codrut.modules.practice.models import SessionKind

    joc = ("Da, hai.", "Înțeleg ce spui. Ce anume te îngrijorează?",
           "Hai să stabilim împreună un termen.", "Pot până joi la prânz.")
    drumuri = {
        "roleplay": await _exersare(doua_apeluri, SessionKind.roleplay, joc),
        "coaching": await _exersare(doua_apeluri, SessionKind.coaching,
                                    ("Am o discuție grea cu șeful.", "Vreau să-i spun nu.")),
        "knowledge": await _exersare(doua_apeluri, SessionKind.knowledge, ("A", "B")),
        "obiectiv": await _exersare(doua_apeluri, SessionKind.roleplay, joc[:3],
                                    pe_obiectiv=True),
    }
    for nume, cereri in drumuri.items():
        assert cereri, nume
        for c in cereri:
            assert _fara_bucati(c.system_instruction), nume
            assert all(_fara_bucati(m.text) for m in c.messages), nume
    for nume in ("roleplay", "obiectiv"):
        cereri = drumuri[nume]
        actor = [c for c in cereri if c.purpose == GenerationPurpose.actor]
        prof = [c for c in cereri if c.purpose == GenerationPurpose.evaluator]
        if doua_apeluri:
            assert prof, nume
            assert all(INVITATIA in c.system_instruction for c in prof), nume
            # actorul nu primește niciodată textul nou (verificat mai sus, pe toate cererile)
            assert all(_fara_bucati(c.system_instruction) for c in actor), nume
        else:
            # un singur apel: instrucțiunea unică de joc are invitația (corecția 6)
            assert any(INVITATIA in c.system_instruction for c in actor), nume


def test_incheierea_sta_intr_un_singur_loc() -> None:
    from codrut.modules.practice import replica_zilei as rz

    gasite: dict[str, list[str]] = {b: [] for b in (*BUCATI, "INCHEIERE_REPLICA_ZILEI",
                                                    "cu_incheierea_replicii_zilei")}
    for f in sorted(SRC.rglob("*")):
        if f.suffix not in (".py", ".md", ".json") or not f.is_file():
            continue
        text = f.read_text(encoding="utf-8")
        for b in gasite:
            if b in text:
                gasite[b].append(f.relative_to(SRC).as_posix())
    fisierul = "modules/practice/prompts/incheiere-replica-zilei.md"
    for b in BUCATI:
        assert gasite[b] == [fisierul], b
    assert gasite["INCHEIERE_REPLICA_ZILEI"] == ["modules/practice/prompts/__init__.py"]
    assert gasite["cu_incheierea_replicii_zilei"] == [
        "modules/practice/prompts/__init__.py", "modules/practice/replica_zilei.py",
        "tools/banca/replica_zilei_banca.py"]
    sursa = inspect.getsource(rz.trimite_replica)
    assert sursa.count("cu_incheierea_replicii_zilei(") == 1
    service = (SRC / "modules/practice/service.py").read_text(encoding="utf-8")
    assert all(b not in service for b in gasite)
