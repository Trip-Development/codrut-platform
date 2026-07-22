import { apiFetch } from "./http";
import { formatPcmLabel, getPcmColor } from "./pcm";
import { getApiBaseUrl, isDemoFallbackEnabled, isLocalSeededDemoFallbackEnabled } from "./runtime";

type ApiErrorPayload = {
  error?: {
    code?: unknown;
    message?: unknown;
    details?: unknown;
  };
  detail?: unknown;
};

export class CompanyMutationError extends Error {
  constructor(
    message: string,
    readonly code?: string,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = "CompanyMutationError";
  }
}

function formatApiErrorDetails(details: unknown): string | null {
  if (!Array.isArray(details)) {
    return null;
  }

  const messages = details
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const issue = item as { loc?: unknown; message?: unknown; msg?: unknown };
      const issueMessage = issue.message ?? issue.msg;
      if (typeof issueMessage !== "string" || !issueMessage.trim()) return null;

      const path = Array.isArray(issue.loc)
        ? issue.loc
            .filter((part) => part !== "body")
            .map(String)
            .join(".")
        : "";
      return path ? `${path}: ${issueMessage}` : issueMessage;
    })
    .filter((message): message is string => Boolean(message));

  if (messages.length > 0) {
    const visibleMessages = messages.slice(0, 3).join("; ");
    return messages.length > 3 ? `${visibleMessages}; încă ${messages.length - 3} erori.` : visibleMessages;
  }

  return null;
}

