"""The structural evaluator - ported from the old application.

The old app made **two** distinct calls when a session ended, not one:

    1. SUMMARY_PROMPT  -> the four axes            (already ported)
    2. /api/evaluate   -> competency_scores on the project's own competencies,
                          plus insight_moments, session_samples and the
                          recommendations for the trainer      (this file)

Because only the first was ported, scores appeared under four names that are not
among the seven competencies, and the trainer's recommendations did not exist at
all. That was never a pedagogy choice - it was a missing route.

Source: ``app/api/evaluate/route.ts`` (316 lines) in the ``codrut-app`` repository.
The system prompt is copied word for word into ``prompts/evaluator.md``.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select

from codrut.contracts.generation import (
    GenerationMessage,
    GenerationPurpose,
    GenerationRequest,
)
from codrut.modules.companies.models import ProjectMembership
from codrut.modules.practice.budget import BudgetExceeded, release, reserve, settle
from codrut.modules.practice.models import (
    CompetencyScore,
    InsightMoment,
    PracticeProgramSettings,
    PracticeTurn,
    SessionSample,
    TurnRole,
)
from codrut.modules.practice.pricing import estimate_pessimistic_cost

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    Path(__file__).parent / "prompts" / "evaluator.md"
).read_text(encoding="utf-8").strip()

# Poarta din aplicatia veche (rd. 143). Comentariul de acolo spune de ce si se
# pastreaza: sub prag nu se salveaza scoruri, ca sa nu se poata aduna puncte din
# sesiuni neserioase si ca sa nu apara scoruri false.
#
# Plicul 143: pragul se socoteste NUMAI pe ce a scris OMUL. Pana acum numara tot transcriptul,
# cu replicile lui Cody, care sunt lungi si au paragrafe — deci trecea mereu. Masurat la 141:
# „Da, hai." si „Ok." (11 semne scrise de om) au primit note pe 9 competente.
MIN_MESSAGES = 3  # replici ale omului
MIN_CHARS = 150  # semne scrise de om

# Prefixul care desparte cele doua feluri de momente. Cele cu `[TRAINER]` sunt
# notele pentru Andrei si NU ajung niciodata pe ecranul participantului.
TRAINER_PREFIX = "[TRAINER]"

INSUFFICIENT_CLOSING = {
    "good_moment": "Ai început să interacționezi cu Cody — primul pas e făcut.",
    "growth_point": (
        "Sesiunea a fost prea scurtă pentru o evaluare reală. Pentru ca antrenamentul "
        "să producă insight, ai nevoie de cel puțin 5-6 schimburi pe aceeași situație."
    ),
    "homework": (
        "Reia sesiunea cu o situație concretă din viața ta — ceva care încă te macină. "
        "Mergi în detaliu cu Cody, nu te grăbi să închizi."
    ),
}


def build_transcript(turns: list[PracticeTurn], participant_name: str) -> str:
    linii = []
    for t in turns:
        cine = participant_name if t.role == TurnRole.participant else "Cody"
        linii.append(f"{cine}: {t.text}")
    return "\n\n".join(linii)


def _extract_json(text: str) -> dict | None:
    """Ia obiectul JSON din raspuns.

    Furnizorul e rugat sa raspunda direct cu JSON, dar se pastreaza si curatarea
    de ```json din aplicatia veche, pentru cazul in care modelul il imbraca oricum.
    """
    s = (text or "").strip()
    if not s:
        return None
    if s.startswith("```json"):
        s = s[7:]
    elif s.startswith("```"):
        s = s[3:]
    if s.endswith("```"):
        s = s[:-3]
    s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


