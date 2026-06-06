import { getApiBaseUrl, isDemoFallbackEnabled } from "./runtime";
import { getCompanyDetail, getCompanyList, type ApiRequestOptions, type CompanyAssignment } from "./companies";

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

export type TrainerProjectRow = {
  id: string;
  company: string;
  projectName: string;
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
  activeProjects: TrainerProjectRow[];
  actions: TrainerAction[];
  visibility: TrainerReportingVisibility;
};

export async function getTrainerDashboardSummary(
  options: ApiRequestOptions = {},
): Promise<TrainerDashboardSummary> {
  const fallback: TrainerDashboardSummary = {
    stats: [
      {
        label: "Livrare",
        value: 3,
        detail: "Proiecte active cu invitatii, completari si raportare in lucru.",
      },
      {
        label: "Completare",
        value: 68,
        suffix: "%",
        detail: "Rata agregata pentru task-urile proiectelor active.",
        tone: "success",
      },
      {
        label: "De urmarit",
        value: 9,
        detail: "Participanti fara progres sau cu link neaccesat.",
        tone: "warning",
      },
      {
        label: "Blocaje",
        value: 2,
        detail: "Date lipsa in roster sau erori de livrare email.",
        tone: "danger",
      },
    ],
    cards: [
      {
        title: "Companii",
        description: "Lista companiilor si statusul pregatirii pentru intake.",
        meta: "Platform",
      },
      {
        title: "Participanti",
        description: "Roster, conturi, roluri si stari de invitatie.",
        meta: "Identity",
      },
      {
        title: "Chestionare",
        description: "Sarcini asignate, pornite, trimise si validate.",
        meta: "Forms",
      },
      {
        title: "Email",
        description: "Invitatii, remindere, erori de livrare si test-mode.",
        meta: "Comms",
      },
    ],
    activeProjects: [
      {
        id: "demo-project",
        company: "Client demo",
        projectName: "Intake Iunie",
        stage: "completion",
        invited: 42,
        completed: 28,
        total: 42,
        blockers: ["3 emailuri nelivrate", "2 manageri fara cont activ"],
        nextAction: "Trimite reminder pentru participantii fara progres",
        href: "/trainer/companies/demo-project",
      },
      {
        id: "leadership-pilot",
        company: "Echipa directie",
        projectName: "Leadership pilot",
        stage: "invites",
        invited: 11,
        completed: 4,
        total: 14,
        blockers: ["Roster incomplet pentru doua pozitii"],
        nextAction: "Valideaza organigrama si retrimite invitatiile",
        href: "/trainer/companies/leadership-pilot",
      },
      {
        id: "past-client-video",
        company: "Campanie clienti trecuti",
        projectName: "Video follow-up",
        stage: "reporting",
        invited: 26,
        completed: 18,
        total: 26,
        blockers: [],
        nextAction: "Verifica raportul saptamanal open/click/view",
        href: "/trainer/email",
      },
    ],
    actions: [
      {
        label: "Finalizeaza roster Intake Iunie",
        detail: "Confirma Reports To, pozitie, locatie si email pentru import.",
        href: "/trainer/org-chart",
        urgency: "today",
      },
      {
        label: "Trimite reminder 360",
        detail: "Noua persoane nu au inceput task-ul confidential.",
        href: "/trainer/email",
        urgency: "today",
      },
      {
        label: "Revizuieste vizibilitatea raportarii",
        detail: "Trainerul vede detaliu; managerii evaluati primesc agregat.",
        href: "/trainer/reports",
        urgency: "soon",
      },
    ],
    visibility: {
      trainerRawAccess: true,
      managerView: "aggregate_only",
      note: "Setare demo: Andrei/trainer vede raspunsuri pentru lucru, persoanele evaluate vad doar raport agregat sau nimic pana la validare.",
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
            label: "Proiecte",
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
        activeProjects: [],
      };
    }

    const totalInvited = companies.reduce((total, company) => total + company.assignmentCount, 0);
    const totalCompleted = companies.reduce((total, company) => total + company.completedCount, 0);
    const activeProjects = companies.map((company) => ({
      id: company.id,
      company: company.name,
      projectName: `Intake ${company.name}`,
      stage: company.stage,
      invited: company.assignmentCount,
      completed: company.completedCount,
      total: company.assignmentCount,
      blockers: company.assignmentCount === 0 ? ["Fara asignari configurate"] : [],
      nextAction:
        company.assignmentCount === 0
          ? "Configureaza roster si chestionare"
          : company.completedCount < company.assignmentCount
            ? "Urmareste participantii fara progres"
            : "Deschide rapoartele calculate",
      href: `/trainer/companies/${company.id}`,
    }));

    const completionRate = totalInvited > 0 ? Math.round((totalCompleted / totalInvited) * 100) : 0;
    const deUrmarit = totalInvited - totalCompleted;

    return {
      stats: [
        {
          label: "Proiecte",
          value: companies.length,
          detail: "Proiecte active cu invitatii, completari si raportare in lucru.",
        },
        {
          label: "Rata completare",
          value: completionRate,
          suffix: "%",
          detail: "Rata agregata pentru task-urile proiectelor active.",
          tone: "success",
        },
        {
          label: "De urmarit",
          value: deUrmarit,
          detail: "Participanti fara progres sau cu link neaccesat.",
          tone: "warning",
        },
        {
          label: "Blocaje",
          value: 0,
          detail: "Erori raportate pe fluxul operational curent.",
          tone: "default",
        },
      ],
      cards: fallback.cards,
      activeProjects,
      actions: fallback.actions,
      visibility: fallback.visibility,
    };
  } catch {
    if (!isDemoFallbackEnabled()) {
      return {
        ...fallback,
        stats: [],
        activeProjects: [],
        actions: [],
      };
    }
    return fallback;
  }
}

