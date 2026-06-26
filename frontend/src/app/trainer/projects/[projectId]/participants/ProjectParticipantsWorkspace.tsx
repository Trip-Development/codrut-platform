"use client";

import { useMemo, useState } from "react";

import type { CompanyParticipant, ParticipantInvitationStatus } from "@/api/companies";
import { displayReportsToName } from "@/api/roster-format";

type ProjectParticipantsWorkspaceProps = {
  participants: CompanyParticipant[];
  invitationStatuses: ParticipantInvitationStatus[];
};

type AccessRow = {
  participant: CompanyParticipant;
  internalRoleLabel: string;
  accountTypeLabel: string;
  accountStateLabel: string;
  deliveryLabel: string;
  hasAccount: boolean;
  hasSecureLink: boolean;
};

type TabKey = "roster" | "access";

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: "roster", label: "Roster" },
  { key: "access", label: "Acces intern" },
];

export function buildProjectParticipantAccessRows(
  participants: CompanyParticipant[],
  invitationStatuses: ParticipantInvitationStatus[],
): AccessRow[] {
  const statusByParticipant = new Map(
    invitationStatuses.map((status) => [status.participant_id, status]),
  );

  return participants.map((participant) => {
    const status = statusByParticipant.get(participant.id);
    const isLeadership = participant.role_group === "leadership";
    const hasAccount = Boolean(participant.user_id);
    const hasSecureLink = Boolean(status?.has_active_secure_link || status?.active_secure_link_url);
    const latestDelivery = status?.latest_delivery_mode;

    let deliveryLabel = "Nepregătit";
    if (latestDelivery === "email") {
      deliveryLabel = status?.latest_email_status === "failed" || status?.latest_email_status === "bounced"
        ? "Email cu eroare"
        : "Email trimis";
    } else if (latestDelivery === "secure_links" || hasSecureLink) {
      deliveryLabel = "Link securizat activ";
    }

    return {
      participant,
      internalRoleLabel: isLeadership ? "Manager / leadership" : "Membru",
      accountTypeLabel: isLeadership ? "Cont permanent" : "Acces temporar",
      accountStateLabel: hasAccount ? "Cont creat" : isLeadership ? "Cont de creat" : "Fără cont permanent",
      deliveryLabel,
      hasAccount,
      hasSecureLink,
    };
  });
}

export function ProjectParticipantsWorkspace({
  participants,
  invitationStatuses,
}: ProjectParticipantsWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<TabKey>("roster");
  const accessRows = useMemo(
    () => buildProjectParticipantAccessRows(participants, invitationStatuses),
    [participants, invitationStatuses],
  );
  const permanentCount = accessRows.filter((row) => row.accountTypeLabel === "Cont permanent").length;
  const temporaryCount = accessRows.length - permanentCount;
  const activeAccountCount = accessRows.filter((row) => row.hasAccount).length;
  const activeSecureLinkCount = accessRows.filter((row) => row.hasSecureLink).length;

  return (
    <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
      <div className="border-b border-[var(--border)] px-5 py-4">
        <p className="text-xs font-semibold text-burgundy/75">Roster proiect</p>
        <h2 className="mt-1 text-xl font-semibold text-foreground">Participanți în proiect</h2>
        <p className="mt-2 text-sm leading-6 text-foreground/62">
          Datele de manager, rol, locație și acces sunt specifice acestui proiect.
        </p>
        <div className="mt-4 flex flex-wrap gap-2" role="tablist" aria-label="Vizualizări participanți">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`rounded-full border px-4 py-2 text-sm font-semibold transition-colors ${
                activeTab === tab.key
                  ? "border-burgundy bg-burgundy text-white"
                  : "border-[var(--border)] bg-surface-muted text-foreground/70 hover:text-foreground"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {activeTab === "roster" ? (
        <RosterTable participants={participants} />
      ) : (
        <AccessTable
          rows={accessRows}
          permanentCount={permanentCount}
          temporaryCount={temporaryCount}
          activeAccountCount={activeAccountCount}
          activeSecureLinkCount={activeSecureLinkCount}
        />
      )}
    </section>
  );
}

function RosterTable({ participants }: { participants: CompanyParticipant[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-surface-muted text-xs font-semibold text-foreground/50">
          <tr>
            <th className="px-5 py-3">Nume</th>
            <th className="px-5 py-3">Manager</th>
            <th className="px-5 py-3">Poziție</th>
            <th className="px-5 py-3">Locație</th>
            <th className="px-5 py-3">Email</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border)]">
          {participants.length === 0 ? (
            <tr>
              <td colSpan={5} className="px-5 py-6 text-center text-foreground/62">
                Niciun participant în acest proiect încă.
              </td>
            </tr>
          ) : (
            participants.map((member) => (
              <tr key={member.id} className="align-top transition-colors hover:bg-surface-muted/40">
                <td className="px-5 py-4 font-semibold text-foreground">{member.full_name}</td>
                <td className="px-5 py-4 text-foreground/62">{displayReportsToName(member.reports_to_name)}</td>
                <td className="px-5 py-4 text-foreground/62">{member.position ?? "-"}</td>
                <td className="px-5 py-4 text-foreground/62">{member.location ?? "-"}</td>
                <td className="px-5 py-4 text-foreground/62">{member.email}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function AccessTable({
  rows,
  permanentCount,
  temporaryCount,
  activeAccountCount,
  activeSecureLinkCount,
}: {
  rows: AccessRow[];
  permanentCount: number;
  temporaryCount: number;
  activeAccountCount: number;
  activeSecureLinkCount: number;
}) {
  return (
    <div>
      <div className="grid gap-3 border-b border-[var(--border)] bg-surface-muted/40 px-5 py-4 text-sm sm:grid-cols-4">
        <AccessMetric label="Cont permanent" value={permanentCount} />
        <AccessMetric label="Acces temporar" value={temporaryCount} />
        <AccessMetric label="Conturi create" value={activeAccountCount} />
        <AccessMetric label="Linkuri active" value={activeSecureLinkCount} />
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-surface-muted text-xs font-semibold text-foreground/50">
            <tr>
              <th className="px-5 py-3">Participant</th>
              <th className="px-5 py-3">Rol intern</th>
              <th className="px-5 py-3">Tip acces</th>
              <th className="px-5 py-3">Stare cont</th>
              <th className="px-5 py-3">Livrare</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-5 py-6 text-center text-foreground/62">
                  Niciun participant în acest proiect încă.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.participant.id} className="align-top transition-colors hover:bg-surface-muted/40">
                  <td className="px-5 py-4">
                    <p className="font-semibold text-foreground">{row.participant.full_name}</p>
                    <p className="mt-1 text-xs text-foreground/52">{row.participant.email}</p>
                  </td>
                  <td className="px-5 py-4 text-foreground/70">{row.internalRoleLabel}</td>
                  <td className="px-5 py-4">
                    <span className="inline-flex rounded-full bg-surface-muted px-3 py-1 text-xs font-semibold text-foreground/75">
                      {row.accountTypeLabel}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-foreground/70">{row.accountStateLabel}</td>
                  <td className="px-5 py-4 text-foreground/70">{row.deliveryLabel}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AccessMetric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-xs font-semibold text-foreground/50">{label}</p>
      <p className="mt-1 text-lg font-semibold text-foreground">{value}</p>
    </div>
  );
}
