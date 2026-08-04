"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2Icon } from "lucide-react";

import { acceptCurrentTerms, getAuthenticatedSession } from "@/api/auth";
import { apiFetch, ensureCsrfToken } from "@/api/http";
import {
  exchangeInviteSession,
  isInviteSessionConflictError,
  type InviteBundle,
} from "@/api/invites";
import { getApiBaseUrl } from "@/api/runtime";
import { BrandMark } from "@/components/brand/brand-mark";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { cn } from "@/utils/cn";

type ValidInviteBundle = Extract<InviteBundle, { state: "valid" }>;

const CONSENT_FEEDBACK_MIN_MS = 450;
const INVITE_STORAGE_KEY = "codrut_invite";

function inviteStoragePayload(token: string, bundle: ValidInviteBundle) {
  return {
    email: bundle.participantEmail,
    token,
    fullName: bundle.participantFullName,
    anonymousName: bundle.anonymousName,
    isLeadership: bundle.isLeadership,
  };
}

function storeInviteForRegistration(token: string, bundle: ValidInviteBundle): void {
  try {
    window.sessionStorage?.setItem(INVITE_STORAGE_KEY, JSON.stringify(inviteStoragePayload(token, bundle)));
  } catch {
    // Registration shows an explicit missing-invite state if browser storage is unavailable.
  }
}

function waitForConsentFeedback(): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, CONSENT_FEEDBACK_MIN_MS);
  });
}

function safeInviteDestination(destination: string | null | undefined, fallback: string): string {
  return destination?.startsWith("/") && !destination.startsWith("//")
    ? destination
    : fallback;
}

export function inviteSwitchDestination(
  token: string,
  participantEmail: string,
  alreadyRegistered: boolean,
): string {
  if (!alreadyRegistered) return `/invite/${token}`;
  const returnTo = encodeURIComponent(`/invite/${token}`);
  return `/login?returnTo=${returnTo}&email=${encodeURIComponent(participantEmail)}`;
}

