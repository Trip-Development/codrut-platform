from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from codrut.modules.practice.models import OutcomeKind, SessionKind, SessionState, TurnRole


class PracticeSessionCreateRequest(BaseModel):
    project_id: UUID
    kind: SessionKind = SessionKind.roleplay
    scenario_id: UUID | None = None


class PracticeTurnCreateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)


class PracticeSessionEndRequest(BaseModel):
    outcome_kind: OutcomeKind = OutcomeKind.good
    note: str | None = None


class PracticeTurnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    ordinal: int
    role: TurnRole
    text: str
    created_at: datetime


class PracticeSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    program_settings_id: UUID
    participant_profile_id: UUID
    pack_id: UUID
    scenario_id: UUID | None = None
    kind: SessionKind
    state: SessionState
    started_at: datetime
    ended_at: datetime | None = None
    turn_count: int = 0
    prompt_version: str | None = None
    first_turn: PracticeTurnResponse | None = None


class PracticeTurnSubmitResponse(BaseModel):
    participant_turn: PracticeTurnResponse
    actor_turn: PracticeTurnResponse | None = None
    session_state: SessionState = SessionState.open


class PracticeSessionDetailResponse(BaseModel):
    session: PracticeSessionResponse
    turns: list[PracticeTurnResponse]