function formatApiError(payload: ApiErrorPayload | null, fallbackMessage: string): string {
  const detailsMessage = formatApiErrorDetails(payload?.error?.details ?? payload?.detail);
  if (detailsMessage) {
    return detailsMessage;
  }

  if (typeof payload?.error?.message === "string" && payload.error.message.trim()) {
    return payload.error.message;
  }

  if (typeof payload?.detail === "string" && payload.detail.trim()) {
    return payload.detail;
  }

  return fallbackMessage;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CompanyListItem = {
  id: string;
  name: string;
  participantCount: number;
  projectCount: number;
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
  project_count: number;
  assignment_count: number;
  completed_count: number;
  scored_count: number;
  stage: CompanyListItem["stage"];
};

export type CompanyParticipant = {
  id: string;
  project_membership_id?: string;
  full_name: string;
  email: string | null;
  reports_to_name: string | null;
  position: string | null;
  location: string | null;
  role_group: string | null;
  pcm_profile: string | null;
  pcm_base?: string | null;
  pcm_phase?: string | null;
  anonymous_name?: string | null;
  user_id: string | null;
  is_shadow_account?: boolean;
};

export function hasPermanentParticipantAccount(participant: CompanyParticipant): boolean {
  return Boolean(participant.user_id) && participant.is_shadow_account !== true;
}

export type UpdateCompanyParticipantPayload = {
  projectId?: string | null;
  fullName?: string;
  email?: string;
  reportsToName?: string | null;
  position?: string | null;
  location?: string | null;
  roleGroup?: string | null;
};

export type CompanyProjectStatus = "draft" | "active" | "completed" | "archived";

export type CompanyProject = {
  id: string;
  company_id: string;
  company_name?: string;
  name: string;
  description: string | null;
  project_type: string | null;
  status: CompanyProjectStatus;
  starts_at: string | null;
  due_at: string | null;
  form_opens_at: string | null;
  form_closes_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CompanyProjectPayload = {
  name?: string;
  description?: string | null;
  projectType?: string | null;
  status?: CompanyProjectStatus;
  startsAt?: string | null;
  dueAt?: string | null;
  formOpensAt?: string | null;
  formClosesAt?: string | null;
};

export type CompanyAssignment = {
  id: string;
  company_id: string;
  project_id: string | null;
  assessment_cycle_id?: string | null;
  assignment_round_id?: string;
  respondent_profile_id: string;
  questionnaire_key: string;
  target_type: "self" | "person" | "team";
  target_person_id: string | null;
  target_team_id: string | null;
  access_mode?: "account_link";
  status: "assigned" | "invited" | "started" | "submitted" | "validated" | "scored" | "cancelled";
  visibility_policy?: "trainer_raw_review" | "reviewed_anonymized";
  due_at?: string | null;
  invited_at?: string | null;
  started_at?: string | null;
  submitted_at: string | null;
  validated_at?: string | null;
  scored_at: string | null;
  reminder_due_at?: string | null;
  last_reminder_sent_at?: string | null;
};

export type CreateCompanyAssignmentPayload = {
  projectId?: string | null;
  assessmentCycleId?: string | null;
  respondentProfileId: string;
  questionnaireKey: string;
  targetType: CompanyAssignment["target_type"];
  targetPersonId?: string | null;
  targetTeamId?: string | null;
  visibilityPolicy?: NonNullable<CompanyAssignment["visibility_policy"]>;
};

export type CompanyAssignmentPlanScope = {
  id: string;
  name: string;
  type: "leadership_team" | "manager_team" | "manager" | "member" | string;
  participant_ids: string[];
};

export type CompanyAssignmentPlanItem = {
  key: string;
  scope_id: string;
  scope_name: string;
  scope_type: CompanyAssignmentPlanScope["type"];
  respondent_profile_id: string;
  respondent_name: string;
  questionnaire_key: string;
  target_type: CompanyAssignment["target_type"];
  target_person_id: string | null;
  target_person_name: string | null;
  target_team_id: string | null;
  target_team_name: string | null;
  target_team_type: CompanyTeam["type"] | null;
  target_team_member_ids: string[];
  target_team_leader_id: string | null;
  visibility_policy: NonNullable<CompanyAssignment["visibility_policy"]>;
  selected: boolean;
  existing_assignment_id: string | null;
};

export type CompanyAssignmentPlan = {
  project_id: string | null;
  assessment_cycle_id?: string | null;
  source_cycle_id?: string | null;
  scopes: CompanyAssignmentPlanScope[];
  assignments: CompanyAssignmentPlanItem[];
  suggested_count: number;
  existing_count: number;
};

export type CompanyAssignmentPlanSaveResponse = {
  assignments: CompanyAssignment[];
  created_count: number;
  existing_count: number;
};

export type RosterInviteResult = {
  participant_id: string;
  email: string | null;
  full_name: string;
  delivery_mode: "email" | "secure_links";
  email_sent: boolean;
  email_queued?: boolean;
  error: string | null;
  invite_url: string | null;
};

export type ParticipantInvitationStatus = {
  participant_id: string;
  assessment_cycle_id?: string | null;
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
  emails_queued?: number;
  emails_failed: number;
};

export type ParticipantInvitationMode = "email" | "secure_links";

export type ParticipantInviteBatchResponse = {
  results: RosterInviteResult[];
  total: number;
  emails_sent: number;
  emails_queued?: number;
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
  projects: CompanyProject[];
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

export type ProjectScopeOptions = {
  projectId?: string | null;
  assessmentCycleId?: string | null;
  sourceCycleId?: string | null;
};

export type AssessmentCycleStatus = "draft" | "active" | "closed";

export type AssessmentCycleQuestionnaire = {
  id: string;
  questionnaire_definition_id: string;
  questionnaire_key: string;
  display_order: number;
};

export type AssessmentCycle = {
  id: string;
  company_id: string;
  project_id: string;
  sequence: number;
  name: string;
  status: AssessmentCycleStatus;
  source_cycle_id: string | null;
  starts_at: string | null;
  due_at: string | null;
  closed_at: string | null;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
  questionnaires: AssessmentCycleQuestionnaire[];
};

export type CreateAssessmentCyclePayload = {
  name?: string | null;
  sourceCycleId?: string | null;
  startsAt?: string | null;
  dueAt?: string | null;
};

export type UpdateAssessmentCyclePayload = {
  name?: string | null;
  startsAt?: string | null;
  dueAt?: string | null;
};

export type ReportAverage = {
  id: string;
  label: string;
  avg: number;
  interpretation?: string | null;
  range_label?: string | null;
};

export type ReportDistribution = {
  id: string;
  label: string;
  value: number;
  color?: string | null;
};

export type ReportTeamLens = {
  id: string;
  name: string;
  member_count: number;
  assigned_count: number;
  completed_count: number;
  completion_rate: number;
  lencioni_count: number;
  driver_count: number;
  boss_360_count: number;
  pcm_base_count: number;
  pcm_phase_count: number;
  lencioni_averages: ReportAverage[];
  driver_averages: ReportAverage[];
  boss_360_averages: ReportAverage[];
  pcm_base_distribution: ReportDistribution[];
  pcm_phase_distribution: ReportDistribution[];
};

export type ReportHierarchyIssue = {
  code: string;
  participant_id?: string | null;
  participant_name?: string | null;
  reports_to_name?: string | null;
  message: string;
};

export type CompanyScoringResult = {
  id: string;
  assignment_id: string;
  scores: Record<string, unknown>;
  primary_result: string | null;
};

export type CompanyReportAggregate = {
  total_assigned: number;
  total_completed: number;
  completion_rate: number;
  lencioni_count: number;
  driver_count: number;
  boss_360_count: number;
  pcm_base_count: number;
  pcm_phase_count: number;
  lencioni_averages: ReportAverage[];
  driver_averages: ReportAverage[];
  boss_360_averages: ReportAverage[];
  pcm_base_distribution: ReportDistribution[];
  pcm_phase_distribution: ReportDistribution[];
  team_lenses: ReportTeamLens[];
  hierarchy_ambiguous: boolean;
  hierarchy_ambiguity_message: string | null;
  hierarchy_issues: ReportHierarchyIssue[];
  results: CompanyScoringResult[];
};

export type CompanyReportComparison = {
  baseline_cycle_id: string;
  comparison_cycle_id: string;
  baseline: CompanyReportAggregate;
  comparison: CompanyReportAggregate;
};

export type IcareAnswerReviewRow = {
  assignment_id: string;
  response_id: string;
  submitted_at: string | null;
  respondent_profile_id: string;
  respondent_name: string;
  respondent_email?: string | null;
  target_profile_id?: string | null;
  target_name?: string | null;
  target_type: string;
  section_id: string;
  section_label: string;
  measurement_id: string;
  measurement_label: string;
  statement_id: string;
  statement_label: string;
  answer_value: number | string;
  answer_label: string;
  answer_description?: string | null;
};

export type IcareAnswerReview = {
  rows: IcareAnswerReviewRow[];
  row_count: number;
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

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Date indisponibile.";
}

function projectQuery(scope: ProjectScopeOptions = {}): string {
  const params = new URLSearchParams();
  if (scope.projectId) params.set("project_id", scope.projectId);
  if (scope.assessmentCycleId) params.set("assessment_cycle_id", scope.assessmentCycleId);
  if (scope.sourceCycleId) params.set("source_cycle_id", scope.sourceCycleId);
  const query = params.toString();
  return query ? `?${query}` : "";
}

function hasBrowserSessionCookie(): boolean {
  return typeof document !== "undefined" && document.cookie.includes("codrut_session=");
}

function shouldUseBrowserDemoFallback(options: ApiRequestOptions = {}): boolean {
  return (
    typeof window !== "undefined" &&
    !process.env.VITEST &&
    isDemoFallbackEnabled() &&
    !hasBrowserSessionCookie() &&
    !options.headers
  );
}

function fallbackCompanyList(): CompanyListItem[] {
  return [
    {
      id: "demo-project",
      name: "Atlas Mobility",
      participantCount: fallbackCompanyParticipants("demo-project").length,
      projectCount: fallbackCompanyProjects("demo-project").length,
      assignmentCount: fallbackCompanyAssignments("demo-project").length,
      completedCount: fallbackCompanyAssignments("demo-project").filter(isCompletedAssignment).length,
      stage: "completion",
    },
    {
      id: "leadership-pilot",
      name: "Echipa direcție",
      participantCount: fallbackCompanyParticipants("leadership-pilot").length,
      projectCount: fallbackCompanyProjects("leadership-pilot").length,
      assignmentCount: fallbackCompanyAssignments("leadership-pilot").length,
      completedCount: fallbackCompanyAssignments("leadership-pilot").filter(isCompletedAssignment).length,
      stage: "completion",
    },
    {
      id: "past-client-video",
      name: "Clinica Meridian",
      participantCount: fallbackCompanyParticipants("past-client-video").length,
      projectCount: fallbackCompanyProjects("past-client-video").length,
      assignmentCount: fallbackCompanyAssignments("past-client-video").length,
      completedCount: fallbackCompanyAssignments("past-client-video").filter(isCompletedAssignment).length,
      stage: "reporting",
    },
    {
      id: "nova-retail",
      name: "Nova Retail Group",
      participantCount: fallbackCompanyParticipants("nova-retail").length,
      projectCount: fallbackCompanyProjects("nova-retail").length,
      assignmentCount: fallbackCompanyAssignments("nova-retail").length,
      completedCount: fallbackCompanyAssignments("nova-retail").filter(isCompletedAssignment).length,
      stage: "setup",
    },
  ];
}

function fallbackCompanyRecords(): Array<{ id: string; name: string }> {
  return [
    { id: "demo-project", name: "Atlas Mobility" },
    { id: "leadership-pilot", name: "Echipa direcție" },
    { id: "past-client-video", name: "Clinica Meridian" },
    { id: "nova-retail", name: "Nova Retail Group" },
  ];
}

function fallbackCompanyRecord(companyId: string): { id: string; name: string } | null {
  return fallbackCompanyRecords().find((company) => company.id === companyId) ?? null;
}

function shouldUseSeededCompanyFallback(companyId: string): boolean {
  return isLocalSeededDemoFallbackEnabled() && fallbackCompanyRecord(companyId) !== null;
}

function fallbackCompanyDetail(company: { id: string; name: string }): CompanyDetail {
  const projects = fallbackCompanyProjects(company.id);
  const participants = fallbackCompanyParticipants(company.id);
  const assignments = fallbackCompanyAssignments(company.id);
  const completedAssignments = assignments.filter(isCompletedAssignment).length;
  const scoredCount = assignments.filter((assignment) => assignment.status === "scored").length;
  const pendingCount = assignments.filter(
    (assignment) => assignment.status === "assigned" || assignment.status === "invited" || assignment.status === "started",
  ).length;

  return {
    id: company.id,
    name: company.name,
    projects,
    participants,
    assignments,
    invitationStatuses: [],
    teams: [],
    stats: {
      totalParticipants: participants.length,
      totalAssignments: assignments.length,
      completedAssignments,
      completionRate: assignments.length > 0
        ? Math.round((completedAssignments / assignments.length) * 100)
        : 0,
      scoredCount,
      pendingCount,
    },
  };
}

function fallbackCompanyProjects(companyId?: string): CompanyProject[] {
  const projects: CompanyProject[] = [
    {
      id: "demo-project",
      company_id: "demo-project",
      company_name: "Atlas Mobility",
      name: "Leadership operațional Q3",
      description: null,
      project_type: "Leadership",
      status: "active",
      starts_at: "2026-06-01T00:00:00.000Z",
      due_at: "2026-07-15T00:00:00.000Z",
      form_opens_at: "2026-06-01T00:00:00.000Z",
      form_closes_at: "2026-07-15T00:00:00.000Z",
      created_at: "2026-06-01T00:00:00.000Z",
      updated_at: "2026-06-20T00:00:00.000Z",
    },
    {
      id: "leadership-pilot",
      company_id: "leadership-pilot",
      company_name: "Echipa direcție",
      name: "Pilot leadership iulie",
      description: null,
      project_type: "Leadership",
      status: "active",
      starts_at: "2026-06-15T00:00:00.000Z",
      due_at: "2026-07-15T00:00:00.000Z",
      form_opens_at: "2026-06-15T00:00:00.000Z",
      form_closes_at: "2026-07-15T00:00:00.000Z",
      created_at: "2026-06-15T00:00:00.000Z",
      updated_at: "2026-06-24T00:00:00.000Z",
    },
    {
      id: "atlas-retrospective",
      company_id: "demo-project",
      company_name: "Atlas Mobility",
      name: "Retrospectivă echipe service",
      description: null,
      project_type: "Follow-up",
      status: "completed",
      starts_at: "2026-04-01T00:00:00.000Z",
      due_at: "2026-05-10T00:00:00.000Z",
      form_opens_at: "2026-04-01T00:00:00.000Z",
      form_closes_at: "2026-05-10T00:00:00.000Z",
      created_at: "2026-03-25T00:00:00.000Z",
      updated_at: "2026-05-12T00:00:00.000Z",
    },
    {
      id: "meridian-aftercare",
      company_id: "past-client-video",
      company_name: "Clinica Meridian",
      name: "Follow-up management clinică",
      description: null,
      project_type: "Leadership",
      status: "archived",
      starts_at: "2026-02-01T00:00:00.000Z",
      due_at: "2026-03-01T00:00:00.000Z",
      form_opens_at: "2026-02-01T00:00:00.000Z",
      form_closes_at: "2026-03-01T00:00:00.000Z",
      created_at: "2026-01-20T00:00:00.000Z",
      updated_at: "2026-03-08T00:00:00.000Z",
    },
    {
      id: "nova-intake",
      company_id: "nova-retail",
      company_name: "Nova Retail Group",
      name: "Pregătire cohortă retail",
      description: null,
      project_type: "Intake",
      status: "draft",
      starts_at: "2026-08-01T00:00:00.000Z",
      due_at: "2026-09-05T00:00:00.000Z",
      form_opens_at: null,
      form_closes_at: null,
      created_at: "2026-06-26T00:00:00.000Z",
      updated_at: "2026-06-28T00:00:00.000Z",
    },
  ];
  return companyId ? projects.filter((project) => project.company_id === companyId) : projects;
}

function fallbackCompanyParticipants(companyId: string): CompanyParticipant[] {
  if (companyId === "leadership-pilot") {
    return [
      fallbackParticipant("alex-dima", "Alex Dima", null, "CEO", "thinker", "persister", "leadership-pilot"),
      fallbackParticipant("mara-ionescu", "Mara Ionescu", "Alex Dima", "Manager Operațiuni", "harmonizer", "harmonizer", "leadership-pilot"),
      fallbackParticipant("sorin-pavel", "Sorin Pavel", "Alex Dima", "Manager Comercial", "persister", "thinker", "leadership-pilot"),
      fallbackParticipant("diana-luca", "Diana Luca", "Mara Ionescu", "Specialist HR", "harmonizer", "imaginer", "leadership-pilot"),
      fallbackParticipant("tudor-stan", "Tudor Stan", "Mara Ionescu", "Coordonator proiect", "promoter", "rebel", "leadership-pilot"),
      fallbackParticipant("ioana-rusu", "Ioana Rusu", "Sorin Pavel", "Consultant vânzări", "rebel", "promoter", "leadership-pilot"),
    ];
  }
  if (companyId === "demo-project") {
    return [
      fallbackParticipant("radu-munteanu", "Radu Munteanu", null, "Director General", "persister", "thinker"),
      fallbackParticipant("bianca-pavel", "Bianca Pavel", "Radu Munteanu", "Director Operațiuni", "harmonizer", "harmonizer"),
      fallbackParticipant("sorin-dima", "Sorin Dima", "Radu Munteanu", "Director Service", "persister", "persister"),
      fallbackParticipant("mihai-matei", "Mihai Matei", "Bianca Pavel", "Șef flotă", "promoter", "rebel"),
      fallbackParticipant("ana-stan", "Ana Stan", "Bianca Pavel", "Coordonator call-center", "harmonizer", "imaginer"),
      fallbackParticipant("claudia-neagu", "Claudia Neagu", "Sorin Dima", "Analist operațional", "thinker", "harmonizer"),
    ];
  }
  if (companyId === "past-client-video") {
    return [
      fallbackParticipant("diana-ene", "Diana Ene", null, "Director Clinică", "harmonizer", "persister", "past-client-video"),
      fallbackParticipant("teodor-marin", "Teodor Marin", "Diana Ene", "Coordonator recepție", "thinker", "thinker", "past-client-video"),
      fallbackParticipant("anca-serban", "Anca Șerban", "Diana Ene", "Manager îngrijire pacienți", "persister", "harmonizer", "past-client-video"),
    ];
  }
  if (companyId === "nova-retail") {
    return [
      fallbackParticipant("cristina-olaru", "Cristina Olaru", null, "Director Comercial", "promoter", "promoter", "nova-retail"),
      fallbackParticipant("daniel-voicu", "Daniel Voicu", "Cristina Olaru", "Manager magazin", "thinker", "persister", "nova-retail"),
    ];
  }
  return [];
}

function fallbackParticipant(
  id: string,
  fullName: string,
  reportsToName: string | null,
  position: string,
  pcmBase: string,
  pcmPhase: string,
  companyId = "demo-project",
): CompanyParticipant {
  const isManager = reportsToName === null || position.startsWith("Director") || position.startsWith("Manager");
  return {
    id,
    project_membership_id: `membership-${id}`,
    full_name: fullName,
    email: `${id}@${companyId}.local`,
    reports_to_name: reportsToName,
    position,
    location: "București",
    role_group: isManager ? "manager" : "member",
    pcm_profile: pcmBase,
    pcm_base: pcmBase,
    pcm_phase: pcmPhase,
    user_id: isManager ? `user-${id}` : null,
  };
}

function fallbackCompanyAssignments(companyId: string, projectId?: string | null): CompanyAssignment[] {
  const assignments =
    companyId === "leadership-pilot"
      ? [
          fallbackAssignment("leadership-lencioni-alex", companyId, "alex-dima", "lencioni", "team", null, "leadership"),
          fallbackAssignment("leadership-lencioni-mara", companyId, "mara-ionescu", "lencioni", "team", null, "leadership"),
          fallbackAssignment("leadership-lencioni-sorin", companyId, "sorin-pavel", "lencioni", "team", null, "leadership"),
          fallbackAssignment("mara-team-lencioni-diana", companyId, "diana-luca", "lencioni", "team", null, "team-mara-ionescu"),
          fallbackAssignment("mara-team-lencioni-tudor", companyId, "tudor-stan", "lencioni", "team", null, "team-mara-ionescu"),
          fallbackAssignment("sorin-team-lencioni-ioana", companyId, "ioana-rusu", "lencioni", "team", null, "team-sorin-pavel"),
          fallbackAssignment("alex-driver", companyId, "alex-dima", "distress_drivers", "self"),
          fallbackAssignment("alex-pcm", companyId, "alex-dima", "pcm_base", "self"),
          fallbackAssignment("mara-driver", companyId, "mara-ionescu", "distress_drivers", "self"),
          fallbackAssignment("mara-pcm", companyId, "mara-ionescu", "pcm_base", "self"),
          fallbackAssignment("sorin-driver", companyId, "sorin-pavel", "distress_drivers", "self"),
          fallbackAssignment("sorin-pcm", companyId, "sorin-pavel", "pcm_base", "self"),
          fallbackAssignment("icare-alex-self", companyId, "alex-dima", "boss_360", "person", "alex-dima"),
          fallbackAssignment("icare-mara-on-alex", companyId, "mara-ionescu", "boss_360", "person", "alex-dima"),
          fallbackAssignment("icare-sorin-on-alex", companyId, "sorin-pavel", "boss_360", "person", "alex-dima"),
          fallbackAssignment("icare-mara-self", companyId, "mara-ionescu", "boss_360", "person", "mara-ionescu"),
          fallbackAssignment("icare-alex-on-mara", companyId, "alex-dima", "boss_360", "person", "mara-ionescu"),
          fallbackAssignment("icare-sorin-on-mara", companyId, "sorin-pavel", "boss_360", "person", "mara-ionescu"),
          fallbackAssignment("icare-diana-on-mara", companyId, "diana-luca", "boss_360", "person", "mara-ionescu"),
          fallbackAssignment("icare-tudor-on-mara", companyId, "tudor-stan", "boss_360", "person", "mara-ionescu"),
          fallbackAssignment("icare-sorin-self", companyId, "sorin-pavel", "boss_360", "person", "sorin-pavel"),
          fallbackAssignment("icare-alex-on-sorin", companyId, "alex-dima", "boss_360", "person", "sorin-pavel"),
          fallbackAssignment("icare-ioana-on-sorin", companyId, "ioana-rusu", "boss_360", "person", "sorin-pavel"),
        ]
      : companyId === "demo-project"
        ? [
            fallbackAssignment("atlas-lencioni-radu", companyId, "radu-munteanu", "lencioni", "team"),
            fallbackAssignment("atlas-lencioni-bianca", companyId, "bianca-pavel", "lencioni", "team"),
            fallbackAssignment("atlas-lencioni-sorin", companyId, "sorin-dima", "lencioni", "team", null, null, "submitted"),
            fallbackAssignment("atlas-driver-mihai", companyId, "mihai-matei", "distress_drivers", "self", null, null, "started"),
            fallbackAssignment("atlas-driver-ana", companyId, "ana-stan", "distress_drivers", "self", null, null, "invited"),
            fallbackAssignment("atlas-driver-claudia", companyId, "claudia-neagu", "distress_drivers", "self"),
            fallbackAssignment("atlas-360-radu-bianca", companyId, "bianca-pavel", "boss_360", "person", "radu-munteanu"),
            fallbackAssignment("atlas-360-radu-sorin", companyId, "sorin-dima", "boss_360", "person", "radu-munteanu", null, "validated"),
          ]
        : companyId === "past-client-video"
          ? [
              fallbackAssignment("meridian-lencioni-diana", companyId, "diana-ene", "lencioni", "team", null, null, "scored", "meridian-aftercare"),
              fallbackAssignment("meridian-driver-teodor", companyId, "teodor-marin", "distress_drivers", "self", null, null, "scored", "meridian-aftercare"),
              fallbackAssignment("meridian-360-diana-anca", companyId, "anca-serban", "boss_360", "person", "diana-ene", null, "scored", "meridian-aftercare"),
            ]
          : companyId === "nova-retail"
            ? [
                fallbackAssignment("nova-intake-cristina", companyId, "cristina-olaru", "lencioni", "team", null, null, "assigned", "nova-intake"),
              ]
        : [];
  return projectId ? assignments.filter((assignment) => assignment.project_id === projectId) : assignments;
}

function fallbackAssignment(
  id: string,
  companyId: string,
  respondentProfileId: string,
  questionnaireKey: string,
  targetType: CompanyAssignment["target_type"],
  targetPersonId: string | null = null,
  targetTeamId: string | null = null,
  status: CompanyAssignment["status"] = "scored",
  projectId = companyId,
): CompanyAssignment {
  const completedAt = ["submitted", "validated", "scored"].includes(status) ? "2026-06-20T10:00:00.000Z" : null;
  return {
    id,
    company_id: companyId,
    project_id: projectId,
    respondent_profile_id: respondentProfileId,
    questionnaire_key: questionnaireKey,
    target_type: targetType,
    target_person_id: targetPersonId,
    target_team_id: targetType === "team" ? (targetTeamId ?? "leadership") : null,
    status,
    due_at: "2026-07-15T00:00:00.000Z",
    invited_at: status === "assigned" ? null : "2026-06-17T09:00:00.000Z",
    started_at: ["started", "submitted", "validated", "scored"].includes(status) ? "2026-06-18T12:00:00.000Z" : null,
    submitted_at: completedAt,
    validated_at: ["validated", "scored"].includes(status) ? "2026-06-21T09:00:00.000Z" : null,
    scored_at: status === "scored" ? "2026-06-21T10:05:00.000Z" : null,
    reminder_due_at: ["invited", "started"].includes(status) ? "2026-06-29T08:00:00.000Z" : null,
    last_reminder_sent_at: status === "started" ? "2026-06-24T08:00:00.000Z" : null,
  };
}

function isCompletedAssignment(assignment: CompanyAssignment): boolean {
  return assignment.status === "submitted" || assignment.status === "validated" || assignment.status === "scored";
}

function fallbackCompanyReportAggregate(companyId: string, projectId?: string | null): CompanyReportAggregate {
  const assignments = fallbackCompanyAssignments(companyId, projectId);
  const participants = fallbackCompanyParticipants(companyId);
  const completedAssignments = assignments.filter(isCompletedAssignment);
  const results = completedAssignments.map((assignment) => ({
    id: `score-${assignment.id}`,
    assignment_id: assignment.id,
    scores: fallbackScoresForAssignment(assignment),
    primary_result: null,
  }));
  const pcmBaseDistribution = fallbackPcmDistribution(participants, assignments, "pcm_base");
  const pcmPhaseDistribution = fallbackPcmDistribution(participants, assignments, "pcm_phase");
  const lencioniAverages = fallbackAverages(assignments, results, "lencioni");
  const driverAverages = fallbackAverages(assignments, results, "distress_drivers");
  const boss360Averages = fallbackAverages(assignments, results, "boss_360");
  const lencioniCount = fallbackReportCount(assignments, results, "lencioni");
  const driverCount = fallbackReportCount(assignments, results, "distress_drivers");
  const boss360Count = fallbackReportCount(assignments, results, "boss_360");

  return {
    total_assigned: assignments.length,
    total_completed: completedAssignments.length,
    completion_rate: assignments.length > 0 ? Math.round((completedAssignments.length / assignments.length) * 100) : 0,
    lencioni_count: lencioniCount,
    driver_count: driverCount,
    boss_360_count: boss360Count,
    pcm_base_count: fallbackDistributionCount(pcmBaseDistribution),
    pcm_phase_count: fallbackDistributionCount(pcmPhaseDistribution),
    lencioni_averages: lencioniAverages,
    driver_averages: driverAverages,
    boss_360_averages: boss360Averages,
    pcm_base_distribution: pcmBaseDistribution,
    pcm_phase_distribution: pcmPhaseDistribution,
    team_lenses: fallbackReportTeamLenses({
      participants,
      assignments,
      lencioniAverages,
      driverAverages,
      boss360Averages,
      lencioniCount,
      driverCount,
      boss360Count,
      pcmBaseDistribution,
      pcmPhaseDistribution,
    }),
    hierarchy_ambiguous: false,
    hierarchy_ambiguity_message: null,
    hierarchy_issues: [],
    results,
  };
}

function fallbackAverages(
  assignments: CompanyAssignment[],
  results: CompanyScoringResult[],
  questionnaireKey: string,
): ReportAverage[] {
  const resultByAssignmentId = new Map(results.map((result) => [result.assignment_id, result]));
  const matchingAssignments = assignments.filter(
    (assignment) => assignment.questionnaire_key === questionnaireKey && resultByAssignmentId.has(assignment.id),
  );
  const values = new Map<string, number[]>();
  for (const assignment of matchingAssignments) {
    const scores = resultByAssignmentId.get(assignment.id)?.scores ?? {};
    for (const [id, value] of Object.entries(scores)) {
      const score = coerceFallbackScore(value);
      if (score === null) continue;
      const existing = values.get(id) ?? [];
      existing.push(score);
      values.set(id, existing);
    }
  }

  return [...values.entries()].map(([id, scores]) => ({
    id,
    label: fallbackScoreLabel(id),
    avg: Number((scores.reduce((sum, score) => sum + score, 0) / scores.length).toFixed(1)),
    interpretation: null,
    range_label: null,
  }));
}

function fallbackReportCount(
  assignments: CompanyAssignment[],
  results: CompanyScoringResult[],
  questionnaireKey: string,
): number {
  const resultAssignmentIds = new Set(results.map((result) => result.assignment_id));
  return assignments.filter((assignment) => assignment.questionnaire_key === questionnaireKey && resultAssignmentIds.has(assignment.id)).length;
}

function fallbackPcmDistribution(
  participants: CompanyParticipant[],
  assignments: CompanyAssignment[],
  field: "pcm_base" | "pcm_phase",
): ReportDistribution[] {
  const participantsById = new Map(participants.map((participant) => [participant.id, participant]));
  const completedPcmRespondents = new Set(
    assignments
      .filter((assignment) => isCompletedAssignment(assignment) && ["pcm_base", "pcm_phase", "phase"].includes(assignment.questionnaire_key))
      .map((assignment) => assignment.respondent_profile_id),
  );
  const counts = new Map<string, number>();

  for (const participantId of completedPcmRespondents) {
    const value = participantsById.get(participantId)?.[field]?.trim();
    if (!value) continue;
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }

  return [...counts.entries()]
    .map(([id, value]) => ({ id, label: formatPcmLabel(id), value, color: getPcmColor(id) }))
    .sort((first, second) => second.value - first.value || first.label.localeCompare(second.label));
}

function fallbackDistributionCount(distribution: ReportDistribution[]): number {
  return distribution.reduce((total, item) => total + item.value, 0);
}

function fallbackReportTeamLenses({
  participants,
  assignments,
  lencioniAverages,
  driverAverages,
  boss360Averages,
  lencioniCount,
  driverCount,
  boss360Count,
  pcmBaseDistribution,
  pcmPhaseDistribution,
}: {
  participants: CompanyParticipant[];
  assignments: CompanyAssignment[];
  lencioniAverages: ReportAverage[];
  driverAverages: ReportAverage[];
  boss360Averages: ReportAverage[];
  lencioniCount: number;
  driverCount: number;
  boss360Count: number;
  pcmBaseDistribution: ReportDistribution[];
  pcmPhaseDistribution: ReportDistribution[];
}): ReportTeamLens[] {
  if (participants.length === 0) return [];
  const completedCount = assignments.filter(isCompletedAssignment).length;

  return [
    {
      id: "leadership",
      name: "Leadership",
      member_count: participants.length,
      assigned_count: assignments.length,
      completed_count: completedCount,
      completion_rate: assignments.length > 0 ? Math.round((completedCount / assignments.length) * 100) : 0,
      lencioni_count: lencioniCount,
      driver_count: driverCount,
      boss_360_count: boss360Count,
      pcm_base_count: fallbackDistributionCount(pcmBaseDistribution),
      pcm_phase_count: fallbackDistributionCount(pcmPhaseDistribution),
      lencioni_averages: lencioniAverages,
      driver_averages: driverAverages,
      boss_360_averages: boss360Averages,
      pcm_base_distribution: pcmBaseDistribution,
      pcm_phase_distribution: pcmPhaseDistribution,
    },
  ];
}

function coerceFallbackScore(value: unknown): number | null {
  const raw = typeof value === "object" && value !== null && "score" in value ? (value as { score?: unknown }).score : value;
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
}

function fallbackScoreLabel(value: string): string {
  return value
    .replace(/_/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toLocaleUpperCase("ro-RO") + part.slice(1))
    .join(" ");
}

function fallbackScoresForAssignment(assignment: CompanyAssignment): Record<string, unknown> {
  if (assignment.questionnaire_key === "distress_drivers") {
    return {
      personal_signal_a: ["mihai-matei", "teodor-marin"].includes(assignment.respondent_profile_id) ? 72 : 38,
      personal_signal_b: ["ana-stan", "claudia-neagu"].includes(assignment.respondent_profile_id) ? 66 : 44,
      personal_signal_c: assignment.respondent_profile_id === "teodor-marin" ? 61 : 54,
    };
  }
  if (assignment.questionnaire_key === "boss_360") {
    return {
      leadership_signal_a: { score: 86 },
      leadership_signal_b: { score: 78 },
      leadership_signal_c: { score: 91 },
    };
  }
  return {
    team_signal_a: { score: 8 },
    team_signal_b: { score: assignment.respondent_profile_id === "radu-munteanu" ? 7 : 6 },
    team_signal_c: { score: 6 },
  };
}

// ---------------------------------------------------------------------------
// Data fetchers
// ---------------------------------------------------------------------------

export async function getCompanyParticipants(
  companyId: string,
  options: ApiRequestOptions = {},
): Promise<CompanyParticipant[]> {
  if (shouldUseSeededCompanyFallback(companyId)) {
    return fallbackCompanyParticipants(companyId);
  }

  try {
    const response = await apiFetch(
      `${getApiBaseUrl()}/companies/${companyId}/participants`,
      { cache: "no-store", credentials: "include", ...options },
    );
    if (!response.ok) {
      if (!isDemoFallbackEnabled()) {
        throw new Error(`Eroare server (${response.status}): Nu s-au putut obține participanții.`);
      }
      return fallbackCompanyParticipants(companyId);
    }
    return (await response.json()) as CompanyParticipant[];
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return fallbackCompanyParticipants(companyId);
  }
}

export async function getProjectParticipants(
  companyId: string,
  projectId: string,
  options: ApiRequestOptions = {},
): Promise<CompanyParticipant[]> {
  if (shouldUseSeededCompanyFallback(companyId)) {
    return fallbackCompanyParticipants(companyId);
  }

  try {
    const response = await apiFetch(
      `${getApiBaseUrl()}/companies/${companyId}/projects/${projectId}/participants`,
      { cache: "no-store", credentials: "include", ...options },
    );
    if (!response.ok) {
      if (!isDemoFallbackEnabled()) {
        throw new Error(`Eroare server (${response.status}): Nu s-au putut obține participanții proiectului.`);
      }
      return fallbackCompanyParticipants(companyId);
    }
    return (await response.json()) as CompanyParticipant[];
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return fallbackCompanyParticipants(companyId);
  }
}

export async function getCompanyAssignments(
  companyId: string,
  options: ApiRequestOptions = {},
  scope: ProjectScopeOptions = {},
): Promise<CompanyAssignment[]> {
  if (shouldUseSeededCompanyFallback(companyId)) {
    return fallbackCompanyAssignments(companyId, scope.projectId);
  }

  try {
    const response = await apiFetch(
      `${getApiBaseUrl()}/companies/${companyId}/assignments${projectQuery(scope)}`,
      { cache: "no-store", credentials: "include", ...options },
    );
    if (!response.ok) {
      if (!isDemoFallbackEnabled()) {
        throw new Error(`Eroare server (${response.status}): Nu s-au putut obține asignările.`);
      }
      return fallbackCompanyAssignments(companyId, scope.projectId);
    }
    return (await response.json()) as CompanyAssignment[];
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return fallbackCompanyAssignments(companyId, scope.projectId);
  }
}

export async function getCompanyReportAggregate(
  companyId: string,
  options: ApiRequestOptions = {},
  scope: ProjectScopeOptions = {},
): Promise<CompanyReportAggregate> {
  if (shouldUseSeededCompanyFallback(companyId)) {
    return fallbackCompanyReportAggregate(companyId, scope.projectId);
  }

  try {
    const response = await apiFetch(
      `${getApiBaseUrl()}/companies/${companyId}/reports/aggregate${projectQuery(scope)}`,
      { cache: "no-store", credentials: "include", ...options },
    );
    if (!response.ok) {
      if (!isDemoFallbackEnabled()) {
        throw new Error(`Eroare server (${response.status}): Nu s-au putut calcula rapoartele.`);
      }
      return fallbackCompanyReportAggregate(companyId, scope.projectId);
    }
    return (await response.json()) as CompanyReportAggregate;
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return fallbackCompanyReportAggregate(companyId, scope.projectId);
  }
}

export async function getCompanyReportComparison(
  companyId: string,
  projectId: string,
  baselineCycleId: string,
  comparisonCycleId: string,
  options: ApiRequestOptions = {},
): Promise<CompanyReportComparison> {
  const params = new URLSearchParams({
    project_id: projectId,
    baseline_cycle_id: baselineCycleId,
    comparison_cycle_id: comparisonCycleId,
  });
  const response = await apiFetch(
    `${getApiBaseUrl()}/companies/${companyId}/reports/comparison?${params.toString()}`,
    { cache: "no-store", credentials: "include", ...options },
  );
  if (!response.ok) {
    const data = (await response.json().catch(() => null)) as ApiErrorPayload | null;
    throw new Error(formatApiError(data, `Backend refuzat (${response.status})`));
  }
  return (await response.json()) as CompanyReportComparison;
}

export async function getIcareAnswerReview(
  companyId: string,
  options: ApiRequestOptions = {},
  scope: ProjectScopeOptions = {},
): Promise<IcareAnswerReview> {
  try {
    const response = await apiFetch(
      `${getApiBaseUrl()}/companies/${companyId}/reports/icare-answers${projectQuery(scope)}`,
      { cache: "no-store", credentials: "include", ...options },
    );
    if (!response.ok) {
      if (!isDemoFallbackEnabled()) {
        throw new Error(`Eroare server (${response.status}): Nu s-au putut obține răspunsurile iCARE.`);
      }
      return { rows: [], row_count: 0 };
    }
    return (await response.json()) as IcareAnswerReview;
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return { rows: [], row_count: 0 };
  }
}

export async function createCompanyAssignment(
  companyId: string,
  payload: CreateCompanyAssignmentPayload,
): Promise<CompanyAssignment> {
  const response = await apiFetch(`${getApiBaseUrl()}/companies/${companyId}/assignments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      respondent_profile_id: payload.respondentProfileId,
      project_id: payload.projectId ?? null,
      ...(payload.assessmentCycleId ? { assessment_cycle_id: payload.assessmentCycleId } : {}),
      questionnaire_key: payload.questionnaireKey,
      target_type: payload.targetType,
      target_person_id: payload.targetPersonId ?? null,
      target_team_id: payload.targetTeamId ?? null,
      visibility_policy: payload.visibilityPolicy ?? "trainer_raw_review",
    }),
  });

  if (!response.ok) {
    const data = (await response.json().catch(() => null)) as ApiErrorPayload | null;
    throw new CompanyMutationError(
      formatApiError(data, `Backend refuzat (${response.status})`),
      typeof data?.error?.code === "string" ? data.error.code : undefined,
      data?.error?.details,
    );
  }

  return (await response.json()) as CompanyAssignment;
}

export async function getCompanyDefaultAssignmentPlan(
  companyId: string,
  options: ApiRequestOptions = {},
  scope: ProjectScopeOptions = {},
): Promise<CompanyAssignmentPlan> {
  const response = await apiFetch(`${getApiBaseUrl()}/companies/${companyId}/assignments/default-plan${projectQuery(scope)}`, {
    cache: "no-store",
    credentials: "include",
    ...options,
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.error?.message ?? `Backend refuzat (${response.status})`);
  }

  return (await response.json()) as CompanyAssignmentPlan;
}

export async function saveCompanyDefaultAssignmentPlan(
  companyId: string,
  assignments: CompanyAssignmentPlanItem[],
  projectId?: string | null,
  assessmentCycleId?: string | null,
): Promise<CompanyAssignmentPlanSaveResponse> {
  const response = await apiFetch(`${getApiBaseUrl()}/companies/${companyId}/assignments/default-plan${projectQuery({ projectId, assessmentCycleId })}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      project_id: projectId ?? null,
      ...(assessmentCycleId ? { assessment_cycle_id: assessmentCycleId } : {}),
      assignments: assignments.map((assignment) => ({
        respondent_profile_id: assignment.respondent_profile_id,
        questionnaire_key: assignment.questionnaire_key,
        target_type: assignment.target_type,
        target_person_id: assignment.target_person_id,
        target_team_id: assignment.target_team_id,
        target_team_name: assignment.target_team_name,
        target_team_type: assignment.target_team_type,
        target_team_member_ids: assignment.target_team_member_ids,
        target_team_leader_id: assignment.target_team_leader_id,
        visibility_policy: assignment.visibility_policy,
      })),
    }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.error?.message ?? `Backend refuzat (${response.status})`);
  }

  return (await response.json()) as CompanyAssignmentPlanSaveResponse;
}

export async function getCompanyTeams(
  companyId: string,
  options: ApiRequestOptions = {},
): Promise<CompanyTeam[]> {
  if (shouldUseSeededCompanyFallback(companyId)) {
    return [];
  }

  try {
    const response = await apiFetch(
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

export async function getCompanyProjects(
  companyId: string,
  options: ApiRequestOptions = {},
): Promise<CompanyProject[]> {
  if (shouldUseSeededCompanyFallback(companyId)) {
    return fallbackCompanyProjects(companyId);
  }

  try {
    const response = await apiFetch(`${getApiBaseUrl()}/companies/${companyId}/projects`, {
      cache: "no-store",
      credentials: "include",
      ...options,
    });
    if (!response.ok) {
      if (!isDemoFallbackEnabled()) {
        throw new Error(`Eroare server (${response.status}): Nu s-au putut obține proiectele.`);
      }
      return fallbackCompanyProjects(companyId);
    }
    return (await response.json()) as CompanyProject[];
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return fallbackCompanyProjects(companyId);
  }
}

export async function getAllCompanyProjects(
  options: ApiRequestOptions = {},
): Promise<CompanyProject[]> {
  try {
    const response = await apiFetch(`${getApiBaseUrl()}/companies/projects`, {
      cache: "no-store",
      credentials: "include",
      ...options,
    });
    if (!response.ok) {
      if (!isDemoFallbackEnabled()) {
        throw new Error(`Eroare server (${response.status}): Nu s-au putut obține proiectele.`);
      }
      return fallbackCompanyProjects();
    }
    return (await response.json()) as CompanyProject[];
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return fallbackCompanyProjects();
  }
}

export async function getCompanyProjectById(
  projectId: string,
  options: ApiRequestOptions = {},
): Promise<CompanyProject | null> {
  try {
    const response = await apiFetch(`${getApiBaseUrl()}/companies/projects/${projectId}`, {
      cache: "no-store",
      credentials: "include",
      ...options,
    });
    if (!response.ok) {
      if (!isDemoFallbackEnabled()) {
        throw new Error(`Eroare server (${response.status}): Nu s-a putut obține proiectul.`);
      }
      return fallbackCompanyProjects().find((project) => project.id === projectId) ?? null;
    }
    return (await response.json()) as CompanyProject;
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return fallbackCompanyProjects().find((project) => project.id === projectId) ?? null;
  }
}

export async function createCompanyProject(
  companyId: string,
  payload: CompanyProjectPayload & { name: string },
): Promise<CompanyProject> {
  const response = await apiFetch(`${getApiBaseUrl()}/companies/${companyId}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(projectPayloadToApi(payload)),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.error?.message ?? `Backend refuzat (${response.status})`);
  }
  return (await response.json()) as CompanyProject;
}

export async function updateCompanyProject(
  companyId: string,
  projectId: string,
  payload: CompanyProjectPayload,
): Promise<CompanyProject> {
  const response = await apiFetch(`${getApiBaseUrl()}/companies/${companyId}/projects/${projectId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(projectPayloadToApi(payload)),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.error?.message ?? `Backend refuzat (${response.status})`);
  }
  return (await response.json()) as CompanyProject;
}

export async function deleteCompanyProject(companyId: string, projectId: string): Promise<void> {
  const response = await apiFetch(`${getApiBaseUrl()}/companies/${companyId}/projects/${projectId}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.error?.message ?? `Backend refuzat (${response.status})`);
  }
}

function assessmentCyclePayloadToApi(
  payload: CreateAssessmentCyclePayload | UpdateAssessmentCyclePayload,
) {
  return {
    ...(payload.name !== undefined ? { name: payload.name } : {}),
    ...("sourceCycleId" in payload && payload.sourceCycleId !== undefined
      ? { source_cycle_id: payload.sourceCycleId }
      : {}),
    ...(payload.startsAt !== undefined ? { starts_at: payload.startsAt } : {}),
    ...(payload.dueAt !== undefined ? { due_at: payload.dueAt } : {}),
  };
}

function assessmentCycleBaseUrl(companyId: string, projectId: string): string {
  return `${getApiBaseUrl()}/companies/${companyId}/projects/${projectId}/assessment-cycles`;
}

export async function getAssessmentCycles(
  companyId: string,
  projectId: string,
  options: ApiRequestOptions = {},
): Promise<AssessmentCycle[]> {
  const response = await apiFetch(assessmentCycleBaseUrl(companyId, projectId), {
    cache: "no-store",
    credentials: "include",
    ...options,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.error?.message ?? `Backend refuzat (${response.status})`);
  }
  return (await response.json()) as AssessmentCycle[];
}

export async function createAssessmentCycle(
  companyId: string,
  projectId: string,
  payload: CreateAssessmentCyclePayload,
): Promise<AssessmentCycle> {
  const response = await apiFetch(assessmentCycleBaseUrl(companyId, projectId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(assessmentCyclePayloadToApi(payload)),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.error?.message ?? `Backend refuzat (${response.status})`);
  }
  return (await response.json()) as AssessmentCycle;
}

export async function updateAssessmentCycle(
  companyId: string,
  projectId: string,
  assessmentCycleId: string,
  payload: UpdateAssessmentCyclePayload,
): Promise<AssessmentCycle> {
  const response = await apiFetch(
    `${assessmentCycleBaseUrl(companyId, projectId)}/${assessmentCycleId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(assessmentCyclePayloadToApi(payload)),
    },
  );
  if (!response.ok) {
    const data = (await response.json().catch(() => null)) as ApiErrorPayload | null;
    throw new CompanyMutationError(
      formatApiError(data, `Backend refuzat (${response.status})`),
      typeof data?.error?.code === "string" ? data.error.code : undefined,
      data?.error?.details,
    );
  }
  return (await response.json()) as AssessmentCycle;
}

export async function deleteAssessmentCycle(
  companyId: string,
  projectId: string,
  assessmentCycleId: string,
): Promise<void> {
  const response = await apiFetch(
    `${assessmentCycleBaseUrl(companyId, projectId)}/${assessmentCycleId}`,
    { method: "DELETE", credentials: "include" },
  );
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.error?.message ?? `Backend refuzat (${response.status})`);
  }
}

export async function closeAssessmentCycle(
  companyId: string,
  projectId: string,
  assessmentCycleId: string,
  cancelUnfinished = false,
): Promise<AssessmentCycle> {
  const response = await apiFetch(
    `${assessmentCycleBaseUrl(companyId, projectId)}/${assessmentCycleId}/close`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ cancel_unfinished: cancelUnfinished }),
    },
  );
  if (!response.ok) {
    const data = (await response.json().catch(() => null)) as ApiErrorPayload | null;
    throw new CompanyMutationError(
      formatApiError(data, `Backend refuzat (${response.status})`),
      typeof data?.error?.code === "string" ? data.error.code : undefined,
      data?.error?.details,
    );
  }
  return (await response.json()) as AssessmentCycle;
}

