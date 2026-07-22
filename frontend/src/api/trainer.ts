import { apiFetch } from "./http";
import { getApiBaseUrl, isDemoFallbackEnabled } from "./runtime";
import {
  getCompanyDetail,
  getCompanyList,
  type ApiRequestOptions,
  type CompanyAssignment,
  type CompanyDetail,
  hasPermanentParticipantAccount,
  type CompanyParticipant,
} from "./companies";

export type TrainerStat = {
  label: string;
  value: number;
  suffix?: string;
  detail: string;
  tone?: "default" | "success" | "warning" | "danger";
};

export type TrainerSurfaceCard = {
  title: string;
  description: string;
  meta: string;
};

export type TrainerCompanyRow = {
  id: string;
  company: string;
  stage: "setup" | "invites" | "completion" | "reporting";
  invited: number;
  completed: number;
  total: number;
  blockers: string[];
  nextAction: string;
  href: string;
};

export type TrainerAction = {
  label: string;
  detail: string;
  href: string;
  urgency: "today" | "soon" | "waiting";
};

export type TrainerReportingVisibility = {
  trainerRawAccess: boolean;
  managerView: "aggregate_only" | "locked";
  note: string;
};

export type TrainerRosterMember = {
  id: string;
  name: string;
  reportsTo?: string;
  position: string;
  location: string;
  email: string;
  pcmProfile?: string;
  role: "leadership" | "member";
  inviteStatus: "account_active" | "link_sent" | "not_sent" | "blocked";
  completion: number;
};

export type TrainerOrgValidation = {
  label: string;
  detail: string;
  severity: "ok" | "warning" | "danger";
};

export type TrainerOperationsSummary = {
  roster: TrainerRosterMember[];
  validations: TrainerOrgValidation[];
};

export type TrainerDashboardSummary = {
  stats: TrainerStat[];
  cards: TrainerSurfaceCard[];
  activeCompanies: TrainerCompanyRow[];
  actions: TrainerAction[];
  visibility: TrainerReportingVisibility;
};

