import { resolveInviteBundle, type InviteTask } from "./invites";
import { apiFetch } from "./http";
import { getApiBaseUrl, isSeededDemoFallbackEnabled } from "./runtime";

export type ParticipantWorkspaceCard = {
  title: string;
  description: string;
  meta?: string;
};

export type ParticipantWorkspaceSummary = {
  participantProfileId?: string;
  participantFullName: string;
  anonymousName?: string | null;
  pcmBase?: string | null;
  pcmPhase?: string | null;
  projectName: string;
  projectId?: string | null;
  assessmentCycleId?: string | null;
  contextSelectionRequired: boolean;
  contexts: ParticipantWorkspaceContext[];
  cycles: ParticipantWorkspaceCycle[];
  projects: ParticipantWorkspaceProject[];
  questionnaireProjects?: ParticipantQuestionnaireProject[];
  companyName: string;
  participantEmail: string;
  deadlineLabel: string;
  tasks: InviteTask[];
  results: ParticipantWorkspaceResult[];
  receivedFeedback?: ParticipantReceivedFeedbackSummary | null;
  receivedFeedbackGroups: ParticipantReceivedFeedbackSummary[];
  cards: ParticipantWorkspaceCard[];
  emptyState: {
    title: string;
    description: string;
  };
};

export type ParticipantWorkspaceProject = {
  id: string;
  name: string;
  /** Tipul proiectului e comutatorul meniului, nu o etichetă. */
  projectType?: string | null;
  status?: "active" | "completed" | "archived";
  historyBucket?: "current" | "history";
  deadlineLabel: string;
  deadlineAt?: string | null;
  cycles?: ParticipantWorkspaceCycle[];
};

export type ParticipantWorkspaceCycle = {
  id: string;
  projectId: string;
  sequence: number;
  name: string;
  status: "draft" | "active" | "closed";
  startsAt?: string | null;
  dueAt?: string | null;
  closedAt?: string | null;
};

export type ParticipantQuestionnaireProject = {
  id: string;
  participantProfileId: string;
  companyName: string;
  name: string;
  status: "active" | "completed" | "archived";
  historyBucket: "current" | "history";
  deadlineLabel: string;
  completedCount: number;
  totalCount: number;
  questionnaires: InviteTask[];
};

export type ParticipantWorkspaceContext = {
  participantProfileId: string;
  participantFullName: string;
  participantEmail?: string | null;
  companyId: string;
  companyName: string;
  projects: ParticipantWorkspaceProject[];
};

export type ParticipantWorkspaceResult = {
  assignmentId: string;
  assessmentCycleId?: string | null;
  projectId?: string | null;
  projectName?: string | null;
  questionnaireKey: string;
  title: string;
  targetLabel: string;
  scores: Record<string, unknown>;
  primaryResult?: string | null;
  scoreUnit?: string | null;
  scaleMin?: number | null;
  scaleMax?: number | null;
  scoreScaleCompatible?: boolean;
  unavailableReason?: "incompatible_score_scales" | null;
};

export type ParticipantReceivedFeedbackDimension = {
  id: string;
  label: string;
  averageScore: number;
  completedCount: number;
};

export type ParticipantReceivedFeedbackSummary = {
  projectId?: string | null;
  projectName?: string | null;
  assignmentRoundId?: string;
  assessmentCycleId?: string | null;
  questionnaireKey?: string;
  questionnaireTitle?: string;
  cohort: "direct_team" | "leadership_peers";
  completedCount: number;
  minimumCompleted: number;
  scoreUnit?: string | null;
  scaleMin?: number | null;
  scaleMax?: number;
  unavailableReason?: "privacy_threshold" | "no_eligible_dimensions" | "scoring_unavailable" | null;
  visible: boolean;
  overallAverage?: number | null;
  dimensions: ParticipantReceivedFeedbackDimension[];
};

type BackendParticipantWorkspaceSummary = {
  participant_profile_id?: string | null;
  participant_full_name?: string | null;
  participant_email?: string | null;
  anonymous_name?: string | null;
  pcm_base?: string | null;
  pcm_phase?: string | null;
  company_id?: string | null;
  company_name?: string | null;
  project_id: string | null;
  project_name?: string | null;
  assessment_cycle_id?: string | null;
  context_selection_required?: boolean;
  contexts?: BackendParticipantWorkspaceContext[];
  cycles?: BackendParticipantWorkspaceCycle[];
  projects?: BackendParticipantWorkspaceProject[];
  questionnaire_projects?: BackendParticipantQuestionnaireProject[];
  deadline_label: string;
  deadline_at?: string | null;
  tasks: InviteTask[];
  results?: BackendParticipantWorkspaceResult[];
  received_feedback?: BackendParticipantReceivedFeedbackSummary | null;
  received_feedback_groups?: BackendParticipantReceivedFeedbackSummary[];
  cards: ParticipantWorkspaceCard[];
  empty_state: ParticipantWorkspaceCard;
};

