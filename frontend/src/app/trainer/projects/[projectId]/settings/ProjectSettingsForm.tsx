"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { updateCompanyProject, type CompanyProject, type CompanyProjectStatus } from "@/api/companies";

const statusOptions: Array<{ value: CompanyProjectStatus; label: string }> = [
  { value: "draft", label: "În pregătire" },
  { value: "active", label: "Activ" },
  { value: "completed", label: "Finalizat" },
  { value: "archived", label: "Arhivat" },
];

export function ProjectSettingsForm({ project }: { project: CompanyProject }) {
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
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) {
      setFieldError("Completează numele proiectului. Toate celelalte câmpuri pot rămâne goale și pot fi modificate ulterior.");
      setMessage(null);
      return;
    }
    setSaving(true);
    setMessage(null);
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
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Setările nu au putut fi salvate.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <p className="text-xs font-semibold text-burgundy/75">Setări proiect</p>
      <h2 className="mt-1 text-xl font-semibold text-foreground">Configurare operațională</h2>
      {fieldError ? (
        <p id="project-settings-error" className="mt-4 rounded-xl border border-burgundy/20 bg-burgundy/10 px-4 py-3 text-sm font-semibold text-burgundy">
          {fieldError}
        </p>
      ) : null}
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <Field
          label="Nume proiect"
          value={name}
          onChange={setName}
          invalid={Boolean(fieldError && !name.trim())}
          describedBy={fieldError ? "project-settings-error" : undefined}
        />
        <label className="block text-xs font-bold text-foreground/58">
          Status
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value as CompanyProjectStatus)}
            className="mt-1 min-h-11 w-full rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-sm font-semibold text-foreground outline-none focus:border-burgundy/45"
          >
            {statusOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <Field label="Tip proiect" value={projectType} onChange={setProjectType} />
        <Field label="Start proiect" value={startsAt} onChange={setStartsAt} type="date" />
        <Field label="Final proiect" value={dueAt} onChange={setDueAt} type="date" />
        <Field label="Formulare active din" value={formOpensAt} onChange={setFormOpensAt} type="date" />
        <Field label="Formulare active până la" value={formClosesAt} onChange={setFormClosesAt} type="date" />
        <label className="block text-xs font-bold text-foreground/58 md:col-span-2">
          Notițe
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            rows={4}
            className="mt-1 w-full resize-none rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-sm font-medium text-foreground outline-none focus:border-burgundy/45"
          />
        </label>
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={saving}
          className="tap-soft rounded-full bg-burgundy px-5 py-2.5 text-sm font-bold text-white hover:bg-burgundy-700 disabled:cursor-not-allowed disabled:opacity-45"
        >
          {saving ? "Se salvează..." : "Salvează setările"}
        </button>
        {message ? <p className="text-sm font-semibold text-foreground/62">{message}</p> : null}
      </div>
    </form>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  required = false,
  invalid = false,
  describedBy,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  required?: boolean;
  invalid?: boolean;
  describedBy?: string;
}) {
  return (
    <label className="block text-xs font-bold text-foreground/58">
      {label}
      <input
        type={type}
        required={required}
        aria-invalid={invalid}
        aria-describedby={describedBy}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 min-h-11 w-full rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-sm font-semibold text-foreground outline-none focus:border-burgundy/45"
      />
    </label>
  );
}

function dateInput(value: string | null): string {
  return value ? value.slice(0, 10) : "";
}

function toIso(value: string): string | null {
  return value ? `${value}T00:00:00.000Z` : null;
}