export async function getTrainerDashboardSummary(
  options: ApiRequestOptions = {},
): Promise<TrainerDashboardSummary> {
  const fallback: TrainerDashboardSummary = {
    stats: [
      {
        label: "Companii",
        value: 3,
        detail: "Companii active cu invitații, completări și raportare în lucru.",
      },
      {
        label: "Completare",
        value: 68,
        suffix: "%",
        detail: "Rata agregată pentru task-urile companiilor active.",
        tone: "success",
      },
      {
        label: "De urmărit",
        value: 9,
        detail: "Participanți fără progres sau cu link neaccesat.",
        tone: "warning",
      },
      {
        label: "Blocaje",
        value: 2,
        detail: "Date lipsă în roster sau erori de livrare email.",
        tone: "danger",
      },
    ],
    cards: [
      {
        title: "Companii",
        description: "Lista companiilor și statusul pregătirii pentru intake.",
        meta: "Platform",
      },
      {
        title: "Participanți",
        description: "Roster, conturi, roluri și stări de invitație.",
        meta: "Identity",
      },
      {
        title: "Chestionare",
        description: "Sarcini asignate, pornite, trimise și validate.",
        meta: "Forms",
      },
      {
        title: "Email",
        description: "Invitații, remindere, erori de livrare și test-mode.",
        meta: "Comms",
      },
    ],
    activeCompanies: [
      {
        id: "demo-project",
        company: "Atlas Mobility",
        stage: "completion",
        invited: 8,
        completed: 6,
        total: 8,
        blockers: ["1 invitație neaccesată", "1 task început, netrimis"],
        nextAction: "Trimite reminder pentru participanții fără progres",
        href: "/trainer/companies/demo-project",
      },
      {
        id: "leadership-pilot",
        company: "Echipa direcție",
        stage: "invites",
        invited: 11,
        completed: 4,
        total: 14,
        blockers: ["Roster incomplet pentru două poziții"],
        nextAction: "Validează organigrama și retrimite invitațiile",
        href: "/trainer/companies/leadership-pilot",
      },
      {
        id: "past-client-video",
        company: "Clinica Meridian",
        stage: "reporting",
        invited: 3,
        completed: 3,
        total: 3,
        blockers: [],
        nextAction: "Verifică raportul final și istoricul participanților",
        href: "/trainer/companies/past-client-video",
      },
      {
        id: "nova-retail",
        company: "Nova Retail Group",
        stage: "setup",
        invited: 0,
        completed: 0,
        total: 1,
        blockers: ["Roster în lucru", "Proiect încă în pregătire"],
        nextAction: "Completează rosterul înainte de asignări",
        href: "/trainer/companies/nova-retail",
      },
    ],
    actions: [
      {
        label: "Finalizează rosterul companiei",
        detail: "Confirmă managerul direct, poziția, locația și emailul înainte de invitații.",
        href: "/trainer/companies",
        urgency: "today",
      },
      {
        label: "Trimite reminder 360",
        detail: "Nouă persoane nu au început task-ul confidențial.",
        href: "/trainer/companies",
        urgency: "today",
      },
      {
        label: "Revizuiește vizibilitatea raportării",
        detail: "Trainerul vede detaliu; managerii evaluați primesc agregat.",
        href: "/trainer/projects",
        urgency: "soon",
      },
    ],
    visibility: {
      trainerRawAccess: true,
      managerView: "aggregate_only",
      note: "Setare demo: Andrei/trainer vede răspunsuri pentru lucru, persoanele evaluate văd doar raport agregat sau nimic până la validare.",
    },
  };

  try {
    const companies = await getCompanyList(options);
    if (companies.length === 0 && isDemoFallbackEnabled()) return fallback;
    if (companies.length === 0) {
      return {
        ...fallback,
        stats: [
          {
            label: "Companii",
            value: 0,
            detail: "Adaugă prima companie pentru a porni fluxul pilot.",
          },
          {
            label: "Rata completare",
            value: 0,
            suffix: "%",
            detail: "Nu există încă asignări active.",
            tone: "default",
          },
          {
            label: "De urmărit",
            value: 0,
            detail: "Nu există participanți activi.",
            tone: "default",
          },
          {
            label: "Blocaje",
            value: 0,
            detail: "Nu există date operaționale încă.",
            tone: "default",
          },
        ],
        activeCompanies: [],
      };
    }

    const totalInvited = companies.reduce((total, company) => total + company.assignmentCount, 0);
    const totalCompleted = companies.reduce((total, company) => total + company.completedCount, 0);
    const activeCompanies = companies.map((company) => ({
      id: company.id,
      company: company.name,
      stage: company.stage,
      invited: company.assignmentCount,
      completed: company.completedCount,
      total: company.assignmentCount,
      blockers: company.assignmentCount === 0 ? ["Fără asignări configurate"] : [],
      nextAction:
        company.assignmentCount === 0
          ? "Configurează rosterul și chestionarele"
          : company.completedCount < company.assignmentCount
            ? "Urmărește participanții fără progres"
            : "Deschide rapoartele calculate",
      href: `/trainer/companies/${company.id}`,
    }));

    const completionRate = totalInvited > 0 ? Math.round((totalCompleted / totalInvited) * 100) : 0;
    const deUrmarit = totalInvited - totalCompleted;

    return {
      stats: [
        {
          label: "Companii",
          value: companies.length,
          detail: "Companii active cu invitații, completări și raportare în lucru.",
        },
        {
          label: "Rata completare",
          value: completionRate,
          suffix: "%",
          detail: "Rata agregată pentru task-urile companiilor active.",
          tone: "success",
        },
        {
          label: "De urmărit",
          value: deUrmarit,
          detail: "Participanți fără progres sau cu link neaccesat.",
          tone: "warning",
        },
        {
          label: "Blocaje",
          value: 0,
          detail: "Erori raportate pe fluxul operațional curent.",
          tone: "default",
        },
      ],
      cards: fallback.cards,
      activeCompanies,
      actions: fallback.actions,
      visibility: fallback.visibility,
    };
  } catch {
    if (!isDemoFallbackEnabled()) {
      return {
        ...fallback,
        stats: [],
        activeCompanies: [],
        actions: [],
      };
    }
    return fallback;
  }
}