async function signOutForInviteSwitch(
  token: string,
  participantEmail: string,
  alreadyRegistered: boolean,
): Promise<void> {
  await ensureCsrfToken();
  const response = await apiFetch(`${getApiBaseUrl()}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok && response.status !== 401) {
    throw new Error("Nu am putut închide sesiunea curentă.");
  }
  window.location.assign(inviteSwitchDestination(token, participantEmail, alreadyRegistered));
}

export function InviteSessionExchange({
  token,
  bundle,
  children,
}: {
  token: string;
  bundle: ValidInviteBundle;
  children: ReactNode;
}) {
  const { replace } = useRouter();
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<"pending" | "ready" | "conflict" | "error">("pending");
  const [error, setError] = useState<string | null>(null);
  const [currentEmail, setCurrentEmail] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setState("pending");
    setError(null);

    void exchangeInviteSession(token)
      .then(async (result) => {
        if (!active) return;
        if (result.action === "dashboard_ready" || result.action === "login_required") {
          replace(safeInviteDestination(result.destination, "/participant"));
          return;
        }
        if (result.action === "account_switch_required") {
          const session = await getAuthenticatedSession();
          if (!active) return;
          setCurrentEmail(session?.user.email ?? null);
          setState("conflict");
          return;
        }
        setState("ready");
      })
      .catch(async (exchangeError: unknown) => {
        if (!active) return;
        if (isInviteSessionConflictError(exchangeError)) {
          const session = await getAuthenticatedSession();
          if (!active) return;
          setCurrentEmail(session?.user.email ?? null);
          setError(exchangeError.message);
          setState("conflict");
          return;
        }
        setError(
          exchangeError instanceof Error
            ? exchangeError.message
            : "Nu am putut pregăti accesul securizat.",
        );
        setState("error");
      });

    return () => {
      active = false;
    };
  }, [attempt, replace, token]);

  if (state === "ready") return <>{children}</>;

  const switchAccount = async () => {
    setState("pending");
    setError(null);
    try {
      await signOutForInviteSwitch(token, bundle.participantEmail, bundle.alreadyRegistered);
    } catch (exchangeError) {
      setError(
        exchangeError instanceof Error
          ? exchangeError.message
          : "Nu am putut schimba sesiunea activă.",
      );
      setState("error");
    }
  };

  return (
    <InviteFrame width="sm">
      <InvitePanel>
        {state === "pending" ? (
          <OperationFeedback
            title="Pregătim accesul securizat"
            detail="Verificăm invitația înainte de a deschide chestionarele."
          />
        ) : state === "conflict" ? (
          <Alert>
            <AlertTitle>Schimbă sesiunea activă?</AlertTitle>
            <AlertDescription>
              Ești autentificat{currentEmail ? ` ca ${currentEmail}` : ""}. Invitația este pentru{" "}
              {bundle.participantEmail}. Continuarea va deschide doar sarcinile acestei invitații.
            </AlertDescription>
          </Alert>
        ) : (
          <Alert variant="destructive">
            <AlertTitle>Accesul nu a putut fi pregătit</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {state === "conflict" ? (
          <Button type="button" onClick={() => void switchAccount()} className="mt-5 w-full">
            Intră cu contul invitat
          </Button>
        ) : null}
        {state === "error" ? (
          <Button type="button" onClick={() => setAttempt((value) => value + 1)} className="mt-5 w-full">
            Reîncearcă
          </Button>
        ) : null}
      </InvitePanel>
    </InviteFrame>
  );
}

export function InviteConsentGate({
  token,
  bundle,
  children,
}: {
  token: string;
  bundle: ValidInviteBundle;
  children: ReactNode;
}) {
  const { refresh, replace } = useRouter();
  const [termsChecked, setTermsChecked] = useState(false);
  const [consentSaved, setConsentSaved] = useState(false);
  const [consentSubmitting, setConsentSubmitting] = useState(false);
  const [consentError, setConsentError] = useState<string | null>(null);
  const [sessionConflict, setSessionConflict] = useState(false);
  const [currentEmail, setCurrentEmail] = useState<string | null>(null);
  const consentSubmittingRef = useRef(false);

  useEffect(() => {
    storeInviteForRegistration(token, bundle);
  }, [bundle, token]);

  const handleAcceptTerms = async () => {
    if (consentSubmittingRef.current) return;

    consentSubmittingRef.current = true;
    setConsentError(null);
    setConsentSubmitting(true);
    try {
      const minimumFeedback = waitForConsentFeedback();
      const exchange = await exchangeInviteSession(token);
      if (exchange.action === "dashboard_ready" || exchange.action === "login_required") {
        replace(safeInviteDestination(exchange.destination, "/participant"));
        return;
      }
      if (exchange.action === "account_switch_required") {
        const session = await getAuthenticatedSession();
        setCurrentEmail(session?.user.email ?? null);
        setSessionConflict(true);
        setConsentError("Invitația aparține unui alt cont.");
        return;
      }
      const acceptedUser = await acceptCurrentTerms();
      if (!acceptedUser.consentCurrent) {
        throw new Error("Acordul nu a fost confirmat de server. Reîncearcă.");
      }
      await minimumFeedback;
      refresh();
      setConsentSaved(true);
    } catch (err) {
      if (isInviteSessionConflictError(err)) {
        const session = await getAuthenticatedSession();
        setCurrentEmail(session?.user.email ?? null);
        setSessionConflict(true);
      }
      setConsentError(err instanceof Error ? err.message : "Nu am putut salva acordul de confidențialitate.");
    } finally {
      consentSubmittingRef.current = false;
      setConsentSubmitting(false);
    }
  };

  const handleSwitchAccount = async () => {
    consentSubmittingRef.current = true;
    setConsentSubmitting(true);
    setConsentError(null);
    try {
      await signOutForInviteSwitch(token, bundle.participantEmail, bundle.alreadyRegistered);
    } catch (err) {
      setConsentError(
        err instanceof Error ? err.message : "Nu am putut schimba sesiunea activă.",
      );
      setSessionConflict(false);
    } finally {
      consentSubmittingRef.current = false;
      setConsentSubmitting(false);
    }
  };

  if (consentSaved) {
    return <>{children}</>;
  }

  return (
    <InviteFrame width="md">
      <InvitePanel>
        <BrandMark size="lg" showText={false} className="mx-auto" />
        <h1 className="mt-8 text-center text-3xl font-semibold leading-tight tracking-normal">
          Confirmă confidențialitatea înainte de chestionare
        </h1>
        <p className="mx-auto mt-4 max-w-md text-center text-sm leading-6 text-muted-foreground">
          Vei răspunde ca <strong className="text-foreground">{bundle.anonymousName ?? "participant anonim"}</strong>{" "}
          pentru proiectul <strong className="text-foreground">{bundle.projectName}</strong>.
        </p>

        <Field
          orientation="horizontal"
          data-disabled={consentSubmitting ? "true" : undefined}
          className="mt-8 rounded-lg border bg-background p-4"
        >
          <Checkbox
            id="invite-terms"
            checked={termsChecked}
            disabled={consentSubmitting}
            onCheckedChange={(checked) => setTermsChecked(checked === true)}
            className="mt-1"
          />
          <div className="flex flex-col gap-1">
            <FieldLabel htmlFor="invite-terms" className="font-semibold">
              Accept regulile de confidențialitate și prelucrare a datelor.
            </FieldLabel>
            <FieldDescription>
              Citește{" "}
              <Link href="/confidentialitate" className="font-semibold text-primary hover:underline">
                politica de confidențialitate
              </Link>
              {" "}și{" "}
              <Link href="/termeni" className="font-semibold text-primary hover:underline">
                termenii de utilizare
              </Link>
              . Acordul permite completarea chestionarelor pentru proiectul asociat invitației.
            </FieldDescription>
          </div>
        </Field>

        {consentError ? (
          <Alert variant="destructive" className="mt-5">
            <AlertTitle>{sessionConflict ? "Schimbă sesiunea activă?" : "Acordul nu a fost salvat"}</AlertTitle>
            <AlertDescription>
              {sessionConflict
                ? `Ești autentificat${currentEmail ? ` ca ${currentEmail}` : ""}. Invitația este pentru ${bundle.participantEmail}.`
                : consentError}
            </AlertDescription>
          </Alert>
        ) : null}

        {consentSubmitting ? (
          <OperationFeedback
            className="mt-5"
            title="Pregătim accesul securizat"
            detail="Deschidem sarcinile proiectului."
          />
        ) : null}

        <Button
          type="button"
          onClick={() => {
            if (sessionConflict) {
              void handleSwitchAccount();
              return;
            }
            void handleAcceptTerms();
          }}
          disabled={!termsChecked || consentSubmitting}
          size="lg"
          className="mt-5 w-full"
        >
          {consentSubmitting ? <Loader2Icon data-icon="inline-start" className="animate-spin" /> : null}
          {consentSubmitting
            ? "Pregătim accesul"
            : sessionConflict
              ? "Intră cu contul invitat"
              : "Continuă la chestionare"}
        </Button>
      </InvitePanel>
    </InviteFrame>
  );
}

function InviteFrame({
  children,
  width,
}: {
  children: ReactNode;
  width: "sm" | "md" | "lg";
}) {
  const maxWidth = {
    sm: "max-w-md",
    md: "max-w-xl",
    lg: "max-w-5xl",
  }[width];

  return (
    <main className="flex min-h-[100dvh] items-center justify-center bg-background px-4 py-10 text-foreground md:px-6">
      <div className={cn("w-full", maxWidth)}>{children}</div>
    </main>
  );
}

function InvitePanel({ children }: { children: ReactNode }) {
  return (
    <section className="rounded-lg border bg-surface p-6 md:p-8">
      {children}
    </section>
  );
}