type BackendParticipantWorkspaceProject = {
  id: string;
  name: string;
  status?: "active" | "completed" | "archived";
  history_bucket?: "current" | "history";
  deadline_label: string;
  deadline_at?: string | null;
  cycles?: BackendParticipantWorkspaceCycle[];
};

type BackendParticipantWorkspaceCycle = {
  id: string;
  project_id: string;
  sequence: number;
  name: string;
  status: "draft" | "active" | "closed";
  starts_at?: string | null;
  due_at?: string | null;
  closed_at?: string | null;
};

type BackendParticipantQuestionnaireProject = {
  id: string;
  participant_profile_id: string;
  company_name: string;
  name: string;
  status: "active" | "completed" | "archived";
  history_bucket: "current" | "history";
  deadline_label: string;
  completed_count: number;
  total_count: number;
  questionnaires?: InviteTask[];
};

type BackendParticipantWorkspaceContext = {
  participant_profile_id: string;
  participant_full_name: string;
  participant_email?: string | null;
  company_id: string;
  company_name: string;
  projects?: BackendParticipantWorkspaceProject[];
};

type BackendParticipantWorkspaceResult = {
  assignment_id: string;
  assessment_cycle_id?: string | null;
  project_id?: string | null;
  project_name?: string | null;
  questionnaire_key: string;
  title: string;
  target_label: string;
  scores: Record<string, unknown>;
  primary_result?: string | null;
  score_unit?: string | null;
  scale_min?: number | null;
  scale_max?: number | null;
  score_scale_compatible?: boolean;
  unavailable_reason?: "incompatible_score_scales" | null;
};

type BackendParticipantReceivedFeedbackDimension = {
  id: string;
  label: string;
  average_score: number;
  completed_count: number;
};

type BackendParticipantReceivedFeedbackSummary = {
  project_id?: string | null;
  project_name?: string | null;
  assignment_round_id?: string;
  assessment_cycle_id?: string | null;
  questionnaire_key?: string;
  questionnaire_title?: string;
  cohort?: "direct_team" | "leadership_peers";
  completed_count: number;
  minimum_completed: number;
  score_unit?: string | null;
  scale_min?: number | null;
  scale_max?: number;
  unavailable_reason?: "privacy_threshold" | "no_eligible_dimensions" | "scoring_unavailable" | null;
  visible: boolean;
  overall_average?: number | null;
  dimensions?: BackendParticipantReceivedFeedbackDimension[];
};

export class ParticipantWorkspaceError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly requestId?: string,
  ) {
    super(message);
    this.name = "ParticipantWorkspaceError";
  }
}

export async function getParticipantWorkspaceSummary(
  options: Pick<RequestInit, "headers"> & {
    participantProfileId?: string | null;
    projectId?: string | null;
    cycleId?: string | null;
  } = {},
): Promise<ParticipantWorkspaceSummary> {
  const params = new URLSearchParams();
  if (options.participantProfileId) params.set("participant_profile_id", options.participantProfileId);
  if (options.projectId) params.set("project_id", options.projectId);
  if (options.cycleId) params.set("cycle_id", options.cycleId);
  const query = params.size > 0 ? `?${params.toString()}` : "";
  const requestOptions: Pick<RequestInit, "headers"> = { headers: options.headers };
  let response: Response;
  try {
    response = await apiFetch(`${getApiBaseUrl()}/participants/me/workspace${query}`, {
      cache: "no-store",
      credentials: "include",
      ...requestOptions,
    });
  } catch {
    if (!isSeededDemoFallbackEnabled()) {
      throw new ParticipantWorkspaceError(
        "Nu am putut încărca spațiul tău de lucru. Verifică conexiunea și încearcă din nou.",
        0,
        "network_error",
      );
    }
    return getDemoParticipantWorkspaceSummary();
  }

  if (response.ok) {
    return mapParticipantWorkspaceSummary((await response.json()) as BackendParticipantWorkspaceSummary);
  }
  const error = await participantWorkspaceErrorFromResponse(response);
  if (error.code === "participant_profile_not_found") {
    return getUnavailableParticipantWorkspaceSummary(
      "Profilul nu este încă legat de acest cont. Verifică adresa de email cu trainerul.",
    );
  }
  if (!isSeededDemoFallbackEnabled()) throw error;

  return getDemoParticipantWorkspaceSummary();
}

