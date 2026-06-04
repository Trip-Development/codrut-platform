import { getApiBaseUrl } from "./runtime";

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

export async function getCompanyParticipants(companyId: string): Promise<CompanyParticipant[]> {
  try {
    const response = await fetch(
      `${getApiBaseUrl()}/companies/${companyId}/participants`,
      { cache: "no-store" },
    );
    if (!response.ok) return [];
    return (await response.json()) as CompanyParticipant[];
  } catch {
    return [];
  }
}

export async function getCompanyAssignments(companyId: string): Promise<CompanyAssignment[]> {
  try {
    const response = await fetch(
      `${getApiBaseUrl()}/companies/${companyId}/assignments`,
      { cache: "no-store" },
    );
    if (!response.ok) return [];
    return (await response.json()) as CompanyAssignment[];
  } catch {
    return [];
  }
}

export async function getCompanyTeams(companyId: string): Promise<CompanyTeam[]> {
  try {
    const response = await fetch(
      `${getApiBaseUrl()}/companies/${companyId}/teams`,
      { cache: "no-store" },
    );
    if (!response.ok) return [];
    return (await response.json()) as CompanyTeam[];
  } catch {
    return [];
  }
}

// ---------------------------------------------------------------------------
// Aggregated fetchers
// ---------------------------------------------------------------------------

export async function getCompanyList(): Promise<CompanyListItem[]> {
  try {
    const companiesResponse = await fetch(`${getApiBaseUrl()}/companies`, {
      cache: "no-store",
    });
    if (!companiesResponse.ok) return [];

    const companies = (await companiesResponse.json()) as Array<{
      id: string;
      name: string;
    }>;
    if (companies.length === 0) return [];

    const enriched = await Promise.all(
      companies.map(async (company) => {
        try {
          const [participants, assignments] = await Promise.all([
            getCompanyParticipants(company.id),
            getCompanyAssignments(company.id),
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
        } catch {
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
  } catch {
    return [];
  }
}

export async function getCompanyDetail(companyId: string): Promise<CompanyDetail | null> {
  try {
    // Fetch the company list to resolve the company name.
    const companiesResponse = await fetch(`${getApiBaseUrl()}/companies`, {
      cache: "no-store",
    });
    if (!companiesResponse.ok) return null;

    const companies = (await companiesResponse.json()) as Array<{
      id: string;
      name: string;
    }>;
    const company = companies.find((c) => c.id === companyId);
    if (!company) return null;

    // Fetch participants, assignments, and teams in parallel.
    const [participants, assignments, teams] = await Promise.all([
      getCompanyParticipants(companyId),
      getCompanyAssignments(companyId),
      getCompanyTeams(companyId),
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
  } catch {
    return null;
  }
}
