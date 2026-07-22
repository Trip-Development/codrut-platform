"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Loader2Icon, Trash2Icon } from "lucide-react";

import { deleteCompany } from "@/api/companies";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";

export type CompanySettingsWorkspaceProps = {
  company: {
    id: string;
    name: string;
    stats: {
      totalParticipants: number;
      totalAssignments: number;
      completedAssignments: number;
      completionRate: number;
    };
  };
};

export function CompanySettingsWorkspace({ company }: CompanySettingsWorkspaceProps) {
  const router = useRouter();
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const deletingRef = useRef(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const confirmationMatches = confirmation.trim() === company.name;
  const canDelete = confirmationMatches && !isDeleting;

  async function handleDelete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canDelete || deletingRef.current) return;

    deletingRef.current = true;
    setIsDeleting(true);
    setMessage(null);
    try {
      await deleteCompany(company.id);
      router.push("/trainer/companies");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Compania nu a putut fi ștearsă.");
      deletingRef.current = false;
      setIsDeleting(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <section className="border-b border-border pb-6">
        <h2 className="text-2xl font-semibold text-foreground">{company.name}</h2>
        <dl className="mt-5 flex flex-wrap gap-x-8 gap-y-3">
          <SettingStat label="Participanți" value={company.stats.totalParticipants} />
          <SettingStat label="Asignări" value={company.stats.totalAssignments} />
          <SettingStat label="Completate" value={company.stats.completedAssignments} />
          <SettingStat label="Rată completare" value={`${company.stats.completionRate}%`} />
        </dl>
      </section>

      <section className="max-w-3xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-foreground">Ștergere companie</h2>
          </div>
          <Button
            type="button"
            variant={isDeleteOpen ? "outline" : "destructive"}
            size="sm"
            onClick={() => setIsDeleteOpen((current) => !current)}
            disabled={isDeleting}
          >
            <Trash2Icon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
            {isDeleteOpen ? "Anulează" : "Șterge compania"}
          </Button>
        </div>

        {isDeleteOpen ? (
          <div className="mt-5 border-l-2 border-destructive pl-4">
            <p className="text-sm leading-6 text-muted-foreground">
              Elimină compania, participanții, echipele, invitațiile și asignările legate de ea.
            </p>

            <form onSubmit={handleDelete} className="mt-4 flex flex-col gap-3" aria-busy={isDeleting}>
              <FieldGroup className="gap-3">
                <Field data-disabled={isDeleting ? true : undefined}>
                  <FieldLabel htmlFor="company-delete-confirmation">
                    Scrie numele companiei
                  </FieldLabel>
                  <Input
                    id="company-delete-confirmation"
                    value={confirmation}
                    onChange={(event) => setConfirmation(event.target.value)}
                    placeholder={company.name}
                    disabled={isDeleting}
                    aria-describedby="company-delete-confirmation-help"
                    className="border-destructive/35 focus-visible:border-destructive focus-visible:ring-destructive/20"
                  />
                  <FieldDescription id="company-delete-confirmation-help">Acțiunea este definitivă.</FieldDescription>
                </Field>
              </FieldGroup>
              <Button
                type="submit"
                disabled={!canDelete || isDeleting}
                variant="destructive"
                className="w-full"
              >
                {isDeleting ? <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" strokeWidth={1.8} /> : null}
                {isDeleting ? "Ștergem compania" : "Șterge definitiv"}
              </Button>
            </form>
            {isDeleting ? (
              <OperationFeedback
                className="mt-4"
                tone="danger"
                title="Ștergem compania"
                detail="Eliminăm datele și revenim la lista de companii."
              />
            ) : null}
          </div>
        ) : null}

        {message ? (
          <InlineFeedback tone="danger" className="mt-3">
            {message}
          </InlineFeedback>
        ) : null}
      </section>
    </div>
  );
}

function SettingStat({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="min-w-24">
      <dt className="text-xs font-semibold text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-2xl font-semibold tabular-nums text-foreground">{value}</dd>
    </div>
  );
}
