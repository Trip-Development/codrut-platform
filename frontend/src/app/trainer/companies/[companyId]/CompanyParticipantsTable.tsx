"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { EyeIcon, HistoryIcon, Loader2Icon, PencilIcon, XIcon } from "lucide-react";

import {
  deleteCompanyParticipant,
  hasPermanentParticipantAccount,
  updateCompanyParticipant,
  type CompanyParticipant,
} from "@/api/companies";
import { directReportsForParticipant } from "@/api/roster-format";
import { IdentityMark } from "@/components/presentation/identity-mark";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { ParticipantManagerSelect } from "@/components/participants/participant-manager-select";
import { ParticipantRemovalSheetContent } from "@/components/participants/participant-removal-sheet-content";
import { Button } from "@/components/ui/button";
import { Sheet, SheetBody, SheetFooter, SheetHeader } from "@/components/ui/sheet";
import { useUrlState } from "@/hooks/use-url-state";
import {
  normalizeWorkspaceSearch,
  WorkspaceSearchInput,
} from "../../projects/project-workspace-controls";

export function CompanyParticipantsTable({
  companyId,
  participants: initialParticipants,
}: {
  companyId: string;
  participants: CompanyParticipant[];
}) {
  const router = useRouter();
  const { get, searchKey, setParam } = useUrlState();
  const [participants, setParticipants] = useState(initialParticipants);
  const [query, setQuery] = useState(() => get("q") ?? "");
  const deferredQuery = useDeferredValue(query);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [reportsToName, setReportsToName] = useState("");
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [confirmingRemoval, setConfirmingRemoval] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const visibleParticipants = useMemo(() => {
    const normalizedQuery = normalizeWorkspaceSearch(deferredQuery);
    if (!normalizedQuery) return participants;

    return participants.filter((participant) =>
      normalizeWorkspaceSearch([
        participant.full_name,
        participant.email,
        participant.position,
        participant.reports_to_name,
        participant.location,
        participant.role_group,
      ].filter(Boolean).join(" ")).includes(normalizedQuery),
    );
  }, [deferredQuery, participants]);
  const editingParticipant = participants.find((participant) => participant.id === editingId) ?? null;
  const editingDirectReports = editingParticipant
    ? directReportsForParticipant(participants, editingParticipant)
    : [];
  const mutationLocked = saving || removing;

  useEffect(() => {
    setParticipants(initialParticipants);
  }, [initialParticipants]);

  useEffect(() => {
    setQuery(get("q") ?? "");
  }, [get, searchKey]);

  function updateQuery(nextQuery: string) {
    setQuery(nextQuery);
    setParam("q", nextQuery || null, "replace");
  }

  function startEdit(participant: CompanyParticipant) {
    if (mutationLocked) return;
    setEditingId(participant.id);
    setReportsToName(participant.reports_to_name ?? "");
    setConfirmingRemoval(false);
    setError(null);
  }

  function closeEditor() {
    setEditingId(null);
    setReportsToName("");
    setConfirmingRemoval(false);
    setError(null);
  }

  async function saveManager() {
    if (!editingParticipant || mutationLocked) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateCompanyParticipant(companyId, editingParticipant.id, {
        reportsToName: reportsToName.trim() || null,
      });
      setParticipants((current) => current.map((participant) =>
        participant.id === editingParticipant.id ? { ...participant, ...updated } : participant));
      closeEditor();
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Managerul nu a putut fi salvat.");
      router.refresh();
    } finally {
      setSaving(false);
    }
  }

  async function removeParticipant() {
    if (!editingParticipant || mutationLocked) return;
    setRemoving(true);
    setError(null);
    try {
      await deleteCompanyParticipant(
        companyId,
        editingParticipant.id,
        editingDirectReports.map((participant) => participant.id),
      );
      const directReportIds = new Set(editingDirectReports.map((participant) => participant.id));
      setParticipants((current) => current
        .filter((participant) => participant.id !== editingParticipant.id)
        .map((participant) => directReportIds.has(participant.id)
          ? { ...participant, reports_to_name: null }
          : participant));
      closeEditor();
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Participantul nu a putut fi șters.");
      router.refresh();
    } finally {
      setRemoving(false);
    }
  }

  return (
    <section
      className="overflow-hidden rounded-lg border border-border bg-surface"
      aria-labelledby="company-participants-title"
      aria-busy={query !== deferredQuery}
    >
      <header className="flex min-h-14 items-center justify-between gap-4 border-b border-border px-5 py-3">
        <h2 id="company-participants-title" className="text-base font-semibold text-foreground">Participanți</h2>
        <div className="flex items-center gap-4">
          <Link
            href={`/trainer/companies/${companyId}/audit`}
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            <HistoryIcon className="h-3.5 w-3.5" />
            Jurnal accesări
          </Link>
          <span className="text-sm font-medium tabular-nums text-muted-foreground">
            {visibleParticipants.length === participants.length
              ? participants.length
              : `${visibleParticipants.length} din ${participants.length}`}
          </span>
        </div>
      </header>
      {participants.length > 0 ? (
        <>
          <div className="border-b border-border p-4">
            <WorkspaceSearchInput
              id="company-participants-search"
              label="Caută participant"
              value={query}
              onValueChange={updateQuery}
              placeholder="Caută participanți"
              className="max-w-2xl"
            />
          </div>
          <span className="sr-only" role="status" aria-live="polite">
            {query !== deferredQuery ? "Se actualizează lista" : ""}
          </span>
          <div className="md:overflow-x-auto md:[scrollbar-width:thin]">
            <table className="block w-full text-left text-sm md:table md:min-w-[52rem] xl:min-w-0 xl:table-fixed">
              <colgroup>
                <col className="w-[22%]" />
                <col className="w-[28%]" />
                <col className="w-[18%]" />
                <col className="w-[20%]" />
                <col className="w-[8%]" />
                <col className="w-[4%]" />
              </colgroup>
              <thead className="hidden bg-muted/60 text-xs font-semibold text-muted-foreground md:table-header-group">
                <tr>
                  <th scope="col" className="min-w-52 px-5 py-3">Participant</th>
                  <th scope="col" className="min-w-56 px-4 py-3">Email</th>
                  <th scope="col" className="min-w-40 px-4 py-3">Rol</th>
                  <th scope="col" className="min-w-40 px-4 py-3">Manager</th>
                  <th scope="col" className="min-w-32 px-4 py-3">Cont</th>
                  <th scope="col" className="relative px-3 py-3 text-right">
                    <span className="sr-only">Acțiuni</span>
                  </th>
                </tr>
              </thead>
              <tbody className="block divide-y divide-border md:table-row-group">
                {visibleParticipants.length > 0 ? visibleParticipants.map((participant) => {
                  const hasPermanentAccount = hasPermanentParticipantAccount(participant);
                  return (
                    <tr key={participant.id} className="relative grid grid-cols-2 gap-x-4 gap-y-3 px-5 py-4 transition-colors hover:bg-muted/35 md:table-row md:px-0 md:py-0">
                      <td className="col-span-2 row-start-1 pr-12 font-semibold text-foreground md:px-5 md:py-4">
                        <span className="flex min-w-0 items-center gap-3">
                          <IdentityMark
                            kind="person"
                            label={participant.full_name}
                            seed={`participant:${participant.id}`}
                            paletteKey={participant.avatar_palette_key}
                            size="sm"
                          />
                          <span className="min-w-0 break-words">{participant.full_name}</span>
                        </span>
                      </td>
                      <td className="col-span-2 row-start-2 break-all text-muted-foreground md:px-4 md:py-4">
                        <span className="mb-1 block text-xs font-medium md:hidden">Email</span>
                        {participant.email ?? "Email lipsă"}
                      </td>
                      <td className="col-start-1 row-start-3 text-foreground md:px-4 md:py-4">
                        <span className="mb-1 block text-xs font-medium text-muted-foreground md:hidden">Rol</span>
                        {participant.position ?? (participant.role_group === "leadership" ? "Leadership" : "Membru")}
                      </td>
                      <td className="col-start-2 row-start-3 text-right text-muted-foreground md:px-4 md:py-4 md:text-left">
                        <span className="mb-1 block text-xs font-medium md:hidden">Manager</span>
                        {participant.reports_to_name ?? "Fără manager"}
                      </td>
                      <td className="col-span-2 row-start-4 border-t pt-3 md:border-0 md:px-4 md:py-4">
                        <span className="mb-1 block text-xs font-medium text-muted-foreground md:hidden">Cont</span>
                        <span className="inline-flex items-center gap-2 whitespace-nowrap font-medium text-foreground">
                          <span
                            aria-hidden="true"
                            className={hasPermanentAccount ? "size-2 rounded-full bg-success-ink" : "size-2 rounded-full bg-muted-foreground"}
                          />
                          {hasPermanentAccount ? "Activ" : "Necreat"}
                        </span>
                      </td>
                      <td className="absolute right-3 top-3 text-right md:static md:px-3 md:py-4">
                        <div className="flex items-center justify-end gap-1">
                          <Link
                            href={`/trainer/companies/${companyId}/participants/${participant.id}/preview`}
                            aria-label={`Vezi ca participant: ${participant.full_name}`}
                            title={`Vezi ca participant: ${participant.full_name}`}
                            className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                          >
                            <EyeIcon className="h-4 w-4" aria-hidden="true" />
                          </Link>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            disabled={mutationLocked}
                            aria-label={`Editează ${participant.full_name}`}
                            title={`Editează ${participant.full_name}`}
                            onClick={() => startEdit(participant)}
                            className="rounded-md text-muted-foreground shadow-none hover:text-burgundy"
                          >
                            <PencilIcon aria-hidden="true" strokeWidth={1.8} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                }) : (
                  <tr className="block md:table-row">
                    <td colSpan={6} className="block px-5 py-10 text-center text-sm text-muted-foreground md:table-cell">
                      Niciun participant pentru căutarea curentă.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p className="px-5 py-10 text-center text-sm text-muted-foreground">Niciun participant adăugat.</p>
      )}

      <Sheet
        open={Boolean(editingParticipant)}
        onOpenChange={(open) => {
          if (!open && !mutationLocked) closeEditor();
        }}
        labelledBy={confirmingRemoval ? "participant-removal-title" : "participant-edit-title"}
        describedBy={confirmingRemoval ? "participant-removal-description" : "participant-edit-description"}
      >
        {editingParticipant ? (
          confirmingRemoval ? (
            <ParticipantRemovalSheetContent
              participant={editingParticipant}
              directReports={editingDirectReports}
              scope="company"
              removing={removing}
              error={error}
              onCancel={() => {
                setConfirmingRemoval(false);
                setError(null);
              }}
              onConfirm={() => void removeParticipant()}
            />
          ) : (
            <div className="flex h-full min-w-0 flex-col">
              <SheetHeader className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <h2 id="participant-edit-title" className="text-lg font-semibold text-foreground">
                    Editează managerul
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
                  disabled={mutationLocked}
                  onClick={closeEditor}
                  className="-mr-2 shrink-0 text-muted-foreground hover:text-foreground"
                >
                  <XIcon aria-hidden="true" strokeWidth={1.8} />
                </Button>
              </SheetHeader>
              <SheetBody aria-busy={saving}>
                {error ? (
                  <InlineFeedback tone="danger" className="mb-5 px-4 py-3">
                    {error}
                  </InlineFeedback>
                ) : null}
                <ParticipantManagerSelect
                  participantId={editingParticipant.id}
                  participants={participants}
                  value={reportsToName}
                  disabled={saving}
                  onChange={setReportsToName}
                />
                <p className="mt-4 text-sm leading-6 text-muted-foreground">
                  Modificarea actualizează relația curentă din companie. Sarcinile și rezultatele deja create nu se schimbă.
                </p>
                {saving ? (
                  <OperationFeedback
                    title="Salvăm managerul"
                    detail="Actualizăm profilul participantului."
                    className="mt-5"
                  />
                ) : null}
              </SheetBody>
              <SheetFooter className="flex items-center justify-between gap-3">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={saving}
                  onClick={() => setConfirmingRemoval(true)}
                  className="text-destructive hover:bg-destructive/8 hover:text-destructive"
                >
                  Șterge din companie
                </Button>
                <div className="flex items-center gap-2">
                  <Button type="button" variant="outline" size="sm" disabled={saving} onClick={closeEditor}>
                    Anulează
                  </Button>
                  <Button type="button" size="sm" disabled={saving} onClick={() => void saveManager()}>
                    {saving ? <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" /> : null}
                    {saving ? "Salvăm managerul" : "Salvează managerul"}
                  </Button>
                </div>
              </SheetFooter>
            </div>
          )
        ) : null}
      </Sheet>
    </section>
  );
}
