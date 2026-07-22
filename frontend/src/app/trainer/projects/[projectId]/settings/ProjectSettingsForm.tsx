"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangleIcon,
  Loader2Icon,
  SaveIcon,
  Trash2Icon,
} from "lucide-react";

import { deleteCompanyProject, updateCompanyProject, type CompanyProject, type CompanyProjectStatus } from "@/api/companies";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { SelectControl } from "@/components/ui/select-control";
import { Textarea } from "@/components/ui/textarea";
import { formatDateInputValue, formatRomanianDate } from "@/utils/date-format";

const statusOptions: Array<{ value: CompanyProjectStatus; label: string }> = [
  { value: "draft", label: "În pregătire" },
  { value: "active", label: "Activ" },
  { value: "completed", label: "Finalizat" },
  { value: "archived", label: "Arhivat" },
];

const labelClass = "text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground";

export type ProjectSettingsFormProps = {
  project: CompanyProject;
};

export function ProjectSettingsForm({ project }: ProjectSettingsFormProps) {
  const router = useRouter();
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description ?? "");
  const [projectType, setProjectType] = useState(project.project_type ?? "team_coaching");
  const [status, setStatus] = useState<CompanyProjectStatus>(project.status);
  const [startsAt, setStartsAt] = useState(dateInput(project.starts_at));
  const [dueAt, setDueAt] = useState(dateInput(project.due_at));
  const [formOpensAt, setFormOpensAt] = useState(dateInput(project.form_opens_at));
  const [formClosesAt, setFormClosesAt] = useState(dateInput(project.form_closes_at));
  const [message, setMessage] = useState<string | null>(null);
  const [messageTone, setMessageTone] = useState<"neutral" | "danger">("neutral");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [deleting, setDeleting] = useState(false);
  const deletingRef = useRef(false);
  const operationLocked = saving || deleting;
  const canDelete = deleteConfirmation.trim() === project.name.trim();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (deletingRef.current || savingRef.current) return;
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

  async function handleDelete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canDelete || deletingRef.current || savingRef.current) return;

    deletingRef.current = true;
    setDeleting(true);
    setMessage(null);
    setMessageTone("neutral");
    try {
      await deleteCompanyProject(project.company_id, project.id);
      router.push("/trainer/projects");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Proiectul nu a putut fi șters.");
      setMessageTone("danger");
      deletingRef.current = false;
      setDeleting(false);
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
              disabled={operationLocked}
            />

            <Field data-disabled={operationLocked ? true : undefined}>
              <FieldLabel className={labelClass}>Status</FieldLabel>
              <SelectControl
                label="Status"
                value={status}
                onChange={(event) => setStatus(event.target.value as CompanyProjectStatus)}
                className="bg-surface"
                disabled={operationLocked}
              >
                {statusOptions.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </SelectControl>
            </Field>

            <SettingsField label="Tip proiect" value={projectType} onChange={setProjectType} disabled={operationLocked} />
            <SettingsField label="Start proiect" value={startsAt} onChange={setStartsAt} type="date" disabled={operationLocked} />
            <SettingsField label="Final proiect" value={dueAt} onChange={setDueAt} type="date" disabled={operationLocked} />
            <SettingsField label="Formulare active din" value={formOpensAt} onChange={setFormOpensAt} type="date" disabled={operationLocked} />
            <SettingsField label="Formulare active până la" value={formClosesAt} onChange={setFormClosesAt} type="date" disabled={operationLocked} />

            <Field className="md:col-span-2" data-disabled={operationLocked ? true : undefined}>
              <FieldLabel htmlFor="project-settings-notes" className={labelClass}>Notițe</FieldLabel>
              <Textarea
                id="project-settings-notes"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={4}
                className="min-h-28 resize-y bg-surface"
                placeholder="Context intern, obiective, limitări sau observații operaționale."
                disabled={operationLocked}
              />
            </Field>
          </FieldGroup>

          <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-border pt-4">
            <Button type="submit" disabled={operationLocked}>
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

      <section className="border-t border-destructive/25 pt-6">
        <h2 className="text-lg font-semibold text-foreground">Ștergere proiect</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
          Ștergerea elimină proiectul și datele asociate. Confirmă cu numele proiectului.
        </p>

        <form
          onSubmit={handleDelete}
          className="mt-5 grid gap-3 md:grid-cols-[minmax(0,1fr)_15rem] md:items-end"
          aria-busy={deleting}
        >
          <Field data-disabled={operationLocked ? true : undefined}>
            <FieldLabel htmlFor="project-delete-confirmation" className={labelClass}>Scrie numele proiectului pentru confirmare</FieldLabel>
            <Input
              id="project-delete-confirmation"
              value={deleteConfirmation}
              onChange={(event) => setDeleteConfirmation(event.target.value)}
              placeholder={project.name}
              className="border-destructive/25 bg-surface focus-visible:border-destructive focus-visible:ring-destructive/20"
              disabled={operationLocked}
            />
          </Field>
          <Button
            type="submit"
            disabled={!canDelete || operationLocked}
            variant="destructive"
          >
            {deleting ? (
              <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" strokeWidth={1.8} />
            ) : (
              <Trash2Icon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
            )}
            {deleting ? "Ștergem proiectul" : "Șterge proiectul"}
          </Button>
        </form>

        {deleting ? (
          <OperationFeedback
            className="mt-4"
            tone="danger"
            title="Ștergem proiectul"
            detail="Eliminăm datele și revenim la lista de proiecte."
          />
        ) : null}
      </section>
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
