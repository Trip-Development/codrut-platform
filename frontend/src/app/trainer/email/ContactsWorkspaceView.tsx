"use client";

import { ArchiveIcon, Building2Icon, CheckIcon, CircleDashedIcon, Loader2Icon, PencilIcon, SearchIcon, XIcon } from "lucide-react";

import type { CampaignRecipientRow } from "@/api/email";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { SelectControl } from "@/components/ui/select-control";
import { cn } from "@/utils/cn";
import {
  campaignRecipientDraft,
  campaignRecipientName,
  campaignRecipientSourceLabel,
  campaignRecipientStatusLabel,
  type CampaignContactDraft,
  type CampaignContactTypeFilter,
} from "./campaign-domain";
import { ContactMetric, IconButton, SegmentedButton } from "./EmailWorkspaceControls";

type BulkContactAction = null | "activate" | "suppress" | "delete";

export type ContactsWorkspaceViewProps = {
  message: string | null;
  contacts: CampaignRecipientRow[];
  inactiveCount: number;
  search: string;
  typeFilter: CampaignContactTypeFilter;
  showInactive: boolean;
  selectedIds: string[];
  visibleSelectedIds: string[];
  selectableIds: Set<string>;
  visibleSelectableIds: string[];
  allVisibleSelected: boolean;
  selectedContactBeingEdited: boolean;
  bulkAction: BulkContactAction;
  editingContactId: string | null;
  drafts: Record<string, CampaignContactDraft>;
  savingContactId: string | null;
  deletingContactId: string | null;
  setSearch: (value: string) => void;
  setTypeFilter: (value: CampaignContactTypeFilter) => void;
  toggleAllVisible: () => void;
  toggleInactive: () => void;
  updateSelectedStatus: (status: "active" | "suppressed") => void;
  deleteSelected: () => void;
  toggleSelected: (recipientId: string) => void;
  updateDraft: <K extends keyof CampaignContactDraft>(recipientId: string, field: K, value: CampaignContactDraft[K]) => void;
  saveContact: (recipient: CampaignRecipientRow) => void;
  cancelEditing: (recipientId: string) => void;
  startEditing: (recipient: CampaignRecipientRow) => void;
  deleteContact: (recipient: CampaignRecipientRow) => void;
  openManualContact: () => void;
};

