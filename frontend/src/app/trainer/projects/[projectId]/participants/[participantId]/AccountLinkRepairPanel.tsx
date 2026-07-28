"use client";

import { useState } from "react";
import { Loader2Icon, ShieldAlertIcon } from "lucide-react";

import {
  repairParticipantAccountLink,
  type ParticipantAccountLinkRepairAction,
  type ParticipantAccountLinkStatus,
} from "@/api/companies";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export function AccountLinkRepairPanel({
  companyId,
  participantId,
  initialStatus,
}: {
  companyId: string;
  participantId: string;
  initialStatus: ParticipantAccountLinkStatus | null;
}) {
  const [status, setStatus] = useState(initialStatus);
  const [action, setAction] = useState<ParticipantAccountLinkRepairAction | null>(null);
  const [confirmationEmail, setConfirmationEmail] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{ tone: "success" | "error"; message: string } | null>(null);

  if (!status) {
    return (
      <section className="border-y border-border px-5 py-4">
        <h2 className="text-sm font-semibold text-foreground">Legătură cont</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Starea contului nu este disponibilă pentru acest participant.
        </p>
      </section>
    );
  }

  const canLinkMatchingAccount = Boolean(
    status.matching_email_account && !status.matching_account_is_linked,
  );
  const canUnlink = Boolean(status.linked_account);

  const startRepair = (nextAction: ParticipantAccountLinkRepairAction) => {
    setAction(nextAction);
    setConfirmationEmail("");
    setReason("");
    setFeedback(null);
  };

  const submitRepair = async () => {
    if (!action || submitting) return;
    setSubmitting(true);
    setFeedback(null);
    try {
      const nextStatus = await repairParticipantAccountLink(companyId, participantId, {
        action,
        confirmationEmail,
        reason,
      });
      setStatus(nextStatus);
      setAction(null);
      setConfirmationEmail("");
      setReason("");
      setFeedback({
        tone: "success",
        message: "Legătura contului a fost actualizată și înregistrată în audit.",
      });
    } catch (error) {
      setFeedback({
        tone: "error",
        message: error instanceof Error ? error.message : "Legătura contului nu a putut fi actualizată.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="border-y border-border">
      <details>
        <summary className="cursor-pointer list-none px-5 py-4 text-sm font-semibold text-foreground">
          Administrare legătură cont
        </summary>
        <div className="border-t border-border px-5 py-5">
          <div className="grid gap-4 md:grid-cols-2">
            <AccountState
              label="Cont legat acum"
              email={status.linked_account?.email}
              role={status.linked_account?.role}
              accountType={status.linked_account?.account_type}
              isShadow={status.linked_account?.is_shadow_account}
            />
            <AccountState
              label="Cont cu același email"
              email={status.matching_email_account?.email}
              role={status.matching_email_account?.role}
              accountType={status.matching_email_account?.account_type}
              isShadow={status.matching_email_account?.is_shadow_account}
            />
          </div>

          <Alert className="mt-5">
            <ShieldAlertIcon aria-hidden="true" />
            <AlertTitle>Operație sensibilă</AlertTitle>
            <AlertDescription>
              Sunt păstrate proiectele, răspunsurile și rezultatele. Sesiunile deschise din invitații sunt revocate.
            </AlertDescription>
          </Alert>

          {!action ? (
            <div className="mt-5 flex flex-wrap gap-2">
              {canLinkMatchingAccount ? (
                <Button type="button" onClick={() => startRepair("link_matching_email")}>
                  Leagă contul cu același email
                </Button>
              ) : null}
              {canUnlink ? (
                <Button type="button" variant="destructive" onClick={() => startRepair("unlink")}>
                  Deconectează contul
                </Button>
              ) : null}
              {!canLinkMatchingAccount && !canUnlink ? (
                <p className="text-sm text-muted-foreground">
                  Nu există încă un cont platformă cu emailul {status.participant_email}.
                </p>
              ) : null}
            </div>
          ) : (
            <div className="mt-5 max-w-2xl space-y-4">
              <div>
                <label htmlFor="account-link-confirmation" className="text-sm font-semibold text-foreground">
                  Scrie exact emailul participantului pentru confirmare
                </label>
                <Input
                  id="account-link-confirmation"
                  value={confirmationEmail}
                  onChange={(event) => setConfirmationEmail(event.target.value)}
                  placeholder={status.participant_email}
                  autoComplete="off"
                  className="mt-2"
                />
              </div>
              <div>
                <label htmlFor="account-link-reason" className="text-sm font-semibold text-foreground">
                  Motivul intervenției
                </label>
                <Textarea
                  id="account-link-reason"
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="Descrie conflictul verificat și motivul reparării."
                  className="mt-2 min-h-24"
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant={action === "unlink" ? "destructive" : "default"}
                  disabled={
                    submitting
                    || confirmationEmail.trim().toLowerCase() !== status.participant_email.toLowerCase()
                    || reason.trim().length < 10
                  }
                  onClick={() => void submitRepair()}
                >
                  {submitting ? <Loader2Icon data-icon="inline-start" className="animate-spin" /> : null}
                  Confirmă repararea
                </Button>
                <Button type="button" variant="outline" disabled={submitting} onClick={() => setAction(null)}>
                  Anulează
                </Button>
              </div>
            </div>
          )}

          {feedback ? (
            <Alert variant={feedback.tone === "error" ? "destructive" : "default"} className="mt-5">
              <AlertTitle>{feedback.tone === "error" ? "Repararea a eșuat" : "Legătură actualizată"}</AlertTitle>
              <AlertDescription>{feedback.message}</AlertDescription>
            </Alert>
          ) : null}
        </div>
      </details>
    </section>
  );
}

function AccountState({
  label,
  email,
  role,
  accountType,
  isShadow,
}: {
  label: string;
  email?: string;
  role?: "trainer" | "participant";
  accountType?: "guest" | "registered";
  isShadow?: boolean;
}) {
  return (
    <div>
      <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-1 break-all text-sm font-semibold text-foreground">{email ?? "Niciun cont"}</p>
      {email ? (
        <p className="mt-1 text-xs text-muted-foreground">
          {accountType === "guest" || (!accountType && isShadow)
            ? "Cont temporar din invitație"
            : role === "trainer"
              ? "Cont permanent de trainer"
              : "Cont permanent de participant"}
        </p>
      ) : null}
    </div>
  );
}
