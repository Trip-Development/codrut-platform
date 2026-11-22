from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session
from codrut.core.config import Settings, get_settings
from codrut.core.errors import DomainError
from codrut.modules.companies.access import require_project_trainer
from codrut.modules.companies.models import ParticipantProfile
from codrut.modules.companies.policies import require_trainer_principal
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.practice.acord import da_acordul, starea_acordului
from codrut.modules.practice.dashboard_service import PracticeDashboardService
from codrut.modules.practice.evolution_service import PracticeEvolutionService
from codrut.modules.practice.generation_provider import build_generation_provider
from codrut.modules.practice.notificare_zilnica import (
    aboneaza,
    descrierea,
    opreste,
    starea,
)
from codrut.modules.practice.objective_service import (
    alege,
    alegerea_mea,
    lista_obiectivelor,
)
from codrut.modules.practice.person_service import PracticePersonService
from codrut.modules.practice.replica_zilei import starea_zilei, trimite_replica
from codrut.modules.practice.room_service import (
    PracticeInvitationsService,
    PracticeRoomService,
)
from codrut.modules.practice.schemas import (
    PointsEarnedItem,
    PracticeConsentRequest,
    PracticeConsentResponse,
    PracticeDailyReminderEndpointRequest,
    PracticeDailyReminderInfoResponse,
    PracticeDailyReminderSetRequest,
    PracticeDailyReminderStateResponse,
    PracticeDailyReplyRequest,
    PracticeDailyReplyResponse,
    PracticeDashboardResponse,
    PracticeEvolutionResponse,
    PracticeObjectiveChoiceResponse,
    PracticeObjectiveChooseRequest,
    PracticeObjectivesResponse,
    PracticePersonResponse,
    PracticeRoomResponse,
    PracticeSessionCreateRequest,
    PracticeSessionDetailResponse,
    PracticeSessionEndRequest,
    PracticeSessionEndResponse,
    PracticeSessionResponse,
    PracticeSetupRequest,
    PracticeSetupResponse,
    PracticeStareSummaryResponse,
    PracticeThemeItem,
    PracticeTranscribeResponse,
    PracticeTurnCreateRequest,
    PracticeTurnResponse,
    PracticeTurnSubmitResponse,
    TrainerNoteCreateRequest,
    TrainerNoteItem,
    TrainingInvitationItem,
    TrainingInvitationSendItem,
    TrainingInvitationSendRequest,
)
from codrut.modules.practice.service import PracticeSessionService
from codrut.modules.practice.setup_service import PracticeSetupService

logger = logging.getLogger(__name__)
router = APIRouter()


async def _raspuns_de_pornire(
    session: AsyncSession, practice_session, prima_replica
) -> PracticeSessionResponse:
    """Raspunsul la pornirea unei sesiuni, cu replica de deschidere a lui Codrut.

    `first_turn` exista in schema de la inceput si era mereu `null` — nimeni nu-l umplea
    si nimeni nu-l citea. Ramane `null` cand modelul n-a raspuns: sesiunea e deschisa,
    iar ecranul arata starea goala.
    """
    raspuns = PracticeSessionResponse.model_validate(practice_session)
    if prima_replica is not None:
        raspuns.first_turn = PracticeTurnResponse.model_validate(prima_replica)
    # Omul isi vede codul pe ecranul de exersare — plicul 138.
    profil = await session.get(ParticipantProfile, practice_session.participant_profile_id)
    raspuns.cody_alias = profil.cody_alias if profil is not None else None
    return raspuns


