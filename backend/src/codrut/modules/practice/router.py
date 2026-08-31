from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from codrut.api.dependencies import current_principal, db_session
from codrut.core.config import Settings, get_settings
from codrut.modules.companies.policies import require_trainer_principal
from codrut.modules.identity.models import UserRole
from codrut.modules.identity.schemas import SessionPrincipal
from codrut.modules.practice.dashboard_service import PracticeDashboardService
from codrut.modules.practice.evolution_service import PracticeEvolutionService
from codrut.modules.practice.person_service import PracticePersonService
from codrut.modules.practice.room_service import (
    PracticeInvitationsService,
    PracticeRoomService,
)
from codrut.modules.practice.schemas import (
    PracticeDashboardResponse,
    PracticeEvolutionResponse,
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

router = APIRouter()


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
    practice_session = await service.start_session(
        principal=principal,
        project_id=payload.project_id,
        kind=payload.kind,
        scenario_id=payload.scenario_id,
    )
    await session.commit()
    return PracticeSessionResponse.model_validate(practice_session)


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

    service = PracticeSessionService(session=session, settings=settings)
    practice_session = await service.start_trainer_session(
        principal=principal,
        project_id=payload.project_id,
        kind=payload.kind,
        scenario_id=payload.scenario_id,
    )
    await session.commit()
    return PracticeSessionResponse.model_validate(practice_session)


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
    return PracticeSessionEndResponse(
        session=PracticeSessionResponse.model_validate(session_obj),
        summary=summary,
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
    require_trainer_principal(principal)
    return PracticeSetupResponse(**await PracticeSetupService(session).get_setup(project_id))


@router.put("/projects/{project_id}/setup", response_model=PracticeSetupResponse)
async def configure_practice_setup(
    project_id: UUID,
    payload: PracticeSetupRequest,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeSetupResponse:
    """Configureaza exersarea si scrie competentele alese. Se poate reveni oricand."""
    require_trainer_principal(principal)
    result = await PracticeSetupService(session).configure(
        project_id=project_id,
        theme_id=payload.theme_id,
        competency_names=payload.competencies,
        is_enabled=payload.is_enabled,
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
    require_trainer_principal(principal)
    date = await PracticeEvolutionService(session).project_evolution(project_id)
    return PracticeEvolutionResponse(**date)


@router.get("/projects/{project_id}/room", response_model=PracticeRoomResponse)
async def get_project_room(
    project_id: UUID,
    principal: Annotated[SessionPrincipal, Depends(current_principal)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> PracticeRoomResponse:
    """Camera de training — ecranul proiectului, cu toate sectiunile lui."""
    require_trainer_principal(principal)
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
    require_trainer_principal(principal)
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
    require_trainer_principal(principal)
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
    require_trainer_principal(principal)
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
    require_trainer_principal(principal)
    randuri = await PracticeInvitationsService(session).send(
        project_id,
        payload.participant_profile_ids,
        trainer_user_id=principal.user_id,
    )
    await session.commit()
    return [TrainingInvitationSendItem(**r) for r in randuri]
