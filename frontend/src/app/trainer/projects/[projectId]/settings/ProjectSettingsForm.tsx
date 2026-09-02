"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangleIcon,
  ArchiveIcon,
  HistoryIcon,
  Loader2Icon,
  RotateCcwIcon,
  SaveIcon,
  Trash2Icon,
} from "lucide-react";

import {
  archiveCompanyProject,
  permanentlyDeleteCompanyProject,
  restoreCompanyProject,
  updateCompanyProject,
  type CompanyProject,
  type CompanyProjectStatus,
  type ProjectLifecycleEvent,
} from "@/api/companies";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { SelectControl } from "@/components/ui/select-control";
import { Textarea } from "@/components/ui/textarea";
import {
  formatDateInputValue,
  formatRomanianDate,
  formatRomanianDateTime,
} from "@/utils/date-format";

const statusOptions: Array<{ value: CompanyProjectStatus; label: string }> = [
  { value: "draft", label: "În pregătire" },
  { value: "active", label: "Activ" },
  { value: "completed", label: "Finalizat" },
];

const labelClass = "text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground";

export type ProjectSettingsFormProps = {
  project: CompanyProject;
  lifecycleEvents?: ProjectLifecycleEvent[];
};

export function ProjectSettingsForm({
  project,
  lifecycleEvents = [],
}: ProjectSettingsFormProps) {
  const router = useRouter();
  const archived = project.status === "archived";
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description ?? "");
  const [projectType, setProjectType] = useState(project.project_type ?? "team_coaching");
  const [status, setStatus] = useState<CompanyProjectStatus>(project.status);
  const [startsAt, setStartsAt] = useState(dateInput(project.starts_at));
  const [dueAt, setDueAt] = useState(dateInput(project.due_at));
  const [formOpensAt, setFormOpensAt] = useState(dateInput(project.form_opens_at));
  const [formClosesAt, setFormClosesAt] = useState(dateInput(project.form_closes_at));
  const [showParticipantResults, setShowParticipantResults] = useState(
    project.show_participant_results ?? false,
  );
  const [confirmOpenResultsModal, setConfirmOpenResultsModal] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [messageTone, setMessageTone] = useState<"neutral" | "danger">("neutral");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [deleting, setDeleting] = useState(false);
  const deletingRef = useRef(false);
  const [restoring, setRestoring] = useState(false);
  const restoringRef = useRef(false);
  const [permanentlyDeleting, setPermanentlyDeleting] = useState(false);
  const permanentlyDeletingRef = useRef(false);
  const operationPending = saving || deleting || restoring || permanentlyDeleting;
  const formLocked = operationPending || archived;
  const canDelete = deleteConfirmation.trim() === project.name.trim();

  function handleToggleShowResults(nextValue: boolean) {
    if (formLocked) return;
    if (nextValue) {
      setConfirmOpenResultsModal(true);
    } else {
      setShowParticipantResults(false);
    }
  }

  function handleConfirmOpenResults() {
    setShowParticipantResults(true);
    setConfirmOpenResultsModal(false);
  }

  function handleCancelOpenResults() {
    setConfirmOpenResultsModal(false);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (archived || operationPending || savingRef.current) return;
    if (!name.trim()) {
      setFieldError("Completează numele proiectului.");
      setMessage(null);
      setMessageTone("neutral");
      return;
    }
    savingRef.current = true;
    setSaving(true);
    setMessage(null);
    setMessageTone("neutral");
    setFieldError(null);
    try {
      await updateCompanyProject(project.company_id, project.id, {
        name: name.trim(),
        description,
        projectType,
        status,
        startsAt: toIso(startsAt),
        dueAt: toIso(dueAt),
        formOpensAt: toIso(formOpensAt),
        formClosesAt: toIso(formClosesAt),
        showParticipantResults,
      });
      setMessage("Setările proiectului au fost salvate.");
      setMessageTone("neutral");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Setările nu au putut fi salvate.");
      setMessageTone("danger");
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  async function handleArchive(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (archived || deletingRef.current || savingRef.current) return;

    deletingRef.current = true;
    setDeleting(true);
    setMessage(null);
    setMessageTone("neutral");
    try {
      await archiveCompanyProject(project.company_id, project.id);
      router.push("/trainer/projects");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Proiectul nu a putut fi arhivat.");
      setMessageTone("danger");
      deletingRef.current = false;
      setDeleting(false);
    }
  }

  async function handleRestore() {
    if (!archived || operationPending || restoringRef.current) return;
    restoringRef.current = true;
    setRestoring(true);
    setMessage(null);
    try {
      await restoreCompanyProject(project.company_id, project.id);
      router.push(`/trainer/projects/${project.id}`);
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Proiectul nu a putut fi restaurat.");
      setMessageTone("danger");
      restoringRef.current = false;
      setRestoring(false);
    }
  }

  async function handlePermanentDelete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!archived || !canDelete || operationPending || permanentlyDeletingRef.current) return;
    permanentlyDeletingRef.current = true;
    setPermanentlyDeleting(true);
    setMessage(null);
    try {
      await permanentlyDeleteCompanyProject(
        project.company_id,
        project.id,
        deleteConfirmation.trim(),
      );
      router.push("/trainer/projects?view=archived");
      router.refresh();
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Proiectul nu a putut fi șters definitiv.",
      );
      setMessageTone("danger");
      permanentlyDeletingRef.current = false;
      setPermanentlyDeleting(false);
    }
  }

  return (
    <div className="flex max-w-6xl flex-col gap-8">
      <section className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_18rem]">
        <form onSubmit={handleSubmit} aria-busy={saving}>
          <h2 className="text-xl font-semibold text-foreground">Configurare</h2>

          {fieldError ? (
            <Alert id="project-settings-error" variant="destructive" className="mt-5 border-destructive/25 bg-destructive/6">
              <AlertTriangleIcon aria-hidden="true" strokeWidth={1.8} />
              <AlertDescription className="font-semibold text-destructive">{fieldError}</AlertDescription>
            </Alert>
          ) : null}

          <FieldGroup className="mt-5 grid gap-4 md:grid-cols-2">
            <SettingsField
              label="Nume proiect"
              value={name}
              onChange={setName}
              invalid={Boolean(fieldError && !name.trim())}
              describedBy={fieldError ? "project-settings-error" : undefined}
              disabled={formLocked}
            />

            <Field data-disabled={formLocked ? true : undefined}>
              <FieldLabel className={labelClass}>Status</FieldLabel>
              <SelectControl
                label="Status"
                value={status}
                onChange={(event) => setStatus(event.target.value as CompanyProjectStatus)}
                className="bg-surface"
                disabled={formLocked}
              >
                {archived ? <option value="archived">Arhivat</option> : null}
                {statusOptions.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </SelectControl>
            </Field>

            <SettingsField label="Tip proiect" value={projectType} onChange={setProjectType} disabled={formLocked} />
            <SettingsField label="Start proiect" value={startsAt} onChange={setStartsAt} type="date" disabled={formLocked} />
            <SettingsField label="Final proiect" value={dueAt} onChange={setDueAt} type="date" disabled={formLocked} />
            <SettingsField label="Formulare active din" value={formOpensAt} onChange={setFormOpensAt} type="date" disabled={formLocked} />
            <SettingsField label="Formulare active până la" value={formClosesAt} onChange={setFormClosesAt} type="date" disabled={formLocked} />

            <div className="rounded-lg border border-border bg-surface p-4 md:col-span-2">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <label htmlFor="project-show-participant-results" className="text-sm font-semibold text-foreground cursor-pointer">
                    Afișează rezultatele pentru participanți
                  </label>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    Când e oprit, participanții văd doar ce au completat și ce mai au de completat.
                  </p>
                </div>
                <div className="flex items-center pt-0.5">
                  <input
                    id="project-show-participant-results"
                    type="checkbox"
                    checked={showParticipantResults}
                    disabled={formLocked}
                    onChange={(e) => handleToggleShowResults(e.target.checked)}
                    className="size-4 rounded border-input text-primary focus:ring-primary disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer"
                  />
                </div>
              </div>
            </div>

            <Field className="md:col-span-2" data-disabled={formLocked ? true : undefined}>
              <FieldLabel htmlFor="project-settings-notes" className={labelClass}>Notițe</FieldLabel>
              <Textarea
                id="project-settings-notes"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={4}
                className="min-h-28 resize-y bg-surface"
                placeholder="Context intern, obiective, limitări sau observații operaționale."
                disabled={formLocked}
              />
            </Field>
          </FieldGroup>

          <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-border pt-4">
            <Button type="submit" disabled={formLocked}>
              {saving ? (
                <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" strokeWidth={1.8} />
              ) : (
                <SaveIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
              )}
              {saving ? "Salvăm setările" : "Salvează setările"}
            </Button>
            {message ? (
              <InlineFeedback tone={messageTone} className="min-w-0 flex-1">
                {message}
              </InlineFeedback>
            ) : null}
          </div>

          {confirmOpenResultsModal ? (
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="confirm-open-results-title"
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs"
            >
              <div className="w-full max-w-md rounded-lg border border-border bg-surface p-6 shadow-xl">
                <h3 id="confirm-open-results-title" className="text-base font-semibold text-foreground">
                  Deschizi rezultatele pentru participanți?
                </h3>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  Sigur deschizi rezultatele pentru toți participanții din acest proiect?
                </p>
                <div className="mt-6 flex justify-end gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleCancelOpenResults}
                  >
                    Anulează
                  </Button>
                  <Button
                    type="button"
                    onClick={handleConfirmOpenResults}
                  >
                    Da, deschide rezultatele
                  </Button>
                </div>
              </div>
            </div>
          ) : null}

          {saving ? (
            <OperationFeedback
              className="mt-4"
              title="Salvăm setările proiectului"
              detail="Actualizăm proiectul."
            />
          ) : null}
        </form>

        <aside className="border-l border-border pl-5">
          <h3 className="text-sm font-semibold text-foreground">Calendar curent</h3>
          <dl className="mt-4 grid gap-4">
            <ProjectFact label="Start proiect" value={formatDateLabel(project.starts_at)} />
            <ProjectFact label="Final proiect" value={formatDateLabel(project.due_at)} />
            <ProjectFact label="Formulare active" value={formatRange(project.form_opens_at, project.form_closes_at)} />
            <ProjectFact label="Ultima actualizare" value={formatDateLabel(project.updated_at)} />
          </dl>
        </aside>
      </section>

      {archived ? (
        <section className="border-t border-border pt-6">
          <h2 className="text-lg font-semibold text-foreground">Proiect arhivat</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Participanții companiei și toate datele proiectului sunt păstrate. Poți restaura
            proiectul fără pierderi.
          </p>
          <Button
            type="button"
            className="mt-5"
            disabled={operationPending}
            onClick={handleRestore}
          >
            {restoring ? (
              <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" />
            ) : (
              <RotateCcwIcon data-icon="inline-start" aria-hidden="true" />
            )}
            {restoring ? "Restaurăm proiectul" : "Restaurează proiectul"}
          </Button>

          <div className="mt-8 border-t border-destructive/25 pt-6">
            <h3 className="text-base font-semibold text-destructive">Ștergere definitivă</h3>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Doar proprietarul companiei poate continua. Acțiunea șterge definitiv proiectul,
              răspunsurile și rapoartele asociate; participanții rămân în companie.
            </p>
            <form
              onSubmit={handlePermanentDelete}
              className="mt-5 grid gap-3 md:grid-cols-[minmax(0,1fr)_15rem] md:items-end"
              aria-busy={permanentlyDeleting}
            >
              <Field data-disabled={operationPending ? true : undefined}>
                <FieldLabel htmlFor="project-delete-confirmation" className={labelClass}>
                  Scrie numele proiectului pentru confirmare
                </FieldLabel>
                <Input
                  id="project-delete-confirmation"
                  value={deleteConfirmation}
                  onChange={(event) => setDeleteConfirmation(event.target.value)}
                  placeholder={project.name}
                  className="border-destructive/25 bg-surface focus-visible:border-destructive focus-visible:ring-destructive/20"
                  disabled={operationPending}
                />
              </Field>
              <Button
                type="submit"
                disabled={!canDelete || operationPending}
                variant="destructive"
              >
                {permanentlyDeleting ? (
                  <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" />
                ) : (
                  <Trash2Icon data-icon="inline-start" aria-hidden="true" />
                )}
                {permanentlyDeleting ? "Ștergem definitiv" : "Șterge definitiv"}
              </Button>
            </form>
          </div>
        </section>
      ) : (
        <section className="border-t border-border pt-6">
          <h2 className="text-lg font-semibold text-foreground">Arhivare proiect</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Proiectul dispare din listele curente, dar participanții, răspunsurile și rapoartele
            rămân păstrate. Îl poți restaura oricând din Arhivă.
          </p>
          <form onSubmit={handleArchive} className="mt-5" aria-busy={deleting}>
            <Button type="submit" disabled={operationPending} variant="outline">
              {deleting ? (
                <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" />
              ) : (
                <ArchiveIcon data-icon="inline-start" aria-hidden="true" />
              )}
              {deleting ? "Arhivăm proiectul" : "Arhivează proiectul"}
            </Button>
          </form>
        </section>
      )}

      {lifecycleEvents.length > 0 ? (
        <section className="border-t border-border pt-6">
          <h2 className="inline-flex items-center gap-2 text-lg font-semibold text-foreground">
            <HistoryIcon aria-hidden="true" className="size-4" />
            Istoric proiect
          </h2>
          <ol className="mt-4 divide-y divide-border rounded-lg border">
            {lifecycleEvents.map((event) => (
              <li key={event.id} className="grid gap-1 px-4 py-3 text-sm sm:grid-cols-[1fr_auto]">
                <span className="font-semibold text-foreground">
                  {lifecycleActionLabel(event.action)}
                </span>
                <time className="text-muted-foreground" dateTime={event.created_at}>
                  {formatRomanianDateTime(event.created_at)}
                </time>
                <span className="text-muted-foreground sm:col-span-2">
                  {event.actor_email ?? "Cont eliminat"}
                </span>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </div>
  );
}

function SettingsField({
  label,
  value,
  onChange,
  type = "text",
  required = false,
  invalid = false,
  describedBy,
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  required?: boolean;
  invalid?: boolean;
  describedBy?: string;
  disabled?: boolean;
}) {
  const inputId = `project-settings-${label
    .toLocaleLowerCase("ro")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")}`;

  return (
    <Field data-invalid={invalid ? true : undefined} data-disabled={disabled ? true : undefined}>
      <FieldLabel htmlFor={inputId} className={labelClass}>{label}</FieldLabel>
      <Input
        id={inputId}
        type={type}
        required={required}
        aria-invalid={invalid}
        aria-describedby={describedBy}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
      />
    </Field>
  );
}

function ProjectFact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-sm font-semibold text-foreground">{value}</dd>
    </div>
  );
}

function dateInput(value: string | null): string {
  return formatDateInputValue(value);
}

function toIso(value: string): string | null {
  return value ? `${value}T00:00:00.000Z` : null;
}

function formatDateLabel(value: string | null): string {
  return formatRomanianDate(value, { fallback: "Neprogramat" });
}

function formatRange(start: string | null, end: string | null): string {
  if (!start && !end) return "Neprogramat";
  return `${formatDateLabel(start)} / ${formatDateLabel(end)}`;
}

function lifecycleActionLabel(action: ProjectLifecycleEvent["action"]): string {
  switch (action) {
    case "archived":
      return "Proiect arhivat";
    case "restored":
      return "Proiect restaurat";
    case "permanently_deleted":
      return "Proiect șters definitiv";
  }
}