export async function getTrainerOperationsSummary(): Promise<TrainerOperationsSummary> {
  const defaultRoster: TrainerRosterMember[] = [
    {
      id: "andrei-popescu",
      name: "Andrei Popescu",
      position: "Director General",
      location: "Bucuresti",
      email: "andrei.popescu@client.ro",
      pcmProfile: "Persister",
      role: "leadership",
      inviteStatus: "account_active",
      completion: 80,
    },
    {
      id: "ioana-ionescu",
      name: "Ioana Ionescu",
      reportsTo: "Andrei Popescu",
      position: "Director Operatiuni",
      location: "Cluj",
      email: "ioana.ionescu@client.ro",
      role: "leadership",
      inviteStatus: "account_active",
      completion: 62,
    },
    {
      id: "mihai-matei",
      name: "Mihai Matei",
      reportsTo: "Ioana Ionescu",
      position: "Team Lead",
      location: "Iasi",
      email: "mihai.matei@client.ro",
      pcmProfile: "Promoter",
      role: "member",
      inviteStatus: "link_sent",
      completion: 33,
    },
    {
      id: "ana-stan",
      name: "Ana Stan",
      reportsTo: "Ioana Ionescu",
      position: "Specialist",
      location: "Remote",
      email: "ana.stan@client.ro",
      role: "member",
      inviteStatus: "link_sent",
      completion: 0,
    },
    {
      id: "elena-radu",
      name: "Elena Radu",
      reportsTo: "Andrei Popescu",
      position: "Director HR",
      location: "Bucuresti",
      email: "elena.radu@client.ro",
      pcmProfile: "Harmonizer",
      role: "leadership",
      inviteStatus: "blocked",
      completion: 20,
    },
  ];

  if (!isDemoFallbackEnabled()) {
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

  const mergedRoster = [...defaultRoster];

  if (typeof window !== "undefined") {
    try {
      const storedLocalCompanies = localStorage.getItem("codrut_local_companies");
      const localCos = storedLocalCompanies ? JSON.parse(storedLocalCompanies) as Array<{ id: string }> : [];
      const companyIds = ["demo-project", "leadership-pilot", "past-client-video", ...localCos.map((c) => c.id)];

      companyIds.forEach((cId) => {
        const storedP = localStorage.getItem(`codrut_participants_${cId}`);
        if (storedP) {
          try {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const parsed = JSON.parse(storedP) as any[];
            parsed.forEach((p) => {
              if (!mergedRoster.some((r) => r.email.toLowerCase() === p.email.toLowerCase())) {
                mergedRoster.push({
                  id: p.id,
                  name: p.full_name,
                  reportsTo: p.reports_to_name || undefined,
                  position: p.position || "Participant",
                  location: p.location || "Remote",
                  email: p.email,
                  pcmProfile: p.pcm_profile || undefined,
                  role: p.role_group || "member",
                  inviteStatus: "link_sent",
                  completion: 0,
                });
              }
            });
          } catch {}
        }
      });
    } catch (e) {
      console.error("Error merging local roster", e);
    }
  }

  return {
    roster: mergedRoster,
    validations: [
      {
        label: "Reports To",
        detail: `${mergedRoster.filter((r) => r.reportsTo || r.id === "andrei-popescu").length}/${mergedRoster.length} persoane au manager validat.`,
        severity: "ok",
      },
      {
        label: "Profil PCM",
        detail: `PCM este optional si este configurat pentru ${mergedRoster.filter((r) => r.pcmProfile).length} persoane.`,
        severity: "ok",
      },
      {
        label: "Email",
        detail: "Elena Radu are invitatie blocata pana la confirmarea adresei.",
        severity: "warning",
      },
    ],
  };
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
    const response = await fetch(`${getApiBaseUrl()}/scoring/assignments/${assignmentId}/result`, {
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
    primary_result: "absence_of_trust",
    scores: {
      absence_of_trust: {
        score: 5,
        interpretation: "Disfunctia trebuie probabil abordata.",
      },
      fear_of_conflict: {
        score: 7,
        interpretation: "Disfunctia poate fi o problema.",
      },
      lack_of_commitment: {
        score: 8,
        interpretation: "Disfunctia probabil nu este o problema.",
      },
      avoidance_of_accountability: {
        score: 6,
        interpretation: "Disfunctia poate fi o problema.",
      },
      inattention_to_results: {
        score: 9,
        interpretation: "Disfunctia probabil nu este o problema.",
      },
    },
  },
  "33333333-3333-4333-8333-333333333333": {
    id: "seeded-score-33333333-3333-4333-8333-333333333333",
    assignment_id: "33333333-3333-4333-8333-333333333333",
    primary_result: "fear_of_conflict",
    scores: {
      absence_of_trust: {
        score: 8,
        interpretation: "Disfunctia probabil nu este o problema.",
      },
      fear_of_conflict: {
        score: 5,
        interpretation: "Disfunctia trebuie probabil abordata.",
      },
      lack_of_commitment: {
        score: 7,
        interpretation: "Disfunctia poate fi o problema.",
      },
      avoidance_of_accountability: {
        score: 8,
        interpretation: "Disfunctia probabil nu este o problema.",
      },
      inattention_to_results: {
        score: 9,
        interpretation: "Disfunctia probabil nu este o problema.",
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
        participantEmail: "mihai.matei@client.ro",
        questionnaireKey: "lencioni",
        projectName: "Intake Iunie",
        status: "scored",
        submittedAt: "2026-06-04T12:00:00Z",
        scoredAt: "2026-06-04T12:00:00Z",
        primaryResult: "absence_of_trust",
      },
      {
        assignmentId: "22222222-2222-4222-8222-222222222222",
        participantName: "Ioana Ionescu",
        participantEmail: "ioana.ionescu@client.ro",
        questionnaireKey: "boss_360",
        projectName: "Intake Iunie",
        status: "submitted",
        submittedAt: "2026-06-04T13:30:00Z",
        primaryResult: null,
      },
      {
        assignmentId: "33333333-3333-4333-8333-333333333333",
        participantName: "Andrei Popescu",
        participantEmail: "andrei.popescu@client.ro",
        questionnaireKey: "lencioni",
        projectName: "Intake Iunie",
        status: "scored",
        submittedAt: "2026-06-04T10:00:00Z",
        scoredAt: "2026-06-04T10:00:00Z",
        primaryResult: "fear_of_conflict",
      },
    ];
}
