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



# ---- configurarea exersarii pe un proiect de training (plic 29, punctele 4 si 6) ----

class ThemeCompetencyItem(BaseModel):
    name: str
    description: str | None = None
    order_index: int = 0


class PracticeThemeItem(BaseModel):
    id: UUID
    name: str
    slug: str | None = None
    competencies: list[ThemeCompetencyItem] = Field(default_factory=list)
    has_knowledge_pack: bool = False
    scenario_count: int = 0
    usable: bool = False


class PracticeSetupRequest(BaseModel):
    theme_id: UUID
    # None inseamna „ia competentele temei" — adica bifate toate, cum sunt implicit.
    # O lista explicita inlocuieste selectia, inclusiv una goala.
    competencies: list[str] | None = None
    is_enabled: bool = True


class PracticeSetupResponse(BaseModel):
    project_id: UUID
    project_name: str
    project_type: str | None = None
    configured: bool
    is_enabled: bool
    theme_id: UUID | None = None
    theme_name: str | None = None
    competencies: list[ThemeCompetencyItem] = Field(default_factory=list)


# ---- evolutia competentelor pe proiect (plic 29, punctul 2) ----

class EvolutionCompetencyItem(BaseModel):
    name: str
    test_in_average: float | None = None
    current_average: float | None = None
    test_out_average: float | None = None
    growth: float | None = None
    level: str
    level_description: str = ""
    color: str = ""
    scores_count: int = 0


class EvolutionWeekPoint(BaseModel):
    week_start: str
    average: float
    scores_count: int


class EvolutionParticipantItem(BaseModel):
    participant_profile_id: UUID
    user_id: UUID | None = None
    full_name: str
    email: str | None = None
    active: bool = True
    test_in_score: float | None = None
    test_out_score: float | None = None
    current_average: float | None = None
    sessions_count: int = 0
    closed_sessions_count: int = 0
    scores_count: int = 0


class PracticeEvolutionResponse(BaseModel):
    project_id: UUID
    project_name: str
    project_type: str | None = None
    participants_total: int
    participants_active: int
    test_in_completed: int | None = None
    test_out_enabled: bool = False
    test_pending_note: str
    competencies: list[EvolutionCompetencyItem] = Field(default_factory=list)
    weekly_average: list[EvolutionWeekPoint] = Field(default_factory=list)
    participants: list[EvolutionParticipantItem] = Field(default_factory=list)


# ---- camera de training: ecranul proiectului (plic 30) ----

class RoomCompetencyItem(BaseModel):
    name: str
    test_in: int = 0
    acum: int = 0
    test_out: int | None = None
    has_test_in: bool = False
    has_data: bool = False
    delta: int | None = None


class RoomQuizWeakSpot(BaseModel):
    name: str
    average: int


class RoomWeekPoint(BaseModel):
    week_start: str
    average: int
    scores_count: int


class RoomParticipantItem(BaseModel):
    participant_profile_id: UUID
    user_id: UUID | None = None
    full_name: str
    email: str | None = None
    has_account: bool = False
    average_score: int = 0
    sessions_count: int = 0
    last_activity: str | None = None
    inactive: bool = True
    has_test_in: bool = False
    has_test_out: bool = False
    active_membership: bool = True


class PracticeRoomResponse(BaseModel):
    project_id: UUID
    project_name: str
    project_type: str | None = None
    theme_name: str | None = None
    practice_configured: bool = False
    starts_at: str | None = None
    due_at: str | None = None
    timeline_percent: float | None = None
    participants_total: int = 0
    average_score: int = 0
    sessions_total: int = 0
    inactive_count: int = 0
    test_in_completed: int = 0
    test_out_completed: int = 0
    active_count: int = 0
    recurrent_count: int = 0
    test_out_active: bool = False
    competencies: list[RoomCompetencyItem] = Field(default_factory=list)
    growth_ranking: list[RoomCompetencyItem] = Field(default_factory=list)
    quiz_weak_spots: list[RoomQuizWeakSpot] = Field(default_factory=list)
    weekly_average: list[RoomWeekPoint] = Field(default_factory=list)
    participants: list[RoomParticipantItem] = Field(default_factory=list)


# ---- pagina omului (plic 30, ecranul 2) ----

class PersonTheoryItem(BaseModel):
    name: str
    test_in: int | None = None
    test_out: int | None = None
    delta: int | None = None


class PersonEvidenceItem(BaseModel):
    name: str
    level: str
    level_description: str = ""
    color: str = ""
    average_score: float = 0
    sessions_count: int = 0
    scores_count: int = 0
    why_not_higher: str = ""


class PersonTextItem(BaseModel):
    id: UUID
    summary: str
    created_at: str


class PersonSampleItem(BaseModel):
    id: UUID
    real_weak: str | None = None
    real_improved: str | None = None
    invented_weak: str | None = None
    invented_improved: str | None = None
    created_at: str


class TrainerNoteItem(BaseModel):
    id: UUID
    note: str
    created_at: str


class TrainerNoteCreateRequest(BaseModel):
    note: str = Field(min_length=1, max_length=4000)


class PracticePersonResponse(BaseModel):
    project_id: UUID
    project_name: str
    participant_profile_id: UUID
    user_id: UUID | None = None
    full_name: str
    email: str | None = None
    has_account: bool = False
    duration_days: int | None = None
    test_in_average: int | None = None
    progress_average: int = 0
    test_out_average: int | None = None
    sessions_count: int = 0
    theory: list[PersonTheoryItem] = Field(default_factory=list)
    evidence: list[PersonEvidenceItem] = Field(default_factory=list)
    top_progress: list[PersonEvidenceItem] = Field(default_factory=list)
    weekly_average: list[RoomWeekPoint] = Field(default_factory=list)
    quiz_weak_spots: list[RoomQuizWeakSpot] = Field(default_factory=list)
    insight_moments: list[PersonTextItem] = Field(default_factory=list)
    trainer_recommendations: list[PersonTextItem] = Field(default_factory=list)
    session_samples: list[PersonSampleItem] = Field(default_factory=list)
    trainer_notes: list[TrainerNoteItem] = Field(default_factory=list)


# ---- invitatiile in forma de training (plic 30) ----

class TrainingInvitationItem(BaseModel):
    participant_profile_id: UUID
    full_name: str
    email: str | None = None
    invited: bool = False
    invited_at: str | None = None
    invite_url: str | None = None
    has_account: bool = False
    has_test_in: bool = False


class TrainingInvitationSendRequest(BaseModel):
    """Pe cine invita trainerul. Bifele din tabel."""

    participant_profile_ids: list[UUID]


class TrainingInvitationSendItem(BaseModel):
    """Ce s-a intamplat cu fiecare om, pe rand.

    `invite_url` vine si cand `email_sent` e fals: linkul e bun oricum, iar
    trainerul il poate copia. `error` spune de ce n-a plecat emailul.
    """

    participant_profile_id: UUID
    full_name: str | None = None
    email: str | None = None
    invite_url: str | None = None
    email_sent: bool = False
    error: str | None = None
