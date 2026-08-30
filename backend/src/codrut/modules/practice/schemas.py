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


class PracticeSessionEndResponse(BaseModel):
    session: PracticeSessionResponse
    summary: str | None = None


class PracticeStareSummaryResponse(BaseModel):
    status: str
    status_text: str
    prompt_version: str
    material_bytes: int
    provider: str
    model: str
    region: str
    sessions_today: int
    turns_today: int
    cached_turns: int = 0
    cache_percent: float = 0.0
    cost_today_usd: float = 0.0
    last_error: str | None = None


class PracticeTranscribeResponse(BaseModel):
    text: str
    estimated_usd: float = 0.0


class CompetencyDashboardItem(BaseModel):
    name: str
    level: str
    level_description: str
    color: str
    total_roleplays: int
    scores_70_count: int
    days_span_70: int
    distinct_days_70: int
    average_score: float
    why_not_higher: str


class InsightMomentItem(BaseModel):
    id: str
    summary: str
    competency_name: str | None = None
    created_at: str


class SessionSampleItem(BaseModel):
    id: str
    real_weak: str | None = None
    real_improved: str | None = None
    invented_weak: str | None = None
    invented_improved: str | None = None
    created_at: str


class PracticeDashboardResponse(BaseModel):
    participant_name: str
    xp_today: int
    xp_daily_cap: int = 100
    xp_total: int
    streak_days: int
    streak_bonus_pct: int
    evidence_ceiling: int
    competencies: list[CompetencyDashboardItem]
    insight_moments: list[InsightMomentItem]
    session_samples: list[SessionSampleItem]

