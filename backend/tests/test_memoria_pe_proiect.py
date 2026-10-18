"""Memoria pe proiect — plicul 185 (hotărârea lui Andrei, 30 sept: „pe proiect”).

Cody, într-o ședință din proiectul P, primește din trecutul omului numai însemnările lui P; Tabloul
deschis pe P arată numai momentele și mostrele din ședințele lui P. Fără proiect deschis: numai cele
care nu țin de nicio ședință (arhiva) — ca notele de la 184.

Drumul omului, nu funcția: ședințe adevărate (`start_session` / `add_participant_turn`) cu
furnizorul local (zero Google) și `get_participant_dashboard_data`. „Ce primește Cody” = promptul
de sistem al tuturor cererilor ședinței noi. Însemnările poartă un marcaj unic, `[MEM-…]`; date
inventate, fără nume de oameni. Testele nu importă nimic ce nu există pe candidatul 22.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from redis.asyncio import Redis

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.companies.models import (
    Company,
    CompanyProject,
    CompanyProjectStatus,
    ProjectMembership,
)
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice.acord import AMPRENTA
from codrut.modules.practice.dashboard_service import PracticeDashboardService
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import (
    InsightMoment,
    ParticipantMemory,
    PracticeConsent,
    PracticeProgramSettings,
    ProgramMode,
    SessionKind,
    SessionSample,
)
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context

MARCAJ = re.compile(r"\[(MEM-[A-Z0-9-]+)\]")
REPLICI = (
    "Bună, hai să începem.",
    "Aș vrea să lucrăm la cum îi spun colegului că termenul nu se mai poate muta.",
)
ACUM = datetime.now(UTC).replace(microsecond=0)
ARHIVA = "legacy_session"


async def _proiect(s, ctx, firma=None):
    """Un proiect de training în firma omului (sau în alta, numai proiectul)."""
    p = CompanyProject(
        company_id=(firma or ctx["company"]).id,
        name=f"P {uuid.uuid4().hex[:6]}",
        status=CompanyProjectStatus.active,
        project_type="training",
    )
    s.add(p)
    await s.flush()
    if firma is not None:
        return p
    s.add(ProjectMembership(company_id=ctx["company"].id, project_id=p.id,
                            participant_profile_id=ctx["profile"].id, active=True))
    s.add(PracticeProgramSettings(
        project_id=p.id, mode=ProgramMode.training, theme_id=ctx["program_settings"].theme_id,
        active_pack_id=ctx["pack"].id, is_enabled=True, max_turns_per_session=10,
        max_sessions_per_day=5, max_chars_per_turn=1200, turn_retention_days=30,
        usd_cap_per_participant=ctx["program_settings"].usd_cap_per_participant,
    ))
    s.add(PracticeConsent(participant_profile_id=ctx["profile"].id, project_id=p.id,
                          text_hash=AMPRENTA, accepted_at=datetime.now(UTC)))
    await s.flush()
    return p


async def _lumea(s):
    """Firma X: A (din fixtură), B, D (gol, „programul nou”); firma Y: C. Ședințe reale sA, sB."""
    settings = Settings(generation_provider="local")
    provider = LocalGenerationProvider(settings)
    ctx = await create_test_context(s)
    cont = User(id=ctx["principal"].user_id, email=ctx["principal"].email,
                password_hash="x", role=UserRole.participant)  # noqa: S106
    s.add(cont)
    await s.flush()
    ctx["profile"].user_id = cont.id   # altfel prima replică nu citește memoria
    a = ctx["project"]
    b = await _proiect(s, ctx)
    d = await _proiect(s, ctx)
    alta = Company(name=f"Alta {uuid.uuid4().hex[:6]}")
    s.add(alta)
    await s.flush()
    c = await _proiect(s, ctx, firma=alta)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    service = PracticeSessionService(session=s, redis=redis, generation_provider=provider,
                                     settings=settings)
    s_a, _ = await service.start_session(principal=ctx["principal"], project_id=a.id,
                                         kind=SessionKind.roleplay)
    s_b, _ = await service.start_session(principal=ctx["principal"], project_id=b.id,
                                         kind=SessionKind.roleplay)
    return {"ctx": ctx, "cont": cont, "A": a, "B": b, "C": c, "D": d, "sA": str(s_a.id),
            "sB": str(s_b.id), "service": service, "provider": provider, "redis": redis}


async def _insemnari(s, w, randuri):
    """`randuri` = (marcaj, proiect sau None, ședință, relevanță), de la cea mai veche."""
    for i, (marcaj, proiect, sedinta, relevanta) in enumerate(randuri):
        s.add(ParticipantMemory(
            user_id=w["cont"].id, project_id=proiect, session_id=sedinta,
            summary=f"[{marcaj}] O însemnare inventată.", key_quotes=[], evolution_signals={},
            personal_context={}, relevant_competencies=[], source_type="roleplay",
            relevance_score=relevanta, created_at=ACUM - timedelta(days=1) + timedelta(minutes=i),
        ))
    await s.flush()


async def _lumea_cu_memorie(s):
    w = await _lumea(s)
    await _insemnari(s, w, [
        ("MEM-A-SEDINTA", None, w["sA"], 90),        # ca închiderea: fără proiect, cu ședința
        ("MEM-A-SLABA", w["A"].id, ARHIVA, 30),
        ("MEM-A-ARHIVA", w["A"].id, ARHIVA, 90),     # ca arhiva: cu proiect, ședință veche
        ("MEM-B-SEDINTA", None, w["sB"], 90),
        ("MEM-B-ARHIVA", w["B"].id, ARHIVA, 90),
        ("MEM-C-ARHIVA", w["C"].id, ARHIVA, 90),
        ("MEM-FARA-PROIECT", None, "sedinta-stearsa", 90),
    ])
    return w


async def _ce_primeste_cody(w, proiect) -> list[str]:
    """Promptul de sistem al fiecărei cereri a unei ședințe noi: prima replică + 2 ale omului."""
    w["provider"].recorded_requests.clear()
    service, principal = w["service"], w["ctx"]["principal"]
    sedinta, _ = await service.start_session(principal=principal, project_id=proiect.id,
                                             kind=SessionKind.roleplay)
    for replica in REPLICI:
        await service.add_participant_turn(principal=principal, session_id=sedinta.id,
                                           text=replica)
    texte = [c.system_instruction or "" for c in w["provider"].recorded_requests]
    assert len(texte) >= 3
    return texte


def _marcaje(texte) -> set[str]:
    return {m for t in texte for m in MARCAJ.findall(t)}


async def _inchide(s, w):
    await s.rollback()
    await w["redis"].aclose()


# --------------------------------------------------------------------------- ce primește Cody


@pytest.mark.asyncio
async def test_cody_in_a_isi_aminteste_numai_din_a() -> None:
    async with SessionLocal() as s:
        w = await _lumea_cu_memorie(s)
        assert _marcaje(await _ce_primeste_cody(w, w["A"])) == {"MEM-A-SEDINTA", "MEM-A-ARHIVA"}
        await _inchide(s, w)


@pytest.mark.asyncio
async def test_cody_in_b_isi_aminteste_numai_din_b() -> None:
    async with SessionLocal() as s:
        w = await _lumea_cu_memorie(s)
        assert _marcaje(await _ce_primeste_cody(w, w["B"])) == {"MEM-B-SEDINTA", "MEM-B-ARHIVA"}
        await _inchide(s, w)


@pytest.mark.asyncio
async def test_proiect_nou_cody_nu_stie_nimic() -> None:
    async with SessionLocal() as s:
        w = await _lumea_cu_memorie(s)
        texte = await _ce_primeste_cody(w, w["D"])
        assert _marcaje(texte) == set()
        assert not any("Sesiune 1 (" in t for t in texte)
        await _inchide(s, w)


@pytest.mark.asyncio
async def test_cinci_insemnari_ale_proiectului() -> None:
    async with SessionLocal() as s:
        w = await _lumea(s)
        # 7 pe A (pe rând: prin ședință, prin proiect), apoi 3 mai noi pe B
        pe_a = [(f"MEM-A{i}", None if i % 2 else w["A"].id, w["sA"] if i % 2 else ARHIVA, 90)
                for i in range(1, 8)]
        pe_b = [(f"MEM-B{i}", w["B"].id, ARHIVA, 90) for i in range(1, 4)]
        await _insemnari(s, w, pe_a + pe_b)
        prima = (await _ce_primeste_cody(w, w["A"]))[0]
        gasite = MARCAJ.findall(prima)
        # cele mai noi 5 ale lui A, în ordine cronologică (poziția în text)
        assert gasite == ["MEM-A3", "MEM-A4", "MEM-A5", "MEM-A6", "MEM-A7"]
        await _inchide(s, w)


@pytest.mark.asyncio
async def test_fara_proiect_nu_ajunge_la_cody() -> None:
    async with SessionLocal() as s:
        w = await _lumea(s)
        await _insemnari(s, w, [
            ("MEM-A-ARHIVA", w["A"].id, ARHIVA, 90),
            ("MEM-FARA-PROIECT", None, "sedinta-stearsa", 90),
        ])
        assert _marcaje(await _ce_primeste_cody(w, w["A"])) == {"MEM-A-ARHIVA"}
        await _inchide(s, w)


@pytest.mark.asyncio
async def test_relevanta_sub_40_ramane_afara() -> None:
    async with SessionLocal() as s:
        w = await _lumea_cu_memorie(s)
        for proiect in ("A", "B", "D"):
            assert "MEM-A-SLABA" not in _marcaje(await _ce_primeste_cody(w, w[proiect]))
        await _inchide(s, w)


# --------------------------------------------------------------------------- Tabloul


async def _momente(s, w, randuri, de_la=0):
    """`randuri` = (ședință, text), de la cel mai vechi (minutul `de_la`); întoarce id-urile."""
    ids = []
    for i, (sedinta, text) in enumerate(randuri, start=de_la):
        m = InsightMoment(user_id=w["cont"].id, conversation_id=sedinta, summary=text,
                          created_at=ACUM - timedelta(hours=2) + timedelta(minutes=i))
        s.add(m)
        await s.flush()
        ids.append(str(m.id))
    return ids


async def _mostre(s, w, sedinte):
    ids = []
    for i, sedinta in enumerate(sedinte):
        m = SessionSample(user_id=w["cont"].id, conversation_id=sedinta,
                          real_weak="O replică inventată.", real_improved="Una mai bună.",
                          created_at=ACUM - timedelta(hours=2) + timedelta(minutes=i))
        s.add(m)
        await s.flush()
        ids.append(str(m.id))
    return ids


async def _tablou(s, w, proiect):
    t = await PracticeDashboardService(s).get_participant_dashboard_data(
        w["ctx"]["principal"], w[proiect].id if proiect else None
    )
    return ([m["id"] for m in t["insight_moments"]], [m["id"] for m in t["session_samples"]])


async def _lumea_tabloului(s):
    w = await _lumea(s)
    a1, a2, b1, trainer, arhiva = await _momente(s, w, [
        (w["sA"], "Un moment inventat, primul."),
        (w["sA"], "Un moment inventat, al doilea."),
        (w["sB"], "Un moment inventat din B."),
        (w["sA"], "[TRAINER] O notă inventată pentru trainer."),
        ("legacy_insight_archive", "Un moment inventat din arhivă."),
    ])
    sa, sb, sarh = await _mostre(s, w, [w["sA"], w["sB"], "legacy_samples_archive"])
    w["m"] = {"a1": a1, "a2": a2, "b1": b1, "trainer": trainer, "arhiva": arhiva}
    w["s"] = {"a": sa, "b": sb, "arhiva": sarh}
    return w


@pytest.mark.asyncio
async def test_tabloul_pe_a_numai_momentele_lui_a() -> None:
    async with SessionLocal() as s:
        w = await _lumea_tabloului(s)
        momente, _ = await _tablou(s, w, "A")
        assert sorted(momente) == sorted([w["m"]["a1"], w["m"]["a2"]])
        await _inchide(s, w)


@pytest.mark.asyncio
async def test_tabloul_pe_b_si_pe_d() -> None:
    async with SessionLocal() as s:
        w = await _lumea_tabloului(s)
        assert (await _tablou(s, w, "B"))[0] == [w["m"]["b1"]]
        assert await _tablou(s, w, "D") == ([], [])
        await _inchide(s, w)


@pytest.mark.asyncio
async def test_tabloul_fara_proiect_numai_arhiva() -> None:
    async with SessionLocal() as s:
        w = await _lumea_tabloului(s)
        assert await _tablou(s, w, None) == ([w["m"]["arhiva"]], [w["s"]["arhiva"]])
        await _inchide(s, w)


@pytest.mark.asyncio
async def test_mostrele_pe_proiect() -> None:
    async with SessionLocal() as s:
        w = await _lumea_tabloului(s)
        assert (await _tablou(s, w, "A"))[1] == [w["s"]["a"]]
        assert (await _tablou(s, w, "B"))[1] == [w["s"]["b"]]
        assert (await _tablou(s, w, None))[1] == [w["s"]["arhiva"]]
        assert (await _tablou(s, w, "D"))[1] == []
        await _inchide(s, w)


@pytest.mark.asyncio
async def test_zece_momente_ale_proiectului() -> None:
    async with SessionLocal() as s:
        w = await _lumea(s)
        pe_a = await _momente(s, w, [(w["sA"], f"Moment inventat {i}.") for i in range(12)])
        # cele 3 din B sunt mai noi decât toate cele din A
        await _momente(s, w, [(w["sB"], f"Moment inventat din B {i}.") for i in range(3)], 12)
        momente, _ = await _tablou(s, w, "A")
        assert len(momente) == 10
        assert set(momente) <= set(pe_a)
        await _inchide(s, w)


@pytest.mark.asyncio
async def test_trainerul_tot_nu_ajunge_la_om() -> None:
    async with SessionLocal() as s:
        w = await _lumea_tabloului(s)
        for proiect in ("A", "B", "D", None):
            assert w["m"]["trainer"] not in (await _tablou(s, w, proiect))[0]
        await _inchide(s, w)