export async function getTrainerOperationsSummary(
  options: ApiRequestOptions = {},
): Promise<TrainerOperationsSummary> {
  const defaultRoster: TrainerRosterMember[] = [
    {
      id: "radu-munteanu",
      name: "Radu Munteanu",
      position: "Director General",
      location: "București",
      email: "radu.munteanu@atlas.example.com",
      pcmProfile: "Persister",
      role: "leadership",
      inviteStatus: "account_active",
      completion: 80,
    },
    {
      id: "bianca-pavel",
      name: "Bianca Pavel",
      reportsTo: "Radu Munteanu",
      position: "Director Operațiuni",
      location: "Cluj",
      email: "bianca.pavel@atlas.example.com",
      role: "leadership",
      inviteStatus: "account_active",
      completion: 62,
    },
    {
      id: "mihai-matei",
      name: "Mihai Matei",
      reportsTo: "Bianca Pavel",
      position: "Șef flotă",
      location: "Iași",
      email: "mihai.matei@atlas.example.com",
      pcmProfile: "Promoter",
      role: "member",
      inviteStatus: "link_sent",
      completion: 33,
    },
    {
      id: "ana-stan",
      name: "Ana Stan",
      reportsTo: "Bianca Pavel",
      position: "Coordonator call-center",
      location: "Remote",
      email: "ana.stan@atlas.example.com",
      role: "member",
      inviteStatus: "link_sent",
      completion: 0,
    },
    {
      id: "sorin-dima",
      name: "Sorin Dima",
      reportsTo: "Radu Munteanu",
      position: "Director Service",
      location: "Bucuresti",
      email: "sorin.dima@atlas.example.com",
      pcmProfile: "Harmonizer",
      role: "leadership",
      inviteStatus: "blocked",
      completion: 20,
    },
  ];

  try {
    const companies = await getCompanyList(options);
    if (companies.length === 0 && isDemoFallbackEnabled()) {
      return fallbackOperationsSummary(defaultRoster);
    }
    if (companies.length === 0) {
      return emptyOperationsSummary();
    }
    if (isDemoFallbackEnabled() && isSeededDemoCompanyList(companies)) {
      return fallbackOperationsSummary(defaultRoster);
    }

    const detailResults = await Promise.allSettled(
      companies.map((company) => getCompanyDetail(company.id, options)),
    );
    const details = detailResults
      .filter((result): result is PromiseFulfilledResult<CompanyDetail | null> => result.status === "fulfilled")
      .map((result) => result.value)
      .filter((detail): detail is CompanyDetail => Boolean(detail));
    const roster = details.flatMap((detail) =>
      detail.participants.map((participant) => toOperationsRosterMember(participant, detail.assignments)),
    );

    return {
      roster,
      validations: buildOperationsValidations(roster, details),
    };
  } catch {
    if (isDemoFallbackEnabled()) {
      return fallbackOperationsSummary(defaultRoster);
    }
    return emptyOperationsSummary();
  }
}

function isSeededDemoCompanyList(companies: Array<{ id: string }>): boolean {
  const seededIds = new Set(["demo-project", "leadership-pilot", "past-client-video", "nova-retail"]);
  return companies.length === seededIds.size && companies.every((company) => seededIds.has(company.id));
}

function fallbackOperationsSummary(defaultRoster: TrainerRosterMember[]): TrainerOperationsSummary {
  return {
    roster: defaultRoster,
    validations: [
      {
        label: "Reports To",
        detail: `${defaultRoster.filter((r) => r.reportsTo || r.id === "radu-munteanu").length}/${defaultRoster.length} persoane au manager validat.`,
        severity: "ok",
      },
      {
        label: "Profil PCM",
        detail: `PCM este opțional și este configurat pentru ${defaultRoster.filter((r) => r.pcmProfile).length} persoane.`,
        severity: "ok",
      },
      {
        label: "Email",
        detail: "Sorin Dima are invitație blocată până la confirmarea adresei.",
        severity: "warning",
      },
    ],
  };
}

