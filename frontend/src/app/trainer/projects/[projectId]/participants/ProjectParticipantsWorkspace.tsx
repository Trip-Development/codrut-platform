"use client";

import { useDeferredValue, useEffect, useId, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FilterIcon,
  Loader2Icon,
  PencilIcon,
  PlusIcon,
  UploadIcon,
  XIcon,
} from "lucide-react";

import {
  hasPermanentParticipantAccount,
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
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ModalCloseButton, ModalLayer } from "@/components/ui/modal-layer";
import { SelectControl } from "@/components/ui/select-control";
import { Sheet, SheetBody, SheetFooter, SheetHeader } from "@/components/ui/sheet";
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

type AccessFilter = "all" | "permanent" | "temporary";
type StatusTone = "success" | "info" | "warning" | "danger" | "neutral";

function normalizeAccessFilter(value: string | null): AccessFilter {
  return value === "permanent" || value === "temporary" ? value : "all";
}

const emptyManualForm: ManualAddForm = {
  fullName: "",
  email: "",
  reportsToName: "",
  position: "",
};
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
    const hasAccount = hasPermanentParticipantAccount(participant);
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
  if (participant.is_shadow_account === true) {
    return false;
  }
  const role = participant.role_group?.trim().toLowerCase();
  if (isExternalMatrixManagerLabel(participant.full_name)) {
    return role === "manager" || role === "leadership" || hasPermanentParticipantAccount(participant);
  }
  const participantName = managerReferenceKey(participant.full_name);
  return role === "manager" || role === "leadership" || hasPermanentParticipantAccount(participant) || managerNameKeys.has(participantName);
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
  const { get, searchKey, setParam } = useUrlState();
  const [participants, setParticipants] = useState(initialParticipants);
  const [query, setQuery] = useState(() => get("q") ?? "");
  const deferredQuery = useDeferredValue(query);
  const [accessFilter, setAccessFilterState] = useState<AccessFilter>(() =>
    normalizeAccessFilter(get("access")),
  );
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

  const accessRows = useMemo(
    () => buildProjectParticipantAccessRows(participants, invitationStatuses),
    [participants, invitationStatuses],
  );
  const visibleRows = useMemo(() => {
    const normalizedQuery = normalizeWorkspaceSearch(deferredQuery);
    return accessRows.filter((row) => {
      if (accessFilter === "permanent" && row.accountTypeLabel !== "Cont permanent") return false;
      if (accessFilter === "temporary" && row.accountTypeLabel !== "Acces temporar") return false;
      if (!normalizedQuery) return true;
      return normalizeWorkspaceSearch([
        row.participant.full_name,
        row.participant.email,
        row.participant.reports_to_name,
        row.participant.position,
        row.participant.location,
        row.participant.role_group,
        row.internalRoleLabel,
        row.accountTypeLabel,
        row.accountStateLabel,
        row.deliveryLabel,
      ].filter(Boolean).join(" ")).includes(normalizedQuery);
    });
  }, [accessFilter, accessRows, deferredQuery]);
  const permanentCount = accessRows.filter((row) => row.accountTypeLabel === "Cont permanent").length;
  const temporaryCount = accessRows.length - permanentCount;
  const activeAccountCount = accessRows.filter((row) => row.hasAccount).length;
  const activeSecureLinkCount = accessRows.filter((row) => row.hasSecureLink).length;
  const editingParticipant = participants.find((participant) => participant.id === editingId) ?? null;
  const editingAccessRow = accessRows.find((row) => row.participant.id === editingId) ?? null;
  const mutationLocked = adding || Boolean(savingId);

  useEffect(() => {
    setParticipants(initialParticipants);
  }, [initialParticipants]);

  useEffect(() => {
    setAccessFilterState(normalizeAccessFilter(get("access")));
    setQuery(get("q") ?? "");
    setShowImportModal(get("modal") === "import");
    setShowAddPanel(get("panel") === "add" || (participants.length === 0 && get("panel") !== "closed"));
  }, [get, participants.length, searchKey]);

  const updateQuery = (nextQuery: string) => {
    setQuery(nextQuery);
    setParam("q", nextQuery || null, "replace");
  };

  const setAccessFilter = (nextFilter: AccessFilter) => {
    setAccessFilterState(nextFilter);
    setParam("access", nextFilter === "all" ? null : nextFilter, "replace");
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
    <section className="min-w-0 max-w-full text-foreground" aria-busy={query !== deferredQuery}>
      <section
        data-slot="participants-workspace"
        aria-label="Registru participanți"
        className="overflow-hidden rounded-lg border border-border bg-surface"
      >
        <header className="border-b border-border px-4 py-4 md:px-5">
          <h2 className="text-lg font-semibold text-foreground">Participanți</h2>
          <p
            aria-label="Rezumat participanți"
            className="mt-1 text-sm leading-6 text-muted-foreground"
          >
            <span className="font-semibold tabular-nums text-foreground">{participants.length}</span>{" "}
            {participants.length === 1 ? "participant" : "participanți"}
            <span aria-hidden="true"> · </span>
            <span className="tabular-nums">{permanentCount}</span>{" "}
            {permanentCount === 1 ? "permanent" : "permanente"}
            <span aria-hidden="true"> · </span>
            <span className="tabular-nums">{temporaryCount}</span>{" "}
            {temporaryCount === 1 ? "temporar" : "temporare"}
            <span aria-hidden="true"> · </span>
            <span className="tabular-nums">{activeSecureLinkCount}</span>{" "}
            {activeSecureLinkCount === 1 ? "link activ" : "linkuri active"}
            <span aria-hidden="true"> · </span>
            <span className="tabular-nums">{activeAccountCount}</span>{" "}
            {activeAccountCount === 1 ? "cont creat" : "conturi create"}
          </p>

          <div
            role="group"
            aria-label="Instrumente participanți"
            className="mt-4 flex min-w-0 flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center"
          >
            <WorkspaceSearchInput
              id="project-participants-search"
              label="Caută participant"
              value={query}
              onValueChange={updateQuery}
              placeholder="Caută participanți"
              className="min-w-[min(100%,16rem)] flex-1 basis-auto sm:basis-64"
            />
            <SelectControl
              label="Filtrează după acces"
              icon={FilterIcon}
              value={accessFilter}
              onChange={(event) => setAccessFilter(normalizeAccessFilter(event.target.value))}
              disabled={mutationLocked}
              wrapperClassName="w-full sm:w-48"
              className="h-11 bg-background"
            >
              <option value="all">Toate tipurile</option>
              <option value="permanent">Acces permanent</option>
              <option value="temporary">Acces temporar</option>
            </SelectControl>
            <div className="grid grid-cols-2 gap-2 sm:flex sm:shrink-0">
              <Button
                type="button"
                onClick={() => setImportModalOpen(true)}
                disabled={mutationLocked}
                variant="outline"
                className={secondaryButtonClass}
              >
                <UploadIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
                Importă
              </Button>
              <Button
                type="button"
                onClick={() => setAddPanelOpen(!showAddPanel)}
                disabled={mutationLocked}
              >
                {showAddPanel ? <XIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} /> : <PlusIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />}
                {showAddPanel ? "Ascunde" : "Adaugă"}
              </Button>
            </div>
          </div>
          <span className="sr-only" role="status" aria-live="polite">
            {query !== deferredQuery ? "Se actualizează lista" : ""}
          </span>
        </header>

        {error && !editingId ? (
          <InlineFeedback
            tone="danger"
            className="mx-4 my-3 px-4 py-3 md:mx-5"
            descriptionClassName="text-sm leading-6"
          >
            {error}
          </InlineFeedback>
        ) : null}

        {showAddPanel ? (
          <div className="border-b border-border px-4 py-4 md:px-5">
            <ManualAddPanel
              form={manualForm}
              pasteText={pasteText}
              adding={adding}
              operationLocked={mutationLocked}
              onUpdateForm={(field, value) => setManualForm((current) => ({ ...current, [field]: value }))}
              onPasteText={setPasteText}
              onAdd={() => void addManualRows()}
            />
          </div>
        ) : null}
        <RosterTable
          rows={visibleRows}
          projectId={projectId}
          operationLocked={mutationLocked}
          onEdit={startEdit}
          emptyMessage={participants.length === 0
            ? "Nu există participanți. Adaugă manual sau importă rosterul."
            : "Niciun participant pentru filtrele curente."}
        />
      </section>

      <Sheet
        open={Boolean(editingParticipant && editingAccessRow && form)}
        onOpenChange={(open) => {
          if (!open && !savingId) cancelEdit();
        }}
        labelledBy="participant-edit-title"
        describedBy="participant-edit-description"
        closeOnBackdrop={!savingId}
      >
        {editingParticipant && editingAccessRow && form ? (
          <div className="flex h-full min-w-0 flex-col">
            <SheetHeader className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <h2 id="participant-edit-title" className="text-lg font-semibold text-foreground">
                  Editează participantul
                </h2>
                <p id="participant-edit-description" className="mt-1 break-words text-sm text-muted-foreground">
                  {editingParticipant.full_name}
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="Închide editarea"
                title="Închide"
                disabled={Boolean(savingId)}
                onClick={cancelEdit}
                className="-mr-2 shrink-0 text-muted-foreground hover:text-foreground"
              >
                <XIcon aria-hidden="true" strokeWidth={1.8} />
              </Button>
            </SheetHeader>
            <SheetBody aria-busy={Boolean(savingId)}>
              {error ? (
                <InlineFeedback tone="danger" className="mb-5 px-4 py-3">
                  {error}
                </InlineFeedback>
              ) : null}
              <FieldGroup className="gap-4">
                <EditField
                  label="Nume"
                  value={form.fullName}
                  required
                  disabled={Boolean(savingId)}
                  onChange={(value) => updateField("fullName", value)}
                />
                <EditField
                  label="Email"
                  value={form.email}
                  required
                  type="email"
                  disabled={Boolean(savingId)}
                  onChange={(value) => updateField("email", value)}
                />
                <EditField
                  label="Manager"
                  value={form.reportsToName}
                  disabled={Boolean(savingId)}
                  onChange={(value) => updateField("reportsToName", value)}
                />
                <EditField
                  label="Poziție"
                  value={form.position}
                  disabled={Boolean(savingId)}
                  onChange={(value) => updateField("position", value)}
                />
                <EditField
                  label="Locație"
                  value={form.location}
                  disabled={Boolean(savingId)}
                  onChange={(value) => updateField("location", value)}
                />
              </FieldGroup>

              <fieldset className="mt-5">
                <legend className="text-sm font-semibold text-foreground">Rol în proiect</legend>
                <div className="mt-2 grid grid-cols-2 gap-1 rounded-lg bg-muted p-1">
                  {(["member", "leadership"] as const).map((role) => (
                    <Button
                      key={role}
                      type="button"
                      variant="ghost"
                      size="sm"
                      aria-pressed={form.roleGroup === role}
                      disabled={Boolean(savingId)}
                      onClick={() => updateField("roleGroup", role)}
                      className={cn(
                        "rounded-md border-0 shadow-none",
                        form.roleGroup === role
                          ? "bg-surface text-foreground shadow-sm hover:bg-surface"
                          : "text-muted-foreground hover:bg-background/70",
                      )}
                    >
                      {role === "member" ? "Membru" : "Leadership"}
                    </Button>
                  ))}
                </div>
              </fieldset>

              <div className="mt-5 border-y border-border py-4">
                <p className="text-xs font-semibold text-muted-foreground">Acces curent</p>
                <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-2">
                  <DotStatus {...accessTypeStatus(editingAccessRow)} />
                  <DotStatus {...participantStateStatus(editingAccessRow)} />
                </div>
              </div>

              {savingId ? (
                <OperationFeedback
                  title={`Salvăm ${editingParticipant.full_name}`}
                  detail="Actualizăm datele participantului și refacem contextul proiectului."
                  className="mt-5"
                />
              ) : null}
            </SheetBody>
            <SheetFooter className="flex items-center justify-end gap-2">
              <Button
                type="button"
                onClick={cancelEdit}
                disabled={Boolean(savingId)}
                variant="outline"
                size="sm"
                className={secondaryButtonClass}
              >
                Anulează
              </Button>
              <Button
                type="button"
                onClick={() => void saveEdit(editingParticipant)}
                disabled={Boolean(savingId) || !form.fullName.trim() || !form.email.trim()}
                size="sm"
              >
                {savingId ? <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" /> : null}
                {savingId ? "Salvăm participantul" : "Salvează"}
              </Button>
            </SheetFooter>
          </div>
        ) : null}
      </Sheet>

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
              <ModalCloseButton
                onClick={() => setImportModalOpen(false)}
              />
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
  rows,
  projectId,
  operationLocked,
  onEdit,
  emptyMessage,
}: {
  rows: AccessRow[];
  projectId: string;
  operationLocked: boolean;
  onEdit: (participant: CompanyParticipant) => void;
  emptyMessage: string;
}) {
  return (
    <div
      data-slot="participants-table-scroll"
      className="min-w-0 max-w-full md:overflow-x-auto"
    >
      <table
        aria-label="Roster participanți"
        className="block w-full border-collapse text-left text-sm md:table md:min-w-[960px] md:table-fixed xl:min-w-0"
      >
        <colgroup>
          <col className="w-[17%]" />
          <col className="w-[22%]" />
          <col className="w-[15%]" />
          <col className="w-[17%]" />
          <col className="w-[11%]" />
          <col className="w-[12%]" />
          <col className="w-[6%]" />
        </colgroup>
        <thead className="hidden bg-muted/70 text-xs font-semibold text-muted-foreground md:table-header-group">
          <tr>
            <th scope="col" className="px-4 py-2.5">Participant</th>
            <th scope="col" className="px-4 py-2.5">Email</th>
            <th scope="col" className="px-4 py-2.5">Manager</th>
            <th scope="col" className="px-4 py-2.5">Poziție</th>
            <th scope="col" className="px-4 py-2.5">Acces</th>
            <th scope="col" className="px-4 py-2.5">Stare</th>
            <th scope="col" className="relative px-3 py-2.5 text-right">
              <span className="sr-only">Acțiuni</span>
            </th>
          </tr>
        </thead>
        <tbody className="block divide-y divide-border md:table-row-group">
          {rows.length === 0 ? (
            <tr className="block md:table-row">
              <td colSpan={7} className="block px-4 py-10 text-center text-muted-foreground md:table-cell">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <ParticipantRow
                key={row.participant.id}
                row={row}
                projectId={projectId}
                operationLocked={operationLocked}
                onEdit={() => onEdit(row.participant)}
              />
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function ParticipantRow({
  row,
  projectId,
  operationLocked,
  onEdit,
}: {
  row: AccessRow;
  projectId: string;
  operationLocked: boolean;
  onEdit: () => void;
}) {
  const participant = row.participant;
  return (
    <tr data-participant-row={participant.id} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-3 px-4 py-4 transition-colors hover:bg-muted/35 md:table-row md:px-0 md:py-0">
      <th scope="row" className="col-start-1 row-start-1 min-w-0 text-left align-middle font-semibold text-foreground md:px-4 md:py-3">
        <Link
          href={`/trainer/projects/${projectId}/participants/${participant.id}`}
          className="whitespace-normal break-words underline-offset-4 hover:text-burgundy hover:underline"
        >
          {participant.full_name}
        </Link>
      </th>
      <td className="col-span-2 row-start-2 break-all align-middle text-foreground/65 md:px-4 md:py-3">
        <span className="mb-1 block text-xs font-medium text-muted-foreground md:hidden">Email</span>
        {participant.email ?? "email lipsă"}
      </td>
      <td className="col-start-1 row-start-3 whitespace-normal break-words align-middle text-foreground/65 md:px-4 md:py-3">
        <span className="mb-1 block text-xs font-medium text-muted-foreground md:hidden">Manager</span>
        {formatManagerName(participant.reports_to_name)}
      </td>
      <td className="col-start-2 row-start-3 max-w-36 whitespace-normal break-words text-right align-middle text-foreground/65 md:max-w-none md:px-4 md:py-3 md:text-left">
        <span className="mb-1 block text-xs font-medium text-muted-foreground md:hidden">Poziție</span>
        {participant.position ?? "-"}
      </td>
      <td className="col-start-1 row-start-4 align-middle md:px-4 md:py-3">
        <span className="mb-1 block text-xs font-medium text-muted-foreground md:hidden">Acces</span>
        <DotStatus {...accessTypeStatus(row)} />
      </td>
      <td className="col-start-2 row-start-4 justify-self-end text-right align-middle md:justify-self-auto md:px-4 md:py-3 md:text-left">
        <span className="mb-1 block text-xs font-medium text-muted-foreground md:hidden">Stare</span>
        <DotStatus {...participantStateStatus(row)} />
      </td>
      <td className="col-start-2 row-start-1 text-right align-middle md:px-3 md:py-3">
        <Button
          type="button"
          onClick={onEdit}
          disabled={operationLocked}
          variant="ghost"
          size="icon-sm"
          aria-label={`Editează ${participant.full_name}`}
          title={`Editează ${participant.full_name}`}
          className="rounded-md text-muted-foreground shadow-none hover:text-burgundy"
        >
          <PencilIcon aria-hidden="true" strokeWidth={1.8} />
        </Button>
      </td>
    </tr>
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

function accessTypeStatus(row: AccessRow): { label: string; tone: StatusTone } {
  return row.accountTypeLabel === "Cont permanent"
    ? { label: "Permanent", tone: "success" }
    : { label: "Temporar", tone: "neutral" };
}

function participantStateStatus(row: AccessRow): { label: string; tone: StatusTone } {
  if (row.hasAccount) return { label: "Cont creat", tone: "success" };
  if (row.deliveryLabel === "Email cu eroare") return { label: "Email cu eroare", tone: "danger" };
  if (row.hasSecureLink) return { label: "Link activ", tone: "info" };
  if (row.deliveryLabel === "Email trimis") return { label: "Email trimis", tone: "info" };
  if (row.accountTypeLabel === "Cont permanent") return { label: "Cont de creat", tone: "warning" };
  return { label: "Nepregătit", tone: "neutral" };
}

function DotStatus({ label, tone }: { label: string; tone: StatusTone }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-xs font-semibold text-foreground/70">
      <span
        aria-hidden="true"
        className={cn(
          "size-1.5 shrink-0 rounded-full",
          tone === "success" && "bg-success-ink",
          tone === "info" && "bg-info",
          tone === "warning" && "bg-warning",
          tone === "danger" && "bg-destructive",
          tone === "neutral" && "bg-muted-foreground",
        )}
      />
      {label}
    </span>
  );
}

function formatManagerName(value: string | null | undefined): string {
  return normalizeReportsToName(value) || "Fără manager";
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