export type { BackendParticipantWorkspaceSummary };

export function mapParticipantWorkspaceSummary(
  data: BackendParticipantWorkspaceSummary,
): ParticipantWorkspaceSummary {
  return {
    participantProfileId: data.participant_profile_id ?? undefined,
    participantFullName: data.participant_full_name ?? "Participant",
    anonymousName: data.anonymous_name,
    pcmBase: data.pcm_base,
    pcmPhase: data.pcm_phase,
    projectName: data.project_name ?? "Selectează programul",
    projectId: data.project_id,
    assessmentCycleId: data.assessment_cycle_id,
    contextSelectionRequired: data.context_selection_required ?? false,
    contexts: (data.contexts ?? []).map(mapParticipantWorkspaceContext),
    cycles: (data.cycles ?? []).map(mapParticipantWorkspaceCycle),
    projects: (data.projects ?? []).map(mapParticipantWorkspaceProject),
    questionnaireProjects: (data.questionnaire_projects ?? []).map(
      mapParticipantQuestionnaireProject,
    ),
    companyName: data.company_name ?? "",
    participantEmail: data.participant_email ?? "",
    deadlineLabel: data.deadline_label,
    tasks: data.tasks,
    results: (data.results ?? []).map(mapParticipantWorkspaceResult),
    receivedFeedback: data.received_feedback ? mapParticipantReceivedFeedback(data.received_feedback) : null,
    receivedFeedbackGroups: (data.received_feedback_groups ?? []).map(mapParticipantReceivedFeedback),
    cards: data.cards,
    emptyState: data.empty_state,
  };
}

function mapParticipantQuestionnaireProject(
  project: BackendParticipantQuestionnaireProject,
): ParticipantQuestionnaireProject {
  return {
    id: project.id,
    participantProfileId: project.participant_profile_id,
    companyName: project.company_name,
    name: project.name,
    status: project.status,
    projectType: project.project_type ?? null,
    historyBucket: project.history_bucket,
    deadlineLabel: project.deadline_label,
    completedCount: project.completed_count,
    totalCount: project.total_count,
    questionnaires: project.questionnaires ?? [],
  };
}

function mapParticipantWorkspaceProject(
  project: BackendParticipantWorkspaceProject,
): ParticipantWorkspaceProject {
  return {
    id: project.id,
    name: project.name,
    status: project.status ?? "active",
    projectType: project.project_type ?? null,
    historyBucket: project.history_bucket ?? "current",
    deadlineLabel: project.deadline_label,
    deadlineAt: project.deadline_at,
    ...(project.cycles
      ? { cycles: project.cycles.map(mapParticipantWorkspaceCycle) }
      : {}),
  };
}

function mapParticipantWorkspaceCycle(
  cycle: BackendParticipantWorkspaceCycle,
): ParticipantWorkspaceCycle {
  return {
    id: cycle.id,
    projectId: cycle.project_id,
    sequence: cycle.sequence,
    name: cycle.name,
    status: cycle.status,
    startsAt: cycle.starts_at,
    dueAt: cycle.due_at,
    closedAt: cycle.closed_at,
  };
}

function mapParticipantWorkspaceContext(
  context: BackendParticipantWorkspaceContext,
): ParticipantWorkspaceContext {
  return {
    participantProfileId: context.participant_profile_id,
    participantFullName: context.participant_full_name,
    participantEmail: context.participant_email,
    companyId: context.company_id,
    companyName: context.company_name,
    projects: (context.projects ?? []).map(mapParticipantWorkspaceProject),
  };
}

function mapParticipantWorkspaceResult(
  result: BackendParticipantWorkspaceResult,
): ParticipantWorkspaceResult {
  return {
    assignmentId: result.assignment_id,
    assessmentCycleId: result.assessment_cycle_id,
    projectId: result.project_id,
    projectName: result.project_name,
    questionnaireKey: result.questionnaire_key,
    title: result.title,
    targetLabel: result.target_label,
    scores: result.scores,
    primaryResult: result.primary_result,
    scoreUnit: result.score_unit,
    scaleMin: result.scale_min,
    scaleMax: result.scale_max,
    scoreScaleCompatible: result.score_scale_compatible,
    unavailableReason: result.unavailable_reason,
  };
}

