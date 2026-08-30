import { apiFetch } from "./http";

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
  const res = await apiFetch("/api/practice/sessions", {
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
  const res = await apiFetch(`/api/practice/sessions/${sessionId}/turns`, {
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
  const res = await apiFetch(`/api/practice/sessions/${sessionId}`);
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

export async function endPracticeSession(
  sessionId: string,
  payload?: { note?: string },
): Promise<PracticeSession> {
  const res = await apiFetch(`/api/practice/sessions/${sessionId}/end`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Nu am putut încheia sesiunea");
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