function emptyOperationsSummary(): TrainerOperationsSummary {
  return {
    roster: [],
    validations: [
      {
        label: "Roster",
        detail: "Nu există încă date reale de roster pentru compania selectată.",
        severity: "warning",
      },
    ],
  };
}

function toOperationsRosterMember(
  participant: CompanyParticipant,
  assignments: CompanyAssignment[],
): TrainerRosterMember {
  const participantAssignments = assignments.filter(
    (assignment) => assignment.respondent_profile_id === participant.id,
  );
  const completedAssignments = participantAssignments.filter(
    (assignment) =>
      assignment.status === "submitted" ||
      assignment.status === "validated" ||
      assignment.status === "scored",
  );

  return {
    id: participant.id,
    name: participant.full_name,
    reportsTo: participant.reports_to_name ?? undefined,
    position: participant.position ?? "Participant",
    location: participant.location ?? "Remote",
    email: participant.email ?? "Email indisponibil",
    pcmProfile: participant.pcm_profile ?? undefined,
    role: participant.role_group === "leadership" ? "leadership" : "member",
    inviteStatus: deriveInviteStatus(participant, participantAssignments),
    completion:
      participantAssignments.length > 0
        ? Math.round((completedAssignments.length / participantAssignments.length) * 100)
        : 0,
  };
}

function deriveInviteStatus(
  participant: CompanyParticipant,
  assignments: CompanyAssignment[],
): TrainerRosterMember["inviteStatus"] {
  if (hasPermanentParticipantAccount(participant)) return "account_active";
  if (assignments.length === 0) return "not_sent";
  return "link_sent";
}

function buildOperationsValidations(
  roster: TrainerRosterMember[],
  details: CompanyDetail[],
): TrainerOrgValidation[] {
  if (roster.length === 0) {
    return [
      {
        label: "Roster",
        detail: "Nu există încă participanți importați în companiile active.",
        severity: "warning",
      },
    ];
  }

  const names = new Set(roster.map((member) => member.name));
  const validReportsTo = roster.filter((member) => !member.reportsTo || names.has(member.reportsTo)).length;
  const pcmCount = roster.filter((member) => member.pcmProfile).length;
  const dataErrorCount = details.reduce((total, detail) => total + (detail.dataErrors?.length ?? 0), 0);

  return [
    {
      label: "Reports To",
      detail: `${validReportsTo}/${roster.length} persoane au manager validat.`,
      severity: validReportsTo === roster.length ? "ok" : "warning",
    },
    {
      label: "Profil PCM",
      detail: `PCM este opțional și este configurat pentru ${pcmCount} persoane.`,
      severity: "ok",
    },
    {
      label: "Date backend",
      detail:
        dataErrorCount === 0
          ? "Rosterul, asignările și echipele au fost citite din backend."
          : `${dataErrorCount} citiri backend au eșuat parțial.`,
      severity: dataErrorCount === 0 ? "ok" : "warning",
    },
  ];
}

export type ScoringResultRecord = {
  id: string;
  assignment_id: string;
  scores: Record<string, unknown>;
  primary_result: string | null;
};

export async function getScoringResult(
  assignmentId: string,
  options: ApiRequestOptions = {},
): Promise<ScoringResultRecord | null> {
  try {
    const response = await apiFetch(`${getApiBaseUrl()}/scoring/assignments/${assignmentId}/result`, {
      cache: "no-store",
      credentials: "include",
      ...options,
    });
    if (!response.ok) {
      return isDemoFallbackEnabled() ? (fallbackScoringResults[assignmentId] ?? null) : null;
    }
    return (await response.json()) as ScoringResultRecord;
  } catch {
    return isDemoFallbackEnabled() ? (fallbackScoringResults[assignmentId] ?? null) : null;
  }
}

