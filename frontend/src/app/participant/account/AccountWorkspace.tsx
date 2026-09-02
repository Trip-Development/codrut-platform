import type { SessionState } from "@/api/auth";
import type { InviteTask } from "@/api/invites";
import { formatPcmLabel, getPcmProfile } from "@/api/pcm";
import {
  AccountSettingsPanel,
  type AccountSettingsDetailRow,
} from "@/components/settings/account-settings-panel";

type WorkspaceSummary = {
  projectName: string;
  participantFullName?: string;
  companyName?: string;
  participantEmail?: string | null;
  pcmBase?: string | null;
  pcmPhase?: string | null;
  showParticipantResults?: boolean;
  tasks?: InviteTask[];
};

type AccountWorkspaceProps = {
  session: SessionState;
  summary: WorkspaceSummary;
};

export function AccountWorkspace({ session, summary }: AccountWorkspaceProps) {
  const email = summary.participantEmail || session.user.email || "Email indisponibil";
  const company = summary.companyName || "Companie neasociată";
  const accountRows: AccountSettingsDetailRow[] = [
    { label: "Email", value: email, tone: "accent" },
    { label: "Rol", value: "Participant" },
  ];
  const showPcm = summary.showParticipantResults !== false && Boolean(summary.pcmBase || summary.pcmPhase);
  const contextRows: AccountSettingsDetailRow[] = [
    { label: "Companie", value: company },
    { label: "Proiect", value: summary.projectName },
    ...(showPcm ? pcmRow("Bază PCM", summary.pcmBase) : []),
    ...(showPcm ? pcmRow("Fază PCM", summary.pcmPhase) : []),
  ];

  return (
    <AccountSettingsPanel
      accountRows={accountRows}
      contextRows={contextRows}
      passwordEnabled={session.state === "authenticated"}
      passwordFieldIdPrefix="participant"
      reauthHref="/login"
    />
  );
}

function pcmRow(label: string, value?: string | null): AccountSettingsDetailRow[] {
  if (!value) return [];
  const profile = getPcmProfile(value);
  return [
    {
      label,
      value: formatPcmLabel(value),
      tone: "accent",
      color: profile?.color,
    },
  ];
}
