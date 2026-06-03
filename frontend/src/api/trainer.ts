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

export async function getTrainerOperationsSummary(): Promise<TrainerOperationsSummary> {
  return {
    roster: [
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
    ],
    validations: [
      {
        label: "Reports To",
        detail: "4/5 persoane au manager validat; directorul general ramane radacina.",
        severity: "ok",
      },
      {
        label: "Profil PCM",
        detail: "PCM este optional si lipseste pentru 2 persoane, conform asteptarii.",
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
