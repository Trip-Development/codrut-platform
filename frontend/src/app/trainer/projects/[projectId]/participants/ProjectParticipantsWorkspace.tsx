"use client";

import { useDeferredValue, useEffect, useId, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2Icon } from "lucide-react";

import {
  importCompanyRoster,
  updateCompanyParticipant,
  type CompanyParticipant,
  type CompanyProject,
  type ParticipantInvitationStatus,
} from "@/api/companies";
import {
  isExternalMatrixManagerLabel,
  managerReferenceKey,
  normalizeReportsToName,
} from "@/api/roster-format";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { RosterImporter } from "@/components/roster-importer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ModalLayer } from "@/components/ui/modal-layer";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/utils/cn";
import { useUrlState } from "@/hooks/use-url-state";
import {
  normalizeWorkspaceSearch,
  WorkspaceSearchInput,
} from "../../project-workspace-controls";

export type ProjectParticipantsWorkspaceProps = {
  companyId: string;
  projectId: string;
  companyName: string;
  project: Pick<CompanyProject, "id" | "name" | "status" | "company_id">;
  participants: CompanyParticipant[];
  invitationStatuses: ParticipantInvitationStatus[];
};

type ParticipantEditForm = {
  fullName: string;
  email: string;
  reportsToName: string;
  position: string;
  location: string;
  roleGroup: "leadership" | "member";
};

type ManualAddForm = Omit<ParticipantEditForm, "location" | "roleGroup">;

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

function normalizeParticipantsTab(value: string | null): TabKey {
  return value === "access" ? "access" : "roster";
}

const emptyManualForm: ManualAddForm = {
  fullName: "",
  email: "",
  reportsToName: "",
  position: "",
};
const workspaceShellClass =
  "overflow-hidden border-y border-border bg-surface text-foreground";
const workspaceHeaderClass = "border-b border-border px-5 py-5";
const secondaryButtonClass =
  "border-border bg-surface text-foreground hover:border-burgundy/45 hover:text-burgundy";

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
      .map((name) => managerReferenceKey(name))
      .filter((key) => Boolean(key)),
  );
}

function isPermanentAccountParticipant(participant: CompanyParticipant, managerNameKeys: Set<string>): boolean {
  const role = participant.role_group?.trim().toLowerCase();
  if (isExternalMatrixManagerLabel(participant.full_name)) {
    return role === "manager" || role === "leadership" || Boolean(participant.user_id);
  }
  const participantName = managerReferenceKey(participant.full_name);
  return role === "manager" || role === "leadership" || Boolean(participant.user_id) || managerNameKeys.has(participantName);
}

