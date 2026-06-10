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

export type CompanyDetail = {
  id: string;
  name: string;
  participants: CompanyParticipant[];
  assignments: CompanyAssignment[];
  teams: CompanyTeam[];
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

// ---------------------------------------------------------------------------
// Data fetchers
// ---------------------------------------------------------------------------

export async function getCompanyParticipants(
  companyId: string,
  options: ApiRequestOptions = {},
): Promise<CompanyParticipant[]> {
  let localParticipants: CompanyParticipant[] = [];
  if (isDemoFallbackEnabled() && typeof window !== "undefined") {
    const stored = localStorage.getItem(`codrut_participants_${companyId}`);
    if (stored) {
      try {
        localParticipants = JSON.parse(stored) as CompanyParticipant[];
      } catch (e) {
        console.error("Error loading local participants", e);
      }
    }
  }

  try {
    const response = await fetch(
      `${getApiBaseUrl()}/companies/${companyId}/participants`,
      { cache: "no-store", credentials: "include", ...options },
    );
    if (!response.ok) {
      if (!isDemoFallbackEnabled()) {
        throw new Error(`Eroare server (${response.status}): Nu s-au putut obține participanții.`);
      }
      return localParticipants;
    }
    const serverParticipants = (await response.json()) as CompanyParticipant[];

    if (!isDemoFallbackEnabled()) {
      return serverParticipants;
    }

    const map = new Map<string, CompanyParticipant>();
    serverParticipants.forEach((p) => map.set(p.id, p));
    localParticipants.forEach((p) => map.set(p.id, p));
    return Array.from(map.values());
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return localParticipants;
  }
}

export async function getCompanyAssignments(
  companyId: string,
  options: ApiRequestOptions = {},
): Promise<CompanyAssignment[]> {
  let localAssignments: CompanyAssignment[] = [];
  if (isDemoFallbackEnabled() && typeof window !== "undefined") {
    const stored = localStorage.getItem(`codrut_assignments_${companyId}`);
    if (stored) {
      try {
        localAssignments = JSON.parse(stored) as CompanyAssignment[];
      } catch (e) {
        console.error("Error loading local assignments", e);
      }
    }
  }

  try {
    const response = await fetch(
      `${getApiBaseUrl()}/companies/${companyId}/assignments`,
      { cache: "no-store", credentials: "include", ...options },
    );
    if (!response.ok) {
      if (!isDemoFallbackEnabled()) {
        throw new Error(`Eroare server (${response.status}): Nu s-au putut obține asignările.`);
      }
      return localAssignments;
    }
    const serverAssignments = (await response.json()) as CompanyAssignment[];

    if (!isDemoFallbackEnabled()) {
      return serverAssignments;
    }

    const map = new Map<string, CompanyAssignment>();
    serverAssignments.forEach((a) => map.set(a.id, a));
    localAssignments.forEach((a) => map.set(a.id, a));
    return Array.from(map.values());
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return localAssignments;
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

function getLocalCompanies(): Array<{ id: string; name: string }> {
  if (!isDemoFallbackEnabled()) return [];
  if (typeof window === "undefined") return [];
  const stored = localStorage.getItem("codrut_local_companies");
  if (!stored) return [];
  try {
    return JSON.parse(stored) as Array<{ id: string; name: string }>;
  } catch {
    return [];
  }
}

export async function getCompanyList(options: ApiRequestOptions = {}): Promise<CompanyListItem[]> {
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

  const localCompanies = getLocalCompanies();
  const map = new Map<string, { id: string; name: string }>();

  if (serverCompanies.length === 0 && localCompanies.length === 0 && isDemoFallbackEnabled()) {
    map.set("demo-project", { id: "demo-project", name: "Client demo" });
    map.set("leadership-pilot", { id: "leadership-pilot", name: "Echipa directie" });
    map.set("past-client-video", { id: "past-client-video", name: "Campanie clienti trecuti" });
  } else {
    serverCompanies.forEach((c) => map.set(c.id, c));
    localCompanies.forEach((c) => map.set(c.id, c));
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
        if (!isDemoFallbackEnabled()) {
          throw e;
        }
        return {
          id: company.id,
          name: company.name,
          participantCount: 0,
          assignmentCount: 0,
          completedCount: 0,
          stage: "setup" as const,
        };
      }
    }),
  );

  return enriched;
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

  const localCompanies = getLocalCompanies();
  const map = new Map<string, { id: string; name: string }>();

  if (serverCompanies.length === 0 && localCompanies.length === 0 && isDemoFallbackEnabled()) {
    map.set("demo-project", { id: "demo-project", name: "Client demo" });
    map.set("leadership-pilot", { id: "leadership-pilot", name: "Echipa directie" });
    map.set("past-client-video", { id: "past-client-video", name: "Campanie clienti trecuti" });
  } else {
    serverCompanies.forEach((c) => map.set(c.id, c));
    localCompanies.forEach((c) => map.set(c.id, c));
  }

  const company = map.get(companyId);
  if (!company) return null;

  try {
    const [participants, assignments, teams] = await Promise.all([
      getCompanyParticipants(companyId, options),
      getCompanyAssignments(companyId, options),
      getCompanyTeams(companyId, options),
    ]);

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
      teams,
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
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return null;
  }
}