// ---------------------------------------------------------------------------
// Aggregated fetchers
// ---------------------------------------------------------------------------

export async function getCompanyList(options: ApiRequestOptions = {}): Promise<CompanyListItem[]> {
  if (shouldUseBrowserDemoFallback(options)) {
    return fallbackCompanyList();
  }

  const summaryResponse = await apiFetch(`${getApiBaseUrl()}/companies/summary`, {
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
    const companiesResponse = await apiFetch(`${getApiBaseUrl()}/companies`, {
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
    fallbackCompanyRecords().forEach((company) => map.set(company.id, company));
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
          projectCount: 0,
          assignmentCount: assignments.length,
          completedCount,
          stage: deriveStage(assignments.length, completedCount),
        };
      } catch (e) {
        return {
          id: company.id,
          name: company.name,
          participantCount: 0,
          projectCount: 0,
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
    projectCount: summary.project_count,
    assignmentCount: summary.assignment_count,
    completedCount: summary.completed_count,
    stage: summary.stage,
  };
}

export async function createCompany(name: string): Promise<{ id: string; name: string }> {
  const response = await apiFetch(`${getApiBaseUrl()}/companies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Nu sunteți autentificat. Vă rugăm să vă reconectați.");
    }
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.error?.message ?? `Eroare server: ${response.status}`);
  }
  return (await response.json()) as { id: string; name: string };
}

export async function deleteCompany(companyId: string): Promise<void> {
  const response = await apiFetch(`${getApiBaseUrl()}/companies/${companyId}`, {
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
    "Role Group"?: string;
    email: string;
    "Profil PCM": string;
    "PCM Bază"?: string;
    "PCM Fază"?: string;
  }>,
  options: {
    sendInvites?: boolean;
    projectId?: string | null;
    idempotencyKey?: string;
  } = {},
): Promise<RosterImportResponse> {
  const idempotencyKey = options.idempotencyKey ?? createIdempotencyKey("roster");
  const response = await apiFetch(`${getApiBaseUrl()}/companies/${companyId}/participants/roster`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    credentials: "include",
    body: JSON.stringify({
      rows,
      send_invites: options.sendInvites ?? false,
      project_id: options.projectId ?? null,
    }),
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ApiErrorPayload | null;
    throw new Error(formatApiError(payload, `Backend refuzat (${response.status})`));
  }

  return (await response.json()) as RosterImportResponse;
}

export async function updateCompanyParticipant(
  companyId: string,
  participantId: string,
  payload: UpdateCompanyParticipantPayload,
): Promise<CompanyParticipant> {
  const response = await apiFetch(`${getApiBaseUrl()}/companies/${companyId}/participants/${participantId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      project_id: payload.projectId ?? null,
      full_name: payload.fullName,
      email: payload.email,
      reports_to_name: payload.reportsToName,
      position: payload.position,
      location: payload.location,
      role_group: payload.roleGroup,
    }),
  });

  if (!response.ok) {
    const data = (await response.json().catch(() => null)) as ApiErrorPayload | null;
    throw new Error(formatApiError(data, `Backend refuzat (${response.status})`));
  }

  return (await response.json()) as CompanyParticipant;
}

export async function sendParticipantInvitations(
  companyId: string,
  payload: {
    participantIds?: string[];
    projectId?: string | null;
    assessmentCycleId?: string | null;
    mode: ParticipantInvitationMode;
    targetMode?: "unsent" | "selected" | "all";
    forceRotate?: boolean;
    idempotencyKey?: string;
  },
): Promise<ParticipantInviteBatchResponse> {
  const response = await apiFetch(`${getApiBaseUrl()}/companies/${companyId}/participants/invitations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": payload.idempotencyKey ?? createIdempotencyKey("invite-batch"),
    },
    credentials: "include",
    body: JSON.stringify({
      participant_ids: payload.participantIds,
      project_id: payload.projectId ?? null,
      ...(payload.assessmentCycleId ? { assessment_cycle_id: payload.assessmentCycleId } : {}),
      mode: payload.mode,
      target_mode: payload.targetMode ?? (payload.participantIds?.length ? "selected" : "unsent"),
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
  projectId?: string | null,
  options: string | { assessmentCycleId?: string | null; idempotencyKey?: string } = {},
): Promise<RosterInviteResult | null> {
  const assessmentCycleId = typeof options === "string" ? null : options.assessmentCycleId;
  const idempotencyKey = typeof options === "string"
    ? options
    : (options.idempotencyKey ?? createIdempotencyKey("invite-resend"));
  const response = await apiFetch(
    `${getApiBaseUrl()}/companies/${companyId}/participants/${participantId}/resend-invite${projectQuery({ projectId, assessmentCycleId })}`,
    {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
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

function createIdempotencyKey(scope: string): string {
  const suffix = globalThis.crypto?.randomUUID?.()
    ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `${scope}-${suffix}`;
}

export async function getCompanyInvitationStatuses(
  companyId: string,
  options: ApiRequestOptions = {},
  scope: ProjectScopeOptions = {},
): Promise<ParticipantInvitationStatus[]> {
  if (shouldUseSeededCompanyFallback(companyId)) {
    return [];
  }

  try {
    const response = await apiFetch(
      `${getApiBaseUrl()}/companies/${companyId}/participants/invitations/status${projectQuery(scope)}`,
      { cache: "no-store", credentials: "include", ...options },
    );
    if (!response.ok) {
      if (!isDemoFallbackEnabled()) {
        throw new Error(`Eroare server (${response.status}): Nu s-a putut obține statusul invitațiilor.`);
      }
      return [];
    }
    return (await response.json()) as ParticipantInvitationStatus[];
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return [];
  }
}

export async function createCompanyTeam(
  companyId: string,
  payload: { name: string; type: CompanyTeam["type"] },
): Promise<CompanyTeam> {
  const response = await apiFetch(`${getApiBaseUrl()}/companies/${companyId}/teams`, {
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
  const response = await apiFetch(
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
  const response = await apiFetch(`${getApiBaseUrl()}/companies/${companyId}/teams/${teamId}/memberships`, {
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
  const localFallbackCompany = fallbackCompanyRecord(companyId);
  if (localFallbackCompany && isLocalSeededDemoFallbackEnabled()) {
    return fallbackCompanyDetail(localFallbackCompany);
  }

  let serverCompanies: Array<{ id: string; name: string }> = [];
  try {
    const response = await apiFetch(`${getApiBaseUrl()}/companies`, {
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

  if (isLocalSeededDemoFallbackEnabled() || (serverCompanies.length === 0 && isDemoFallbackEnabled())) {
    fallbackCompanyRecords().forEach((company) => map.set(company.id, company));
  }
  serverCompanies.forEach((c) => map.set(c.id, c));

  const company = map.get(companyId);
  if (!company) return null;

  const [projectsResult, participantsResult, assignmentsResult, invitationStatusesResult, teamsResult] = await Promise.allSettled([
    getCompanyProjects(companyId, options),
    getCompanyParticipants(companyId, options),
    getCompanyAssignments(companyId, options),
    getCompanyInvitationStatuses(companyId, options),
    getCompanyTeams(companyId, options),
  ]);

  const projects = projectsResult.status === "fulfilled" ? projectsResult.value : [];
  const participants = participantsResult.status === "fulfilled" ? participantsResult.value : [];
  const assignments = assignmentsResult.status === "fulfilled" ? assignmentsResult.value : [];
  const invitationStatuses = invitationStatusesResult.status === "fulfilled" ? invitationStatusesResult.value : [];
  const teams = teamsResult.status === "fulfilled" ? teamsResult.value : [];
  const dataErrors = [
    projectsResult.status === "rejected" ? `Proiecte: ${errorMessage(projectsResult.reason)}` : null,
    participantsResult.status === "rejected" ? `Participanți: ${errorMessage(participantsResult.reason)}` : null,
    assignmentsResult.status === "rejected" ? `Asignări: ${errorMessage(assignmentsResult.reason)}` : null,
    invitationStatusesResult.status === "rejected" ? `Invitații: ${errorMessage(invitationStatusesResult.reason)}` : null,
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
    projects,
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

function projectPayloadToApi(payload: CompanyProjectPayload) {
  const body: Record<string, string | null> = {};
  if ("name" in payload) body.name = payload.name ?? "";
  if ("description" in payload) body.description = payload.description ?? null;
  if ("projectType" in payload) body.project_type = payload.projectType ?? null;
  if ("status" in payload) body.status = payload.status ?? "draft";
  if ("startsAt" in payload) body.starts_at = payload.startsAt ?? null;
  if ("dueAt" in payload) body.due_at = payload.dueAt ?? null;
  if ("formOpensAt" in payload) body.form_opens_at = payload.formOpensAt ?? null;
  if ("formClosesAt" in payload) body.form_closes_at = payload.formClosesAt ?? null;
  return body;
}
