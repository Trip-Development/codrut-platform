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

export type TrainerDashboardSummary = {
  stats: TrainerStat[];
  cards: TrainerSurfaceCard[];
  activeProjects: TrainerProjectRow[];
  actions: TrainerAction[];
  visibility: TrainerReportingVisibility;
};

export async function getTrainerDashboardSummary(): Promise<TrainerDashboardSummary> {
  return {
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
        href: "/trainer/projects/demo-project",
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
        href: "/trainer/projects/leadership-pilot",
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
}