@router.post(
    "/sessions",
    response_model=PracticeSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_practice_session(
    payload: PracticeSessionCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeSessionResponse:
    """Start a new practice session for an authenticated participant."""
    service = PracticeSessionService(session=session)
    practice_session, prima_replica = await service.start_session(
        principal=principal,
        project_id=payload.project_id,
        kind=payload.kind,
        scenario_id=payload.scenario_id,
        pe_obiectiv=payload.pe_obiectiv,
    )
    await session.commit()
    return await _raspuns_de_pornire(session, practice_session, prima_replica)


@router.post(
    "/trainer/sessions",
    response_model=PracticeSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_trainer_practice_session(
    payload: PracticeSessionCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PracticeSessionResponse:
    """Start a practice session directly for a trainer (only when enabled)."""
    if not settings.practice_trainer_direct_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )

    if not principal.can_access_workspace(UserRole.trainer):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )
    await require_project_trainer(session, principal, payload.project_id)
    # Plicul 244: trainerul nu are obiectiv.
    if payload.pe_obiectiv:
        raise DomainError(
            "Pe obiectiv exersează numai participantul.",
            code="obiectiv_numai_pentru_participant",
        )

    service = PracticeSessionService(session=session, settings=settings)
    practice_session, prima_replica = await service.start_trainer_session(
        principal=principal,
        project_id=payload.project_id,
        kind=payload.kind,
        scenario_id=payload.scenario_id,
    )
    await session.commit()
    return await _raspuns_de_pornire(session, practice_session, prima_replica)


@router.post(
    "/sessions/{session_id}/turns",
    response_model=PracticeTurnSubmitResponse,
)
async def submit_practice_turn(
    session_id: UUID,
    payload: PracticeTurnCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeTurnSubmitResponse:
    """Submit a participant turn, trigger actor generation, and return turn results."""
    service = PracticeSessionService(session=session)
    p_turn, actor_turn, session_state = await service.submit_turn(
        principal=principal,
        session_id=session_id,
        text=payload.text,
    )
    return PracticeTurnSubmitResponse(
        participant_turn=PracticeTurnResponse.model_validate(p_turn),
        actor_turn=PracticeTurnResponse.model_validate(actor_turn) if actor_turn else None,
        session_state=session_state,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=PracticeSessionDetailResponse,
)
async def get_practice_session_history(
    session_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeSessionDetailResponse:
    """Retrieve practice session details and its ordered conversation history."""
    service = PracticeSessionService(session=session)
    session_obj, turns = await service.get_session_history(
        principal=principal,
        session_id=session_id,
    )
    return PracticeSessionDetailResponse(
        session=PracticeSessionResponse.model_validate(session_obj),
        turns=[PracticeTurnResponse.model_validate(t) for t in turns],
    )


@router.post(
    "/sessions/{session_id}/end",
    response_model=PracticeSessionEndResponse,
)
async def end_practice_session(
    session_id: UUID,
    payload: PracticeSessionEndRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeSessionEndResponse:
    """Explicitly end a practice session, generate summary, and record outcome."""
    service = PracticeSessionService(session=session)
    session_obj, summary = await service.end_session(
        principal=principal,
        session_id=session_id,
        outcome_kind=payload.outcome_kind,
        note=payload.note,
    )
    await session.commit()
    # Plicul 177: „+N puncte la …”. Închiderea nu are voie să pice din cauza anunțului.
    try:
        puncte = await PracticeDashboardService(session).puncte_castigate_in_sedinta(
            principal, session_id
        )
    except Exception:
        logger.warning("practice_puncte_la_inchidere_esuat sesiune=%s", session_id, exc_info=True)
        puncte = []
    return PracticeSessionEndResponse(
        session=PracticeSessionResponse.model_validate(session_obj),
        summary=summary,
        points_earned=[PointsEarnedItem(**p) for p in puncte],
    )


@router.get(
    "/stare-summary",
    response_model=PracticeStareSummaryResponse,
)
async def get_stare_summary(
    session: Annotated[AsyncSession, Depends(db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PracticeStareSummaryResponse:
    """Get system health and Cody prompt/stat summary for the /stare page."""
    service = PracticeSessionService(session=session, settings=settings)
    data = await service.get_stare_summary()
    return PracticeStareSummaryResponse(**data)


@router.post(
    "/transcribe",
    response_model=PracticeTranscribeResponse,
)
async def transcribe_practice_audio(
    file: Annotated[UploadFile, File(...)],
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PracticeTranscribeResponse:
    """Transcribe an audio recording into text with Vertex AI Gemini."""
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fisierul audio este gol.",
        )
    service = PracticeSessionService(session=session, settings=settings)
    text, cost_usd = await service.transcribe(
        audio_bytes=audio_bytes,
        mime_type=file.content_type or "audio/webm",
    )
    return PracticeTranscribeResponse(
        text=text,
        estimated_usd=float(round(cost_usd, 6)),
    )


@router.get(
    "/dashboard",
    response_model=PracticeDashboardResponse,
)
@router.get(
    "/participant/dashboard",
    response_model=PracticeDashboardResponse,
)
async def get_participant_practice_dashboard(
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    project_id: UUID | None = None,
) -> PracticeDashboardResponse:
    """Get participant practice stats, XP, streak, and competency evidence levels."""
    dashboard_service = PracticeDashboardService(session=session)
    data = await dashboard_service.get_participant_dashboard_data(
        principal=principal,
        project_id=project_id,
    )
    return PracticeDashboardResponse(**data)




# ---- acordul la prima intrare (plicul 139) ----
# Ecranul citeste textul de aici si trimite amprenta textului pe care l-a vazut omul. Refuzul
# adevarat e la pornirea sedintei (`acord_lipsa`), nu pe ecran.


@router.get(
    "/projects/{project_id}/conversatia-neincheiata",
    response_model=PracticeSessionDetailResponse | None,
)
async def get_conversatia_neincheiata(
    project_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeSessionDetailResponse | None:
    """Conversația neîncheiată a omului pe proiect, sau `null` — plicul 209. Numai citire."""
    service = PracticeSessionService(session=session)
    gasita = await service.conversatia_neincheiata(principal=principal, project_id=project_id)
    if gasita is None:
        return None
    session_obj, turns = gasita
    return PracticeSessionDetailResponse(
        session=await _raspuns_de_pornire(session, session_obj, None),
        turns=[PracticeTurnResponse.model_validate(t) for t in turns],
    )


@router.get("/projects/{project_id}/acord", response_model=PracticeConsentResponse)
async def get_practice_consent(
    project_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeConsentResponse:
    """Textul acordului, cu codul omului in el, si daca l-a bifat deja pe proiectul asta."""
    stare = await starea_acordului(session, principal, project_id)
    await session.commit()  # codul, daca s-a dat acum
    return PracticeConsentResponse(**stare)


@router.post("/projects/{project_id}/acord", response_model=PracticeConsentResponse)
async def give_practice_consent(
    project_id: UUID,
    payload: PracticeConsentRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeConsentResponse:
    """Omul a bifat: se tine minte cine, ce proiect, cand si ce text."""
    stare = await da_acordul(session, principal, project_id, payload.amprenta)
    await session.commit()
    return PracticeConsentResponse(**stare)


# ---- obiectivele de aplicare (plicul 230, L1-P1) ----
# Numai ale omului, pentru el însuși: omul se caută ca la acord. Nicio rută de trainer/HR nu
# primește alegerea cuiva; în jurnal nu se scrie nimic despre ea.


@router.get("/projects/{project_id}/obiective", response_model=PracticeObjectivesResponse)
async def get_practice_objectives(
    project_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeObjectivesResponse:
    """Lista de obiective a proiectului (goală dacă proiectul nu are una)."""
    return PracticeObjectivesResponse(**await lista_obiectivelor(session, principal, project_id))


@router.get("/projects/{project_id}/obiectiv", response_model=PracticeObjectiveChoiceResponse)
async def get_my_practice_objective(
    project_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeObjectiveChoiceResponse:
    """Obiectivul ales de om pe proiect, data primei alegeri și istoricul."""
    return PracticeObjectiveChoiceResponse(**await alegerea_mea(session, principal, project_id))


@router.post("/projects/{project_id}/obiectiv", response_model=PracticeObjectiveChoiceResponse)
async def choose_practice_objective(
    project_id: UUID,
    payload: PracticeObjectiveChooseRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeObjectiveChoiceResponse:
    """Omul își alege obiectivul; alegerea veche rămâne în istoric."""
    stare = await alege(session, principal, project_id, payload.objective_id)
    await session.commit()
    return PracticeObjectiveChoiceResponse(**stare)


# ---- „O replică pe zi” (plicul 236, L2-P1) ----
# Numai ale omului, pentru el însuși: omul se caută ca la acord, cu aceleași verificări ca la
# pornirea unei ședințe. Nicio rută de trainer/HR nu primește nimic despre replica zilei; în
# jurnal nu se scrie nimic despre ea.


@router.get("/projects/{project_id}/replica-zilei", response_model=PracticeDailyReplyResponse)
async def get_daily_reply(
    project_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeDailyReplyResponse:
    """Situația zilei, replica de azi (dacă există) și seria."""
    stare = await starea_zilei(session, principal, project_id, acum=datetime.now(UTC))
    await session.commit()
    return PracticeDailyReplyResponse(**stare)


@router.post("/projects/{project_id}/replica-zilei", response_model=PracticeDailyReplyResponse)
async def submit_daily_reply(
    project_id: UUID,
    payload: PracticeDailyReplyRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PracticeDailyReplyResponse:
    """Omul trimite replica zilei; profesorul de azi îi răspunde."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        stare = await trimite_replica(
            session, principal, project_id, payload.situation_id, payload.replica,
            profesor=build_generation_provider(settings), settings=settings, redis=redis,
            acum=datetime.now(UTC),
        )
    finally:
        await redis.aclose()
    return PracticeDailyReplyResponse(**stare)


# ---- notificarea zilnică a replicii zilei (plicul 252, L3-P2) ----
# Numai ale omului, cu aceleași verificări ca la replica zilei. Omul o pornește singur și o
# oprește oricând (rândul se șterge). Nimic despre ea la trainer, HR sau pe Tablou.


@router.get(
    "/projects/{project_id}/notificare-zilnica",
    response_model=PracticeDailyReminderInfoResponse,
)
async def get_daily_reminder(
    project_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PracticeDailyReminderInfoResponse:
    """E disponibilă notificarea, cheia publică și orele din care alege omul."""
    return PracticeDailyReminderInfoResponse(
        **await descrierea(session, principal, project_id, settings)
    )


@router.post(
    "/projects/{project_id}/notificare-zilnica/stare",
    response_model=PracticeDailyReminderStateResponse,
)
async def get_daily_reminder_state(
    project_id: UUID,
    payload: PracticeDailyReminderEndpointRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeDailyReminderStateResponse:
    """E pornită pe acest telefon, pentru acest om și proiect?"""
    return PracticeDailyReminderStateResponse(
        **await starea(session, principal, project_id, payload.endpoint)
    )


@router.put(
    "/projects/{project_id}/notificare-zilnica",
    response_model=PracticeDailyReminderStateResponse,
)
async def set_daily_reminder(
    project_id: UUID,
    payload: PracticeDailyReminderSetRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PracticeDailyReminderStateResponse:
    """Omul pornește notificarea sau îi schimbă ora."""
    stare = await aboneaza(
        session, principal, project_id, payload.endpoint, payload.ora, settings
    )
    await session.commit()
    return PracticeDailyReminderStateResponse(**stare)


@router.post(
    "/projects/{project_id}/notificare-zilnica/opreste",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def stop_daily_reminder(
    project_id: UUID,
    payload: PracticeDailyReminderEndpointRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> None:
    """Omul oprește notificarea: rândul se șterge."""
    await opreste(session, principal, project_id, payload.endpoint)
    await session.commit()


# ---- configurarea exersarii pe un proiect de training (plic 29, punctele 4 si 6) ----
# Pana acum niciun punct al aplicatiei nu crea `practice_program_settings`; randul se
# punea de mana, cu un script. Rutele astea inchid ocolul: trainerul alege tema, bifeaza
# competentele, si aplicatia scrie ea configurarea.


@router.get("/themes", response_model=list[PracticeThemeItem])
async def list_practice_themes(
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[PracticeThemeItem]:
    """Temele din care poate alege trainerul, fiecare cu competentele ei."""
    require_trainer_principal(principal)
    themes = await PracticeSetupService(session).list_themes()
    return [PracticeThemeItem(**t) for t in themes]


@router.get("/projects/{project_id}/setup", response_model=PracticeSetupResponse)
async def get_practice_setup(
    project_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeSetupResponse:
    """Cum e configurata exersarea pe proiect: tema si competentele bifate."""
    await require_project_trainer(session, principal, project_id)
    return PracticeSetupResponse(**await PracticeSetupService(session).get_setup(project_id))


@router.put("/projects/{project_id}/setup", response_model=PracticeSetupResponse)
async def configure_practice_setup(
    project_id: UUID,
    payload: PracticeSetupRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeSetupResponse:
    """Configureaza exersarea si scrie competentele alese. Se poate reveni oricand."""
    await require_project_trainer(session, principal, project_id)
    result = await PracticeSetupService(session).configure(
        project_id=project_id,
        theme_id=payload.theme_id,
        competency_names=payload.competencies,
        is_enabled=payload.is_enabled,
        max_sessions_per_day=payload.max_sessions_per_day,
        quiz_enabled=payload.quiz_enabled,
        objective_catalog=payload.objective_catalog,
    )
    await session.commit()
    return PracticeSetupResponse(**result)


@router.get("/projects/{project_id}/evolution", response_model=PracticeEvolutionResponse)
async def get_project_evolution(
    project_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeEvolutionResponse:
    """Evolutia competentelor pe echipa — fila trainerului la proiectele de training."""
    await require_project_trainer(session, principal, project_id)
    date = await PracticeEvolutionService(session).project_evolution(project_id)
    return PracticeEvolutionResponse(**date)


@router.get("/projects/{project_id}/room", response_model=PracticeRoomResponse)
async def get_project_room(
    project_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeRoomResponse:
    """Camera de training — ecranul proiectului, cu toate sectiunile lui."""
    await require_project_trainer(session, principal, project_id)
    return PracticeRoomResponse(**await PracticeRoomService(session).project_room(project_id))


@router.get(
    "/projects/{project_id}/participants/{profile_id}",
    response_model=PracticePersonResponse,
)
async def get_project_person(
    project_id: UUID,
    profile_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticePersonResponse:
    """Pagina omului — al doilea ecran al camerei de training."""
    await require_project_trainer(session, principal, project_id)
    date = await PracticePersonService(session).person(project_id, profile_id)
    return PracticePersonResponse(**date)


@router.post(
    "/projects/{project_id}/participants/{profile_id}/notes",
    response_model=TrainerNoteItem,
    status_code=status.HTTP_201_CREATED,
)
async def add_trainer_note(
    project_id: UUID,
    profile_id: UUID,
    payload: TrainerNoteCreateRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> TrainerNoteItem:
    """Nota trainerului despre un participant. Andrei scrie, se salveaza."""
    await require_project_trainer(session, principal, project_id)
    nota = await PracticePersonService(session).add_note(
        project_id, profile_id, principal.user_id, payload.note,
    )
    await session.commit()
    return TrainerNoteItem(**nota)


@router.get(
    "/projects/{project_id}/invitations",
    response_model=list[TrainingInvitationItem],
)
async def list_training_invitations(
    project_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[TrainingInvitationItem]:
    """Cine e invitat, cine a intrat, cine a facut testul de intrare."""
    await require_project_trainer(session, principal, project_id)
    randuri = await PracticeInvitationsService(session).statuses(project_id)
    return [TrainingInvitationItem(**r) for r in randuri]


@router.post(
    "/projects/{project_id}/invitations",
    response_model=list[TrainingInvitationSendItem],
)
async def send_training_invitations(
    project_id: UUID,
    payload: TrainingInvitationSendRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[TrainingInvitationSendItem]:
    """Face invitatiile pentru oamenii bifati si incearca emailul.

    Calea obisnuita de invitatii cere o asignare de chestionar, pe care un
    proiect de training n-o are — de aceea trainingul are calea lui. Linkul se
    intoarce si cand emailul nu pleaca.
    """
    await require_project_trainer(session, principal, project_id)
    randuri = await PracticeInvitationsService(session).send(
        project_id,
        payload.participant_profile_ids,
        trainer_user_id=principal.user_id,
    )
    await session.commit()
    return [TrainingInvitationSendItem(**r) for r in randuri]
