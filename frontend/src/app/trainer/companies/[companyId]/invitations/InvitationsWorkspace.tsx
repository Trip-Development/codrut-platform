"use client";

import { useMemo, useState } from "react";

import {
  resendParticipantInvitation,
  sendParticipantInvitations,
  type CompanyAssignment,
  type CompanyParticipant,
  type ParticipantInvitationStatus,
  type ParticipantInvitationMode,
  type RosterInviteResult,
} from "@/api/companies";

type InvitationsWorkspaceProps = {
  companyId: string;
  companyName: string;
  participants: CompanyParticipant[];
  assignments: CompanyAssignment[];
  invitationStatuses: ParticipantInvitationStatus[];
};

type ParticipantInviteRow = {
  participant: CompanyParticipant;
  assignments: CompanyAssignment[];
  totalTasks: number;
  completedTasks: number;
  completionLabel: string;
  signedUp: boolean;
  deliveryLabel: string;
  deliveryTone: "default" | "success" | "warning" | "danger";
  secureLinkUrl: string | null;
  nextAction: string;
};

const completedStatuses = new Set(["submitted", "validated", "scored"]);
const activeInviteStatuses = new Set(["invited", "started", "submitted", "validated", "scored"]);

export function buildInvitationRows(
  participants: CompanyParticipant[],
  assignments: CompanyAssignment[],
  invitationStatuses: ParticipantInvitationStatus[],
  resultsByParticipant: Map<string, RosterInviteResult>,
): ParticipantInviteRow[] {
  const assignmentsByParticipant = new Map<string, CompanyAssignment[]>();
  const statusByParticipant = new Map(
    invitationStatuses.map((status) => [status.participant_id, status]),
  );

  for (const assignment of assignments) {
    assignmentsByParticipant.set(assignment.respondent_profile_id, [
      ...(assignmentsByParticipant.get(assignment.respondent_profile_id) ?? []),
      assignment,
    ]);
  }

  return participants.map((participant) => {
    const participantAssignments = assignmentsByParticipant.get(participant.id) ?? [];
    const persistedStatus = statusByParticipant.get(participant.id);
    const result = resultsByParticipant.get(participant.id);
    const completedTasks = participantAssignments.filter((assignment) => completedStatuses.has(assignment.status)).length;
    const totalTasks = participantAssignments.length;
    const signedUp = Boolean(participant.user_id);

    let deliveryLabel = "Fără asignări";
    let deliveryTone: ParticipantInviteRow["deliveryTone"] = "default";
    const secureLinkUrl = result?.invite_url ?? persistedStatus?.active_secure_link_url ?? null;

    if (result?.error) {
      deliveryLabel = "Eroare trimitere";
      deliveryTone = "danger";
    } else if (result?.email_sent) {
      deliveryLabel = "Email trimis";
      deliveryTone = "success";
    } else if (result?.delivery_mode === "secure_links") {
      deliveryLabel = "Link securizat generat";
      deliveryTone = "success";
    } else if (persistedStatus?.latest_email_status === "failed" || persistedStatus?.latest_email_status === "bounced") {
      deliveryLabel = "Eroare trimitere";
      deliveryTone = "danger";
    } else if (persistedStatus?.latest_email_status === "queued") {
      deliveryLabel = "Email în coadă";
      deliveryTone = "warning";
    } else if (persistedStatus?.latest_email_status) {
      deliveryLabel = "Email trimis";
      deliveryTone = "success";
    } else if (persistedStatus?.has_active_secure_link) {
      deliveryLabel = "Link securizat activ";
      deliveryTone = "success";
    } else if (participantAssignments.some((assignment) => activeInviteStatuses.has(assignment.status))) {
      deliveryLabel = "Invitație activă";
      deliveryTone = "success";
    } else if (totalTasks > 0) {
      deliveryLabel = "Pregătit, netrimis";
      deliveryTone = "warning";
    }

    const completionLabel = totalTasks > 0 ? `${completedTasks}/${totalTasks}` : "0/0";
    const nextAction =
      totalTasks === 0
        ? "Configurează asignări"
        : completedTasks === totalTasks
          ? "Verifică raportul"
          : deliveryTone === "success"
            ? "Urmărește progresul"
            : "Trimite invitația";

    return {
      participant,
      assignments: participantAssignments,
      totalTasks,
      completedTasks,
      completionLabel,
      signedUp,
      deliveryLabel,
      deliveryTone,
      secureLinkUrl,
      nextAction,
    };
  });
}