const fallbackScoringResults: Record<string, ScoringResultRecord> = {
  "11111111-1111-4111-8111-111111111111": {
    id: "seeded-score-11111111-1111-4111-8111-111111111111",
    assignment_id: "11111111-1111-4111-8111-111111111111",
    primary_result: "team_signal_a",
    scores: {
      team_signal_a: {
        score: 5,
        label: "Semnal de echipă A",
      },
      team_signal_b: {
        score: 7,
        label: "Semnal de echipă B",
      },
    },
  },
  "33333333-3333-4333-8333-333333333333": {
    id: "seeded-score-33333333-3333-4333-8333-333333333333",
    assignment_id: "33333333-3333-4333-8333-333333333333",
    primary_result: "team_signal_b",
    scores: {
      team_signal_a: {
        score: 8,
        label: "Semnal de echipă A",
      },
      team_signal_b: {
        score: 5,
        label: "Semnal de echipă B",
      },
    },
  },
};

export type TrainerReportItem = {
  assignmentId: string;
  participantName: string;
  participantEmail: string;
  questionnaireKey: string;
  projectName: string;
  status: string;
  submittedAt: string | null;
  scoredAt?: string | null;
  primaryResult?: string | null;
};

export async function getTrainerReports(options: ApiRequestOptions = {}): Promise<TrainerReportItem[]> {
  try {
    const companies = await getCompanyList(options);
    if (companies.length === 0) return isDemoFallbackEnabled() ? fallbackTrainerReports() : [];

    const nestedReports = await Promise.all(
      companies.map(async (company) => {
        const detail = await getCompanyDetail(company.id, options);
        if (!detail) return [];

        const participantsById = new Map(
          detail.participants.map((participant) => [participant.id, participant]),
        );

        return Promise.all(
          detail.assignments
            .filter((assignment) => assignment.status === "submitted" || assignment.status === "scored")
            .map(async (assignment) => {
              const participant = participantsById.get(assignment.respondent_profile_id);
              const result = await getScoringResult(assignment.id);

              return toTrainerReportItem({
                assignment,
                projectName: company.name,
                participantName: participant?.full_name ?? "Participant necunoscut",
                participantEmail: participant?.email ?? "email indisponibil",
                primaryResult: result?.primary_result ?? null,
              });
            }),
        );
      }),
    );

    const reports = nestedReports.flat();
    return reports.length > 0 ? reports : isDemoFallbackEnabled() ? fallbackTrainerReports() : [];
  } catch {
    return isDemoFallbackEnabled() ? fallbackTrainerReports() : [];
  }
}

function toTrainerReportItem({
  assignment,
  projectName,
  participantName,
  participantEmail,
  primaryResult,
}: {
  assignment: CompanyAssignment;
  projectName: string;
  participantName: string;
  participantEmail: string;
  primaryResult: string | null;
}): TrainerReportItem {
  return {
    assignmentId: assignment.id,
    participantName,
    participantEmail,
    questionnaireKey: assignment.questionnaire_key,
    projectName,
    status: assignment.status,
    submittedAt: assignment.submitted_at,
    scoredAt: assignment.scored_at,
    primaryResult,
  };
}

function fallbackTrainerReports(): TrainerReportItem[] {
  return [
      {
        assignmentId: "11111111-1111-4111-8111-111111111111",
        participantName: "Mihai Matei",
        participantEmail: "mihai.matei@example.com",
        questionnaireKey: "lencioni",
        projectName: "Intake Iunie",
        status: "scored",
        submittedAt: "2026-06-04T12:00:00Z",
        scoredAt: "2026-06-04T12:00:00Z",
        primaryResult: "team_signal_a",
      },
      {
        assignmentId: "22222222-2222-4222-8222-222222222222",
        participantName: "Ioana Ionescu",
        participantEmail: "ioana.ionescu@example.com",
        questionnaireKey: "boss_360",
        projectName: "Intake Iunie",
        status: "submitted",
        submittedAt: "2026-06-04T13:30:00Z",
        primaryResult: null,
      },
      {
        assignmentId: "33333333-3333-4333-8333-333333333333",
        participantName: "Andrei Popescu",
        participantEmail: "andrei.popescu@example.com",
        questionnaireKey: "lencioni",
        projectName: "Intake Iunie",
        status: "scored",
        submittedAt: "2026-06-04T10:00:00Z",
        scoredAt: "2026-06-04T10:00:00Z",
        primaryResult: "team_signal_b",
      },
    ];
}
