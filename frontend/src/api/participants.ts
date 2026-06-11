import { resolveInviteBundle, type InviteTask } from "./invites";
import { getApiBaseUrl, isDemoFallbackEnabled } from "./runtime";

export type ParticipantWorkspaceCard = {
  title: string;
  description: string;
  meta?: string;
};

export type ParticipantWorkspaceSummary = {
  participantProfileId?: string;
  participantFullName: string;
  projectName: string;
  projectId?: string | null;
  companyName: string;
  participantEmail: string;
  deadlineLabel: string;
  pcmBase?: string | null;
  pcmPhase?: string | null;
  tasks: InviteTask[];
  cards: ParticipantWorkspaceCard[];
  emptyState: {
    title: string;
    description: string;
  };
};

type BackendParticipantWorkspaceSummary = {
  participant_profile_id: string;
  participant_full_name: string;
  participant_email: string;
  company_id: string;
  company_name: string;
  project_id: string | null;
  project_name: string;
  deadline_label: string;
  deadline_at?: string | null;
  pcm_base?: string | null;
  pcm_phase?: string | null;
  tasks: InviteTask[];
  cards: ParticipantWorkspaceCard[];
  empty_state: ParticipantWorkspaceCard;
};

export async function getParticipantWorkspaceSummary(
  options: Pick<RequestInit, "headers"> = {},
): Promise<ParticipantWorkspaceSummary> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/participants/me/workspace`, {
      cache: "no-store",
      credentials: "include",
      ...options,
    });
    if (response.ok) {
      return mapParticipantWorkspaceSummary((await response.json()) as BackendParticipantWorkspaceSummary);
    }
  } catch {
    // Fall through to explicit demo fallback below when enabled.
  }

  if (!isDemoFallbackEnabled()) {
    throw new Error("Participant workspace unavailable.");
  }

  return getDemoParticipantWorkspaceSummary();
}

function mapParticipantWorkspaceSummary(
  data: BackendParticipantWorkspaceSummary,
): ParticipantWorkspaceSummary {
  return {
    participantProfileId: data.participant_profile_id,
    participantFullName: data.participant_full_name,
    projectName: data.project_name,
    projectId: data.project_id,
    companyName: data.company_name,
    participantEmail: data.participant_email,
    deadlineLabel: data.deadline_label,
    pcmBase: data.pcm_base,
    pcmPhase: data.pcm_phase,
    tasks: data.tasks,
    cards: data.cards,
    emptyState: data.empty_state,
  };
}

async function getDemoParticipantWorkspaceSummary(): Promise<ParticipantWorkspaceSummary> {
  const bundle = await resolveInviteBundle("demo-token");
  const tasks = bundle.state === "valid" ? bundle.tasks : [];

  return {
    participantFullName: bundle.state === "valid" ? bundle.participantFullName : "Participant demo",
    projectName: bundle.state === "valid" ? bundle.projectName : "Proiect demo",
    projectId: null,
    companyName: "Companie demo",
    participantEmail: bundle.state === "valid" ? bundle.participantEmail : "participant@companie.ro",
    deadlineLabel: bundle.state === "valid" ? bundle.deadlineLabel : "deadline-ul proiectului",
    tasks,
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