export function ProjectParticipantsWorkspace({
  companyId,
  projectId,
  companyName,
  project,
  participants: initialParticipants,
  invitationStatuses,
}: ProjectParticipantsWorkspaceProps) {
  const router = useRouter();
  const { get, searchKey, setParam, setParams } = useUrlState();
  const [participants, setParticipants] = useState(initialParticipants);
  const [query, setQuery] = useState(() => get("q") ?? "");
  const deferredQuery = useDeferredValue(query);
  const [activeTab, setActiveTabState] = useState<TabKey>(normalizeParticipantsTab(get("view")));
  const [showAddPanel, setShowAddPanel] = useState(get("panel") === "add" || initialParticipants.length === 0);
  const [showImportModal, setShowImportModal] = useState(get("modal") === "import");
  const [manualForm, setManualForm] = useState<ManualAddForm>(emptyManualForm);
  const [pasteText, setPasteText] = useState("");
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ParticipantEditForm | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const addingRef = useRef(false);
  const savingParticipantRef = useRef<string | null>(null);

  const statusByParticipantId = useMemo(
    () => new Map(invitationStatuses.map((status) => [status.participant_id, status])),
    [invitationStatuses],
  );
  const managerNameKeys = useMemo(() => buildManagerNameKeys(participants), [participants]);
  const accessRows = useMemo(
    () => buildProjectParticipantAccessRows(participants, invitationStatuses),
    [participants, invitationStatuses],
  );
  const visibleParticipants = useMemo(() => {
    const normalizedQuery = normalizeWorkspaceSearch(deferredQuery);
    if (!normalizedQuery) return participants;
    return participants.filter((participant) =>
      normalizeWorkspaceSearch([
        participant.full_name,
        participant.email,
        participant.reports_to_name,
        participant.position,
        participant.location,
        participant.role_group,
      ].filter(Boolean).join(" ")).includes(normalizedQuery),
    );
  }, [deferredQuery, participants]);
  const visibleAccessRows = useMemo(() => {
    const visibleIds = new Set(visibleParticipants.map((participant) => participant.id));
    return accessRows.filter((row) => visibleIds.has(row.participant.id));
  }, [accessRows, visibleParticipants]);
  const permanentCount = accessRows.filter((row) => row.accountTypeLabel === "Cont permanent").length;
  const temporaryCount = accessRows.length - permanentCount;
  const activeAccountCount = accessRows.filter((row) => row.hasAccount).length;
  const activeSecureLinkCount = accessRows.filter((row) => row.hasSecureLink).length;
  const mutationLocked = adding || Boolean(savingId);

  useEffect(() => {
    setParticipants(initialParticipants);
  }, [initialParticipants]);

  useEffect(() => {
    setActiveTabState(normalizeParticipantsTab(get("view")));
    setQuery(get("q") ?? "");
    setShowImportModal(get("modal") === "import");
    setShowAddPanel(get("panel") === "add" || (participants.length === 0 && get("panel") !== "closed"));
  }, [get, participants.length, searchKey]);

  const selectTab = (tab: TabKey) => {
    setActiveTabState(tab);
    setParams({ view: tab === "roster" ? null : tab }, "push");
  };

  const updateQuery = (nextQuery: string) => {
    setQuery(nextQuery);
    setParam("q", nextQuery || null, "replace");
  };

  const setAddPanelOpen = (open: boolean) => {
    setShowAddPanel(open);
    setParam("panel", open ? "add" : "closed", "push");
  };

  const setImportModalOpen = (open: boolean) => {
    if (open && (addingRef.current || savingParticipantRef.current)) return;
    setShowImportModal(open);
    setParam("modal", open ? "import" : null, open ? "push" : "replace");
  };

  const startEdit = (participant: CompanyParticipant) => {
    if (addingRef.current || savingParticipantRef.current) return;
    const storedRole = participant.role_group?.trim().toLowerCase();
    setError(null);
    setEditingId(participant.id);
    setForm({
      fullName: participant.full_name,
      email: participant.email ?? "",
      reportsToName: participant.reports_to_name ?? "",
      position: participant.position ?? "",
      location: participant.location ?? "",
      roleGroup: storedRole === "leadership" || storedRole === "manager"
        ? "leadership"
        : storedRole === "member"
          ? "member"
          : isPermanentAccountParticipant(participant, buildManagerNameKeys(participants))
            ? "leadership"
            : "member",
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
    if (!form || addingRef.current || savingParticipantRef.current) return;

    savingParticipantRef.current = participant.id;
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
        roleGroup: form.roleGroup,
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
      savingParticipantRef.current = null;
      setSavingId(null);
    }
  };

  const addManualRows = async () => {
    if (addingRef.current || savingParticipantRef.current) return;

    const rows = buildManualImportRows(manualForm, pasteText);
    if (rows.length === 0) {
      setError("Adaugă cel puțin un participant cu nume și email.");
      return;
    }

    addingRef.current = true;
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
      setParticipants((current) => mergeParticipants(current, result.participants));
      setManualForm(emptyManualForm);
      setPasteText("");
      setAddPanelOpen(false);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Participanții nu au putut fi salvați.");
    } finally {
      addingRef.current = false;
      setAdding(false);
    }
  };

  return (
    <section className={workspaceShellClass} aria-busy={query !== deferredQuery}>
      <div className={workspaceHeaderClass}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-foreground">Participanți</h2>
            <div className="mt-4 flex flex-wrap gap-x-7 gap-y-3">
              <ParticipantMetric label="Roster" value={participants.length} />
              <ParticipantMetric label="Permanente" value={permanentCount} />
              <ParticipantMetric label="Linkuri active" value={activeSecureLinkCount} />
              <ParticipantMetric label="Conturi create" value={activeAccountCount} />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              onClick={() => setImportModalOpen(true)}
              disabled={mutationLocked}
              size="sm"
            >
              Importă participanți
            </Button>
            <Button
              type="button"
              onClick={() => setAddPanelOpen(!showAddPanel)}
              disabled={mutationLocked}
              variant="outline"
              size="sm"
              className={secondaryButtonClass}
            >
              {showAddPanel ? "Ascunde adăugarea" : "Adaugă manual"}
            </Button>
          </div>
        </div>
        <div className="mt-5 inline-flex h-10 w-fit items-center gap-1 rounded-md bg-muted p-1" role="tablist" aria-label="Vizualizări participanți">
          {tabs.map((tab) => (
            <Button
              key={tab.key}
              type="button"
              role="tab"
              variant="ghost"
              size="sm"
              aria-selected={activeTab === tab.key}
              onClick={() => selectTab(tab.key)}
              disabled={mutationLocked && activeTab !== tab.key}
              className={cn(
                "h-8 min-w-28 justify-center rounded-sm border-0 px-3 shadow-none",
                activeTab === tab.key
                  ? "bg-surface text-foreground shadow-sm hover:bg-surface"
                  : "text-muted-foreground hover:bg-background/70",
              )}
            >
              {tab.label}
            </Button>
          ))}
        </div>
        {participants.length > 0 ? (
          <WorkspaceSearchInput
            id="project-participants-search"
            label="Caută participant"
            value={query}
            onValueChange={updateQuery}
            placeholder="Caută după nume, email, rol sau manager"
            className="mt-4 max-w-2xl"
          />
        ) : null}
        <span className="sr-only" role="status" aria-live="polite">
          {query !== deferredQuery ? "Se actualizează lista" : ""}
        </span>
      </div>

      {error ? (
        <InlineFeedback
          tone="danger"
          className="rounded-none border-x-0 border-t-0 px-5 py-3"
          descriptionClassName="text-sm leading-6"
        >
          {error}
        </InlineFeedback>
      ) : null}

      {activeTab === "roster" ? (
        <>
          {showAddPanel ? (
            <ManualAddPanel
              form={manualForm}
              pasteText={pasteText}
              adding={adding}
              operationLocked={mutationLocked}
              onUpdateForm={(field, value) => setManualForm((current) => ({ ...current, [field]: value }))}
              onPasteText={setPasteText}
              onAdd={() => void addManualRows()}
            />
          ) : null}
          <RosterTable
            participants={visibleParticipants}
            projectId={projectId}
            statusByParticipantId={statusByParticipantId}
            managerNameKeys={managerNameKeys}
            editingId={editingId}
            form={form}
            savingId={savingId}
            operationLocked={mutationLocked}
            onCancel={cancelEdit}
            onEdit={startEdit}
            onSave={(participant) => void saveEdit(participant)}
            onUpdateField={updateField}
            emptyMessage={participants.length === 0
              ? "Nu există participanți. Adaugă manual sau importă rosterul."
              : "Niciun participant pentru căutarea curentă."}
          />
        </>
      ) : (
        <AccessTable
          rows={visibleAccessRows}
          permanentCount={permanentCount}
          temporaryCount={temporaryCount}
          activeAccountCount={activeAccountCount}
          activeSecureLinkCount={activeSecureLinkCount}
          emptyMessage={participants.length === 0
            ? "Niciun participant în acest proiect încă."
            : "Niciun participant pentru căutarea curentă."}
        />
      )}

      {showImportModal ? (
        <ModalLayer
          labelledBy="project-import-title"
          onClose={() => setImportModalOpen(false)}
          panelClassName="max-w-5xl"
        >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 id="project-import-title" className="mt-1 text-xl font-semibold text-foreground">
                  Import participanți pentru {project.name}
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">{companyName}</p>
              </div>
              <Button
                type="button"
                onClick={() => setImportModalOpen(false)}
                variant="outline"
                size="sm"
                className={secondaryButtonClass}
              >
                Închide
              </Button>
            </div>
            <div className="mt-5 max-h-[80vh] overflow-y-auto pr-1">
              <RosterImporter
                companies={[{ id: companyId, name: companyName }]}
                defaultCompanyId={companyId}
                existingParticipants={participants}
                projects={[project]}
                defaultProjectId={projectId}
                requireProject
                lockCompany
                compact
              />
            </div>
        </ModalLayer>
      ) : null}
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
  operationLocked,
  onCancel,
  onEdit,
  onSave,
  onUpdateField,
  emptyMessage,
}: {
  participants: CompanyParticipant[];
  projectId: string;
  statusByParticipantId: Map<string, ParticipantInvitationStatus>;
  managerNameKeys: Set<string>;
  editingId: string | null;
  form: ParticipantEditForm | null;
  savingId: string | null;
  operationLocked: boolean;
  onCancel: () => void;
  onEdit: (participant: CompanyParticipant) => void;
  onSave: (participant: CompanyParticipant) => void;
  onUpdateField: (field: keyof ParticipantEditForm, value: string) => void;
  emptyMessage: string;
}) {
  return (
    <div className="min-w-0 max-w-full overflow-x-auto px-5 pb-5">
      <div
        role="table"
        aria-label="Roster participanți"
        className="min-w-0 overflow-hidden rounded-lg border border-border bg-surface text-sm shadow-sm sm:min-w-[920px]"
      >
        <div role="rowgroup">
          <div
            role="row"
            className="hidden grid-cols-[1.05fr_1.35fr_0.9fr_0.9fr_10rem_6rem] bg-muted text-xs font-semibold text-muted-foreground sm:grid"
          >
            <span role="columnheader" className="px-5 py-3">Nume</span>
            <span role="columnheader" className="px-5 py-3">Email</span>
            <span role="columnheader" className="px-5 py-3">Manager</span>
            <span role="columnheader" className="px-5 py-3">Poziție</span>
            <span role="columnheader" className="px-5 py-3">Tip acces</span>
            <span role="columnheader" className="px-5 py-3 text-right">Acțiuni</span>
          </div>
        </div>
        {participants.length === 0 ? (
          <div role="rowgroup">
            <div role="row">
              <div role="cell" aria-colspan={6} className="px-5 py-8 text-center text-foreground/62">
                {emptyMessage}
              </div>
            </div>
          </div>
        ) : (
          <div role="rowgroup" className="divide-y divide-border">
            {participants.map((member) => (
              <ParticipantRow
                key={member.id}
                participant={member}
                projectId={projectId}
                invitationStatus={statusByParticipantId.get(member.id) ?? null}
                managerNameKeys={managerNameKeys}
                form={editingId === member.id ? form : null}
                saving={savingId === member.id}
                operationLocked={operationLocked}
                onCancel={onCancel}
                onEdit={() => onEdit(member)}
                onSave={() => onSave(member)}
                onUpdateField={onUpdateField}
              />
            ))}
          </div>
        )}
      </div>
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
  operationLocked,
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
  operationLocked: boolean;
  onCancel: () => void;
  onEdit: () => void;
  onSave: () => void;
  onUpdateField: (field: keyof ParticipantEditForm, value: string) => void;
}) {
  if (!form) {
    return (
      <div
        role="row"
        data-participant-row={participant.id}
        className="grid min-w-0 gap-4 px-4 py-4 sm:grid-cols-[1.05fr_1.35fr_0.9fr_0.9fr_10rem_6rem] sm:items-center sm:gap-0 sm:px-0"
      >
        <div role="cell" className="min-w-0 sm:px-5">
          <span className="mb-1 block text-[11px] font-semibold text-muted-foreground sm:hidden">Nume</span>
          <Link
            href={`/trainer/projects/${projectId}/participants/${participant.id}`}
            className="font-semibold text-foreground underline-offset-4 hover:text-burgundy hover:underline"
          >
            {participant.full_name}
          </Link>
        </div>
        <div role="cell" className="min-w-0 text-foreground/62 sm:px-5">
          <span className="mb-1 block text-[11px] font-semibold text-muted-foreground sm:hidden">Email</span>
          <span className="break-all sm:block sm:truncate">{participant.email ?? "email lipsă"}</span>
        </div>
        <div role="cell" className="min-w-0 text-foreground/62 sm:px-5">
          <span className="mb-1 block text-[11px] font-semibold text-muted-foreground sm:hidden">Manager</span>
          <span className="break-words">{formatManagerName(participant.reports_to_name)}</span>
        </div>
        <div role="cell" className="min-w-0 text-foreground/62 sm:px-5">
          <span className="mb-1 block text-[11px] font-semibold text-muted-foreground sm:hidden">Poziție</span>
          <span className="break-words">{participant.position ?? "-"}</span>
        </div>
        <div role="cell" className="min-w-0 sm:px-5">
          <span className="mb-1 block text-[11px] font-semibold text-muted-foreground sm:hidden">Tip acces</span>
          <AccountTypeBadge participant={participant} invitationStatus={invitationStatus} managerNameKeys={managerNameKeys} />
        </div>
        <div role="cell" className="min-w-0 sm:px-3 sm:text-right">
          <Button
            type="button"
            onClick={onEdit}
            disabled={operationLocked}
            variant="outline"
            size="xs"
            className={secondaryButtonClass}
          >
            Editează
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div role="row" data-participant-row={participant.id} className="bg-muted">
      <div role="cell" aria-colspan={6} className="px-4 py-4 sm:px-5">
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          <EditField
            label="Nume"
            value={form.fullName}
            required
            disabled={saving}
            onChange={(value) => onUpdateField("fullName", value)}
          />
          <EditField
            label="Email"
            value={form.email}
            required
            type="email"
            disabled={saving}
            onChange={(value) => onUpdateField("email", value)}
          />
          <EditField
            label="Manager"
            value={form.reportsToName}
            disabled={saving}
            onChange={(value) => onUpdateField("reportsToName", value)}
          />
          <EditField
            label="Poziție"
            value={form.position}
            disabled={saving}
            onChange={(value) => onUpdateField("position", value)}
          />
          <EditField
            label="Locație"
            value={form.location}
            disabled={saving}
            onChange={(value) => onUpdateField("location", value)}
          />
          <div className="border-l border-border pl-3 py-1">
            <span className="text-xs font-bold text-foreground/58">Rol proiect</span>
            <button
              type="button"
              onClick={() => onUpdateField("roleGroup", form.roleGroup === "leadership" ? "member" : "leadership")}
              className={`tap-soft mt-2 rounded-md border px-3 py-1.5 text-xs font-semibold transition ${
                form.roleGroup === "leadership"
                  ? "border-emerald-500/35 bg-emerald-500/12 text-emerald-700"
                  : "border-[var(--border)] bg-background text-foreground/55 hover:border-burgundy/35 hover:text-burgundy"
              }`}
              aria-pressed={form.roleGroup === "leadership"}
            >
              {form.roleGroup === "leadership" ? "Leadership" : "Membru"}
            </button>
          </div>
          <div className="border-l border-border pl-3 py-1">
            <span className="text-xs font-bold text-foreground/58">Tip acces</span>
            <div className="mt-2">
              <AccountTypeBadge participant={participant} invitationStatus={invitationStatus} managerNameKeys={managerNameKeys} />
            </div>
          </div>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <Button
            type="button"
            onClick={onCancel}
            disabled={saving}
            variant="outline"
            size="sm"
            className={secondaryButtonClass}
          >
            Anulează
          </Button>
          <Button
            type="button"
            onClick={onSave}
            disabled={saving || !form.fullName.trim() || !form.email.trim()}
            size="sm"
          >
            {saving ? <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" /> : null}
            {saving ? "Salvăm participantul" : "Salvează"}
          </Button>
        </div>
        {saving ? (
          <OperationFeedback
            title={`Salvăm ${participant.full_name}`}
            detail="Actualizăm datele participantului și refacem contextul proiectului."
            className="mt-4"
          />
        ) : null}
      </div>
    </div>
  );
}

function ManualAddPanel({
  form,
  pasteText,
  adding,
  operationLocked,
  onUpdateForm,
  onPasteText,
  onAdd,
}: {
  form: ManualAddForm;
  pasteText: string;
  adding: boolean;
  operationLocked: boolean;
  onUpdateForm: (field: keyof ManualAddForm, value: string) => void;
  onPasteText: (value: string) => void;
  onAdd: () => void;
}) {
  const parsedCount = buildManualImportRows(form, pasteText).length;

  return (
    <div className="border-b border-border bg-muted/35 px-5 py-4" aria-busy={adding}>
      <FieldGroup className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <EditField label="Nume" value={form.fullName} disabled={operationLocked} onChange={(value) => onUpdateForm("fullName", value)} />
        <EditField label="Email" value={form.email} type="email" disabled={operationLocked} onChange={(value) => onUpdateForm("email", value)} />
        <EditField label="Manager" value={form.reportsToName} disabled={operationLocked} onChange={(value) => onUpdateForm("reportsToName", value)} />
        <EditField label="Poziție" value={form.position} disabled={operationLocked} onChange={(value) => onUpdateForm("position", value)} />
      </FieldGroup>
      <Field className="mt-4" data-disabled={operationLocked ? true : undefined}>
        <FieldLabel htmlFor="manual-participant-rows">
          Lipește rânduri: nume, email, poziție, manager
        </FieldLabel>
        <Textarea
          id="manual-participant-rows"
          value={pasteText}
          onChange={(event) => onPasteText(event.target.value)}
          rows={4}
          disabled={operationLocked}
          className="min-h-28 bg-surface"
          placeholder={"Ana Popescu, ana@companie.ro, Manager, -\nMihai Ionescu\tmihai@companie.ro\tConsultant\tAna Popescu"}
        />
        <FieldDescription>Separă coloanele prin virgulă sau tab.</FieldDescription>
      </Field>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs font-semibold text-muted-foreground">
          {parsedCount} {parsedCount === 1 ? "rând pregătit" : "rânduri pregătite"}
        </p>
        <Button
          type="button"
          onClick={onAdd}
          disabled={operationLocked || parsedCount === 0}
          size="sm"
        >
          {adding ? <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" /> : null}
          {adding ? "Salvăm participanții" : "Salvează participanții"}
        </Button>
      </div>
      {adding ? (
        <OperationFeedback
          title="Salvăm participanții"
          detail="Actualizăm rosterul proiectului."
          className="mt-4"
        />
      ) : null}
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
      <Badge variant="secondary" className="status-success-soft">
        cont permanent
      </Badge>
    );
  }

  if (invitationStatus?.has_active_secure_link || invitationStatus?.latest_delivery_mode === "secure_links") {
    return (
      <Badge variant="secondary" className="status-info-soft">
        invitație temporară activă
      </Badge>
    );
  }

  return (
    <Badge variant="outline">
      membru temporar
    </Badge>
  );
}

function AccessTable({
  rows,
  permanentCount,
  temporaryCount,
  activeAccountCount,
  activeSecureLinkCount,
  emptyMessage,
}: {
  rows: AccessRow[];
  permanentCount: number;
  temporaryCount: number;
  activeAccountCount: number;
  activeSecureLinkCount: number;
  emptyMessage: string;
}) {
  return (
    <div>
      <div className="flex flex-wrap gap-x-8 gap-y-3 border-b border-border bg-muted/35 px-5 py-4 text-sm">
        <AccessMetric label="Cont permanent" value={permanentCount} />
        <AccessMetric label="Acces temporar" value={temporaryCount} />
        <AccessMetric label="Conturi create" value={activeAccountCount} />
        <AccessMetric label="Linkuri active" value={activeSecureLinkCount} />
      </div>
      <div className="min-w-0 max-w-full overflow-x-auto px-5 pb-5">
        <div
          role="table"
          aria-label="Acces participanți"
          className="min-w-0 overflow-hidden rounded-lg border border-border bg-surface text-sm shadow-sm sm:min-w-[860px]"
        >
          <div role="rowgroup">
            <div
              role="row"
              className="hidden grid-cols-[1.35fr_1fr_0.9fr_0.9fr_1fr] bg-muted text-xs font-semibold text-muted-foreground sm:grid"
            >
              <span role="columnheader" className="px-5 py-3">Participant</span>
              <span role="columnheader" className="px-5 py-3">Rol intern</span>
              <span role="columnheader" className="px-5 py-3">Tip acces</span>
              <span role="columnheader" className="px-5 py-3">Stare cont</span>
              <span role="columnheader" className="px-5 py-3">Livrare</span>
            </div>
          </div>
          {rows.length === 0 ? (
            <div role="rowgroup">
              <div role="row">
                <div role="cell" aria-colspan={5} className="px-5 py-8 text-center text-foreground/62">
                  {emptyMessage}
                </div>
              </div>
            </div>
          ) : (
            <div role="rowgroup" className="divide-y divide-border">
              {rows.map((row) => (
                <div
                  key={row.participant.id}
                  role="row"
                  className="grid min-w-0 gap-4 px-4 py-4 sm:grid-cols-[1.35fr_1fr_0.9fr_0.9fr_1fr] sm:items-center sm:gap-0 sm:px-0"
                >
                  <div role="cell" className="min-w-0 sm:px-5">
                    <span className="mb-1 block text-[11px] font-semibold text-muted-foreground sm:hidden">Participant</span>
                    <p className="font-semibold text-foreground">{row.participant.full_name}</p>
                    <p className="mt-1 break-all text-xs text-foreground/52 sm:truncate">
                      {row.participant.email ?? "email lipsă"}
                    </p>
                  </div>
                  <AccessRowValue label="Rol intern">{row.internalRoleLabel}</AccessRowValue>
                  <div role="cell" className="min-w-0 sm:px-5">
                    <span className="mb-1 block text-[11px] font-semibold text-muted-foreground sm:hidden">Tip acces</span>
                    <Badge variant="outline">{row.accountTypeLabel}</Badge>
                  </div>
                  <AccessRowValue label="Stare cont">{row.accountStateLabel}</AccessRowValue>
                  <AccessRowValue label="Livrare">{row.deliveryLabel}</AccessRowValue>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function AccessRowValue({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div role="cell" className="min-w-0 text-foreground/70 sm:px-5">
      <span className="mb-1 block text-[11px] font-semibold text-muted-foreground sm:hidden">{label}</span>
      <span className="break-words">{children}</span>
    </div>
  );
}

function AccessMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-w-28">
      <p className="text-xs font-semibold text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-foreground">{value}</p>
    </div>
  );
}

function formatManagerName(value: string | null | undefined): string {
  return normalizeReportsToName(value) || "Fără manager";
}

function ParticipantMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-w-20">
      <p className="text-[11px] font-semibold text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-foreground">{value}</p>
    </div>
  );
}

function EditField({
  label,
  value,
  onChange,
  required = false,
  type = "text",
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  type?: "email" | "text";
  disabled?: boolean;
}) {
  const inputId = useId();

  return (
    <Field data-disabled={disabled ? true : undefined}>
      <FieldLabel htmlFor={inputId}>{label}</FieldLabel>
      <Input
        id={inputId}
        type={type}
        required={required}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="h-10"
      />
    </Field>
  );
}

function cleanOptional(value: string): string | null {
  const cleaned = value.trim();
  return cleaned || null;
}

function mergeParticipants(
  current: CompanyParticipant[],
  incoming: CompanyParticipant[],
): CompanyParticipant[] {
  const byId = new Map(current.map((participant) => [participant.id, participant]));
  for (const participant of incoming) {
    byId.set(participant.id, {
      ...byId.get(participant.id),
      ...participant,
    });
  }
  return Array.from(byId.values()).sort((first, second) =>
    first.full_name.localeCompare(second.full_name, "ro-RO"),
  );
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