function mapParticipantReceivedFeedback(
  feedback: BackendParticipantReceivedFeedbackSummary,
): ParticipantReceivedFeedbackSummary {
  return {
    projectId: feedback.project_id,
    projectName: feedback.project_name,
    assignmentRoundId: feedback.assignment_round_id,
    assessmentCycleId: feedback.assessment_cycle_id,
    questionnaireKey: feedback.questionnaire_key,
    questionnaireTitle: feedback.questionnaire_title,
    cohort: feedback.cohort ?? "leadership_peers",
    completedCount: feedback.completed_count,
    minimumCompleted: feedback.minimum_completed,
    scoreUnit: feedback.score_unit,
    scaleMin: feedback.scale_min,
    scaleMax: feedback.scale_max,
    unavailableReason: feedback.unavailable_reason,
    visible: feedback.visible,
    overallAverage: feedback.overall_average,
    dimensions: (feedback.dimensions ?? []).map((dimension) => ({
      id: dimension.id,
      label: dimension.label,
      averageScore: dimension.average_score,
      completedCount: dimension.completed_count,
    })),
  };
}

async function getDemoParticipantWorkspaceSummary(): Promise<ParticipantWorkspaceSummary> {
  const bundle = await resolveInviteBundle("demo-token");
  const demoProjectName = bundle.state === "valid"
    ? bundle.projectName
    : "Leadership operațional Q3";
  const tasks = bundle.state === "valid"
    ? bundle.tasks.map((task) => ({
        ...task,
        projectId: task.projectId ?? "synthetic-leadership-project",
        projectName: task.projectName ?? demoProjectName,
      }))
    : [];

  return {
    participantFullName: bundle.state === "valid" ? bundle.participantFullName : "Mihai Matei",
    anonymousName: bundle.state === "valid" ? bundle.anonymousName : "SignalHarbor5271",
    pcmBase: "thinker",
    pcmPhase: "persister",
    projectName: demoProjectName,
    projectId: null,
    assessmentCycleId: "synthetic-cycle-current",
    contextSelectionRequired: false,
    contexts: [],
    cycles: [
      {
        id: "synthetic-cycle-baseline",
        projectId: "synthetic-leadership-project",
        sequence: 1,
        name: "Evaluare inițială",
        status: "closed",
      },
      {
        id: "synthetic-cycle-current",
        projectId: "synthetic-leadership-project",
        sequence: 2,
        name: "Reevaluare 1",
        status: "active",
      },
    ],
    projects: [
      {
        id: "synthetic-leadership-project",
        name: demoProjectName,
        deadlineLabel: bundle.state === "valid" ? bundle.deadlineLabel : "deadline-ul proiectului",
        cycles: [
          {
            id: "synthetic-cycle-baseline",
            projectId: "synthetic-leadership-project",
            sequence: 1,
            name: "Evaluare inițială",
            status: "closed",
          },
          {
            id: "synthetic-cycle-current",
            projectId: "synthetic-leadership-project",
            sequence: 2,
            name: "Reevaluare 1",
            status: "active",
          },
        ],
      },
    ],
    questionnaireProjects: tasks.length > 0
      ? [
          {
            id: "synthetic-leadership-project",
            participantProfileId: "participant-local",
            companyName: "Atlas Mobility",
            name: demoProjectName,
            status: "active",
            historyBucket: "current",
            deadlineLabel:
              bundle.state === "valid"
                ? bundle.deadlineLabel
                : "deadline-ul proiectului",
            completedCount: tasks.filter(
              (task) => task.status === "completed",
            ).length,
            totalCount: tasks.length,
            questionnaires: tasks,
          },
        ]
      : [],
    companyName: "Atlas Mobility",
    participantEmail: bundle.state === "valid" ? bundle.participantEmail : "participant.demo@example.com",
    deadlineLabel: bundle.state === "valid" ? bundle.deadlineLabel : "deadline-ul proiectului",
    tasks,
    receivedFeedback: {
      projectId: "synthetic-leadership-project",
      projectName: "Leadership operațional Q3",
      assessmentCycleId: "synthetic-cycle-current",
      cohort: "leadership_peers",
      completedCount: 3,
      minimumCompleted: 2,
      visible: true,
      overallAverage: 4.0,
      dimensions: [
        { id: "clarity", label: "Claritate", averageScore: 4.2, completedCount: 3 },
        { id: "support", label: "Sprijin", averageScore: 3.8, completedCount: 3 },
        { id: "follow_through", label: "Consecvență", averageScore: 4.0, completedCount: 3 },
      ],
    },
    receivedFeedbackGroups: [
      {
        projectId: "synthetic-leadership-project",
        projectName: "Leadership operațional Q3",
        assessmentCycleId: "synthetic-cycle-current",
        cohort: "leadership_peers",
        completedCount: 3,
        minimumCompleted: 2,
        visible: true,
        overallAverage: 4.0,
        dimensions: [
          { id: "clarity", label: "Claritate", averageScore: 4.2, completedCount: 3 },
          { id: "support", label: "Sprijin", averageScore: 3.8, completedCount: 3 },
          { id: "follow_through", label: "Consecvență", averageScore: 4.0, completedCount: 3 },
        ],
      },
    ],
    results: [
      {
        assignmentId: "synthetic-personal-result",
        assessmentCycleId: "synthetic-cycle-current",
        projectId: "synthetic-leadership-project",
        projectName: "Leadership operațional Q3",
        questionnaireKey: "synthetic_personal_checkin",
        title: "Autoevaluare de leadership",
        targetLabel: "Autoevaluare",
        primaryResult: "focus",
        scores: {
          focus: { score: 76, label: "Focalizare" },
          planning: { score: 68, label: "Planificare" },
          collaboration: { score: 82, label: "Colaborare" },
        },
      },
      {
        assignmentId: "synthetic-team-result",
        assessmentCycleId: "synthetic-cycle-current",
        projectId: "synthetic-leadership-project",
        projectName: "Leadership operațional Q3",
        questionnaireKey: "synthetic_team_checkin",
        title: "Evaluare de echipă",
        targetLabel: "Echipa pilot",
        primaryResult: "alignment",
        scores: {
          alignment: {
            score: 72,
            label: "Aliniere",
            interpretation: "Echipa are o bază comună, cu câteva decizii care merită clarificate.",
          },
          delivery: { score: 81, label: "Livrare" },
          learning: { score: 66, label: "Învățare" },
        },
      },
    ],
    cards: [
      {
        title: "De completat",
        description: `${tasks.filter((task) => task.status !== "completed").length} sarcini active`,
        meta: "Astăzi",
      },
      {
        title: "Confidențial",
        description: "Managerii evaluați nu văd răspunsuri individuale.",
        meta: "Regula",
      },
      {
        title: "Fără cont",
        description: "Linkul securizat strânge toate sarcinile pentru emailul tău.",
        meta: "Acces",
      },
    ],
    emptyState: {
      title: "Fără chestionare finalizate încă",
      description:
        "Când participantul are sarcini active, acest loc poate afișa un call-to-action și un sumar clar al pasului următor.",
    },
  };
}

