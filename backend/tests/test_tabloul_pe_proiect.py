"""Tabloul arată competențele proiectului, și se mișcă pentru un om nou — plicul 143.

Hotărârea lui Andrei, 24 septembrie: tabloul se repară azi. Găsit la 141:

A. Tabloul grupa notele pe o listă fixă de 7, din aplicația veche („Reformulare activă",
   „Verificarea înțelegerii"…), nu pe competențele alese de trainer pe proiect. Două competențe
   ale proiectului primeau note și nu apăreau deloc.
B. Pragul de ședință scurtă număra și replicile lui Cody, care sunt lungi, deci trecea mereu:
   „Da, hai." și „Ok." au primit note pe 9 competențe.
C. La închidere Cody i se adresa omului pe cod: „Falcon 48, în acest exercițiu…". Codul e o
   etichetă, nu un nume — apare numai pe ecran.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from redis.asyncio import Redis
from sqlalchemy import select

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice.competency_aliases import CANONICAL_COMPETENCIES
from codrut.modules.practice.dashboard_service import PracticeDashboardService
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import CompetencyScore, ProjectCompetency, SessionKind
from codrut.modules.practice.prompts import get_summary_prompt, get_system_prompt_for_kind
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context

# Competențele „Test proiect" de pe probă, în ordinea trainerului. Două nu sunt în lista veche.
COMPETENTE = [
    "Ascultare activă",
    "Exprimarea asertivă a nevoilor și limitelor",
    "Feedback constructiv",
    "Gestionarea propriilor reacții emoționale",
    "Gestionarea reacțiilor celorlalți",
    "Rezolvarea colaborativă a conflictelor",
    "Verificarea înțelegerii și a alinierii",
]


async def _om_cu_cont(session, ctx) -> User:
    cont = User(
        id=ctx["principal"].user_id,
        email=ctx["principal"].email,
        password_hash="x",  # noqa: S106
        role=UserRole.participant,
    )
    session.add(cont)
    await session.flush()
    ctx["profile"].user_id = cont.id
    await session.flush()
    return cont


def _nota(cont, proiect, nume: str, scor: int) -> CompetencyScore:
    return CompetencyScore(
        user_id=cont.id, project_id=proiect.id, competency_id=None, score=scor,
        level=1, justification=None, conversation_id="sedinta-test", competency_name=nume,
        source_type="roleplay",
    )


# --------------------------------------------------------------------------- A · tabloul


@pytest.mark.asyncio
async def test_tabloul_arata_exact_competentele_proiectului_cu_notele_lor() -> None:
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        cont = await _om_cu_cont(session, ctx)
        proiect = ctx["project"]
        for i, nume in enumerate(COMPETENTE):
            session.add(ProjectCompetency(project_id=proiect.id, name=nume, order_index=i))
        session.add_all([
            # scrisă altfel decât în proiect: litere mici, fără diacritice, spații în plus
            _nota(cont, proiect, "rezolvarea  colaborativa a conflictelor", 80),
            _nota(cont, proiect, "Verificarea înțelegerii și a alinierii", 60),
            _nota(cont, proiect, "Ascultare activă", 50),
            # din aplicația veche — nu sunt ale proiectului, nu apar
            _nota(cont, proiect, "Comunicare Asertivă", 90),
            _nota(cont, proiect, "Reformulare activă", 90),
        ])
        await session.flush()

        date = await PracticeDashboardService(session).get_participant_dashboard_data(
            principal=ctx["principal"], project_id=proiect.id
        )
        afisate = [c["name"] for c in date["competencies"]]
        assert afisate == COMPETENTE
        pe_nume = {c["name"]: c for c in date["competencies"]}
        assert pe_nume["Rezolvarea colaborativă a conflictelor"]["average_score"] == 80
        assert pe_nume["Verificarea înțelegerii și a alinierii"]["average_score"] == 60
        assert pe_nume["Ascultare activă"]["average_score"] == 50
        assert pe_nume["Feedback constructiv"]["average_score"] == 0
        await session.rollback()


@pytest.mark.asyncio
async def test_fara_competente_alese_tabloul_ramane_cel_de_azi() -> None:
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        await _om_cu_cont(session, ctx)
        date = await PracticeDashboardService(session).get_participant_dashboard_data(
            principal=ctx["principal"], project_id=ctx["project"].id
        )
        assert [c["name"] for c in date["competencies"]] == CANONICAL_COMPETENCIES
        fara_proiect = await PracticeDashboardService(session).get_participant_dashboard_data(
            principal=ctx["principal"]
        )
        assert [c["name"] for c in fara_proiect["competencies"]] == CANONICAL_COMPETENCIES
        await session.rollback()


# --------------------------------------------------------------------------- B · ședința scurtă


class FurnizorCuNote(LocalGenerationProvider):
    """Ca furnizorul local, dar evaluatorul structural dă note (JSON valid), ca Google."""

    async def generate(self, request):
        rez = await super().generate(request)
        if request.response_mime_type == "application/json":
            note = [{"competency": n, "score": 40, "level": 1, "justification": "x",
                     "evaluated": True} for n in COMPETENTE]
            return replace(rez, text=json.dumps({"scores": note}))
        if request.purpose.value == "actor":
            # replicile lui Cody sunt lungi și au paragrafe (ca la 141) — de aici trecea mereu
            # pragul vechi, care număra blocurile și semnele din tot transcriptul
            paragraf = "Cody spune ceva lung despre situație. " * 7
            return replace(rez, text="\n\n".join([paragraf] * 3))
        return rez


async def _sedinta_si_note(replici: tuple[str, ...]) -> int:
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        await _om_cu_cont(session, ctx)
        for i, nume in enumerate(COMPETENTE):
            session.add(ProjectCompetency(project_id=ctx["project"].id, name=nume, order_index=i))
        await session.flush()
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(
            session=session, redis=redis, generation_provider=FurnizorCuNote(settings),
            settings=settings,
        )
        sedinta, _ = await service.start_session(
            principal=ctx["principal"], project_id=ctx["project"].id, kind=SessionKind.roleplay
        )
        for r in replici:
            await service.add_participant_turn(
                principal=ctx["principal"], session_id=sedinta.id, text=r
            )
        await service.end_session(principal=ctx["principal"], session_id=sedinta.id)
        note = (await session.execute(
            select(CompetencyScore).where(
                CompetencyScore.conversation_id == str(sedinta.id),
                CompetencyScore.source_type == "roleplay",
            )
        )).scalars().all()
        await session.rollback()
        await redis.aclose()
        return len(note)


@pytest.mark.asyncio
async def test_da_hai_si_ok_nu_primesc_nicio_nota() -> None:
    assert await _sedinta_si_note(("Da, hai.", "Ok.")) == 0


@pytest.mark.asyncio
async def test_o_sedinta_adevarata_primeste_note_ca_azi() -> None:
    replici = (
        "Da, hai.",
        "Înțeleg ce spui. Ce anume te-a deranjat cel mai tare în situația asta, concret?",
        "Raportul a întârziat de trei ori luna asta; echipa a trimis cifre greșite clientului.",
        "Aș vrea să stabilim împreună un termen clar pentru următorul raport, joi la prânz.",
    )
    assert await _sedinta_si_note(replici) == len(COMPETENTE)


# ----------------------------------------------------------------- C · fără adresare pe cod


def test_regula_spune_ca_nu_i_te_adresezi_pe_cod() -> None:
    for mod in ("roleplay", "knowledge", "coaching"):
        prompt = get_system_prompt_for_kind(mod, name="Falcon 48", history_length=4)
        assert "pe om îl cheamă" not in prompt, mod
        assert "INTERZIS să i te adresezi pe cod" in prompt, mod
        assert "Falcon 48" in prompt, mod  # codul rămâne, ca etichetă
        assert "Dacă îl cheamă Andrei, îi spui" not in prompt, mod


def test_rezumatul_nu_cere_adresarea_pe_cod() -> None:
    text = get_summary_prompt(name="Falcon 48", opt_text="roleplay", history="Falcon 48: salut")
    assert "Adresează-te direct lui" not in text
    assert "INTERZIS să i te adresezi pe cod" in text


def test_numele_nu_se_foloseste_ca_apelativ_nici_in_ghilimele_date_ca_exemplu() -> None:
    """Exemplele din prompt nu arată un apelativ cu cod („Falcon 48, ai spus…")."""
    prompt = get_system_prompt_for_kind("roleplay", name="Falcon 48", history_length=4)
    assert "Falcon 48," not in prompt

