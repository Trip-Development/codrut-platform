"""După o ședință prea scurtă, omul vede textul lui Andrei, nu o sinteză inventată — plicul 144.

Găsit la 143: sub prag, evaluatorul întorcea `INSUFFICIENT_CLOSING`, dar nimeni nu-l folosea. Omul
vedea sinteza modelului, care judeca „Da, hai." și „Ok." ca pe o conversație („ai evitat
confruntarea directă și ai cedat inițiativa…").

Hotărârea lui Andrei, 24 septembrie: sub prag, omul vede textul care există deja. Pragul se
socotește o singură dată, cu aceeași funcție ca la 143; sub prag, niciun apel spre model și nimic
salvat din conversație. Peste prag, nimic nu se schimbă.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from redis.asyncio import Redis
from sqlalchemy import select

from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice.evaluator import INSUFFICIENT_CLOSING, sedinta_prea_scurta
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import (
    CompetencyScore,
    InsightMoment,
    ParticipantMemory,
    PracticeOutcome,
    ProjectCompetency,
    SessionKind,
    SessionState,
)
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context

# Ce vede omul — textul lui Andrei, cuvânt cu cuvânt, sub titlurile din `rezumat.md`.
TEXTUL = (
    "##Concluzie\n"
    "Ai început să interacționezi cu Cody — primul pas e făcut.\n\n"
    "Sesiunea a fost prea scurtă pentru o evaluare reală. Pentru ca antrenamentul să producă "
    "insight, ai nevoie de cel puțin 5-6 schimburi pe aceeași situație.\n\n"
    "##Recomandări\n"
    "Reia sesiunea cu o situație concretă din viața ta — ceva care încă te macină. Mergi în "
    "detaliu cu Cody, nu te grăbi să închizi."
)

SINTEZA_CU_NOTE = (
    "##Concluzie\nAi evitat confruntarea directă.\n\n##Recomandări\n• Fii mai clar.\n"
    '```json\n{"topic": "Sarcini", "characters": [], "scores": {"questionsRatio": 3, '
    '"assertiveness": 2, "sbiFeedback": 1, "conciseness": 3}}\n```'
)


class FurnizorCuSinteza(LocalGenerationProvider):
    """Ca furnizorul local, dar rezumatul vine cu blocul JSON de note — cum îl scrie Google."""

    async def generate(self, request):
        rez = await super().generate(request)
        if request.system_instruction == "Ești analizator de discurs.":
            return replace(rez, text=SINTEZA_CU_NOTE)
        return rez


async def _inchide(replici: tuple[str, ...]):
    settings = Settings(generation_provider="local")
    provider = FurnizorCuSinteza(settings)
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        cont = User(id=ctx["principal"].user_id, email=ctx["principal"].email,
                    password_hash="x", role=UserRole.participant)  # noqa: S106
        session.add(cont)
        await session.flush()
        ctx["profile"].user_id = cont.id
        # ca pe proba si pe productie: proiectul are competente, deci la inchidere se cheama si
        # evaluatorul structural (fara ele, se opreste fara apel)
        for i, nume in enumerate(("Ascultare activă", "Feedback constructiv")):
            session.add(ProjectCompetency(project_id=ctx["project"].id, name=nume, order_index=i))
        await session.flush()
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(
            session=session, redis=redis, generation_provider=provider, settings=settings
        )
        sedinta, _ = await service.start_session(
            principal=ctx["principal"], project_id=ctx["project"].id, kind=SessionKind.roleplay
        )
        for r in replici:
            await service.add_participant_turn(
                principal=ctx["principal"], session_id=sedinta.id, text=r
            )
        inainte = len(provider.recorded_requests)
        inchisa, text = await service.end_session(
            principal=ctx["principal"], session_id=sedinta.id
        )
        rezultat = {
            "apeluri": len(provider.recorded_requests) - inainte,
            "text": text,
            "stare": inchisa.state,
            "note": len((await session.execute(select(CompetencyScore).where(
                CompetencyScore.conversation_id == str(sedinta.id))
            )).scalars().all()),
            "momente": len((await session.execute(select(InsightMoment).where(
                InsightMoment.conversation_id == str(sedinta.id))
            )).scalars().all()),
            "memorie": len((await session.execute(select(ParticipantMemory).where(
                ParticipantMemory.session_id == str(sedinta.id))
            )).scalars().all()),
            "nota_sedintei": (await session.execute(select(PracticeOutcome.note).where(
                PracticeOutcome.session_id == sedinta.id)
            )).scalar_one_or_none(),
        }
        await session.rollback()
        await redis.aclose()
        return rezultat


def test_textul_e_cel_din_cod_cuvant_cu_cuvant() -> None:
    """Nu se rescrie nimic: „5-6 schimburi" rămâne, deși pragul e 3 — e sfatul lui Andrei."""
    assert INSUFFICIENT_CLOSING["good_moment"] in TEXTUL
    assert INSUFFICIENT_CLOSING["growth_point"] in TEXTUL
    assert INSUFFICIENT_CLOSING["homework"] in TEXTUL


def test_pragul_e_cel_de_la_143() -> None:
    assert sedinta_prea_scurta(["Da, hai.", "Ok."]) is True
    la_prag = ["a" * 50, "b" * 50, "c" * 50]  # 3 replici, 150 de semne
    assert sedinta_prea_scurta(la_prag) is False
    assert sedinta_prea_scurta(["a" * 50, "b" * 50, "c" * 49]) is True


@pytest.mark.asyncio
async def test_da_hai_si_ok_zero_apeluri_textul_lui_andrei_nimic_salvat() -> None:
    r = await _inchide(("Da, hai.", "Ok."))
    assert r["apeluri"] == 0
    assert r["text"] == TEXTUL
    assert r["stare"] == SessionState.closed
    assert (r["note"], r["momente"], r["memorie"]) == (0, 0, 0)
    # aceeași proză în nota ședinței, ca trainerul să vadă de ce n-are evaluare
    assert r["nota_sedintei"] == TEXTUL


@pytest.mark.asyncio
async def test_exact_la_prag_sedinta_e_evaluata_ca_azi() -> None:
    replici = ("Da, hai.", "x" * 71, "y" * 71)  # 8 + 71 + 71 = 150 de semne, 3 replici
    assert sum(len(x) for x in replici) == 150
    r = await _inchide(replici)
    assert r["apeluri"] == 2  # rezumatul și evaluatorul structural
    assert r["text"] != TEXTUL


@pytest.mark.asyncio
async def test_o_sedinta_adevarata_merge_pe_calea_de_azi() -> None:
    replici = (
        "Da, hai.",
        "Înțeleg ce spui. Ce anume te-a deranjat cel mai tare în situația asta, concret?",
        "Raportul a întârziat de trei ori; echipa a trimis cifre greșite clientului.",
        "Aș vrea să stabilim împreună un termen clar pentru următorul raport, joi la prânz.",
    )
    r = await _inchide(replici)
    assert r["apeluri"] == 2
    assert r["text"].startswith("##Concluzie\nAi evitat confruntarea directă.")
    assert r["note"] == 4  # cele patru din rezumat, ca azi
