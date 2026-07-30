"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { Loader2Icon } from "lucide-react";

import { acceptCurrentTerms } from "@/api/auth";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";

export function ConsentForm() {
  const [accepted, setAccepted] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const savingRef = useRef(false);

  async function handleSubmit() {
    if (!accepted || savingRef.current) return;
    savingRef.current = true;
    setIsSaving(true);
    setError(null);
    try {
      const user = await acceptCurrentTerms();
      if (!user.consentCurrent) {
        throw new Error("Acordul nu a fost confirmat de server. Reîncearcă.");
      }
      window.location.assign("/participant");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Acordul nu a putut fi salvat.");
      savingRef.current = false;
      setIsSaving(false);
    }
  }

  return (
    <div className="mt-8">
      <Field orientation="horizontal" data-disabled={isSaving ? "true" : undefined}>
        <Checkbox
          id="participant-current-terms"
          checked={accepted}
          disabled={isSaving}
          onCheckedChange={(checked) => setAccepted(checked === true)}
          className="mt-1"
        />
        <div className="flex flex-col gap-1.5">
          <FieldLabel htmlFor="participant-current-terms" className="font-semibold">
            Accept politica de confidențialitate și termenii de utilizare.
          </FieldLabel>
          <FieldDescription>
            Citește{" "}
            <Link href="/confidentialitate" className="font-semibold text-burgundy hover:underline">
              politica de confidențialitate
            </Link>{" "}
            și{" "}
            <Link href="/termeni" className="font-semibold text-burgundy hover:underline">
              termenii
            </Link>
            .
          </FieldDescription>
        </div>
      </Field>

      {error ? (
        <Alert variant="destructive" className="mt-5">
          <AlertTitle>Acordul nu a fost salvat</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {isSaving ? (
        <OperationFeedback className="mt-5" title="Salvăm acordul" detail="Deschidem spațiul tău." />
      ) : null}

      <Button type="button" size="lg" className="mt-6 w-full" disabled={!accepted || isSaving} onClick={handleSubmit}>
        {isSaving ? <Loader2Icon data-icon="inline-start" className="animate-spin" /> : null}
        {isSaving ? "Salvăm acordul" : "Continuă"}
      </Button>
    </div>
  );
}
