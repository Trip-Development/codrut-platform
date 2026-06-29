"use client";

import { FormEvent, useState } from "react";

import { changePassword } from "@/api/auth";

type DetailRow = {
  label: string;
  value: string;
  tone?: "default" | "accent";
  color?: string;
};

type AccountSettingsPanelProps = {
  eyebrow: string;
  title: string;
  description: string;
  accountRows: DetailRow[];
  contextRows: DetailRow[];
  notes: string[];
  passwordEnabled: boolean;
};

export function AccountSettingsPanel({
  eyebrow,
  title,
  description,
  accountRows,
  contextRows,
  notes,
  passwordEnabled,
}: AccountSettingsPanelProps) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [status, setStatus] = useState<{ kind: "success" | "error"; message: string } | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus(null);

    if (newPassword.length < 12) {
      setStatus({ kind: "error", message: "Parola nouă trebuie să aibă cel puțin 12 caractere." });
      return;
    }

    if (newPassword !== confirmPassword) {
      setStatus({ kind: "error", message: "Confirmarea nu se potrivește cu parola nouă." });
      return;
    }

    setIsSaving(true);
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setStatus({ kind: "success", message: "Parola a fost actualizată." });
    } catch (error) {
      setStatus({
        kind: "error",
        message: error instanceof Error ? error.message : "Parola nu a putut fi actualizată.",
      });
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_24rem]">
      <section className="surface-panel overflow-hidden p-0">
        <div className="border-b border-[var(--border)] px-5 py-4 md:px-6">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">{eyebrow}</p>
          <h2 className="mt-2 font-display text-2xl font-semibold text-foreground">{title}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/62">{description}</p>
        </div>

        <div className="grid gap-0 lg:grid-cols-2">
          <SettingsList title="Cont" rows={accountRows} />
          <SettingsList title="Context operațional" rows={contextRows} />
        </div>
      </section>

      <aside className="surface-panel p-5 md:p-6">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">Securitate</p>
        <h2 className="mt-2 font-display text-xl font-semibold text-foreground">Schimbă parola</h2>
        <p className="mt-2 text-sm leading-6 text-foreground/62">
          Introdu parola curentă, apoi setează o parolă nouă de minimum 12 caractere.
        </p>

        {passwordEnabled ? (
          <form className="mt-5 grid gap-3" onSubmit={handleSubmit}>
            <PasswordField
              label="Parola curentă"
              value={currentPassword}
              onChange={setCurrentPassword}
              autoComplete="current-password"
            />
            <PasswordField
              label="Parolă nouă"
              value={newPassword}
              onChange={setNewPassword}
              autoComplete="new-password"
            />
            <PasswordField
              label="Confirmă parola nouă"
              value={confirmPassword}
              onChange={setConfirmPassword}
              autoComplete="new-password"
            />

            {status ? (
              <p
                className={`rounded-2xl px-4 py-3 text-sm font-semibold ${
                  status.kind === "success"
                    ? "border border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200"
                    : "border border-red-500/25 bg-red-500/10 text-red-700 dark:text-red-200"
                }`}
                role="status"
              >
                {status.message}
              </p>
            ) : null}

            <button
              type="submit"
              className="btn-primary mt-1"
              disabled={isSaving || !currentPassword || !newPassword || !confirmPassword}
            >
              {isSaving ? "Se actualizează..." : "Actualizează parola"}
            </button>
          </form>
        ) : (
          <p className="mt-5 rounded-2xl border border-[var(--border)] bg-surface-muted px-4 py-3 text-sm leading-6 text-foreground/62">
            Schimbarea parolei este disponibilă doar pentru conturi autentificate.
          </p>
        )}

        <div className="mt-6 border-t border-[var(--border)] pt-5">
          <h3 className="text-sm font-bold text-foreground">Note</h3>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-foreground/62">
            {notes.map((note) => (
              <li key={note} className="flex gap-2">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-burgundy/70" />
                <span>{note}</span>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}

function SettingsList({ title, rows }: { title: string; rows: DetailRow[] }) {
  return (
    <div className="border-t border-[var(--border)] p-5 md:p-6 lg:border-r lg:border-t-0 last:lg:border-r-0">
      <h3 className="text-sm font-bold text-foreground">{title}</h3>
      <dl className="mt-4 divide-y divide-[var(--border)]">
        {rows.map((row) => (
          <div key={row.label} className="grid gap-1 py-3 sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-4">
            <dt className="text-xs font-bold uppercase tracking-wider text-foreground/45">{row.label}</dt>
            <dd
              className={`flex min-w-0 items-center gap-2 break-words text-sm font-semibold ${
                row.tone === "accent" ? "text-burgundy" : "text-foreground"
              }`}
            >
              {row.color ? (
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: row.color }}
                />
              ) : null}
              <span className="min-w-0 break-words">{row.value}</span>
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function PasswordField({
  label,
  value,
  onChange,
  autoComplete,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
}) {
  return (
    <label className="grid gap-2">
      <span className="text-xs font-bold uppercase tracking-wider text-foreground/45">{label}</span>
      <input
        className="control-input"
        type="password"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete={autoComplete}
      />
    </label>
  );
}
