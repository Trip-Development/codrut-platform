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
