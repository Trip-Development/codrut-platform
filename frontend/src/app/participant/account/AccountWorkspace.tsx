"use client";

import type { InviteTask } from "@/api/invites";
import { formatPcmLabel, getPcmProfile } from "@/api/pcm";
import { AccountSettingsPanel } from "@/components/settings/account-settings-panel";

type WorkspaceSummary = {
  projectName: string;
  participantFullName?: string;
  companyName?: string;
  participantEmail?: string | null;
  pcmBase?: string | null;
  pcmPhase?: string | null;
  tasks?: InviteTask[];
};

type AccountWorkspaceProps = {
  session: import("@/api/auth").SessionState;
  summary: WorkspaceSummary;
};

export function AccountWorkspace({ session, summary }: AccountWorkspaceProps) {
  const name = summary.participantFullName || session.user.name || "Participant";
  const email = summary.participantEmail || session.user.email || "Email indisponibil";
  const company = summary.companyName || "Companie neasociată";
  const pcmRows = [
    summary.pcmBase ? formatPcmRow("Bază PCM", summary.pcmBase) : null,
    summary.pcmPhase ? formatPcmRow("Fază PCM", summary.pcmPhase) : null,
  ].filter(Boolean) as { label: string; value: string; tone?: "accent"; color?: string }[];

  return (
    <AccountSettingsPanel
      eyebrow="Cont participant"
      title={name}
      description="Detaliile de aici sunt legate de profilul tău corporate și de proiectul activ. Rezultatele agregate și interpretările rămân în tabul Rezultate."
      passwordEnabled={session.state === "authenticated"}
      accountRows={[
        { label: "Email", value: email, tone: "accent" },
        { label: "Rol", value: "Participant" },
        {
          label: "Sesiune",
          value: session.state === "authenticated" ? "Autentificat" : "Acces temporar",
        },
        { label: "Confidențialitate", value: "Răspunsurile brute nu sunt afișate în cont" },
      ]}
      contextRows={[
        { label: "Companie", value: company },
        { label: "Proiect curent", value: summary.projectName },
        ...pcmRows,
        { label: "Rezultate", value: "Scoruri și interpretări sumarizate în tabul Rezultate" },
      ]}
      notes={[
        "Feedbackul 360 este folosit pentru rapoarte agregate și nu expune răspunsuri brute.",
        "Trainerul urmărește progresul și completările pentru gestionarea proiectului.",
        "Resetarea parolei rămâne disponibilă din ecranul de autentificare dacă nu mai știi parola curentă.",
      ]}
    />
  );
}

function formatPcmRow(label: string, value: string) {
  const profile = getPcmProfile(value);
  return {
    label,
    value: formatPcmLabel(value),
    tone: "accent" as const,
    color: profile?.color,
  };
}
