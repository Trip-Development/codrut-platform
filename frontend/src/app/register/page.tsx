"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2Icon, LockKeyholeIcon } from "lucide-react";

import { apiFetch } from "@/api/http";
import {
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  PASSWORD_POLICY_HELP,
  validatePasswordPolicy,
} from "@/api/password-policy";
import { getApiBaseUrl, isDemoFallbackEnabled } from "@/api/runtime";
import { CURRENT_TERMS_VERSION } from "@/api/terms";
import { AuthQuotePanel, AuthTextLink } from "@/components/auth/auth-shell";
import { BrandMark } from "@/components/brand/brand-mark";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { OperationFeedback } from "@/components/presentation/operation-feedback";

const INVITE_STORAGE_KEY = "codrut_invite";

type RegisterInviteData = {
  email?: string;
  token?: string;
  fullName?: string;
  isLeadership?: boolean;
};

function readStoredInvite(): RegisterInviteData | null {
  if (typeof window === "undefined") return null;
  try {
    const storedInvite = window.sessionStorage?.getItem(INVITE_STORAGE_KEY);
    if (!storedInvite) return null;
    return JSON.parse(storedInvite) as RegisterInviteData;
  } catch {
    return null;
  }
}

function storeInvite(inviteData: RegisterInviteData): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage?.setItem(INVITE_STORAGE_KEY, JSON.stringify(inviteData));
  } catch {
    // The current form state remains usable if browser storage is unavailable.
  }
}

function clearStoredInvite(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage?.removeItem(INVITE_STORAGE_KEY);
  } catch {
    // Ignore unavailable browser storage after successful registration.
  }
}

