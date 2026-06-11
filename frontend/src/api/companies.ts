import { getApiBaseUrl, isDemoFallbackEnabled } from "./runtime";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CompanyListItem = {
  id: string;
  name: string;
  participantCount: number;
  assignmentCount: number;
  completedCount: number;
  stage: "setup" | "invites" | "completion" | "reporting";
  dataUnavailable?: boolean;
  dataError?: string;
};

type CompanySummaryResponse = {
  id: string;
  name: string;
  participant_count: number;
  assignment_count: number;
  completed_count: number;
  scored_count: number;
  stage: CompanyListItem["stage"];
};

export type CompanyParticipant = {
  id: string;
  full_name: string;
  email: string;
  reports_to_name: string | null;
  position: string | null;
  location: string | null;
  role_group: string | null;
  pcm_profile: string | null;
  user_id: string | null;
};

export type CompanyAssignment = {
  id: string;
  company_id: string;
  respondent_profile_id: string;
  questionnaire_key: string;
  target_type: "self" | "person" | "team";
  status: "assigned" | "invited" | "started" | "submitted" | "validated" | "scored";
  submitted_at: string | null;
  scored_at: string | null;
};

export type RosterInviteResult = {
  participant_id: string;
  email: string;
  full_name: string;
  delivery_mode: "email" | "secure_links";
  email_sent: boolean;
  error: string | null;
  invite_url: string | null;
};

export type ParticipantInvitationStatus = {
  participant_id: string;
  latest_delivery_mode: "email" | "secure_links" | null;
  latest_email_status: string | null;
  latest_email_error: string | null;
  last_sent_at: string | null;
  email_send_count: number;
  has_active_secure_link: boolean;
  active_secure_link_expires_at: string | null;
  active_secure_link_url: string | null;
};

export type RosterImportResponse = {
  participants: CompanyParticipant[];
  email_results: RosterInviteResult[];
  total_imported: number;
  emails_sent: number;
  emails_failed: number;
};

export type ParticipantInvitationMode = "email" | "secure_links";

export type ParticipantInviteBatchResponse = {
  results: RosterInviteResult[];
  total: number;
  emails_sent: number;
  emails_failed: number;
  links_generated: number;
};

export type CompanyTeam = {
  id: string;
  company_id: string;
  name: string;
  type: "leadership" | "functional";
};

export type CompanyTeamMembership = {
  id: string;
  team_id: string;
  participant_profile_id: string;
  role: "leader" | "member";
};

export type CompanyDetail = {
  id: string;
  name: string;
  participants: CompanyParticipant[];
  assignments: CompanyAssignment[];
  invitationStatuses: ParticipantInvitationStatus[];
  teams: CompanyTeam[];
  dataErrors?: string[];
  stats: {
    totalParticipants: number;
    totalAssignments: number;
    completedAssignments: number;
    completionRate: number;
    scoredCount: number;
    pendingCount: number;
  };
};

export type ApiRequestOptions = Pick<RequestInit, "headers">;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function deriveStage(
  assignmentCount: number,
  completedCount: number,
): "setup" | "invites" | "completion" | "reporting" {
  if (assignmentCount === 0) return "setup";
  if (completedCount === assignmentCount) return "reporting";
  if (completedCount > 0) return "completion";
  return "invites";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Date indisponibile.";
}

// ---------------------------------------------------------------------------
// Data fetchers
// ---------------------------------------------------------------------------

export async function getCompanyParticipants(
  companyId: string,
  options: ApiRequestOptions = {},
): Promise<CompanyParticipant[]> {
  try {
    const response = await fetch(
      `${getApiBaseUrl()}/companies/${companyId}/participants`,
      { cache: "no-store", credentials: "include", ...options },
    );
    if (!response.ok) {
      if (!isDemoFallbackEnabled()) {
        throw new Error(`Eroare server (${response.status}): Nu s-au putut obține participanții.`);
      }
      return [];
    }
    return (await response.json()) as CompanyParticipant[];
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return [];
  }
}