export function InvitationsWorkspace({
  companyId,
  companyName,
  participants,
  assignments,
  invitationStatuses,
}: InvitationsWorkspaceProps) {
  const [resultsByParticipant, setResultsByParticipant] = useState(new Map<string, RosterInviteResult>());
  const [message, setMessage] = useState<string | null>(null);
  const [sendingMode, setSendingMode] = useState<ParticipantInvitationMode | "resend" | null>(null);
  const [copiedParticipantId, setCopiedParticipantId] = useState<string | null>(null);

  const rows = useMemo(
    () => buildInvitationRows(participants, assignments, invitationStatuses, resultsByParticipant),
    [assignments, invitationStatuses, participants, resultsByParticipant],
  );

  const signedUpCount = rows.filter((row) => row.signedUp).length;
  const activeInvites = rows.filter((row) => row.deliveryTone === "success").length;
  const completedCount = rows.filter((row) => row.totalTasks > 0 && row.completedTasks === row.totalTasks).length;
  const blockedCount = rows.filter((row) => row.deliveryTone === "danger" || row.totalTasks === 0).length;

  async function handleSend(mode: ParticipantInvitationMode) {
    setSendingMode(mode);
    setMessage(null);
    setCopiedParticipantId(null);
    try {
      const result = await sendParticipantInvitations(companyId, { mode });
      setResultsByParticipant((current) => {
        const next = new Map(current);
        for (const item of result.results) {
          next.set(item.participant_id, item);
        }
        return next;
      });
      setMessage(
        mode === "email"
          ? `${result.emails_sent}/${result.total} emailuri trimise.`
          : `${result.links_generated}/${result.total} linkuri securizate generate.`,
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Invitațiile nu au putut fi trimise.");
    } finally {
      setSendingMode(null);
    }
  }

  async function handleResend(participantId: string) {
    setSendingMode("resend");
    setMessage(null);
    setCopiedParticipantId(null);
    try {
      const result = await resendParticipantInvitation(companyId, participantId);
      if (result) {
        setResultsByParticipant((current) => {
          const next = new Map(current);
          next.set(result.participant_id, result);
          return next;
        });
        setMessage(result.email_sent ? `Email retrimis către ${result.email}.` : `Link pregătit pentru ${result.email}.`);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Invitația nu a putut fi retrimisă.");
    } finally {
      setSendingMode(null);
    }
  }

  async function handleCopyLink(row: ParticipantInviteRow) {
    if (!row.secureLinkUrl || typeof navigator === "undefined") return;
    try {
      await navigator.clipboard.writeText(row.secureLinkUrl);
      setCopiedParticipantId(row.participant.id);
      setMessage(`Link securizat copiat pentru ${row.participant.full_name}.`);
    } catch {
      setMessage("Linkul nu a putut fi copiat automat. Copiază-l manual din browser.");
    }
  }

  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
        <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_26rem]">
          <div className="p-5 md:p-6">
            <p className="text-sm font-semibold text-burgundy/75">Invitații companie</p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">Status invitații pentru {companyName}</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/62">
              Vezi cine are invitația activă, cine și-a creat contul, câte task-uri are și ce trebuie urmărit.
            </p>
            <div className="mt-4 grid gap-2 sm:grid-cols-4">
              <InviteSummary label="Invitații active" value={activeInvites} />
              <InviteSummary label="Conturi create" value={signedUpCount} />
              <InviteSummary label="Completate" value={completedCount} />
              <InviteSummary label="Blocaje" value={blockedCount} />
            </div>
          </div>
          <div className="space-y-3 border-t border-[var(--border)] bg-surface-muted/45 p-5 md:p-6 lg:border-l lg:border-t-0">
            <button
              type="button"
              onClick={() => void handleSend("email")}
              disabled={sendingMode !== null || participants.length === 0}
              className="tap-soft w-full rounded-xl bg-burgundy px-4 py-3 text-sm font-bold text-white shadow-sm shadow-burgundy/10 hover:bg-burgundy-700 disabled:cursor-not-allowed disabled:opacity-45"
            >
              {sendingMode === "email" ? "Se trimit emailurile..." : "Trimite emailuri"}
            </button>
            <button
              type="button"
              onClick={() => void handleSend("secure_links")}
              disabled={sendingMode !== null || participants.length === 0}
              className="tap-soft w-full rounded-xl border border-[var(--border)] bg-background px-4 py-3 text-sm font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy disabled:cursor-not-allowed disabled:opacity-45"
            >
              {sendingMode === "secure_links" ? "Se generează linkurile..." : "Generează linkuri securizate"}
            </button>
            <p className="text-xs leading-5 text-foreground/52">
              Rosterul rămâne salvat separat. Trimiterea emailurilor sau generarea linkurilor se face explicit de aici.
            </p>
          </div>
        </div>
        {message ? (
          <p aria-live="polite" className="border-t border-[var(--border)] bg-background/70 px-5 py-3 text-sm font-semibold text-foreground/62">
            {message}
          </p>
        ) : null}
      </section>

      <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
        <div className="border-b border-[var(--border)] px-5 py-4">
          <p className="text-xs font-semibold text-burgundy/75">Urmărire</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">Persoane invitate</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-surface-muted text-xs font-semibold uppercase tracking-[0.1em] text-foreground/50">
              <tr>
                <th className="px-5 py-3">Persoană</th>
                <th className="px-5 py-3">Livrare</th>
                <th className="px-5 py-3">Cont</th>
                <th className="px-5 py-3">Task-uri</th>
                <th className="px-5 py-3">Următorul pas</th>
                <th className="px-5 py-3 text-right">Acțiune</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-6 text-center text-foreground/62">
                    Nu există persoane în roster.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.participant.id} className="align-top transition-colors hover:bg-surface-muted/40">
                    <td className="px-5 py-4">
                      <p className="font-semibold text-foreground">{row.participant.full_name}</p>
                      <p className="mt-1 text-xs text-foreground/50">{row.participant.email}</p>
                    </td>
                    <td className="px-5 py-4">
                      <StatusPill tone={row.deliveryTone}>{row.deliveryLabel}</StatusPill>
                    </td>
                    <td className="px-5 py-4">
                      <StatusPill tone={row.signedUp ? "success" : "warning"}>
                        {row.signedUp ? "Cont activ" : "Neînregistrat"}
                      </StatusPill>
                    </td>
                    <td className="px-5 py-4 text-foreground/62">
                      <p className="font-semibold text-foreground">{row.completionLabel}</p>
                      <p className="mt-1 text-xs text-foreground/50">
                        {row.assignments.map((assignment) => assignment.questionnaire_key).join(", ") || "Fără asignări"}
                      </p>
                    </td>
                    <td className="px-5 py-4 text-foreground/62">{row.nextAction}</td>
                    <td className="px-5 py-4 text-right">
                      {row.secureLinkUrl ? (
                        <button
                          type="button"
                          onClick={() => void handleCopyLink(row)}
                          disabled={sendingMode !== null}
                          className="tap-soft rounded-lg border border-[var(--border)] bg-background px-3 py-2 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy disabled:cursor-not-allowed disabled:opacity-45"
                        >
                          {copiedParticipantId === row.participant.id ? "Copiat" : "Copiază link"}
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => void handleResend(row.participant.id)}
                          disabled={sendingMode !== null || row.totalTasks === 0}
                          className="tap-soft rounded-lg border border-[var(--border)] bg-background px-3 py-2 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy disabled:cursor-not-allowed disabled:opacity-45"
                        >
                          Retrimite
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function InviteSummary({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-background/80 px-3 py-2.5">
      <p className="text-xs font-semibold text-foreground/48">{label}</p>
      <p className="mt-1 text-lg font-semibold text-foreground">{value}</p>
    </div>
  );
}

function StatusPill({
  tone,
  children,
}: {
  tone: ParticipantInviteRow["deliveryTone"];
  children: React.ReactNode;
}) {
  const className =
    tone === "success"
      ? "bg-success/35 text-success-ink"
      : tone === "warning"
        ? "bg-warning/30 text-warning-ink"
        : tone === "danger"
          ? "bg-burgundy-50 text-burgundy dark:bg-burgundy/10"
          : "bg-surface-muted text-foreground/58";

  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${className}`}>{children}</span>;
}