async function participantWorkspaceErrorFromResponse(
  response: Response,
): Promise<ParticipantWorkspaceError> {
  try {
    const body = (await response.json()) as {
      error?: { code?: string; message?: string; request_id?: string };
    };
    return new ParticipantWorkspaceError(
      body.error?.message || "Nu am putut încărca datele contului. Reîncearcă în câteva momente.",
      response.status,
      body.error?.code || `http_${response.status}`,
      body.error?.request_id,
    );
  } catch {
    return new ParticipantWorkspaceError(
      "Nu am putut încărca datele contului. Reîncearcă în câteva momente.",
      response.status,
      `http_${response.status}`,
      response.headers?.get("X-Request-ID") ?? undefined,
    );
  }
}

function getUnavailableParticipantWorkspaceSummary(reason?: string): ParticipantWorkspaceSummary {
  return {
    participantFullName: "Participant",
    anonymousName: null,
    projectName: "Niciun proiect activ",
    projectId: null,
    assessmentCycleId: null,
    contextSelectionRequired: false,
    contexts: [],
    cycles: [],
    projects: [],
    questionnaireProjects: [],
    companyName: "Neasociată",
    participantEmail: "",
    deadlineLabel: "Fără termen",
    tasks: [],
    results: [],
    receivedFeedback: null,
    receivedFeedbackGroups: [],
    cards: [
      {
        title: "Profil în verificare",
        description: "Nu am găsit încă profilul de participant legat de acest cont.",
        meta: "Cont",
      },
      {
        title: "Sarcini",
        description: "Chestionarele apar aici imediat ce invitația este legată corect.",
        meta: "Assessment",
      },
      {
        title: "Suport",
        description: "Trimite trainerului adresa de email folosită pentru autentificare.",
        meta: "Ajutor",
      },
    ],
    emptyState: {
      title: "Spațiul nu este disponibil",
      description:
        reason ||
        "Contul este activ, dar profilul nu este încă legat de o companie sau de un proiect.",
    },
  };
}