export async function getCompanyAssignments(
  companyId: string,
  options: ApiRequestOptions = {},
): Promise<CompanyAssignment[]> {
  try {
    const response = await fetch(
      `${getApiBaseUrl()}/companies/${companyId}/assignments`,
      { cache: "no-store", credentials: "include", ...options },
    );
    if (!response.ok) {
      if (!isDemoFallbackEnabled()) {
        throw new Error(`Eroare server (${response.status}): Nu s-au putut obține asignările.`);
      }
      return [];
    }
    return (await response.json()) as CompanyAssignment[];
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return [];
  }
}

export async function getCompanyTeams(
  companyId: string,
  options: ApiRequestOptions = {},
): Promise<CompanyTeam[]> {
  try {
    const response = await fetch(
      `${getApiBaseUrl()}/companies/${companyId}/teams`,
      { cache: "no-store", credentials: "include", ...options },
    );
    if (!response.ok) {
      if (!isDemoFallbackEnabled()) {
        throw new Error(`Eroare server (${response.status}): Nu s-au putut obține echipele.`);
      }
      return [];
    }
    return (await response.json()) as CompanyTeam[];
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return [];
  }
}

// ---------------------------------------------------------------------------
// Aggregated fetchers
// ---------------------------------------------------------------------------

export async function getCompanyList(options: ApiRequestOptions = {}): Promise<CompanyListItem[]> {
  const summaryResponse = await fetch(`${getApiBaseUrl()}/companies/summary`, {
    cache: "no-store",
    credentials: "include",
    ...options,
  }).catch((error: unknown) => {
    if (!isDemoFallbackEnabled()) {
      throw error;
    }
    return null;
  });

  if (summaryResponse?.ok) {
    const summaries = (await summaryResponse.json()) as CompanySummaryResponse[];
    return summaries.map(companySummaryToListItem);
  }

  if (summaryResponse && !summaryResponse.ok && !isDemoFallbackEnabled() && summaryResponse.status !== 404) {
    throw new Error(`Eroare server (${summaryResponse.status}): Nu s-a putut obține sumarul companiilor.`);
  }

  let serverCompanies: Array<{ id: string; name: string }> = [];
  try {
    const companiesResponse = await fetch(`${getApiBaseUrl()}/companies`, {
      cache: "no-store",
      credentials: "include",
      ...options,
    });
    if (!companiesResponse.ok) {
      if (!isDemoFallbackEnabled()) {
        throw new Error(`Eroare server (${companiesResponse.status}): Nu s-a putut obține lista de companii.`);
      }
    } else {
      serverCompanies = (await companiesResponse.json()) as Array<{ id: string; name: string }>;
    }
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    console.error("Fetch companies failed, using local fallback", e);
  }

  const map = new Map<string, { id: string; name: string }>();

  if (serverCompanies.length === 0 && isDemoFallbackEnabled()) {
    map.set("demo-project", { id: "demo-project", name: "Client demo" });
    map.set("leadership-pilot", { id: "leadership-pilot", name: "Echipa directie" });
    map.set("past-client-video", { id: "past-client-video", name: "Campanie clienti trecuti" });
  } else {
    serverCompanies.forEach((c) => map.set(c.id, c));
  }

  const mergedCompanies = Array.from(map.values());

  const enriched = await Promise.all(
    mergedCompanies.map(async (company) => {
      try {
        const [participants, assignments] = await Promise.all([
          getCompanyParticipants(company.id, options),
          getCompanyAssignments(company.id, options),
        ]);

        const completedCount = assignments.filter(
          (a) => a.status === "submitted" || a.status === "validated" || a.status === "scored",
        ).length;

        return {
          id: company.id,
          name: company.name,
          participantCount: participants.length,
          assignmentCount: assignments.length,
          completedCount,
          stage: deriveStage(assignments.length, completedCount),
        };
      } catch (e) {
        return {
          id: company.id,
          name: company.name,
          participantCount: 0,
          assignmentCount: 0,
          completedCount: 0,
          stage: "setup" as const,
          dataUnavailable: true,
          dataError: errorMessage(e),
        };
      }
    }),
  );

  return enriched;
}

