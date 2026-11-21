"""Plicul 220: jurnalul serverului nu scrie emailul trainerului și textul erorilor de la model.

Regula: în jurnal nu ajung date personale sau conținut de conversație. Textul unei erori de la
model poate purta bucăți din ce a scris omul; emailul trainerului e o dată personală. În jurnal
rămâne numai tipul erorii, iar participantul e identificat numai prin `participant_id`.
Fiecare test pune un MARCAJ acolo unde ar putea scăpa și verifică că nu apare.
"""

from __future__ import annotations

import logging
import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest

from codrut.contracts.generation import GenerationError
from codrut.core.config import Settings
from codrut.core.database import SessionLocal
from codrut.core.errors import DomainError
from codrut.modules.companies.service import CompanyService
from codrut.modules.practice.evaluator import PracticeEvaluator
from codrut.modules.practice.generation_provider import VertexGenerationProvider
from test_participant_workspace_preview import preview_fixture  # noqa: F401

MARCAJ = "MARCAJ-PLIC220-a ce a scris omul"
EMAIL_TRAINER = "trainer-plic220@example.com"


class _FurnizorCarePica:
    async def generate(self, _cerere):
        raise Exception(MARCAJ)  # noqa: TRY002


@pytest.mark.asyncio
async def test_1_evaluatorul_nu_scrie_textul_erorii(caplog) -> None:
    setari = Settings(generation_provider="local")
    evaluator = PracticeEvaluator(
        session=MagicMock(), generation_provider=_FurnizorCarePica(), settings=setari
    )
    replici = ["Replica omului, destul de lungă cât să treacă pragul ședinței scurte."] * 4
    with caplog.at_level(logging.WARNING):
        rezultat = await evaluator.evaluate_session(
            session_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            project_id=None,
            competencies=["Ascultare activă"],
            transcript="\n".join(replici),
            replici_om=replici,
            source_type="roleplay",
        )
    assert "error" in rezultat
    assert "MARCAJ" not in caplog.text
    assert "MARCAJ" not in str(rezultat)
    assert "[EVALUATOR] chemarea a esuat" in caplog.text


@pytest.mark.asyncio
async def test_2_transcrierea_nu_pune_textul_erorii_in_mesaj() -> None:
    setari = Settings(
        generation_provider="vertex",
        vertex_project_id="codrut-cody",
        vertex_region="eu",
        vertex_actor_model="gemini-3.8-flash",
        vertex_evaluator_model="gemini-3.8-flash",
        vertex_transcribe_fallback="",
    )
    cheie = MagicMock()
    cheie.valid = True
    cheie.token = "jeton-de-test"  # noqa: S105

    def pica(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(MARCAJ, request=req)

    async with httpx.AsyncClient(transport=httpx.MockTransport(pica)) as client:
        furnizor = VertexGenerationProvider(settings=setari, credentials=cheie, client=client)
        with pytest.raises(GenerationError) as prins:
            await furnizor.transcribe_audio(b"sunet de proba", "audio/webm")
    err = prins.value
    assert err.code == "transcription_failed"
    assert "MARCAJ" not in str(err)
    assert "MARCAJ" not in err.message


@pytest.mark.asyncio
async def test_3_jurnalul_de_acces_nu_scrie_emailul_trainerului(
    preview_fixture, caplog  # noqa: F811
) -> None:
    data = preview_fixture
    async with SessionLocal() as session:
        service = CompanyService(session)
        with (
            patch.object(
                session, "commit", side_effect=RuntimeError(f"commit picat {EMAIL_TRAINER}")
            ),
            caplog.at_level(logging.DEBUG),
            pytest.raises(DomainError) as prins,
        ):
            await service.get_participant_workspace_preview(
                trainer_user_id=data["trainer_a_id"],
                trainer_email=EMAIL_TRAINER,
                company_id=data["company_a_id"],
                participant_id=data["participant_profile_a_id"],
            )
        await session.rollback()
    assert prins.value.code == "audit_log_failed"
    assert EMAIL_TRAINER not in caplog.text
    for r in caplog.records:
        assert EMAIL_TRAINER not in str(vars(r))
    assert any(
        str(data["participant_profile_a_id"]) in str(vars(r)) for r in caplog.records
    ), "participantul trebuie să rămână identificat prin participant_id"


class _SesiuneFalsa:
    def __init__(self) -> None:
        self.adaugate: list = []

    def add(self, obiect) -> None:
        self.adaugate.append(obiect)

    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_4_nota_sarita_nu_scrie_textul_scorului(caplog) -> None:
    date = {
        "scores": [
            {"competency": "Comunicare asertivă", "evaluated": True, "score": "8/10-MARCAJ",
             "level": 3, "justification": "x"},
        ],
        "insight": "",
        "recommendations_for_trainer": [],
    }
    evaluator = PracticeEvaluator(_SesiuneFalsa(), generation_provider=None, settings=None)
    with caplog.at_level(logging.WARNING):
        await evaluator._persist(date=date, session_id=uuid.uuid4(), user_id=uuid.uuid4(),
                                 project_id=None, source_type="session")
    sarite = [r.getMessage() for r in caplog.records if "practice_nota_sarita" in r.getMessage()]
    assert len(sarite) == 1
    assert "MARCAJ" not in caplog.text


@pytest.mark.asyncio
async def test_5_inchiderea_nu_scrie_textul_erorii_evaluatorului(caplog) -> None:
    from test_inchiderea_trece_prin_buget import _o_sedinta
    from test_practice_session_flow import create_test_context

    settings = Settings(generation_provider="local")

    async def pica(*_a, **_k):
        raise Exception(MARCAJ)  # noqa: TRY002

    async with SessionLocal() as session:
        ctx = await create_test_context(session)
        service, sedinta, redis = await _o_sedinta(session, ctx, settings)
        with (
            patch.object(PracticeEvaluator, "evaluate_session", side_effect=pica) as chemat,
            caplog.at_level(logging.WARNING),
        ):
            await service.end_session(principal=ctx["principal"], session_id=sedinta.id)
        assert chemat.called, "evaluarea structurală nu s-a chemat; testul n-ar dovedi nimic"
        await session.rollback()
        await redis.aclose()
    assert "Structural evaluation failed in end_session" in caplog.text
    assert "MARCAJ" not in caplog.text
