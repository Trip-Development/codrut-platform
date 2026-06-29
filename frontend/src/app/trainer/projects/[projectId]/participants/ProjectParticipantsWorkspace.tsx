"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  importCompanyRoster,
  updateCompanyParticipant,
  type CompanyParticipant,
  type ParticipantInvitationStatus,
} from "@/api/companies";
import { displayReportsToName, normalizeReportsToName } from "@/api/roster-format";

type ProjectParticipantsWorkspaceProps = {
  companyId: string;
  projectId: string;
  participants: CompanyParticipant[];
  invitationStatuses: ParticipantInvitationStatus[];
};

type ParticipantEditForm = {
  fullName: string;
  email: string;
  reportsToName: string;
  position: string;
  location: string;
};

type ManualAddForm = Omit<ParticipantEditForm, "location">;

type ParsedManualParticipant = ManualAddForm & {
  key: string;
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

const emptyManualForm: ManualAddForm = {
  fullName: "",
  email: "",
  reportsToName: "",
  position: "",
};

export function buildProjectParticipantAccessRows(
  participants: CompanyParticipant[],
  invitationStatuses: ParticipantInvitationStatus[],
): AccessRow[] {
  const statusByParticipant = new Map(
    invitationStatuses.map((status) => [status.participant_id, status]),
  );
  const managerNameKeys = buildManagerNameKeys(participants);

  return participants.map((participant) => {
    const status = statusByParticipant.get(participant.id);
    const isPermanentParticipant = isPermanentAccountParticipant(participant, managerNameKeys);
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
      internalRoleLabel: isPermanentParticipant ? "Manager / leadership" : "Membru",
      accountTypeLabel: isPermanentParticipant ? "Cont permanent" : "Acces temporar",
      accountStateLabel: hasAccount ? "Cont creat" : isPermanentParticipant ? "Cont de creat" : "Fără cont permanent",
      deliveryLabel,
      hasAccount,
      hasSecureLink,
    };
  });
}

function buildManagerNameKeys(participants: CompanyParticipant[]): Set<string> {
  return new Set(
    participants
      .map((participant) => normalizeReportsToName(participant.reports_to_name))
      .filter((name): name is string => Boolean(name))
      .map((name) => name.toLocaleLowerCase("ro-RO")),
  );
}

function isPermanentAccountParticipant(participant: CompanyParticipant, managerNameKeys: Set<string>): boolean {
  const role = participant.role_group?.trim().toLowerCase();
  const participantName = participant.full_name.trim().toLocaleLowerCase("ro-RO");
  return role === "manager" || role === "leadership" || Boolean(participant.user_id) || managerNameKeys.has(participantName);
}