export default function RegisterPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);

  useEffect(() => {
    let inviteData = readStoredInvite();

    if (!inviteData) {
      if (!isDemoFallbackEnabled()) {
        setError("Invitația lipsește sau nu mai este activă. Folosește linkul primit pe email.");
        setLoading(false);
        return;
      }

      inviteData = {
        email: "lider.demo@example.com",
        token: "demo-token",
        fullName: "Lider Demo",
        isLeadership: true,
      };
      storeInvite(inviteData);
    }

    setEmail(inviteData.email || "lider.demo@example.com");
    setToken(inviteData.token || "demo-token");
    setLoading(false);
  }, [router]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (submittingRef.current) return;

    setError(null);

    const passwordError = validatePasswordPolicy(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }

    if (password !== confirmPassword) {
      setError("Parolele introduse nu coincid.");
      return;
    }

    if (!termsAccepted) {
      setError("Trebuie să accepți termenii de confidențialitate înainte de înregistrare.");
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);

    try {
      const res = await apiFetch(`${getApiBaseUrl()}/auth/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          email,
          password,
          token,
          terms_accepted: termsAccepted,
          terms_version: CURRENT_TERMS_VERSION,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error?.message || "Înregistrarea a eșuat. Reîncearcă.");
      }

      clearStoredInvite();
      router.push(`/invite/${token}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "A apărut o eroare la înregistrare.";
      setError(msg);
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <main className="flex min-h-[100dvh] items-center justify-center bg-background px-4 py-10 text-foreground">
        <section className="w-full max-w-md rounded-lg border bg-surface p-8 shadow-sm">
          <BrandMark size="lg" showText={false} className="mx-auto" />
          <OperationFeedback
            className="mt-8"
            title="Verificăm invitația"
            detail="Confirmăm că linkul de activare este încă valid."
            meta="în verificare"
          />
        </section>
      </main>
    );
  }

  return (
    <main className="grid min-h-[100dvh] bg-background text-foreground lg:grid-cols-[0.85fr_1.15fr]">
      <AuthQuotePanel variant="activation" />

      <section className="flex items-center justify-center px-4 py-10 md:px-8">
        <div className="w-full max-w-xl">
          <Link href="/" className="mb-10 inline-flex rounded-lg px-2 py-1 transition-colors hover:bg-muted lg:hidden">
            <BrandMark subtitle="Activare cont" />
          </Link>

          <div>
            <Badge variant="outline">Înregistrare</Badge>
            <h1 className="mt-5 text-4xl font-semibold leading-tight tracking-normal">
              Activează accesul permanent.
            </h1>
            <p className="mt-3 max-w-lg text-sm leading-6 text-muted-foreground">
              Emailul vine din invitație. Alege parola contului și confirmă acordul de confidențialitate.
            </p>
          </div>

          {error ? (
            <Alert variant="destructive" className="mt-6">
              <AlertTitle>Înregistrarea nu a reușit</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-5">
            <FieldGroup>
              <Field data-disabled>
                <div className="flex items-center justify-between gap-3">
                  <FieldLabel htmlFor="register-email">Email securizat</FieldLabel>
                  <Badge variant="secondary">
                    <LockKeyholeIcon data-icon="inline-start" />
                    Asociat invitației
                  </Badge>
                </div>
                <Input
                  id="register-email"
                  type="email"
                  value={email}
                  disabled
                  title="Adresa de email este blocată la cea specificată în invitație."
                />
              </Field>

              <Field data-invalid={Boolean(error) || undefined}>
                <FieldLabel htmlFor="register-password">Parolă</FieldLabel>
                <Input
                  id="register-password"
                  type="password"
                  placeholder="Parolă sigură"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  minLength={PASSWORD_MIN_LENGTH}
                  maxLength={PASSWORD_MAX_LENGTH}
                  disabled={submitting}
                  required
                  aria-invalid={Boolean(error) || undefined}
                />
                <FieldDescription>{PASSWORD_POLICY_HELP}</FieldDescription>
              </Field>

              <Field data-invalid={Boolean(error) || undefined}>
                <FieldLabel htmlFor="register-confirm-password">Confirmă parola</FieldLabel>
                <Input
                  id="register-confirm-password"
                  type="password"
                  placeholder="Reintrodu parola"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  autoComplete="new-password"
                  minLength={PASSWORD_MIN_LENGTH}
                  maxLength={PASSWORD_MAX_LENGTH}
                  disabled={submitting}
                  required
                  aria-invalid={Boolean(error) || undefined}
                />
              </Field>

              <Field orientation="horizontal" className="rounded-lg border bg-surface p-4">
                <Checkbox
                  id="register-terms"
                  checked={termsAccepted}
                  onCheckedChange={(checked) => setTermsAccepted(checked === true)}
                  disabled={submitting}
                  className="mt-1"
                />
                <div className="flex flex-col gap-1">
                  <FieldLabel htmlFor="register-terms" className="font-semibold">
                    Accept termenii și politica de confidențialitate.
                  </FieldLabel>
                  <FieldDescription>
                    Citește <Link href="/termeni" className="font-semibold text-primary hover:underline">termenii</Link>
                    {" și "}
                    <Link href="/confidentialitate" className="font-semibold text-primary hover:underline">politica de confidențialitate</Link>.
                  </FieldDescription>
                </div>
              </Field>
            </FieldGroup>

            {submitting ? (
              <OperationFeedback
                title="Creăm contul Cody"
                detail="Validăm invitația, parola și acordul de confidențialitate înainte de activare."
                meta="în activare"
              />
            ) : null}

            <Button type="submit" size="lg" disabled={submitting || !termsAccepted} className="w-full">
              {submitting ? <Loader2Icon data-icon="inline-start" className="animate-spin" /> : null}
              {submitting ? "Activăm contul" : "Finalizează înregistrarea"}
            </Button>
          </form>

          <div className="mt-8 flex flex-col gap-2 text-sm sm:flex-row sm:items-center sm:justify-between">
            <span className="font-medium text-muted-foreground">Ai deja cont?</span>
            <AuthTextLink href="/login">Intră în cont</AuthTextLink>
          </div>
        </div>
      </section>
    </main>
  );
}
