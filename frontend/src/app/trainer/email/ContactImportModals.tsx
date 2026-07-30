"use client";

import type React from "react";
import { Loader2Icon } from "lucide-react";

import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ModalLayer } from "@/components/ui/modal-layer";
import { SelectControl } from "@/components/ui/select-control";
import { cn } from "@/utils/cn";
import { importDraftHasEmailError, type CampaignImportDraft } from "./contact-import-domain";

export type ContactImportModalProps = {
  drafts: CampaignImportDraft[];
  sheetName: string | null;
  activeCount: number;
  invalidCount: number;
  duplicateCount: number;
  isImporting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  onDraftChange: <K extends keyof CampaignImportDraft>(rowId: string, field: K, value: CampaignImportDraft[K]) => void;
};

export function ContactImportModal({
  drafts,
  sheetName,
  activeCount,
  invalidCount,
  duplicateCount,
  isImporting,
  onCancel,
  onConfirm,
  onDraftChange,
}: ContactImportModalProps) {
  if (drafts.length === 0) return null;
  return (
    <ModalLayer
      labelledBy="campaign-import-title"
      onClose={() => { if (!isImporting) onCancel(); }}
      closeOnBackdrop={!isImporting}
      panelClassName="flex max-w-6xl flex-col overflow-hidden p-0"
    >
      <div className="border-b border-[var(--border)] bg-surface-muted px-6 py-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80">Import contacte</p>
            <h2 id="campaign-import-title" className="mt-1 text-xl font-bold text-foreground">Previzualizare {sheetName ?? "sheet"}</h2>
            <p className="mt-1 text-xs font-semibold text-foreground/55">
              {drafts.length} contacte · {activeCount} active · {drafts.length - activeCount} cu trimiterea oprită · {invalidCount} emailuri de corectat{duplicateCount > 0 ? ` · ${duplicateCount} duplicate` : ""}
            </p>
          </div>
          <div className="flex gap-2">
            <Button type="button" disabled={isImporting} onClick={onCancel} variant="outline" size="sm">Anulează</Button>
            <Button type="button" disabled={isImporting || invalidCount > 0} onClick={onConfirm} size="sm">
              {isImporting ? <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" /> : null}
              {isImporting ? "Importăm contactele" : "Confirmă importul"}
            </Button>
          </div>
        </div>
      </div>
      <div className="overflow-auto p-4">
        <table className="w-full min-w-[1040px] text-left text-xs">
          <thead className="sticky top-0 z-10 bg-surface text-[10px] font-bold uppercase tracking-[0.14em] text-foreground/50">
            <tr>
              <th className="px-3 py-2">Activ</th><th className="px-3 py-2">Nume</th><th className="px-3 py-2">Organizație</th>
              <th className="px-3 py-2">Email</th><th className="px-3 py-2">Tip client</th><th className="px-3 py-2">Rând</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {drafts.map((draft) => {
              const invalidEmail = importDraftHasEmailError(draft);
              return (
                <tr key={draft.id} className={draft.send ? "bg-surface" : "bg-surface-muted/70 text-foreground/50"}>
                  <td className="px-3 py-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="xs"
                      onClick={() => onDraftChange(draft.id, "send", !draft.send)}
                      aria-pressed={draft.send}
                      aria-label={`${draft.send ? "Activ" : "Inactiv"} pentru importul rândului ${draft.rowNumber}`}
                      className={cn("rounded-md text-[10px] font-bold", draft.send ? "status-success-soft" : "border-[var(--border)] bg-surface text-foreground/50")}
                    >
                      {draft.send ? "Da" : "Nu"}
                    </Button>
                  </td>
                  <td className="px-3 py-2"><Input value={draft.contact_name} onChange={(event) => onDraftChange(draft.id, "contact_name", event.target.value)} className="h-8 min-w-[13rem] px-2 py-1 text-xs" /></td>
                  <td className="px-3 py-2"><Input value={draft.organization_name} onChange={(event) => onDraftChange(draft.id, "organization_name", event.target.value)} className="h-8 min-w-[13rem] px-2 py-1 text-xs" /></td>
                  <td className="px-3 py-2">
                    <Input
                      type="email"
                      value={draft.email}
                      onChange={(event) => onDraftChange(draft.id, "email", event.target.value)}
                      className={cn("h-8 min-w-[16rem] px-2 py-1 font-mono text-xs", invalidEmail ? "border-destructive bg-destructive/10 text-destructive" : "")}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <SelectControl
                      label={`Segment import rând ${draft.rowNumber}`}
                      value={draft.segment}
                      onChange={(event) => onDraftChange(draft.id, "segment", event.target.value as CampaignImportDraft["segment"])}
                      className="h-8 min-w-[10rem] bg-surface-elevated px-2 py-1 text-xs"
                    >
                      <option value="potential_customer">Prospect</option><option value="past_customer">Client existent</option>
                    </SelectControl>
                  </td>
                  <td className="px-3 py-2 font-mono text-[11px] text-foreground/45">{draft.rowNumber}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </ModalLayer>
  );
}

export type ManualContactModalProps = {
  open: boolean;
  email: string;
  name: string;
  company: string;
  segment: "past_customer" | "potential_customer";
  isSaving: boolean;
  onClose: () => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  setEmail: (value: string) => void;
  setName: (value: string) => void;
  setCompany: (value: string) => void;
  setSegment: (value: "past_customer" | "potential_customer") => void;
};

export function ManualContactModal(props: ManualContactModalProps) {
  if (!props.open) return null;
  return (
    <ModalLayer
      labelledBy="manual-contact-title"
      onClose={() => { if (!props.isSaving) props.onClose(); }}
      closeOnBackdrop={!props.isSaving}
      panelClassName="max-w-md"
    >
      <div className="mb-5 flex flex-col gap-2">
        <h2 id="manual-contact-title" className="text-xl font-bold text-foreground">Adaugă contact manual</h2>
      </div>
      <form onSubmit={props.onSubmit} className="flex flex-col gap-5" aria-busy={props.isSaving}>
        <FieldGroup>
          <Field data-disabled={props.isSaving || undefined}>
            <FieldLabel htmlFor="manual-contact-email">Email</FieldLabel>
            <Input id="manual-contact-email" type="email" required value={props.email} onChange={(event) => props.setEmail(event.target.value)} disabled={props.isSaving} placeholder="exemplu@companie.ro" />
          </Field>
          <Field data-disabled={props.isSaving || undefined}>
            <FieldLabel htmlFor="manual-contact-name">Nume (opțional)</FieldLabel>
            <Input id="manual-contact-name" type="text" value={props.name} onChange={(event) => props.setName(event.target.value)} disabled={props.isSaving} placeholder="Nume și prenume" />
          </Field>
          <Field data-disabled={props.isSaving || undefined}>
            <FieldLabel htmlFor="manual-contact-company">Companie</FieldLabel>
            <Input id="manual-contact-company" type="text" value={props.company} onChange={(event) => props.setCompany(event.target.value)} disabled={props.isSaving} placeholder="Numele companiei" />
          </Field>
          <Field data-disabled={props.isSaving || undefined}>
            <FieldLabel htmlFor="manual-contact-segment">Segment</FieldLabel>
            <SelectControl
              id="manual-contact-segment"
              label="Segment contact manual"
              value={props.segment}
              onChange={(event) => props.setSegment(event.target.value as "past_customer" | "potential_customer")}
              disabled={props.isSaving}
              className="bg-surface-elevated py-3"
            >
              <option value="potential_customer">Prospect</option><option value="past_customer">Client existent</option>
            </SelectControl>
          </Field>
        </FieldGroup>
        <div className="flex justify-end gap-3 pt-1">
          <Button type="button" variant="ghost" onClick={props.onClose} disabled={props.isSaving}>Anulează</Button>
          <Button type="submit" disabled={props.isSaving}>
            {props.isSaving ? <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" /> : null}
            {props.isSaving ? "Salvăm contactul" : "Salvează contact"}
          </Button>
        </div>
        {props.isSaving ? <OperationFeedback title="Salvăm contactul" detail="Adăugăm contactul în lista campaniilor și reîncărcăm datele." /> : null}
      </form>
    </ModalLayer>
  );
}