function companySummaryToListItem(summary: CompanySummaryResponse): CompanyListItem {
  return {
    id: summary.id,
    name: summary.name,
    participantCount: summary.participant_count,
    assignmentCount: summary.assignment_count,
    completedCount: summary.completed_count,
    stage: summary.stage,
  };
}

export async function createCompany(name: string): Promise<{ id: string; name: string }> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/companies`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ name }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(payload?.error?.message ?? `Server returned status ${response.status}`);
    }
    return (await response.json()) as { id: string; name: string };
  } catch (e) {
    throw e;
  }
}

export async function deleteCompany(companyId: string): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/companies/${companyId}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.error?.message ?? `Server returned status ${response.status}`);
  }
}

export async function importCompanyRoster(
  companyId: string,
  rows: Array<{
    Name: string;
    "Reports To": string;
    Position: string;
    Location: string;
    email: string;
    "Profil PCM": string;
  }>,
  options: { sendInvites?: boolean } = {},
): Promise<RosterImportResponse> {
  const response = await fetch(`${getApiBaseUrl()}/companies/${companyId}/participants/roster`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      rows,
      send_invites: options.sendInvites ?? false,
    }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.error?.message ?? `Backend refuzat (${response.status})`);
  }

  return (await response.json()) as RosterImportResponse;
}

export async function sendParticipantInvitations(
  companyId: string,
  payload: {
    participantIds?: string[];
    mode: ParticipantInvitationMode;
    forceRotate?: boolean;
  },
): Promise<ParticipantInviteBatchResponse> {
  const response = await fetch(`${getApiBaseUrl()}/companies/${companyId}/participants/invitations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      participant_ids: payload.participantIds,
      mode: payload.mode,
      force_rotate: payload.forceRotate ?? false,
    }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.error?.message ?? `Backend refuzat (${response.status})`);
  }

  return (await response.json()) as ParticipantInviteBatchResponse;
}

export async function resendParticipantInvitation(
  companyId: string,
  participantId: string,
): Promise<RosterInviteResult | null> {
  const response = await fetch(
    `${getApiBaseUrl()}/companies/${companyId}/participants/${participantId}/resend-invite`,
    {
      method: "POST",
      credentials: "include",
    },
  );

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.error?.message ?? `Backend refuzat (${response.status})`);
  }

  const data = (await response.json()) as RosterImportResponse;
  return data.email_results[0] ?? null;
}

export async function getCompanyInvitationStatuses(
  companyId: string,
  options: ApiRequestOptions = {},
): Promise<ParticipantInvitationStatus[]> {
  const response = await fetch(
    `${getApiBaseUrl()}/companies/${companyId}/participants/invitations/status`,
    { cache: "no-store", credentials: "include", ...options },
  );
  if (!response.ok) {
    if (!isDemoFallbackEnabled()) {
      throw new Error(`Eroare server (${response.status}): Nu s-a putut obține statusul invitațiilor.`);
    }
    return [];
  }
  return (await response.json()) as ParticipantInvitationStatus[];
}

export async function createCompanyTeam(
  companyId: string,
  payload: { name: string; type: CompanyTeam["type"] },
): Promise<CompanyTeam> {
  const response = await fetch(`${getApiBaseUrl()}/companies/${companyId}/teams`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.error?.message ?? `Backend refuzat (${response.status})`);
  }

  return (await response.json()) as CompanyTeam;
}

export async function getCompanyTeamMemberships(
  companyId: string,
  teamId: string,
  options: ApiRequestOptions = {},
): Promise<CompanyTeamMembership[]> {
  const response = await fetch(
    `${getApiBaseUrl()}/companies/${companyId}/teams/${teamId}/memberships`,
    { cache: "no-store", credentials: "include", ...options },
  );
  if (!response.ok) {
    throw new Error(`Eroare server (${response.status}): Nu s-au putut obține membrii echipei.`);
  }
  return (await response.json()) as CompanyTeamMembership[];
}

