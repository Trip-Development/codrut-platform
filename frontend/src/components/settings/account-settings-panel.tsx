"use client";

import { FormEvent, useRef, useState } from "react";
import { CheckCircle2Icon, Loader2Icon } from "lucide-react";

import { changePassword } from "@/api/auth";
import {
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  PASSWORD_POLICY_HELP,
  validatePasswordPolicy,
} from "@/api/password-policy";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/cn";

export type AccountSettingsDetailRow = {
  label: string;
  value: string;
  tone?: "default" | "accent";
  color?: string;
};

type AccountSettingsPanelProps = {
  accountRows: AccountSettingsDetailRow[];
  contextRows?: AccountSettingsDetailRow[];
  notes?: string[];
  passwordEnabled: boolean;
  passwordFieldIdPrefix?: string;
  reauthHref?: string;
};

export function AccountSettingsPanel({
  accountRows,
  contextRows,
  notes,
  passwordEnabled,
  passwordFieldIdPrefix = "trainer",
  reauthHref = "/trainer/login",
}: AccountSettingsPanelProps) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [status, setStatus] = useState<{ kind: "success" | "error"; message: string } | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const savingRef = useRef(false);
  const [reauthRequired, setReauthRequired] = useState(false);
  const hasContextRows = Boolean(contextRows?.length);
  const hasNotes = Boolean(notes?.length);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (savingRef.current || reauthRequired) return;
    setStatus(null);
    setReauthRequired(false);

    const passwordError = validatePasswordPolicy(newPassword);
    if (passwordError) {
      setStatus({ kind: "error", message: passwordError });
      return;
    }

    if (newPassword !== confirmPassword) {
      setStatus({ kind: "error", message: "Confirmarea nu se potrivește cu parola nouă." });
      return;
    }

    savingRef.current = true;
    setIsSaving(true);
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setReauthRequired(true);
      setStatus({
        kind: "success",
        message: "Parola a fost actualizată. Pentru securitate, sesiunile active au fost închise.",
      });
    } catch (error) {
      setStatus({
        kind: "error",
        message: error instanceof Error ? error.message : "Parola nu a putut fi actualizată.",
      });
    } finally {
      savingRef.current = false;
      setIsSaving(false);
    }
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface text-foreground shadow-[0_1px_0_rgba(24,24,27,0.04)]">
      <section className="p-5 md:p-7">
        <h2 className="text-xl font-semibold text-foreground">Profil</h2>
        <div className={cn("mt-5 grid gap-7 border-t border-border pt-5", hasContextRows ? "lg:grid-cols-2" : null)}>
          <SettingsList title="Cont" rows={accountRows} />
          {hasContextRows ? (
            <div className="border-t border-border pt-6 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
              <SettingsList title="Program" rows={contextRows ?? []} />
            </div>
          ) : null}
        </div>
      </section>

      <section className="grid gap-6 border-t border-border p-5 md:p-7 lg:grid-cols-[13rem_minmax(0,32rem)] lg:gap-10">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Securitate</h2>
        </div>

        <div className="min-w-0">
          <h3 className="text-base font-semibold text-foreground">Schimbă parola</h3>
          {passwordEnabled ? (
            reauthRequired ? (
              <PasswordReauthPrompt
                message={status?.message ?? "Pentru securitate, intră din nou în cont."}
                reauthHref={reauthHref}
              />
            ) : (
              <form className="mt-5 flex flex-col gap-4" onSubmit={handleSubmit} aria-busy={isSaving}>
                <FieldGroup>
                  <PasswordField
                    id={`${passwordFieldIdPrefix}-current-password`}
                    label="Parola curentă"
                    value={currentPassword}
                    onChange={setCurrentPassword}
                    autoComplete="current-password"
                    disabled={isSaving || reauthRequired}
                    required
                  />
                  <PasswordField
                    id={`${passwordFieldIdPrefix}-new-password`}
                    label="Parolă nouă"
                    value={newPassword}
                    onChange={setNewPassword}
                    autoComplete="new-password"
                    disabled={isSaving || reauthRequired}
                    required
                    showPolicy
                  />
                  <PasswordField
                    id={`${passwordFieldIdPrefix}-confirm-password`}
                    label="Confirmă parola nouă"
                    value={confirmPassword}
                    onChange={setConfirmPassword}
                    autoComplete="new-password"
                    disabled={isSaving || reauthRequired}
                    required
                  />
                </FieldGroup>

                {status ? (
                  <InlineFeedback tone={status.kind === "error" ? "danger" : "neutral"}>
                    {status.message}
                  </InlineFeedback>
                ) : null}

                <Button
                  type="submit"
                  className="mt-1 w-fit"
                  disabled={reauthRequired || isSaving || !currentPassword || !newPassword || !confirmPassword}
                >
                  {isSaving ? <Loader2Icon data-icon="inline-start" className="animate-spin" /> : null}
                  {isSaving ? "Actualizăm parola" : "Actualizează parola"}
                </Button>
              </form>
            )
          ) : (
            <p className="mt-4 text-sm leading-6 text-muted-foreground">
              Autentifică-te pentru a schimba parola.
            </p>
          )}

          {hasNotes ? (
            <div className="mt-6 border-t border-border pt-5">
              <h3 className="text-sm font-semibold text-foreground">Note</h3>
              <ul className="mt-3 flex flex-col gap-2 text-sm leading-6 text-muted-foreground">
                {(notes ?? []).map((note) => (
                  <li key={note} className="flex gap-2">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-muted-foreground" />
                    <span>{note}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function PasswordReauthPrompt({ message, reauthHref }: { message: string; reauthHref: string }) {
  return (
    <div className="mt-5 flex flex-col gap-4" role="status" aria-live="polite">
      <div className="rounded-lg border border-primary/18 bg-primary/6 p-4">
        <div className="flex items-start gap-3">
          <CheckCircle2Icon aria-hidden="true" className="size-5 shrink-0 text-success-ink" strokeWidth={1.8} />
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-foreground">Parola a fost actualizată</h3>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">{message}</p>
          </div>
        </div>
      </div>
      <Button asChild className="w-full">
        <a href={reauthHref}>Autentifică-te din nou</a>
      </Button>
    </div>
  );
}

function SettingsList({ title, rows }: { title: string; rows: AccountSettingsDetailRow[] }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      <dl className="mt-4 divide-y divide-border">
        {rows.map((row) => (
          <div key={row.label} className="grid gap-1 py-3 sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-4">
            <dt className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{row.label}</dt>
            <dd
              className={cn(
                "flex min-w-0 items-center gap-2 break-words text-sm font-semibold",
                row.tone === "accent" ? "text-brand-text" : "text-foreground",
              )}
            >
              {row.color ? (
                <span className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: row.color }} />
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
  id,
  label,
  value,
  onChange,
  autoComplete,
  disabled = false,
  required = false,
  showPolicy = false,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
  disabled?: boolean;
  required?: boolean;
  showPolicy?: boolean;
}) {
  return (
    <Field data-disabled={disabled || undefined}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Input
        id={id}
        type="password"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete={autoComplete}
        minLength={autoComplete === "new-password" ? PASSWORD_MIN_LENGTH : undefined}
        maxLength={PASSWORD_MAX_LENGTH}
        disabled={disabled}
        required={required}
      />
      {showPolicy ? <FieldDescription>{PASSWORD_POLICY_HELP}</FieldDescription> : null}
    </Field>
  );
}