class PracticeEvaluator:
    """Evalueaza o sesiune pe competentele proiectului si scrie ce a gasit."""

    def __init__(self, session, generation_provider, settings) -> None:
        self.session = session
        self.generation_provider = generation_provider
        self.settings = settings

    async def evaluate_session(
        self,
        *,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        project_id: uuid.UUID | None,
        competencies: list[str],
        transcript: str,
        replici_om: list[str],
        source_type: str = "session",
    ) -> dict:
        if not competencies:
            logger.warning(
                "evaluate_session: proiectul %s nu are nicio competenta aleasa; "
                "nu se evalueaza nimic.", project_id,
            )
            return {"skipped": True, "reason": "no_competencies"}

        scrise = [r.strip() for r in replici_om if (r or "").strip()]
        mesaje = len(scrise)
        caractere = sum(len(r) for r in scrise)
        if mesaje < MIN_MESSAGES or caractere < MIN_CHARS:
            logger.info(
                "[EVALUATOR] Sesiune insuficienta: %s mesaje, %s caractere",
                mesaje, caractere,
            )
            return {
                "insufficient": True,
                "reason": (
                    f"Sesiune prea scurtă ({mesaje} replici, {caractere} semne scrise de om). "
                    f"Minim: {MIN_MESSAGES} replici și {MIN_CHARS} semne scrise de om."
                ),
                "scores": [],
                "session_closing": INSUFFICIENT_CLOSING,
                "recommendations_for_trainer": [],
            }

        prompt = (
            f"Te rog să evaluezi următoarele competențe: {', '.join(competencies)}.\n\n"
            "Aici este transcriptul conversației de evaluat:\n\n"
            f"{transcript}\n\n"
            "Amintește-ți să returnezi DOAR JSON valid, respectând structura cerută."
        )
        cerere = GenerationRequest(
            messages=(GenerationMessage(role="user", text=prompt),),
            system_instruction=SYSTEM_PROMPT,
            purpose=GenerationPurpose.evaluator,
            max_output_tokens=self.settings.vertex_max_output_tokens_evaluator,
            temperature=0.0,
            thinking_budget=self.settings.thinking_budget_evaluator,
            response_mime_type="application/json",
        )

        # A DOUA chemare de la inchidere trece si ea prin buget — plicul 129, partea E.
        #
        # Prima (rezumatul) a fost legata in `service.py`. Asta, evaluarea structurala, ramasese
        # tot pe dinafara: la masuratoarea de dupa reparatie a iesit o singura rezervare dupa
        # ultima replica, desi la inchidere se cheama modelul de DOUA ori. Aceeasi scapare, in
        # alt fisier.
        rezervare_id = None
        try:
            setari_program, plafon = await self._plafonul_proiectului(project_id)
            if setari_program is not None:
                cuvinte = len(prompt.split()) + len(SYSTEM_PROMPT.split())
                rezervare_id = await reserve(
                    session=self.session,
                    program_settings_id=setari_program.id,
                    estimated_usd=estimate_pessimistic_cost(
                        prompt_tokens=max(1, cuvinte),
                        max_output_tokens=self.settings.vertex_max_output_tokens_evaluator,
                        thinking_budget=self.settings.thinking_budget_evaluator,
                        settings=self.settings,
                    ),
                    cap_usd=plafon,
                    session_id=session_id,
                )
        except BudgetExceeded:
            logger.warning("[EVALUATOR] plafonul atins; evaluarea structurala nu se mai face")
            return {"skipped": True, "reason": "budget_exceeded"}

        try:
            rezultat = await self.generation_provider.generate(cerere)
        except Exception as err:
            logger.warning("[EVALUATOR] chemarea a esuat: %s", err)
            if rezervare_id is not None:
                await release(self.session, rezervare_id)
            return {"error": str(err)}

        if rezervare_id is not None:
            await settle(self.session, rezervare_id, actual_usd=rezultat.estimated_usd)

        date = _extract_json(rezultat.text)
        if date is None:
            # Lectia plicului 28: o defectiune tacuta e mai rea decat una zgomotoasa.
            logger.warning(
                "[EVALUATOR] raspunsul nu contine JSON valid (sesiune=%s, "
                "lungime=%s, finish_reason=%s). Nu s-a salvat nimic.",
                session_id, len(rezultat.text or ""), rezultat.finish_reason,
            )
            return {"error": "invalid_json", "raw_length": len(rezultat.text or "")}

        await self._persist(
            date=date,
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            source_type=source_type,
        )
        return date

    async def _plafonul_proiectului(self, project_id):
        """Setarile de program ale proiectului si plafonul lui de bani.

        Aceeasi socoteala ca la replici si la rezumat: cate persoane active are proiectul, ori
        plafonul pe participant. Scrisa aici fiindca evaluatorul n-are alt drum spre ea.
        """
        if project_id is None:
            return None, Decimal("0")
        setari = (
            await self.session.execute(
                select(PracticeProgramSettings).where(
                    PracticeProgramSettings.project_id == project_id
                )
            )
        ).scalars().first()
        if setari is None:
            return None, Decimal("0")
        activi = (
            await self.session.execute(
                select(func.count(ProjectMembership.id)).where(
                    ProjectMembership.project_id == project_id,
                    ProjectMembership.active.is_(True),
                )
            )
        ).scalar_one() or 0
        return setari, Decimal(activi) * setari.usd_cap_per_participant

    async def _persist(
        self,
        *,
        date: dict,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        project_id: uuid.UUID | None,
        source_type: str,
    ) -> None:
        scrise = {"scoruri": 0, "momente": 0, "mostre": 0, "recomandari": 0}

        for scor in date.get("scores") or []:
            if not isinstance(scor, dict) or not scor.get("evaluated"):
                continue
            valoare = scor.get("score")
            nivel = scor.get("level")
            nume = scor.get("competency")
            if valoare is None or nivel is None or not nume:
                continue
            self.session.add(CompetencyScore(
                user_id=user_id,
                project_id=project_id,
                competency_id=None,
                score=max(0, min(100, int(valoare))),
                level=max(1, min(3, int(nivel))),
                justification=scor.get("justification"),
                conversation_id=str(session_id),
                competency_name=str(nume),
                source_type=source_type,
            ))
            scrise["scoruri"] += 1

        insight = date.get("insight")
        if insight:
            self.session.add(InsightMoment(
                user_id=user_id,
                conversation_id=str(session_id),
                competency_id=None,
                summary=str(insight),
            ))
            scrise["momente"] += 1

        real = date.get("sample_real") or {}
        inventat = date.get("sample_invented") or {}
        if real or inventat:
            self.session.add(SessionSample(
                user_id=user_id,
                conversation_id=str(session_id),
                competency_id=None,
                real_weak=real.get("weak"),
                real_improved=real.get("improved"),
                invented_weak=inventat.get("weak"),
                invented_improved=inventat.get("improved"),
            ))
            scrise["mostre"] += 1

        for rec in date.get("recommendations_for_trainer") or []:
            if not isinstance(rec, dict):
                continue
            actiuni = rec.get("actions") or []
            coada = ""
            if isinstance(actiuni, list) and actiuni:
                coada = " Acțiuni: " + " · ".join(str(a) for a in actiuni)
            self.session.add(InsightMoment(
                user_id=user_id,
                conversation_id=str(session_id),
                competency_id=None,
                summary=(
                    f"{TRAINER_PREFIX} {rec.get('competency')} "
                    f"({rec.get('score')}): {rec.get('analysis')}{coada}"
                ),
            ))
            scrise["recomandari"] += 1

        await self.session.flush()
        logger.info(
            "[EVALUATOR] sesiune=%s scris: %s scoruri, %s momente, %s mostre, "
            "%s recomandari pentru trainer",
            session_id, scrise["scoruri"], scrise["momente"],
            scrise["mostre"], scrise["recomandari"],
        )
