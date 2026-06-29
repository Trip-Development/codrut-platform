import { resolveInviteBundle, type InviteTask } from "./invites";
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
  companyName: string;
  participantEmail: string;
  deadlineLabel: string;
  tasks: InviteTask[];
  results: ParticipantWorkspaceResult[];
  cards: ParticipantWorkspaceCard[];
  emptyState: {
    title: string;
    description: string;
  };
};

export type ParticipantWorkspaceResult = {
  assignmentId: string;
  questionnaireKey: string;
  title: string;
  targetLabel: string;
  scores: Record<string, unknown>;
  primaryResult?: string | null;
};

type BackendParticipantWorkspaceSummary = {
  participant_profile_id: string;
  participant_full_name: string;
  participant_email: string;
  anonymous_name?: string | null;
  pcm_base?: string | null;
  pcm_phase?: string | null;
  company_id: string;
  company_name: string;
  project_id: string | null;
  project_name: string;
  deadline_label: string;
  deadline_at?: string | null;
  tasks: InviteTask[];
  results?: BackendParticipantWorkspaceResult[];
  cards: ParticipantWorkspaceCard[];
  empty_state: ParticipantWorkspaceCard;
};

type BackendParticipantWorkspaceResult = {
  assignment_id: string;
  questionnaire_key: string;
  title: string;
  target_label: string;
  scores: Record<string, unknown>;
  primary_result?: string | null;
};

export async function getParticipantWorkspaceSummary(
  options: Pick<RequestInit, "headers"> = {},
): Promise<ParticipantWorkspaceSummary> {
  let unavailableReason: string | undefined;
  try {
    const response = await fetch(`${getApiBaseUrl()}/participants/me/workspace`, {
      cache: "no-store",
      credentials: "include",
      ...options,
    });
    if (response.ok) {
      return mapParticipantWorkspaceSummary((await response.json()) as BackendParticipantWorkspaceSummary);
    }
    unavailableReason = await readWorkspaceError(response);
  } catch {
    unavailableReason = "Nu am putut încărca spațiul tău de lucru acum.";
  }

  if (!isSeededDemoFallbackEnabled()) {
    return getUnavailableParticipantWorkspaceSummary(unavailableReason);
  }

  return getDemoParticipantWorkspaceSummary();
}

function mapParticipantWorkspaceSummary(
  data: BackendParticipantWorkspaceSummary,
): ParticipantWorkspaceSummary {
  return {
    participantProfileId: data.participant_profile_id,
    participantFullName: data.participant_full_name,
    anonymousName: data.anonymous_name,
    pcmBase: data.pcm_base,
    pcmPhase: data.pcm_phase,
    projectName: data.project_name,
    projectId: data.project_id,
    companyName: data.company_name,
    participantEmail: data.participant_email,
    deadlineLabel: data.deadline_label,
    tasks: data.tasks,
    results: (data.results ?? []).map(mapParticipantWorkspaceResult),
    cards: data.cards,
    emptyState: data.empty_state,
  };
}

function mapParticipantWorkspaceResult(
  result: BackendParticipantWorkspaceResult,
): ParticipantWorkspaceResult {
  return {
    assignmentId: result.assignment_id,
    questionnaireKey: result.questionnaire_key,
    title: result.title,
    targetLabel: result.target_label,
    scores: result.scores,
    primaryResult: result.primary_result,
  };
}

async function getDemoParticipantWorkspaceSummary(): Promise<ParticipantWorkspaceSummary> {
  const bundle = await resolveInviteBundle("demo-token");
  const tasks = bundle.state === "valid" ? bundle.tasks : [];

  return {
    participantFullName: bundle.state === "valid" ? bundle.participantFullName : "Mihai Matei",
    anonymousName: bundle.state === "valid" ? bundle.anonymousName : "SignalHarbor5271",
    pcmBase: "thinker",
    pcmPhase: "persister",
    projectName: bundle.state === "valid" ? bundle.projectName : "Leadership operațional Q3",
    projectId: null,
    companyName: "Atlas Mobility",
    participantEmail: bundle.state === "valid" ? bundle.participantEmail : "mihai.matei@atlas-mobility.ro",
    deadlineLabel: bundle.state === "valid" ? bundle.deadlineLabel : "deadline-ul proiectului",
    tasks,
    results: [
      {
        assignmentId: "demo-driver-result",
        questionnaireKey: "distress_drivers",
        title: "Driveri de stres TA",
        targetLabel: "Autoevaluare",
        primaryResult: "be_strong",
        scores: {
          be_strong: 76,
          be_perfect: 58,
          try_hard: 42,
          hurry_up: 66,
          please_people: 34,
        },
      },
      {
        assignmentId: "demo-lencioni-result",
        questionnaireKey: "lencioni",
        title: "Lencioni - evaluare echipă",
        targetLabel: "Echipa de direcție",
        primaryResult: "fear_of_conflict",
        scores: {
          absence_of_trust: { score: 7, interpretation: "Disfuncția poate fi o problemă." },
          fear_of_conflict: { score: 5, interpretation: "Disfuncția trebuie probabil abordată." },
          lack_of_commitment: { score: 8, interpretation: "Disfuncția probabil nu este o problemă." },
          avoidance_of_accountability: { score: 6, interpretation: "Disfuncția poate fi o problemă." },
          inattention_to_results: { score: 9, interpretation: "Disfuncția probabil nu este o problemă." },
        },
      },
      {
        assignmentId: "demo-icare-result",
        questionnaireKey: "boss_360",
        title: "iCARE 360 pentru manager",
        targetLabel: "Manager direct",
        primaryResult: "icare_06_aduce_claritate",
        scores: {
          icare_01_dezvolta_oamenii: { score: 83 },
          icare_02_conduce_prin_puterea_exemplului: { score: 75 },
          icare_03_creeaza_un_mediu_care_stimuleaza_implicarea: { score: 72 },
          icare_06_aduce_claritate: { score: 61 },
          icare_12_agilitate_antreprenoriala: { score: 79 },
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

async function readWorkspaceError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: { message?: string } };
    return body.error?.message || "Nu am putut încărca spațiul tău de lucru acum.";
  } catch {
    return "Nu am putut încărca spațiul tău de lucru acum.";
  }
}

function getUnavailableParticipantWorkspaceSummary(reason?: string): ParticipantWorkspaceSummary {
  return {
    participantFullName: "Participant",
    anonymousName: null,
    projectName: "Spațiul tău de lucru",
    projectId: null,
    companyName: "Codruț",
    participantEmail: "",
    deadlineLabel: "după ce profilul este sincronizat",
    tasks: [],
    results: [],
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
      title: "Spațiul de participant nu este încă disponibil",
      description:
        reason ||
        "Contul este activ, dar profilul de participant nu este conectat la o companie sau la un proiect.",
    },
  };
}