export function ContactsWorkspaceView(props: ContactsWorkspaceViewProps) {
  return (
    <div className="p-5">
      {props.message ? <InlineFeedback className="mb-4" descriptionClassName="text-xs leading-5">{props.message}</InlineFeedback> : null}
      <div className="mb-4 grid gap-3 border-b border-[var(--border)] pb-4 xl:grid-cols-[minmax(24rem,1fr)_auto] xl:items-center">
        <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-center">
          <label className="relative min-w-0 flex-1">
            <SearchIcon aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" strokeWidth={1.8} />
            <Input value={props.search} onChange={(event) => props.setSearch(event.target.value)} placeholder="Caută nume, email sau companie" className="h-11 min-w-0 rounded-md bg-background pl-9 text-sm" aria-label="Caută contacte campanie" />
          </label>
          <div className="inline-flex w-fit rounded-md bg-surface-muted p-1">
            {[["all", "Toate"], ["past_customer", "Clienți existenți"], ["potential_customer", "Prospecte"]].map(([value, label]) => (
              <SegmentedButton key={value} onClick={() => props.setTypeFilter(value as CampaignContactTypeFilter)} active={props.typeFilter === value} className="h-7 px-3 text-[10px] uppercase tracking-wider">{label}</SegmentedButton>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 xl:justify-end">
          <span className="rounded-md bg-surface-muted px-3 py-2 text-[11px] font-semibold text-foreground/55">{props.contacts.length} afișate</span>
          <Button type="button" onClick={props.toggleAllVisible} disabled={props.visibleSelectableIds.length === 0} variant="outline" size="sm">{props.allVisibleSelected ? "Deselectează vizibile" : "Selectează vizibile"}</Button>
          <Button type="button" onClick={props.toggleInactive} variant="outline" size="sm" aria-expanded={props.showInactive}>{props.showInactive ? "Ascunde restricționate" : `Arată restricționate (${props.inactiveCount})`}</Button>
          {props.visibleSelectedIds.length > 0 ? (
            <div className="flex flex-wrap items-center gap-2 rounded-md border border-burgundy/20 bg-burgundy/5 px-2 py-1.5">
              <span className="px-1 text-[11px] font-bold text-burgundy">{props.visibleSelectedIds.length} selectate</span>
              <Button type="button" onClick={() => props.updateSelectedStatus("active")} disabled={props.bulkAction !== null || props.selectedContactBeingEdited} variant="outline" size="sm" className="border-success/30 bg-success/10 text-success-ink hover:border-success/45 hover:bg-success/15">
                {props.bulkAction === "activate" ? <Loader2Icon data-icon="inline-start" aria-hidden="true" className="animate-spin" strokeWidth={1.8} /> : null}{props.bulkAction === "activate" ? "Activăm contactele" : "Activează"}
              </Button>
              <Button type="button" onClick={() => props.updateSelectedStatus("suppressed")} disabled={props.bulkAction !== null || props.selectedContactBeingEdited} variant="outline" size="sm">
                {props.bulkAction === "suppress" ? <Loader2Icon data-icon="inline-start" aria-hidden="true" className="animate-spin" strokeWidth={1.8} /> : null}{props.bulkAction === "suppress" ? "Oprim trimiterile" : "Oprește trimiterea"}
              </Button>
              <IconButton label="Arhivează contactele selectate" tone="danger" disabled={props.bulkAction !== null || props.selectedContactBeingEdited} onClick={props.deleteSelected}><ArchiveIcon aria-hidden="true" className="size-4" strokeWidth={1.8} /></IconButton>
            </div>
          ) : null}
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-[var(--border)] bg-surface">
        <table className="min-w-[66rem] text-left text-xs">
          <thead className="border-b border-[var(--border)] bg-surface-muted text-[10px] font-semibold uppercase tracking-[0.12em] text-foreground/50">
            <tr><th className="w-12 px-4 py-3">Select</th><th className="min-w-[22rem] px-4 py-3">Contact</th><th className="px-4 py-3">Segment</th><th className="px-4 py-3">Activ</th><th className="px-4 py-3">Interacțiuni</th><th className="px-4 py-3 text-right">Acțiuni</th></tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {props.contacts.length > 0 ? props.contacts.map((recipient) => {
              const isEditing = props.editingContactId === recipient.id;
              const draft = props.drafts[recipient.id] ?? campaignRecipientDraft(recipient);
              const isUnsubscribed = recipient.status === "unsubscribed";
              const isActive = recipient.status !== "suppressed" && !isUnsubscribed;
              const isPastCustomer = recipient.clientType === "tip_1";
              const SegmentIcon = isPastCustomer ? Building2Icon : CircleDashedIcon;
              return (
                <tr key={recipient.id} className={cn("group/contact transition-colors hover:bg-surface-muted/70", !isActive ? "bg-surface-muted/35 text-foreground/55" : null)}>
                  <td className={cn("px-4 py-2.5 align-middle", isEditing && "align-top")}><Checkbox checked={props.selectableIds.has(recipient.id) && props.selectedIds.includes(recipient.id)} disabled={!props.selectableIds.has(recipient.id)} onCheckedChange={() => props.toggleSelected(recipient.id)} aria-label={`Selectează ${recipient.email}`} /></td>
                  <td className={cn("min-w-[17rem] px-4 py-2.5 align-middle", isEditing && "align-top")}>
                    {isEditing ? (
                      <div className="flex flex-col gap-2"><Input value={draft.organization_name} onChange={(event) => props.updateDraft(recipient.id, "organization_name", event.target.value)} className="h-9 px-3 py-2 text-xs" placeholder="Companie" /><Input value={draft.contact_name} onChange={(event) => props.updateDraft(recipient.id, "contact_name", event.target.value)} className="h-9 px-3 py-2 text-xs" placeholder="Nume contact" /><Input type="email" value={draft.email} onChange={(event) => props.updateDraft(recipient.id, "email", event.target.value)} className="h-9 px-3 py-2 font-mono text-xs" placeholder="email@companie.ro" /></div>
                    ) : (
                      <div className="flex min-w-0 items-start gap-3">
                        <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold uppercase text-white", isPastCustomer ? "bg-zinc-800" : "bg-burgundy", !isActive && "bg-zinc-400")}>{(campaignRecipientName(recipient) || recipient.company || recipient.email).slice(0, 2)}</span>
                        <div className="min-w-0"><p className="truncate text-sm font-semibold text-foreground">{recipient.company}</p><p className="mt-1 truncate text-xs font-medium text-foreground/60">{campaignRecipientName(recipient) || "Contact lipsă"}</p><p className="mt-1 truncate font-mono text-[11px] text-foreground/40">{recipient.email}</p></div>
                      </div>
                    )}
                  </td>
                  <td className={cn("min-w-[11rem] px-4 py-2.5 align-middle", isEditing && "align-top")}>
                    {isEditing ? (
                      <div className="flex flex-col gap-2"><SelectControl label={`Segment pentru ${campaignRecipientName(recipient) || recipient.email}`} value={draft.segment} onChange={(event) => props.updateDraft(recipient.id, "segment", event.target.value as CampaignContactDraft["segment"])} className="h-9 bg-surface-elevated px-3 py-2 text-xs"><option value="potential_customer">Prospect</option><option value="past_customer">Client existent</option></SelectControl><SelectControl label={`Status campanie pentru ${campaignRecipientName(recipient) || recipient.email}`} value={draft.status} onChange={(event) => props.updateDraft(recipient.id, "status", event.target.value as CampaignContactDraft["status"])} disabled={isUnsubscribed} className="h-9 bg-surface-elevated px-3 py-2 text-xs"><option value="active">Activ</option><option value="suppressed">Adresă respinsă</option>{isUnsubscribed ? <option value="unsubscribed">Dezabonat</option> : null}</SelectControl></div>
                    ) : (
                      <div className="flex min-w-[9rem] items-start gap-2.5">
                        <SegmentIcon aria-hidden="true" className={cn("mt-0.5 size-4 shrink-0", isPastCustomer ? "text-zinc-600" : "text-burgundy")} strokeWidth={1.8} />
                        <div>
                          <p className="text-xs font-semibold text-foreground">{isPastCustomer ? "Client existent" : "Prospect"}</p>
                          <p className="mt-1 text-[11px] text-muted-foreground">{campaignRecipientSourceLabel(recipient.source)}</p>
                        </div>
                      </div>
                    )}
                  </td>
                  <td className={cn("px-4 py-2.5 align-middle", isEditing && "align-top")}>
                    {isEditing ? <span className="text-xs font-medium text-muted-foreground">În editare</span> : <ContactStatus status={recipient.status} />}
                  </td>
                  <td className={cn("px-4 py-2.5 align-middle", isEditing && "align-top")}><div className="flex min-w-[17rem] flex-wrap gap-x-4 gap-y-1.5"><ContactMetric label="Desch." value={recipient.openCount} /><ContactMetric label="Click" value={recipient.clickCount} /><ContactMetric label="Video" value={recipient.viewCount} /><ContactMetric label="Răsp." value={recipient.replyCount} /><ContactMetric label="Cal." value={recipient.calendlyClickCount} /></div></td>
                  <td className={cn("px-4 py-2.5 align-middle", isEditing && "align-top")}><div className="flex justify-end gap-2 opacity-80 transition group-hover/contact:opacity-100 group-focus-within/contact:opacity-100">
                    {isEditing ? <><IconButton appearance="plain" label={props.savingContactId === recipient.id ? "Salvăm contactul" : `Salvează ${recipient.email}`} tone="success" disabled={props.savingContactId === recipient.id} onClick={() => props.saveContact(recipient)}><CheckIcon aria-hidden="true" className="size-4" strokeWidth={1.8} /></IconButton><IconButton appearance="plain" label={`Anulează editarea pentru ${recipient.email}`} disabled={props.savingContactId === recipient.id} onClick={() => props.cancelEditing(recipient.id)}><XIcon aria-hidden="true" className="size-4" strokeWidth={1.8} /></IconButton></> : <><IconButton appearance="plain" label={`Editează ${recipient.email}`} onClick={() => props.startEditing(recipient)}><PencilIcon aria-hidden="true" className="size-4" strokeWidth={1.8} /></IconButton><IconButton appearance="plain" label={props.deletingContactId === recipient.id ? "Arhivăm contactul" : `Arhivează ${recipient.email}`} tone="danger" disabled={props.deletingContactId === recipient.id} onClick={() => props.deleteContact(recipient)}><ArchiveIcon aria-hidden="true" className="size-4" strokeWidth={1.8} /></IconButton></>}
                  </div></td>
                </tr>
              );
            }) : (
              <tr><td colSpan={6} className="px-6 py-12 text-center text-sm font-medium text-foreground/50"><p>Niciun contact înregistrat încă.</p><div className="mt-4 flex items-center justify-center gap-3"><span className="text-foreground/40">Importă un fișier CSV sau</span><Button type="button" variant="outline" size="xs" onClick={props.openManualContact} className="text-burgundy hover:border-burgundy/45 hover:text-burgundy-700">adaugă manual</Button></div></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ContactStatus({ status }: { status: CampaignRecipientRow["status"] }) {
  const dotClass = status === "suppressed"
    ? "bg-destructive"
    : status === "unsubscribed"
      ? "bg-destructive"
      : status === "archived"
        ? "bg-zinc-400"
      : status === "needs_contact_name"
        ? "bg-warning"
        : "bg-emerald-500";

  return (
    <span className="inline-flex items-center gap-2 text-xs font-semibold text-foreground">
      <span aria-hidden="true" className={cn("size-2 rounded-full", dotClass)} />
      {campaignRecipientStatusLabel(status)}
    </span>
  );
}