export function ProjectParticipantsWorkspace({
  companyId,
  projectId,
  participants: initialParticipants,
  invitationStatuses,
}: ProjectParticipantsWorkspaceProps) {
  const router = useRouter();
  const [participants, setParticipants] = useState(initialParticipants);
  const [activeTab, setActiveTab] = useState<TabKey>("roster");
  const [showAddPanel, setShowAddPanel] = useState(initialParticipants.length === 0);
  const [manualForm, setManualForm] = useState<ManualAddForm>(emptyManualForm);
  const [pasteText, setPasteText] = useState("");
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ParticipantEditForm | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const statusByParticipantId = useMemo(
    () => new Map(invitationStatuses.map((status) => [status.participant_id, status])),
    [invitationStatuses],
  );
  const managerNameKeys = useMemo(() => buildManagerNameKeys(participants), [participants]);
  const accessRows = useMemo(
    () => buildProjectParticipantAccessRows(participants, invitationStatuses),
    [participants, invitationStatuses],
  );
  const permanentCount = accessRows.filter((row) => row.accountTypeLabel === "Cont permanent").length;
  const temporaryCount = accessRows.length - permanentCount;
  const activeAccountCount = accessRows.filter((row) => row.hasAccount).length;
  const activeSecureLinkCount = accessRows.filter((row) => row.hasSecureLink).length;

  const startEdit = (participant: CompanyParticipant) => {
    setError(null);
    setEditingId(participant.id);
    setForm({
      fullName: participant.full_name,
      email: participant.email,
      reportsToName: participant.reports_to_name ?? "",
      position: participant.position ?? "",
      location: participant.location ?? "",
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setForm(null);
    setError(null);
  };

  const updateField = (field: keyof ParticipantEditForm, value: string) => {
    setForm((current) => (current ? { ...current, [field]: value } : current));
  };

  const saveEdit = async (participant: CompanyParticipant) => {
    if (!form) return;

    setSavingId(participant.id);
    setError(null);
    try {
      const updated = await updateCompanyParticipant(companyId, participant.id, {
        projectId,
        fullName: form.fullName.trim(),
        email: form.email.trim(),
        reportsToName: cleanOptional(form.reportsToName),
        position: cleanOptional(form.position),
        location: cleanOptional(form.location),
      });

      setParticipants((current) =>
        current.map((item) =>
          item.id === participant.id
            ? {
                ...item,
                ...updated,
                project_membership_id: item.project_membership_id,
                reports_to_name: updated.reports_to_name,
                position: updated.position,
                location: updated.location,
                role_group: updated.role_group,
              }
            : item,
        ),
      );
      setEditingId(null);
      setForm(null);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Participantul nu a putut fi salvat.");
    } finally {
      setSavingId(null);
    }
  };

  const addManualRows = async () => {
    const rows = buildManualImportRows(manualForm, pasteText);
    if (rows.length === 0) {
      setError("Adaugă cel puțin un participant cu nume și email.");
      return;
    }

    setAdding(true);
    setError(null);
    try {
      const result = await importCompanyRoster(
        companyId,
        rows.map((row) => ({
          Name: row.fullName,
          "Reports To": row.reportsToName,
          Position: row.position,
          Location: "",
          email: row.email,
          "Profil PCM": "",
        })),
        { projectId },
      );
      setParticipants(result.participants);
      setManualForm(emptyManualForm);
      setPasteText("");
      setShowAddPanel(false);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Participanții nu au putut fi salvați.");
    } finally {
      setAdding(false);
    }
  };

  return (
    <section className="surface-panel overflow-hidden">
      <div className="border-b border-[var(--border)] px-5 py-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-semibold text-burgundy/75">Roster proiect</p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">Participanți în proiect</h2>
            <p className="mt-2 text-sm leading-6 text-foreground/62">
              Tabelul este read-only implicit. Intră în editare doar pentru corecții operaționale.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowAddPanel((current) => !current)}
            className="tap-soft rounded-full border border-[var(--border)] bg-background px-4 py-2 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy"
          >
            {showAddPanel ? "Ascunde adăugarea" : "Adaugă manual"}
          </button>
        </div>
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

      {error ? (
        <p className="status-panel-danger rounded-none border-x-0 border-t-0 px-5 py-3">
          {error}
        </p>
      ) : null}

      {activeTab === "roster" ? (
        <>
          {showAddPanel ? (
            <ManualAddPanel
              form={manualForm}
              pasteText={pasteText}
              adding={adding}
              onUpdateForm={(field, value) => setManualForm((current) => ({ ...current, [field]: value }))}
              onPasteText={setPasteText}
              onAdd={() => void addManualRows()}
            />
          ) : null}
          <RosterTable
            participants={participants}
            projectId={projectId}
            statusByParticipantId={statusByParticipantId}
            managerNameKeys={managerNameKeys}
            editingId={editingId}
            form={form}
            savingId={savingId}
            onCancel={cancelEdit}
            onEdit={startEdit}
            onSave={(participant) => void saveEdit(participant)}
            onUpdateField={updateField}
          />
        </>
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

function RosterTable({
  participants,
  projectId,
  statusByParticipantId,
  managerNameKeys,
  editingId,
  form,
  savingId,
  onCancel,
  onEdit,
  onSave,
  onUpdateField,
}: {
  participants: CompanyParticipant[];
  projectId: string;
  statusByParticipantId: Map<string, ParticipantInvitationStatus>;
  managerNameKeys: Set<string>;
  editingId: string | null;
  form: ParticipantEditForm | null;
  savingId: string | null;
  onCancel: () => void;
  onEdit: (participant: CompanyParticipant) => void;
  onSave: (participant: CompanyParticipant) => void;
  onUpdateField: (field: keyof ParticipantEditForm, value: string) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table min-w-full text-left text-sm">
        <thead>
          <tr>
            <th>Nume</th>
            <th>Email</th>
            <th>Manager</th>
            <th>Poziție</th>
            <th>Tip acces</th>
            <th className="text-right">Acțiuni</th>
          </tr>
        </thead>
        <tbody>
          {participants.length === 0 ? (
            <tr>
              <td colSpan={6} className="px-5 py-6 text-center text-foreground/62">
                Niciun participant în acest proiect încă. Adaugă manual, lipește rânduri sau importă un fișier mai jos.
              </td>
            </tr>
          ) : (
            participants.map((member) => (
              <ParticipantRow
                key={member.id}
                participant={member}
                projectId={projectId}
                invitationStatus={statusByParticipantId.get(member.id) ?? null}
                managerNameKeys={managerNameKeys}
                form={editingId === member.id ? form : null}
                saving={savingId === member.id}
                onCancel={onCancel}
                onEdit={() => onEdit(member)}
                onSave={() => onSave(member)}
                onUpdateField={onUpdateField}
              />
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function ParticipantRow({
  participant,
  projectId,
  invitationStatus,
  managerNameKeys,
  form,
  saving,
  onCancel,
  onEdit,
  onSave,
  onUpdateField,
}: {
  participant: CompanyParticipant;
  projectId: string;
  invitationStatus: ParticipantInvitationStatus | null;
  managerNameKeys: Set<string>;
  form: ParticipantEditForm | null;
  saving: boolean;
  onCancel: () => void;
  onEdit: () => void;
  onSave: () => void;
  onUpdateField: (field: keyof ParticipantEditForm, value: string) => void;
}) {
  if (!form) {
    return (
      <tr>
        <td className="font-semibold text-foreground">
          <Link
            href={`/trainer/projects/${projectId}/participants/${participant.id}`}
            className="text-foreground underline-offset-4 hover:text-burgundy hover:underline"
          >
            {participant.full_name}
          </Link>
        </td>
        <td className="text-foreground/62">{participant.email}</td>
        <td className="text-foreground/62">{displayReportsToName(participant.reports_to_name)}</td>
        <td className="text-foreground/62">{participant.position ?? "-"}</td>
        <td>
          <AccountTypeBadge participant={participant} invitationStatus={invitationStatus} managerNameKeys={managerNameKeys} />
        </td>
        <td className="text-right">
          <button
            type="button"
            onClick={onEdit}
            className="tap-soft rounded-full border border-[var(--border)] bg-background px-3 py-2 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy"
          >
            Editează
          </button>
        </td>
      </tr>
    );
  }

  return (
    <tr className="bg-surface-muted">
      <td colSpan={6} className="px-5 py-4">
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          <EditField
            label="Nume"
            value={form.fullName}
            required
            onChange={(value) => onUpdateField("fullName", value)}
          />
          <EditField
            label="Email"
            value={form.email}
            required
            type="email"
            onChange={(value) => onUpdateField("email", value)}
          />
          <EditField
            label="Manager"
            value={form.reportsToName}
            onChange={(value) => onUpdateField("reportsToName", value)}
          />
          <EditField
            label="Poziție"
            value={form.position}
            onChange={(value) => onUpdateField("position", value)}
          />
          <EditField
            label="Locație"
            value={form.location}
            onChange={(value) => onUpdateField("location", value)}
          />
          <div className="rounded-xl border border-[var(--border)] bg-surface-muted px-3 py-3">
            <span className="text-xs font-bold text-foreground/58">Tip acces</span>
            <div className="mt-2">
              <AccountTypeBadge participant={participant} invitationStatus={invitationStatus} managerNameKeys={managerNameKeys} />
            </div>
            <p className="mt-2 text-xs font-medium leading-5 text-foreground/52">
              Tipul de acces se schimbă prin invitații și apartenența la echipa de leadership, nu prin editarea câmpurilor operaționale.
            </p>
          </div>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={saving}
            className="tap-soft rounded-full border border-[var(--border)] bg-background px-4 py-2 text-xs font-bold text-foreground hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-45"
          >
            Anulează
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={saving || !form.fullName.trim() || !form.email.trim()}
            className="tap-soft rounded-full bg-burgundy px-4 py-2 text-xs font-bold text-white hover:bg-burgundy-700 disabled:cursor-not-allowed disabled:opacity-45"
          >
            {saving ? "Se salvează..." : "Salvează"}
          </button>
        </div>
      </td>
    </tr>
  );
}

function ManualAddPanel({
  form,
  pasteText,
  adding,
  onUpdateForm,
  onPasteText,
  onAdd,
}: {
  form: ManualAddForm;
  pasteText: string;
  adding: boolean;
  onUpdateForm: (field: keyof ManualAddForm, value: string) => void;
  onPasteText: (value: string) => void;
  onAdd: () => void;
}) {
  const parsedCount = buildManualImportRows(form, pasteText).length;

  return (
    <div className="border-b border-[var(--border)] bg-surface-muted px-5 py-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <EditField label="Nume" value={form.fullName} onChange={(value) => onUpdateForm("fullName", value)} />
        <EditField label="Email" value={form.email} type="email" onChange={(value) => onUpdateForm("email", value)} />
        <EditField label="Manager" value={form.reportsToName} onChange={(value) => onUpdateForm("reportsToName", value)} />
        <EditField label="Poziție" value={form.position} onChange={(value) => onUpdateForm("position", value)} />
      </div>
      <label className="mt-4 block">
        <span className="text-xs font-bold text-foreground/58">Lipește rânduri: nume, email, poziție, manager</span>
        <textarea
          value={pasteText}
          onChange={(event) => onPasteText(event.target.value)}
          rows={4}
          className="control-input mt-1.5 w-full"
          placeholder={"Ana Popescu, ana@companie.ro, Manager, -\nMihai Ionescu\tmihai@companie.ro\tConsultant\tAna Popescu"}
        />
      </label>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs font-semibold text-foreground/52">
          {parsedCount} rânduri pregătite pentru salvare prin importul de roster.
        </p>
        <button
          type="button"
          onClick={onAdd}
          disabled={adding || parsedCount === 0}
          className="tap-soft rounded-full bg-burgundy px-4 py-2 text-xs font-bold text-white hover:bg-burgundy-700 disabled:cursor-not-allowed disabled:opacity-45"
        >
          {adding ? "Se salvează..." : "Salvează participanții"}
        </button>
      </div>
    </div>
  );
}

function AccountTypeBadge({
  participant,
  invitationStatus,
  managerNameKeys,
}: {
  participant: CompanyParticipant;
  invitationStatus: ParticipantInvitationStatus | null;
  managerNameKeys: Set<string>;
}) {
  if (isPermanentAccountParticipant(participant, managerNameKeys)) {
    return (
      <span className="status-pill border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/55 dark:bg-emerald-950/30 dark:text-emerald-200">
        cont permanent
      </span>
    );
  }

  if (invitationStatus?.has_active_secure_link || invitationStatus?.latest_delivery_mode === "secure_links") {
    return (
      <span className="status-pill border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-900/55 dark:bg-sky-950/30 dark:text-sky-200">
        invitație temporară activă
      </span>
    );
  }

  return (
    <span className="status-pill">
      membru temporar
    </span>
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
      <div className="grid gap-3 border-b border-[var(--border)] bg-surface-muted px-5 py-4 text-sm sm:grid-cols-4">
        <AccessMetric label="Cont permanent" value={permanentCount} />
        <AccessMetric label="Acces temporar" value={temporaryCount} />
        <AccessMetric label="Conturi create" value={activeAccountCount} />
        <AccessMetric label="Linkuri active" value={activeSecureLinkCount} />
      </div>
      <div className="overflow-x-auto">
        <table className="data-table min-w-full text-left text-sm">
          <thead>
            <tr>
              <th>Participant</th>
              <th>Rol intern</th>
              <th>Tip acces</th>
              <th>Stare cont</th>
              <th>Livrare</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-5 py-6 text-center text-foreground/62">
                  Niciun participant în acest proiect încă.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.participant.id}>
                  <td>
                    <p className="font-semibold text-foreground">{row.participant.full_name}</p>
                    <p className="mt-1 text-xs text-foreground/52">{row.participant.email}</p>
                  </td>
                  <td className="text-foreground/70">{row.internalRoleLabel}</td>
                  <td>
                    <span className="status-pill">{row.accountTypeLabel}</span>
                  </td>
                  <td className="text-foreground/70">{row.accountStateLabel}</td>
                  <td className="text-foreground/70">{row.deliveryLabel}</td>
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

function EditField({
  label,
  value,
  onChange,
  required = false,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  type?: "email" | "text";
}) {
  return (
    <label className="block">
      <span className="text-xs font-bold text-foreground/58">{label}</span>
      <input
        type={type}
        required={required}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="control-input mt-1.5 w-full"
      />
    </label>
  );
}

function cleanOptional(value: string): string | null {
  const cleaned = value.trim();
  return cleaned || null;
}

function buildManualImportRows(form: ManualAddForm, pasteText: string): ParsedManualParticipant[] {
  const rows: ParsedManualParticipant[] = [];

  if (form.fullName.trim() || form.email.trim()) {
    rows.push({ ...cleanManualRow(form), key: "manual-form" });
  }

  parsePastedRows(pasteText).forEach((row, index) => {
    rows.push({ ...row, key: `paste-${index}` });
  });

  return rows.filter((row) => row.fullName && row.email);
}

function parsePastedRows(value: string): ManualAddForm[] {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const cells = line.includes("\t") ? line.split("\t") : line.split(",");
      const [fullName = "", email = "", position = "", reportsToName = ""] = cells.map((cell) => cell.trim());
      return cleanManualRow({ fullName, email, position, reportsToName });
    });
}

function cleanManualRow(row: ManualAddForm): ManualAddForm {
  return {
    fullName: row.fullName.trim(),
    email: row.email.trim(),
    reportsToName: normalizeReportsToName(row.reportsToName),
    position: row.position.trim(),
  };
}
