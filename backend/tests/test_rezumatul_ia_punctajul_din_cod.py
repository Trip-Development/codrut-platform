"""Plicul 226 — nota din rezumatul de final o pune codul (hotărârea din plicul 199).

Banca din 18 nov (plicul 225, cazul R02): aplicația a dat modelului „6,5/10 (media notelor din
joc: 5, 8)”, iar rezumatul a scris „5,7/10 (media notelor din joc: 4, 5, 8)” — recalculat de
model. Textul rezumatului ajunge în `InsightMoment.summary`, `ParticipantMemory.summary`,
`PracticeOutcome.note` și pe ecran, deci nota trebuie să fie cea din cod, oricum ar scrie modelul.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from redis.asyncio import Redis
from sqlalchemy import select

from codrut.contracts.generation import GenerationRequest, GenerationResult
from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.modules.identity.models import User, UserRole
from codrut.modules.practice.generation_provider import LocalGenerationProvider
from codrut.modules.practice.models import (
    InsightMoment,
    ParticipantMemory,
    PracticeOutcome,
    PracticeTurn,
    SessionKind,
    TurnRole,
)
from codrut.modules.practice.prompts import pune_punctajul_in_rezumat
from codrut.modules.practice.service import PracticeSessionService
from test_practice_session_flow import create_test_context

JSON_R02 = (
    "```json\n{\n  \"topic\": \"Feedback\",\n  \"characters\": [\n"
    "    { \"name\": \"Cody\", \"role\": \"coleg\" }\n  ],\n  \"scores\": {\n"
    "    \"questionsRatio\": 5,\n    \"assertiveness\": 7,\n    \"sbiFeedback\": 7,\n"
    "    \"conciseness\": 9\n  }\n}\n```"
)

# Textul real al rezumatului R02, din jurnalul băncii
# (SPEC-CODY/MASURATORI/2026-11-18-banca-etalon.jsonl).
REZUMAT_R02 = (
    "##Concluzie\nAi început conversația oferind o evaluare vagă, însă ai arătat deschidere "
    "cerând îndrumare pentru a-ți îmbunătăți mesajul. Ai învățat rapid cum să treci de la o "
    "critică generală la un feedback clar și aplicat pe situație. Ai încheiat exercițiul "
    "punctând exact lipsurile din raport și setând o așteptare precisă pentru colega ta. "
    "Punctajul tău final este 5,7/10 (media notelor din joc: 4, 5, 8).\n\n"
    "##Recomandări\n"
    "• Înlocuiește aprecierile generale precum „e slab” cu descrierea exactă a elementelor "
    "care lipsesc sau necesită corecturi.\n"
    "• Menționează impactul pe care îl are munca incompletă asupra proiectului sau a echipei, "
    "pentru a da mai mult context cerințelor tale.\n"
    "• Formulează cerințele sub formă de ghidare constructivă, întrebând colega ce soluții "
    "vede pentru a include recomandările lipsă.\n\n---\n\n" + JSON_R02
)
PUNCTAJ_R02 = "6,5/10 (media notelor din joc: 5, 8)"


def _concluzia(text: str) -> str:
    return text.split("##Recomandări")[0]


def test_nota_recalculata_de_model_e_inlocuita_cu_cea_din_cod() -> None:
    nou = pune_punctajul_in_rezumat(REZUMAT_R02, PUNCTAJ_R02)
    assert nou is not None
    concluzia = _concluzia(nou)
    assert "Punctajul final: 6,5/10 (media notelor din joc: 5, 8)." in concluzia
    assert "5,7" not in nou
    assert "4, 5, 8" not in nou
    # restul Concluziei rămâne, iar de la Recomandări încolo nimic nu se schimbă
    assert "Ai început conversația oferind o evaluare vagă" in concluzia
    assert "setând o așteptare precisă pentru colega ta." in concluzia
    coada = REZUMAT_R02[REZUMAT_R02.index("##Recomandări") :]
    assert nou.endswith(coada)
    assert nou.count(JSON_R02) == 1


def test_fara_nota_in_concluzie_linia_se_adauga() -> None:
    text = (
        "##Concluzie\nAi lucrat bine pe mesajul pentru colegă.\n\n"
        "##Recomandări\n• Una\n\n---\n\n" + JSON_R02
    )
    nou = pune_punctajul_in_rezumat(text, PUNCTAJ_R02)
    assert nou is not None
    assert _concluzia(nou).strip().endswith(f"Punctajul final: {PUNCTAJ_R02}.")
    assert nou.endswith("##Recomandări\n• Una\n\n---\n\n" + JSON_R02)


def test_fara_recomandari_linia_vine_inaintea_blocului_json() -> None:
    text = "##Concluzie\nAi încheiat cu 9/10 la final. Ai fost clar.\n\n---\n\n" + JSON_R02
    nou = pune_punctajul_in_rezumat(text, PUNCTAJ_R02)
    assert nou is not None
    assert "9/10" not in nou
    inainte, dupa = nou.split("---", 1)
    assert f"Ai fost clar. Punctajul final: {PUNCTAJ_R02}." in inainte
    assert dupa.endswith(JSON_R02)


def test_quiz_numarul_de_raspunsuri_vine_din_cod() -> None:
    text = (
        "##Concluzie\nAi răspuns la întrebări despre feedback. Ai avut 3 din 3 răspunsuri "
        "corecte.\n\n##Recomandări\n• Una\n\n---\n\n" + JSON_R02
    )
    nou = pune_punctajul_in_rezumat(text, "2 din 3 răspunsuri corecte")
    assert nou is not None
    assert "3 din 3" not in nou
    assert "Punctajul final: 2 din 3 răspunsuri corecte." in _concluzia(nou)


def test_cand_codul_da_linie_textul_ramane_neatins() -> None:
    assert pune_punctajul_in_rezumat(REZUMAT_R02, "—") == REZUMAT_R02
    assert pune_punctajul_in_rezumat(None, PUNCTAJ_R02) is None


class _FurnizorR02(LocalGenerationProvider):
    """Rezumatul întoarce textul real R02; restul apelurilor, ca furnizorul local."""

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        rezultat = await super().generate(request)
        if request.system_instruction == "Ești analizator de discurs.":
            return replace(rezultat, text=REZUMAT_R02)
        return rezultat


@pytest.mark.asyncio
async def test_inchiderea_salveaza_nota_din_cod_peste_tot() -> None:
    settings = Settings(generation_provider="local")
    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        # ca la plicul 223: notele și memoria cer un cont adevărat (cheie străină)
        cont = User(id=ctx["principal"].user_id, email=ctx["principal"].email,
                    password_hash="x", role=UserRole.participant)  # noqa: S106
        session.add(cont)
        await session.flush()
        ctx["profile"].user_id = cont.id
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        service = PracticeSessionService(
            session=session,
            redis=redis,
            generation_provider=_FurnizorR02(settings),
            settings=settings,
        )
        sedinta, _ = await service.start_session(
            principal=ctx["principal"], project_id=ctx["project"].id, kind=SessionKind.roleplay
        )
        # destul de lungă cât să nu fie „prea scurtă” (altfel rezumatul nici nu se cere)
        for i in range(4):
            await service.add_participant_turn(
                principal=ctx["principal"],
                session_id=sedinta.id,
                text=(
                    f"Replica {i} a omului, destul de lungă cât să adune caractere: spun ce "
                    "s-a întâmplat, ce m-a deranjat și ce aș vrea să stabilim de aici încolo."
                ),
            )
        # notele din joc ale lui Cody: numai 5 și 8, ca la R02
        replici_cody = (
            await session.execute(
                select(PracticeTurn)
                .where(
                    PracticeTurn.session_id == sedinta.id,
                    PracticeTurn.role != TurnRole.participant,
                )
                .order_by(PracticeTurn.ordinal)
            )
        ).scalars().all()
        assert len(replici_cody) >= 3
        replici_cody[1].text = "Personajul răspunde.\n***\nevaluare [🏆 Scor: 5/10]"
        replici_cody[2].text = "Personajul răspunde.\n***\nevaluare [🏆 Scor: 8/10]"
        await session.flush()

        _, rezumat = await service.end_session(principal=ctx["principal"], session_id=sedinta.id)

        assert rezumat is not None
        assert "6,5/10" in rezumat
        assert "5,7" not in rezumat and "4, 5, 8" not in rezumat

        memoria = (
            await session.execute(
                select(ParticipantMemory).where(ParticipantMemory.session_id == str(sedinta.id))
            )
        ).scalar_one()
        assert "6,5/10" in memoria.summary and "5,7" not in memoria.summary
        momentul = (
            await session.execute(
                select(InsightMoment).where(InsightMoment.conversation_id == str(sedinta.id))
            )
        ).scalar_one()
        assert "5,7" not in momentul.summary
        rezultat = (
            await session.execute(
                select(PracticeOutcome).where(PracticeOutcome.session_id == sedinta.id)
            )
        ).scalars().first()
        assert rezultat is not None and rezultat.note is not None
        assert "5,7" not in rezultat.note

        await session.rollback()
        await redis.aclose()
