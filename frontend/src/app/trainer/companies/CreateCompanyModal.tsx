"use client";

import { useRef, useState, type FormEvent } from "react";
import { Loader2Icon, XIcon } from "lucide-react";

import { createCompany } from "@/api/companies";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ModalLayer } from "@/components/ui/modal-layer";

export type CreatedCompany = {
  id: string;
  name: string;
};

export type CreateCompanyModalProps = {
  onClose: () => void;
  onCreated: (company: CreatedCompany) => void;
  onMessage: (message: string) => void;
};

export function CreateCompanyModal({ onClose, onCreated, onMessage }: CreateCompanyModalProps) {
  const [name, setName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submittingRef = useRef(false);

  function closeIfIdle() {
    if (!isSubmitting) {
      onClose();
    }
  }

  async function handleCreateCompany(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submittingRef.current) return;

    const trimmedName = name.trim();
    if (!trimmedName) return;

    submittingRef.current = true;
    setIsSubmitting(true);
    setError(null);
    onMessage("");
    try {
      const created = await createCompany(trimmedName);
      onCreated(created);
      setName("");
      onClose();
      onMessage("Compania a fost creată și salvată.");
    } catch (error) {
      const nextError = error instanceof Error ? error.message : "Compania nu a putut fi creată.";
      setError(nextError);
      onMessage(nextError);
    } finally {
      submittingRef.current = false;
      setIsSubmitting(false);
    }
  }

  return (
    <ModalLayer
      labelledBy="create-company-title"
      onClose={closeIfIdle}
      closeOnBackdrop={!isSubmitting}
    >
      <div className="flex items-start justify-between gap-4">
        <h3 id="create-company-title" className="text-xl font-semibold text-foreground">
          Companie nouă
        </h3>
        <Button
          type="button"
          onClick={closeIfIdle}
          disabled={isSubmitting}
          variant="outline"
          size="icon-sm"
          aria-label="Închide"
        >
          <XIcon aria-hidden="true" strokeWidth={1.8} />
        </Button>
      </div>

      <form onSubmit={handleCreateCompany} className="mt-6">
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="company-name" className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              Nume companie
            </FieldLabel>
            <Input
              id="company-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Ex. Michelin România"
              disabled={isSubmitting}
              autoFocus
            />
          </Field>
          {error ? <InlineFeedback tone="danger">{error}</InlineFeedback> : null}
          {isSubmitting ? <p role="status" className="text-sm font-semibold text-muted-foreground">Creăm spațiul companiei</p> : null}
          <Button type="submit" disabled={isSubmitting || !name.trim()} className="w-full">
            {isSubmitting ? <Loader2Icon data-icon="inline-start" className="animate-spin" /> : null}
            {isSubmitting ? "Creăm compania" : "Salvează compania"}
          </Button>
        </FieldGroup>
      </form>
    </ModalLayer>
  );
}
