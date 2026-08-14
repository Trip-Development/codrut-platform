"use client";

import { Loader2Icon, Trash2Icon } from "lucide-react";

import type { CompanyParticipant } from "@/api/companies";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { Button } from "@/components/ui/button";
import { SheetBody, SheetFooter, SheetHeader } from "@/components/ui/sheet";

export function ParticipantRemovalSheetContent({
  participant,
  directReports,
  scope,
  removing,
  error,
  onCancel,
  onConfirm,
}: {
  participant: CompanyParticipant;
  directReports: CompanyParticipant[];
  scope: "project" | "company";
  removing: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const projectScope = scope === "project";
  const actionLabel = projectScope ? "Elimină din proiect" : "Șterge din companie";

  return (
    <div className="flex h-full min-w-0 flex-col">
      <SheetHeader>
        <h2 id="participant-removal-title" className="text-lg font-semibold text-foreground">
          {actionLabel}
        </h2>
        <p id="participant-removal-description" className="mt-1 break-words text-sm text-muted-foreground">
          {participant.full_name}
        </p>
      </SheetHeader>
      <SheetBody aria-busy={removing}>
        {error ? (
          <InlineFeedback tone="danger" className="mb-5 px-4 py-3">
            {error}
          </InlineFeedback>
        ) : null}
        <p className="text-sm leading-6 text-foreground">
          {projectScope
            ? "Participantul va fi scos numai din acest proiect. Contul, profilul companiei, rezultatele și sarcinile deja generate rămân neschimbate."
            : "Profilul poate fi șters numai dacă nu aparține niciunui proiect și nu are cont sau istoric protejat."}
        </p>
        {directReports.length > 0 ? (
          <div className="mt-5 rounded-lg border border-warning/25 bg-warning/8 px-4 py-4">
            <p className="text-sm font-semibold text-foreground">
              {directReports.length === 1
                ? "O persoană raportează acestui participant"
                : `${directReports.length} persoane raportează acestui participant`}
            </p>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              După eliminare vor rămâne fără manager. Le poți reasigna înainte sau ulterior din editare.
            </p>
            <ul className="mt-3 space-y-1 text-sm font-medium text-foreground">
              {directReports.map((directReport) => (
                <li key={directReport.id}>• {directReport.full_name}</li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="mt-5 text-sm text-muted-foreground">
            Nicio persoană nu raportează acestui participant în acest context.
          </p>
        )}
        {removing ? (
          <OperationFeedback
            tone="danger"
            title={projectScope ? "Eliminăm participantul din proiect" : "Ștergem participantul"}
            detail="Verificăm din nou relațiile înainte de salvare."
            className="mt-5"
          />
        ) : null}
      </SheetBody>
      <SheetFooter className="flex items-center justify-end gap-2">
        <Button type="button" variant="outline" size="sm" disabled={removing} onClick={onCancel}>
          Înapoi
        </Button>
        <Button type="button" variant="destructive" size="sm" disabled={removing} onClick={onConfirm}>
          {removing ? <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" /> : <Trash2Icon data-icon="inline-start" aria-hidden="true" />}
          {removing ? "Se procesează" : actionLabel}
        </Button>
      </SheetFooter>
    </div>
  );
}