export async function addCompanyTeamMembership(
  companyId: string,
  teamId: string,
  payload: { participantProfileId: string; role: CompanyTeamMembership["role"] },
): Promise<CompanyTeamMembership> {
  const response = await fetch(`${getApiBaseUrl()}/companies/${companyId}/teams/${teamId}/memberships`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      participant_profile_id: payload.participantProfileId,
      role: payload.role,
    }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.error?.message ?? `Backend refuzat (${response.status})`);
  }

  return (await response.json()) as CompanyTeamMembership;
}

export async function getCompanyDetail(
  companyId: string,
  options: ApiRequestOptions = {},
): Promise<CompanyDetail | null> {
  let serverCompanies: Array<{ id: string; name: string }> = [];
  try {
    const response = await fetch(`${getApiBaseUrl()}/companies`, {
      cache: "no-store",
      credentials: "include",
      ...options,
    });
    if (!response.ok) {
      if (!isDemoFallbackEnabled()) {
        throw new Error(`Eroare server (${response.status}): Nu s-a putut obține compania.`);
      }
    } else {
      serverCompanies = (await response.json()) as Array<{ id: string; name: string }>;
    }
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
  }

  const map = new Map<string, { id: string; name: string }>();

  if (serverCompanies.length === 0 && isDemoFallbackEnabled()) {
    map.set("demo-project", { id: "demo-project", name: "Client demo" });
    map.set("leadership-pilot", { id: "leadership-pilot", name: "Echipa directie" });
    map.set("past-client-video", { id: "past-client-video", name: "Campanie clienti trecuti" });
  } else {
    serverCompanies.forEach((c) => map.set(c.id, c));
  }

  const company = map.get(companyId);
  if (!company) return null;

  const [participantsResult, assignmentsResult, invitationStatusesResult, teamsResult] = await Promise.allSettled([
    getCompanyParticipants(companyId, options),
    getCompanyAssignments(companyId, options),
    getCompanyInvitationStatuses(companyId, options),
    getCompanyTeams(companyId, options),
  ]);

  const participants = participantsResult.status === "fulfilled" ? participantsResult.value : [];
  const assignments = assignmentsResult.status === "fulfilled" ? assignmentsResult.value : [];
  const invitationStatuses = invitationStatusesResult.status === "fulfilled" ? invitationStatusesResult.value : [];
  const teams = teamsResult.status === "fulfilled" ? teamsResult.value : [];
  const dataErrors = [
    participantsResult.status === "rejected" ? `Participanti: ${errorMessage(participantsResult.reason)}` : null,
    assignmentsResult.status === "rejected" ? `Asignari: ${errorMessage(assignmentsResult.reason)}` : null,
    invitationStatusesResult.status === "rejected" ? `Invitatii: ${errorMessage(invitationStatusesResult.reason)}` : null,
    teamsResult.status === "rejected" ? `Echipe: ${errorMessage(teamsResult.reason)}` : null,
  ].filter((error): error is string => Boolean(error));

  const completedAssignments = assignments.filter(
    (a) => a.status === "submitted" || a.status === "validated" || a.status === "scored",
  ).length;

  const scoredCount = assignments.filter((a) => a.status === "scored").length;

  const pendingCount = assignments.filter(
    (a) => a.status === "assigned" || a.status === "invited" || a.status === "started",
  ).length;

  return {
    id: company.id,
    name: company.name,
    participants,
    assignments,
    invitationStatuses,
    teams,
    dataErrors: dataErrors.length > 0 ? dataErrors : undefined,
    stats: {
      totalParticipants: participants.length,
      totalAssignments: assignments.length,
      completedAssignments,
      completionRate:
        assignments.length > 0
          ? Math.round((completedAssignments / assignments.length) * 100)
          : 0,
      scoredCount,
      pendingCount,
    },
  };
}
