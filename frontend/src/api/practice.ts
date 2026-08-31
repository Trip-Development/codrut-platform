import { apiFetch } from "./http";
import { getApiBaseUrl } from "./runtime";

export type SessionKind = "roleplay" | "coaching" | "knowledge" | "research";
export type SessionState = "open" | "closed";
export type TurnRole = "participant" | "actor";

export type PracticeTurn = {
  id: string;
  sessionId: string;
  ordinal: number;
  role: TurnRole;
  text: string;
  createdAt: string;
  expiresAt: string;
};

export type PracticeSession = {
  id: string;
  participantProfileId: string;
  programSettingsId: string;
  scenarioId?: string | null;
  kind: SessionKind;
  state: SessionState;
  turnCount: number;
  startedAt: string;
  endedAt?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type PracticeSessionDetail = {
  session: PracticeSession;
  turns: PracticeTurn[];
};

export type PracticeTurnSubmitResponse = {
  participantTurn: PracticeTurn;
  actorTurn: PracticeTurn | null;
  sessionState: SessionState;
};

export async function startPracticeSession(payload: {
  projectId: string;
  kind: SessionKind;
  scenarioId?: string;
}): Promise<PracticeSession> {
  const res = await apiFetch(`${getApiBaseUrl()}/practice/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: payload.projectId,
      kind: payload.kind,
      scenario_id: payload.scenarioId,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Nu am putut porni sesiunea de practică");
  }
  const data = await res.json();
  return {
    id: data.id,
    participantProfileId: data.participant_profile_id,
    programSettingsId: data.program_settings_id,
    scenarioId: data.scenario_id,
    kind: data.kind,
    state: data.state,
    turnCount: data.turn_count,
    startedAt: data.started_at,
    endedAt: data.ended_at,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
  };
}

export async function submitPracticeTurn(
  sessionId: string,
  text: string,
): Promise<PracticeTurnSubmitResponse> {
  const res = await apiFetch(`${getApiBaseUrl()}/practice/sessions/${sessionId}/turns`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Nu am putut trimite mesajul");
  }
  const data = await res.json();
  return {
    participantTurn: {
      id: data.participant_turn.id,
      sessionId: data.participant_turn.session_id,
      ordinal: data.participant_turn.ordinal,
      role: data.participant_turn.role,
      text: data.participant_turn.text,
      createdAt: data.participant_turn.created_at,
      expiresAt: data.participant_turn.expires_at,
    },
    actorTurn: data.actor_turn
      ? {
          id: data.actor_turn.id,
          sessionId: data.actor_turn.session_id,
          ordinal: data.actor_turn.ordinal,
          role: data.actor_turn.role,
          text: data.actor_turn.text,
          createdAt: data.actor_turn.created_at,
          expiresAt: data.actor_turn.expires_at,
        }
      : null,
    sessionState: data.session_state,
  };
}

export async function getPracticeSessionHistory(
  sessionId: string,
): Promise<PracticeSessionDetail> {
  const res = await apiFetch(`${getApiBaseUrl()}/practice/sessions/${sessionId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Nu am putut încărca istoricul sesiunii");
  }
  const data = await res.json();
  return {
    session: {
      id: data.session.id,
      participantProfileId: data.session.participant_profile_id,
      programSettingsId: data.session.program_settings_id,
      scenarioId: data.session.scenario_id,
      kind: data.session.kind,
      state: data.session.state,
      turnCount: data.session.turn_count,
      startedAt: data.session.started_at,
      endedAt: data.session.ended_at,
      createdAt: data.session.created_at,
      updatedAt: data.session.updated_at,
    },
    turns: (data.turns || []).map((t: {
      id: string;
      session_id: string;
      ordinal: number;
      role: TurnRole;
      text: string;
      created_at: string;
      expires_at: string;
    }) => ({
      id: t.id,
      sessionId: t.session_id,
      ordinal: t.ordinal,
      role: t.role,
      text: t.text,
      createdAt: t.created_at,
      expiresAt: t.expires_at,
    })),
  };
}

export type PracticeStareSummary = {
  status: string;
  statusText: string;
  promptVersion: string;
  materialBytes: number;
  provider: string;
  model: string;
  region: string;
  sessionsToday: number;
  turnsToday: number;
  cachedTurns: number;
  cachePercent: number;
  costTodayUsd: number;
  lastError?: string | null;
};

export type CompetencyDashboardItem = {
  name: string;
  level: "INTEGRARE" | "CONSOLIDARE" | "APLICARE" | "CONȘTIENTIZARE";
  levelDescription: string;
  color: string;
  totalRoleplays: number;
  scores70Count: number;
  daysSpan70: number;
  distinctDays70: number;
  averageScore: number;
  whyNotHigher: string;
};

export type InsightMomentItem = {
  id: string;
  summary: string;
  competencyName?: string | null;
  createdAt: string;
};

export type SessionSampleItem = {
  id: string;
  realWeak?: string | null;
  realImproved?: string | null;
  inventedWeak?: string | null;
  inventedImproved?: string | null;
  createdAt: string;
};

export type PracticeDashboardData = {
  participantName: string;
  xpToday: number;
  xpDailyCap: number;
  xpTotal: number;
  streakDays: number;
  streakBonusPct: number;
  evidenceCeiling: number;
  competencies: CompetencyDashboardItem[];
  insightMoments: InsightMomentItem[];
  sessionSamples: SessionSampleItem[];
};

export async function endPracticeSession(
  sessionId: string,
  payload?: { note?: string },
): Promise<{ session: PracticeSession; summary: string | null }> {
  const res = await apiFetch(`${getApiBaseUrl()}/practice/sessions/${sessionId}/end`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Nu am putut încheia sesiunea");
  }
  const data = await res.json();
  const sessionData = data.session || data;
  return {
    session: {
      id: sessionData.id,
      participantProfileId: sessionData.participant_profile_id,
      programSettingsId: sessionData.program_settings_id,
      scenarioId: sessionData.scenario_id,
      kind: sessionData.kind,
      state: sessionData.state,
      turnCount: sessionData.turn_count,
      startedAt: sessionData.started_at,
      endedAt: sessionData.ended_at,
      createdAt: sessionData.created_at,
      updatedAt: sessionData.updated_at,
    },
    summary: data.summary ?? null,
  };
}

export async function getPracticeStareSummary(): Promise<PracticeStareSummary> {
  const res = await apiFetch(`${getApiBaseUrl()}/practice/stare-summary`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Nu am putut obține starea sistemului");
  }
  const data = await res.json();
  return {
    status: data.status,
    statusText: data.status_text,
    promptVersion: data.prompt_version,
    materialBytes: data.material_bytes,
    provider: data.provider,
    model: data.model,
    region: data.region,
    sessionsToday: data.sessions_today,
    turnsToday: data.turns_today,
    cachedTurns: data.cached_turns,
    cachePercent: data.cache_percent || 0,
    costTodayUsd: data.cost_today_usd,
    lastError: data.last_error,
  };
}

export async function transcribeAudio(
  audioBlob: Blob,
): Promise<{ text: string; estimatedUsd: number }> {
  const formData = new FormData();
  formData.append("file", audioBlob, "recording.webm");

  const res = await apiFetch(`${getApiBaseUrl()}/practice/transcribe`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Nu am putut transcrie înregistrarea audio");
  }
  const data = await res.json();
  return {
    text: data.text,
    estimatedUsd: data.estimated_usd || 0,
  };
}

type RawCompetency = {
  name: string;
  level: CompetencyDashboardItem["level"];
  level_description: string;
  color: string;
  total_roleplays: number;
  scores_70_count: number;
  days_span_70: number;
  distinct_days_70: number;
  average_score: number;
  why_not_higher: string;
};

type RawInsightMoment = {
  id: string;
  summary: string;
  competency_name?: string | null;
  created_at: string;
};

type RawSessionSample = {
  id: string;
  real_weak?: string | null;
  real_improved?: string | null;
  invented_weak?: string | null;
  invented_improved?: string | null;
  created_at: string;
};

export async function getPracticeDashboard(
  projectId?: string,
): Promise<PracticeDashboardData> {
  const query = projectId ? `?project_id=${projectId}` : "";
  const res = await apiFetch(`${getApiBaseUrl()}/practice/dashboard${query}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Nu am putut încărca tabloul participantului");
  }
  const data = await res.json();
  return {
    participantName: data.participant_name,
    xpToday: data.xp_today,
    xpDailyCap: data.xp_daily_cap || 100,
    xpTotal: data.xp_total,
    streakDays: data.streak_days,
    streakBonusPct: data.streak_bonus_pct,
    evidenceCeiling: data.evidence_ceiling,
    competencies: (data.competencies || []).map((c: RawCompetency) => ({
      name: c.name,
      level: c.level,
      levelDescription: c.level_description,
      color: c.color,
      totalRoleplays: c.total_roleplays,
      scores70Count: c.scores_70_count,
      daysSpan70: c.days_span_70,
      distinctDays70: c.distinct_days_70,
      averageScore: c.average_score,
      whyNotHigher: c.why_not_higher,
    })),
    insightMoments: (data.insight_moments || []).map((m: RawInsightMoment) => ({
      id: m.id,
      summary: m.summary,
      competencyName: m.competency_name,
      createdAt: m.created_at,
    })),
    sessionSamples: (data.session_samples || []).map((s: RawSessionSample) => ({
      id: s.id,
      realWeak: s.real_weak,
      realImproved: s.real_improved,
      inventedWeak: s.invented_weak,
      inventedImproved: s.invented_improved,
      createdAt: s.created_at,
    })),
  };
}


// ---- evolutia competentelor pe proiect (plic 29, punctul 2) ----

export type EvolutionCompetency = {
  name: string;
  testInAverage: number | null;
  currentAverage: number | null;
  testOutAverage: number | null;
  growth: number | null;
  level: string;
  levelDescription: string;
  color: string;
  scoresCount: number;
};

export type EvolutionWeekPoint = {
  weekStart: string;
  average: number;
  scoresCount: number;
};

export type EvolutionParticipant = {
  participantProfileId: string;
  userId: string | null;
  fullName: string;
  email: string | null;
  active: boolean;
  testInScore: number | null;
  testOutScore: number | null;
  currentAverage: number | null;
  sessionsCount: number;
  closedSessionsCount: number;
  scoresCount: number;
};

export type ProjectEvolution = {
  projectId: string;
  projectName: string;
  projectType: string | null;
  participantsTotal: number;
  participantsActive: number;
  testInCompleted: number | null;
  testOutEnabled: boolean;
  testPendingNote: string;
  competencies: EvolutionCompetency[];
  weeklyAverage: EvolutionWeekPoint[];
  participants: EvolutionParticipant[];
};

type RawEvolutionCompetency = {
  name: string;
  test_in_average: number | null;
  current_average: number | null;
  test_out_average: number | null;
  growth: number | null;
  level: string;
  level_description: string;
  color: string;
  scores_count: number;
};

type RawEvolutionWeek = { week_start: string; average: number; scores_count: number };

type RawEvolutionParticipant = {
  participant_profile_id: string;
  user_id: string | null;
  full_name: string;
  email: string | null;
  active: boolean;
  test_in_score: number | null;
  test_out_score: number | null;
  current_average: number | null;
  sessions_count: number;
  closed_sessions_count: number;
  scores_count: number;
};

export async function getProjectEvolution(
  projectId: string,
  options: { headers?: HeadersInit } = {},
): Promise<ProjectEvolution | null> {
  // `fetch` poate ARUNCA (adresă nevalidă, rețea, backend căzut) — nu doar să
  // întoarcă un răspuns ne-OK. Excepția trecea pe lângă `!res.ok` și pe lângă
  // tratarea lui `null` din pagină, și fila crăpa cu „Ref:". Se prinde aici.
  let res: Response;
  try {
    res = await apiFetch(`${getApiBaseUrl()}/practice/projects/${projectId}/evolution`, {
      cache: "no-store",
      credentials: "include",
      ...options,
    });
  } catch {
    return null;
  }
  if (!res.ok) return null;
  const data = await res.json().catch(() => null);
  if (!data) return null;
  return {
    projectId: data.project_id,
    projectName: data.project_name,
    projectType: data.project_type ?? null,
    participantsTotal: data.participants_total,
    participantsActive: data.participants_active,
    testInCompleted: data.test_in_completed ?? null,
    testOutEnabled: Boolean(data.test_out_enabled),
    testPendingNote: data.test_pending_note,
    competencies: (data.competencies || []).map((c: RawEvolutionCompetency) => ({
      name: c.name,
      testInAverage: c.test_in_average,
      currentAverage: c.current_average,
      testOutAverage: c.test_out_average,
      growth: c.growth,
      level: c.level,
      levelDescription: c.level_description,
      color: c.color,
      scoresCount: c.scores_count,
    })),
    weeklyAverage: (data.weekly_average || []).map((w: RawEvolutionWeek) => ({
      weekStart: w.week_start,
      average: w.average,
      scoresCount: w.scores_count,
    })),
    participants: (data.participants || []).map((p: RawEvolutionParticipant) => ({
      participantProfileId: p.participant_profile_id,
      userId: p.user_id,
      fullName: p.full_name,
      email: p.email,
      active: p.active,
      testInScore: p.test_in_score,
      testOutScore: p.test_out_score,
      currentAverage: p.current_average,
      sessionsCount: p.sessions_count,
      closedSessionsCount: p.closed_sessions_count,
      scoresCount: p.scores_count,
    })),
  };
}

// ---- configurarea exersarii pe proiect (plic 29, punctele 4 si 6) ----

export type ThemeCompetency = {
  name: string;
  description: string | null;
  orderIndex: number;
};

export type PracticeTheme = {
  id: string;
  name: string;
  slug: string | null;
  competencies: ThemeCompetency[];
  hasKnowledgePack: boolean;
  scenarioCount: number;
  usable: boolean;
};

export type PracticeSetup = {
  projectId: string;
  projectName: string;
  projectType: string | null;
  configured: boolean;
  isEnabled: boolean;
  themeId: string | null;
  themeName: string | null;
  competencies: ThemeCompetency[];
};

type RawThemeCompetency = { name: string; description: string | null; order_index: number };

function mapCompetency(c: RawThemeCompetency): ThemeCompetency {
  return { name: c.name, description: c.description, orderIndex: c.order_index };
}

export async function getPracticeThemes(): Promise<PracticeTheme[]> {
  const res = await apiFetch(`${getApiBaseUrl()}/practice/themes`, { credentials: "include" });
  if (!res.ok) return [];
  const data = await res.json();
  return (data || []).map((t: {
    id: string;
    name: string;
    slug: string | null;
    competencies: RawThemeCompetency[];
    has_knowledge_pack: boolean;
    scenario_count: number;
    usable: boolean;
  }) => ({
    id: t.id,
    name: t.name,
    slug: t.slug,
    competencies: (t.competencies || []).map(mapCompetency),
    hasKnowledgePack: t.has_knowledge_pack,
    scenarioCount: t.scenario_count,
    usable: t.usable,
  }));
}

type RawPracticeSetup = {
  project_id: string;
  project_name: string;
  project_type: string | null;
  configured: boolean;
  is_enabled: boolean;
  theme_id: string | null;
  theme_name: string | null;
  competencies: RawThemeCompetency[];
};

function mapSetup(data: RawPracticeSetup): PracticeSetup {
  return {
    projectId: data.project_id,
    projectName: data.project_name,
    projectType: data.project_type,
    configured: data.configured,
    isEnabled: data.is_enabled,
    themeId: data.theme_id,
    themeName: data.theme_name,
    competencies: (data.competencies || []).map(mapCompetency),
  };
}

export async function getPracticeSetup(projectId: string): Promise<PracticeSetup | null> {
  const res = await apiFetch(`${getApiBaseUrl()}/practice/projects/${projectId}/setup`, {
    credentials: "include",
  });
  if (!res.ok) return null;
  return mapSetup(await res.json());
}

export async function configurePracticeSetup(
  projectId: string,
  input: { themeId: string; competencies: string[] },
): Promise<PracticeSetup> {
  const res = await apiFetch(`${getApiBaseUrl()}/practice/projects/${projectId}/setup`, {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      theme_id: input.themeId,
      competencies: input.competencies,
      is_enabled: true,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.error?.message || err.detail || "Nu am putut salva configurarea.");
  }
  return mapSetup(await res.json());
}

// ---- camera de training: ecranul proiectului (plic 30) ----

export type RoomCompetency = {
  name: string;
  testIn: number;
  acum: number;
  testOut: number | null;
  hasTestIn: boolean;
  hasData: boolean;
  delta: number | null;
};

export type RoomQuizWeakSpot = { name: string; average: number };
export type RoomWeekPoint = { weekStart: string; average: number; scoresCount: number };

export type RoomParticipant = {
  participantProfileId: string;
  userId: string | null;
  fullName: string;
  email: string | null;
  hasAccount: boolean;
  averageScore: number;
  sessionsCount: number;
  lastActivity: string | null;
  inactive: boolean;
  hasTestIn: boolean;
  hasTestOut: boolean;
  activeMembership: boolean;
};

export type TrainingRoom = {
  projectId: string;
  projectName: string;
  projectType: string | null;
  themeName: string | null;
  practiceConfigured: boolean;
  startsAt: string | null;
  dueAt: string | null;
  timelinePercent: number | null;
  participantsTotal: number;
  averageScore: number;
  sessionsTotal: number;
  inactiveCount: number;
  testInCompleted: number;
  testOutCompleted: number;
  activeCount: number;
  recurrentCount: number;
  testOutActive: boolean;
  competencies: RoomCompetency[];
  growthRanking: RoomCompetency[];
  quizWeakSpots: RoomQuizWeakSpot[];
  weeklyAverage: RoomWeekPoint[];
  participants: RoomParticipant[];
};

type RawRoomCompetency = {
  name: string;
  test_in: number;
  acum: number;
  test_out: number | null;
  has_test_in: boolean;
  has_data: boolean;
  delta: number | null;
};

function mapRoomCompetency(c: RawRoomCompetency): RoomCompetency {
  return {
    name: c.name,
    testIn: c.test_in,
    acum: c.acum,
    testOut: c.test_out,
    hasTestIn: c.has_test_in,
    hasData: c.has_data,
    delta: c.delta,
  };
}

export async function getTrainingRoom(
  projectId: string,
  options: { headers?: HeadersInit } = {},
): Promise<TrainingRoom | null> {
  // Ca la reparatia din 31 august: `fetch` poate ARUNCA, nu doar sa intoarca
  // un raspuns ne-OK. Camera nu are voie sa crape cu „Ref:".
  let res: Response;
  try {
    res = await apiFetch(`${getApiBaseUrl()}/practice/projects/${projectId}/room`, {
      cache: "no-store",
      credentials: "include",
      ...options,
    });
  } catch {
    return null;
  }
  if (!res.ok) return null;
  const d = await res.json().catch(() => null);
  if (!d) return null;
  return {
    projectId: d.project_id,
    projectName: d.project_name,
    projectType: d.project_type ?? null,
    themeName: d.theme_name ?? null,
    practiceConfigured: Boolean(d.practice_configured),
    startsAt: d.starts_at ?? null,
    dueAt: d.due_at ?? null,
    timelinePercent: d.timeline_percent ?? null,
    participantsTotal: d.participants_total ?? 0,
    averageScore: d.average_score ?? 0,
    sessionsTotal: d.sessions_total ?? 0,
    inactiveCount: d.inactive_count ?? 0,
    testInCompleted: d.test_in_completed ?? 0,
    testOutCompleted: d.test_out_completed ?? 0,
    activeCount: d.active_count ?? 0,
    recurrentCount: d.recurrent_count ?? 0,
    testOutActive: Boolean(d.test_out_active),
    competencies: (d.competencies || []).map(mapRoomCompetency),
    growthRanking: (d.growth_ranking || []).map(mapRoomCompetency),
    quizWeakSpots: (d.quiz_weak_spots || []).map(
      (q: RoomQuizWeakSpot) => ({ name: q.name, average: q.average }),
    ),
    weeklyAverage: (d.weekly_average || []).map(
      (w: { week_start: string; average: number; scores_count: number }) => ({
        weekStart: w.week_start,
        average: w.average,
        scoresCount: w.scores_count,
      }),
    ),
    participants: (d.participants || []).map((p: {
      participant_profile_id: string;
      user_id: string | null;
      full_name: string;
      email: string | null;
      has_account: boolean;
      average_score: number;
      sessions_count: number;
      last_activity: string | null;
      inactive: boolean;
      has_test_in: boolean;
      has_test_out: boolean;
      active_membership: boolean;
    }) => ({
      participantProfileId: p.participant_profile_id,
      userId: p.user_id,
      fullName: p.full_name,
      email: p.email,
      hasAccount: p.has_account,
      averageScore: p.average_score,
      sessionsCount: p.sessions_count,
      lastActivity: p.last_activity,
      inactive: p.inactive,
      hasTestIn: p.has_test_in,
      hasTestOut: p.has_test_out,
      activeMembership: p.active_membership,
    })),
  };
}

// ---- pagina omului (plic 30, ecranul 2) ----

export type PersonTheory = { name: string; testIn: number | null; testOut: number | null; delta: number | null };
export type PersonEvidence = {
  name: string;
  level: string;
  levelDescription: string;
  color: string;
  averageScore: number;
  sessionsCount: number;
  scoresCount: number;
  whyNotHigher: string;
};
export type PersonText = { id: string; summary: string; createdAt: string };
export type PersonSample = {
  id: string;
  realWeak: string | null;
  realImproved: string | null;
  inventedWeak: string | null;
  inventedImproved: string | null;
  createdAt: string;
};
export type TrainerNote = { id: string; note: string; createdAt: string };

export type PracticePerson = {
  projectId: string;
  projectName: string;
  participantProfileId: string;
  userId: string | null;
  fullName: string;
  email: string | null;
  hasAccount: boolean;
  durationDays: number | null;
  testInAverage: number | null;
  progressAverage: number;
  testOutAverage: number | null;
  sessionsCount: number;
  theory: PersonTheory[];
  evidence: PersonEvidence[];
  topProgress: PersonEvidence[];
  weeklyAverage: RoomWeekPoint[];
  quizWeakSpots: RoomQuizWeakSpot[];
  insightMoments: PersonText[];
  trainerRecommendations: PersonText[];
  sessionSamples: PersonSample[];
  trainerNotes: TrainerNote[];
};

type RawEvidence = {
  name: string;
  level: string;
  level_description: string;
  color: string;
  average_score: number;
  sessions_count: number;
  scores_count: number;
  why_not_higher: string;
};

function mapEvidence(e: RawEvidence): PersonEvidence {
  return {
    name: e.name,
    level: e.level,
    levelDescription: e.level_description,
    color: e.color,
    averageScore: e.average_score,
    sessionsCount: e.sessions_count,
    scoresCount: e.scores_count,
    whyNotHigher: e.why_not_higher,
  };
}

function mapText(t: { id: string; summary: string; created_at: string }): PersonText {
  return { id: t.id, summary: t.summary, createdAt: t.created_at };
}

export async function getPracticePerson(
  projectId: string,
  profileId: string,
  options: { headers?: HeadersInit } = {},
): Promise<PracticePerson | null> {
  let res: Response;
  try {
    res = await apiFetch(
      `${getApiBaseUrl()}/practice/projects/${projectId}/participants/${profileId}`,
      { cache: "no-store", credentials: "include", ...options },
    );
  } catch {
    return null;
  }
  if (!res.ok) return null;
  const d = await res.json().catch(() => null);
  if (!d) return null;
  return {
    projectId: d.project_id,
    projectName: d.project_name,
    participantProfileId: d.participant_profile_id,
    userId: d.user_id ?? null,
    fullName: d.full_name,
    email: d.email ?? null,
    hasAccount: Boolean(d.has_account),
    durationDays: d.duration_days ?? null,
    testInAverage: d.test_in_average ?? null,
    progressAverage: d.progress_average ?? 0,
    testOutAverage: d.test_out_average ?? null,
    sessionsCount: d.sessions_count ?? 0,
    theory: (d.theory || []).map((t: { name: string; test_in: number | null; test_out: number | null; delta: number | null }) => ({
      name: t.name, testIn: t.test_in, testOut: t.test_out, delta: t.delta,
    })),
    evidence: (d.evidence || []).map(mapEvidence),
    topProgress: (d.top_progress || []).map(mapEvidence),
    weeklyAverage: (d.weekly_average || []).map(
      (w: { week_start: string; average: number; scores_count: number }) => ({
        weekStart: w.week_start, average: w.average, scoresCount: w.scores_count,
      }),
    ),
    quizWeakSpots: (d.quiz_weak_spots || []).map((q: RoomQuizWeakSpot) => ({ name: q.name, average: q.average })),
    insightMoments: (d.insight_moments || []).map(mapText),
    trainerRecommendations: (d.trainer_recommendations || []).map(mapText),
    sessionSamples: (d.session_samples || []).map((s: {
      id: string; real_weak: string | null; real_improved: string | null;
      invented_weak: string | null; invented_improved: string | null; created_at: string;
    }) => ({
      id: s.id,
      realWeak: s.real_weak,
      realImproved: s.real_improved,
      inventedWeak: s.invented_weak,
      inventedImproved: s.invented_improved,
      createdAt: s.created_at,
    })),
    trainerNotes: (d.trainer_notes || []).map(
      (n: { id: string; note: string; created_at: string }) => ({
        id: n.id, note: n.note, createdAt: n.created_at,
      }),
    ),
  };
}

export async function addTrainerNote(
  projectId: string,
  profileId: string,
  note: string,
): Promise<TrainerNote> {
  const res = await apiFetch(
    `${getApiBaseUrl()}/practice/projects/${projectId}/participants/${profileId}/notes`,
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note }),
    },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.error?.message || err.detail || "Nu am putut salva nota.");
  }
  const n = await res.json();
  return { id: n.id, note: n.note, createdAt: n.created_at };
}

// ---- invitatiile in forma de training (plic 30) ----

export type TrainingInvitation = {
  participantProfileId: string;
  fullName: string;
  email: string | null;
  invited: boolean;
  invitedAt: string | null;
  /** Linkul personal, cand invitatia e inca activa. Nu se scrie nicaieri in jurnal. */
  inviteUrl: string | null;
  hasAccount: boolean;
  hasTestIn: boolean;
};

export type TrainingInvitationSent = {
  participantProfileId: string;
  fullName: string | null;
  email: string | null;
  inviteUrl: string | null;
  emailSent: boolean;
  error: string | null;
};

export async function getTrainingInvitations(
  projectId: string,
  options: { headers?: HeadersInit } = {},
): Promise<TrainingInvitation[]> {
  let res: Response;
  try {
    res = await apiFetch(`${getApiBaseUrl()}/practice/projects/${projectId}/invitations`, {
      cache: "no-store",
      credentials: "include",
      ...options,
    });
  } catch {
    return [];
  }
  if (!res.ok) return [];
  const data = await res.json().catch(() => []);
  return (data || []).map((r: {
    participant_profile_id: string;
    full_name: string;
    email: string | null;
    invited: boolean;
    invited_at: string | null;
    invite_url: string | null;
    has_account: boolean;
    has_test_in: boolean;
  }) => ({
    participantProfileId: r.participant_profile_id,
    fullName: r.full_name,
    email: r.email,
    invited: r.invited,
    invitedAt: r.invited_at,
    inviteUrl: r.invite_url ?? null,
    hasAccount: r.has_account,
    hasTestIn: r.has_test_in,
  }));
}

/**
 * Trimite invitatiile pentru un proiect de training.
 *
 * Nu ruta obisnuita de invitatii: aceea cere ca omul sa aiba deja o asignare de
 * chestionar, iar un proiect de training n-are niciuna, deci ii sarea tacut pe
 * toti. Asta e calea trainingului si intoarce linkul chiar si cand emailul nu
 * pleaca.
 */
export async function sendTrainingInvitations(
  projectId: string,
  participantProfileIds: string[],
): Promise<TrainingInvitationSent[]> {
  const res = await apiFetch(`${getApiBaseUrl()}/practice/projects/${projectId}/invitations`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ participant_profile_ids: participantProfileIds }),
  });
  if (!res.ok) {
    const detaliu = await res.json().catch(() => null);
    throw new Error(detaliu?.detail ?? "Nu am putut trimite invitatiile.");
  }
  const data = await res.json();
  return (data || []).map((r: {
    participant_profile_id: string;
    full_name: string | null;
    email: string | null;
    invite_url: string | null;
    email_sent: boolean;
    error: string | null;
  }) => ({
    participantProfileId: r.participant_profile_id,
    fullName: r.full_name,
    email: r.email,
    inviteUrl: r.invite_url,
    emailSent: r.email_sent,
    error: r.error,
  }));
}
