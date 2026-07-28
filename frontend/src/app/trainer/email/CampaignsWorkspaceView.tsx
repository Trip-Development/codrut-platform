"use client";

import { useState } from "react";
import {
  Building2Icon,
  ChevronDownIcon,
  Loader2Icon,
  PencilIcon,
  SearchIcon,
  Trash2Icon,
  UsersIcon,
} from "lucide-react";

import type { CampaignRecipientRow, CampaignSendResponse, EmailCampaign } from "@/api/email";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { SearchableCombobox } from "@/components/ui/searchable-combobox";
import { SelectControl } from "@/components/ui/select-control";
import { cn } from "@/utils/cn";
import {
  campaignDeliveryLabel,
  campaignMembershipCompanyGroups,
  campaignRecipientName,
  campaignSendFailureDetail,
  campaignSendResultSummary,
  campaignSegmentLabel,
  type CampaignContactTypeFilter,
  type CampaignDeliveryState,
  type CampaignSendMode,
} from "./campaign-domain";
import { campaignSendBlockedReason, campaignSendReadinessError } from "./campaign-validation";
import { CampaignStatusBadge, IconButton } from "./EmailWorkspaceControls";

export type CampaignsWorkspaceViewProps = {
  campaigns: EmailCampaign[];
  isLoading: boolean;
  memberships: Record<string, string[]>;
  membershipSearches: Record<string, string>;
  membershipTypeFilters: Record<string, CampaignContactTypeFilter>;
  membershipCompanySelections: Record<string, string>;
  membershipErrors: Record<string, string>;
  sendResults: Record<string, CampaignSendResponse>;
  openCampaignId: string | null;
  sendingCampaignId: string | null;
  sendingMode: CampaignSendMode | null;
  sendingRecipientId: string | null;
  deletingCampaignId: string | null;
  savingMembershipId: string | null;
  getActiveMemberIds: (campaign: EmailCampaign) => string[];
  getSendableMemberIds: (campaign: EmailCampaign) => string[];
  getRecipientDelivery: (campaign: EmailCampaign, recipientId: string) => CampaignDeliveryState;
  isDeliveryLocked: (delivery: CampaignDeliveryState) => boolean;
  getEligibleRecipients: () => CampaignRecipientRow[];
  getVisibleEligibleRecipients: (campaign: EmailCampaign) => CampaignRecipientRow[];
  setOpenCampaignId: (id: string | null) => void;
  setMembershipSearch: (campaignId: string, value: string) => void;
  setMembershipTypeFilter: (campaignId: string, value: CampaignContactTypeFilter) => void;
  setMembershipCompany: (campaignId: string, value: string) => void;
  toggleMembershipRecipient: (campaign: EmailCampaign, recipientId: string) => void;
  toggleMembershipCompany: (campaign: EmailCampaign, companyKey: string, mode: "select" | "deselect") => void;
  sendCampaign: (campaign: EmailCampaign, mode: CampaignSendMode) => void;
  sendRecipient: (
    campaign: EmailCampaign,
    recipient: CampaignRecipientRow,
    action: "send" | "resend",
  ) => void;
  editCampaign: (campaign: EmailCampaign) => void;
  deleteCampaign: (campaign: EmailCampaign) => void;
};

export function CampaignsWorkspaceView(props: CampaignsWorkspaceViewProps) {
  const [sendModes, setSendModes] = useState<Record<string, Extract<CampaignSendMode, "selected" | "all">>>({});

  if (props.isLoading) {
    return <div className="p-5"><OperationFeedback title="Încărcăm campaniile" detail="Aducem listele, destinatarii și istoricul de trimitere." /></div>;
  }
  if (props.campaigns.length === 0) {
    return <div className="p-5"><p className="rounded-lg border border-dashed border-[var(--border)] bg-surface-muted px-4 py-10 text-center text-sm font-semibold text-foreground/55">Nicio campanie salvată încă.</p></div>;
  }

  return (
    <div className="p-5">
      <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-surface">
        {props.campaigns.map((campaign) => {
          const memberIds = props.memberships[campaign.id] ?? [];
          const activeMemberIds = props.getActiveMemberIds(campaign);
          const sendableMemberIds = props.getSendableMemberIds(campaign);
          const sentMemberCount = activeMemberIds.filter((recipientId) => props.getRecipientDelivery(campaign, recipientId) === "sent").length;
          const unsentLabel = sendableMemberIds.length === 1
            ? "1 netrimis"
            : `${sendableMemberIds.length} netrimiși`;
          const eligibleRecipients = props.getEligibleRecipients();
          const visibleEligibleRecipients = props.getVisibleEligibleRecipients(campaign);
          const membershipSearch = props.membershipSearches[campaign.id] ?? "";
          const membershipTypeFilter = props.membershipTypeFilters[campaign.id] ?? "all";
          const companyGroups = campaignMembershipCompanyGroups(eligibleRecipients, memberIds);
          const selectedCompanyKey = props.membershipCompanySelections[campaign.id] ?? "";
          const selectedCompanyGroup = companyGroups.find((group) => group.key === selectedCompanyKey);
          const isOpen = props.openCampaignId === campaign.id;
          const isSending = props.sendingCampaignId === campaign.id;
          const sendMode = sendModes[campaign.id] ?? "selected";
          const readinessError = campaignSendReadinessError(campaign);
          const sendBlockedReason = campaignSendBlockedReason({
            campaign,
            mode: sendMode,
            sendableRecipientCount: sendableMemberIds.length,
            activeRecipientCount: activeMemberIds.length,
            isSending,
            isDeleting: props.deletingCampaignId === campaign.id,
          });
          const sendBlockedReasonId = `campaign-${campaign.id}-send-blocked-reason`;
          const latestSendResult = props.sendResults[campaign.id];
          const deliverySummary = latestSendResult
            ? campaignSendResultSummary(latestSendResult)
            : sentMemberCount > 0
              ? `${sentMemberCount} trimise`
              : "Netrimisă";
          const latestSendFailure = latestSendResult
            ? campaignSendFailureDetail(latestSendResult)
            : null;
          const sendFeedbackDetail = props.sendingRecipientId
            ? `Trimitem campania către un singur destinatar pentru ${campaign.name}.`
            : props.sendingMode === "selected"
            ? `Trimitem campania către ${sendableMemberIds.length} destinatari netrimiși pentru ${campaign.name}.`
            : props.sendingMode === "all"
              ? `Retrimitem campania către toți destinatarii salvați pentru ${campaign.name}.`
              : `Trimitem campania către destinatarii netrimiși pentru ${campaign.name}.`;

          return (
            <article key={campaign.id} className={cn("overflow-hidden border-b border-[var(--border)] bg-surface transition-colors last:border-b-0", isOpen && "bg-background")}>
              <button type="button" aria-expanded={isOpen} onClick={() => props.setOpenCampaignId(isOpen ? null : campaign.id)} className="grid w-full gap-3 px-4 py-3 text-left transition hover:bg-surface-muted xl:grid-cols-[minmax(18rem,1.1fr)_minmax(27rem,1.5fr)_auto] xl:items-center">
                <span className="min-w-0">
                  <span className="flex flex-wrap items-center gap-2"><CampaignStatusBadge status={campaign.status} /><Badge variant="outline" className="rounded-md text-[10px] uppercase tracking-[0.12em]">{campaignSegmentLabel(campaign.segment)}</Badge></span>
                  <span className="mt-2 block truncate text-sm font-semibold text-foreground">{campaign.name}</span>
                  <span className="mt-1 block truncate text-xs font-medium text-muted-foreground">{campaign.subject}</span>
                </span>
                  <span className="grid min-w-0 gap-3 text-xs sm:grid-cols-4">
                  <span className="min-w-0"><span className="block font-medium text-muted-foreground">Listă</span><span className="mt-1 block truncate font-semibold text-foreground">Destinatari ({activeMemberIds.length}/{eligibleRecipients.length}, {unsentLabel})</span></span>
                  <span><span className="block font-medium text-muted-foreground">Trimiși</span><span className="mt-1 block font-semibold tabular-nums text-foreground">{sentMemberCount}</span></span>
                  <span><span className="block font-medium text-muted-foreground">Conținut</span><span className="mt-1 block font-semibold text-foreground">{campaign.video_url ? "Video" : campaign.thumbnail_url ? "Imagine" : campaign.landing_page_url ? "Link" : "Doar email"}</span></span>
                  <span><span className="block font-medium text-muted-foreground">Livrare</span><span className="mt-1 block font-semibold text-foreground">{deliverySummary}</span></span>
                </span>
                <span className="inline-flex h-9 items-center justify-center gap-2 rounded-md px-2 text-xs font-semibold text-foreground/62">{isOpen ? "Închide" : "Deschide"}<ChevronDownIcon aria-hidden="true" className={cn("size-4 transition-transform", isOpen && "rotate-180")} strokeWidth={1.8} /></span>
              </button>

              {isOpen ? (
                <div className="grid border-t border-[var(--border)] bg-background xl:grid-cols-[minmax(0,1fr)_16rem]">
                  <div className="min-w-0 p-4">
                    <FieldGroup className="grid gap-2 rounded-md bg-surface-muted p-2 lg:grid-cols-[minmax(0,1fr)_11rem_minmax(13rem,0.8fr)]">
                      <Field>
                        <FieldLabel className="sr-only" htmlFor={`campaign-${campaign.id}-recipient-search`}>Caută destinatari pentru {campaign.name}</FieldLabel>
                        <div className="relative"><SearchIcon aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" strokeWidth={1.8} /><Input id={`campaign-${campaign.id}-recipient-search`} value={membershipSearch} onChange={(event) => props.setMembershipSearch(campaign.id, event.target.value)} className="h-9 rounded-md bg-background pl-9 pr-3 text-xs" placeholder="Caută în toate contactele" /></div>
                      </Field>
                      <SearchableCombobox
                        icon={UsersIcon}
                        label={`Filtrează destinatari după tip pentru ${campaign.name}`}
                        value={membershipTypeFilter === "all" ? "" : membershipTypeFilter}
                        allLabel="Toate tipurile"
                        options={[
                          { value: "past_customer", label: "Clienți existenți" },
                          { value: "potential_customer", label: "Prospecte" },
                        ]}
                        onValueChange={(value) => props.setMembershipTypeFilter(
                          campaign.id,
                          (value || "all") as CampaignContactTypeFilter,
                        )}
                        size="sm"
                      />
                      <SearchableCombobox
                        icon={Building2Icon}
                        label={`Alege companie pentru ${campaign.name}`}
                        value={selectedCompanyKey}
                        allLabel="Alege companie"
                        options={companyGroups.map((group) => ({
                          value: group.key,
                          label: `${group.label} (${group.selectedCount}/${group.recipientIds.length})`,
                        }))}
                        onValueChange={(value) => props.setMembershipCompany(campaign.id, value)}
                        size="sm"
                      />
                    </FieldGroup>

                    {selectedCompanyGroup ? (
                      <div className="mt-3 flex flex-col gap-2 rounded-md border border-burgundy/15 bg-burgundy/5 px-3 py-2 text-xs sm:flex-row sm:items-center sm:justify-between">
                        <span className="font-semibold text-foreground/65">{selectedCompanyGroup.label}: {selectedCompanyGroup.selectedCount}/{selectedCompanyGroup.recipientIds.length} selectați</span>
                        <span className="flex flex-wrap gap-2"><Button type="button" size="xs" variant="outline" disabled={props.savingMembershipId === campaign.id} onClick={() => props.toggleMembershipCompany(campaign, selectedCompanyGroup.key, "select")}>Selectează compania</Button><Button type="button" size="xs" variant="outline" disabled={props.savingMembershipId === campaign.id} onClick={() => props.toggleMembershipCompany(campaign, selectedCompanyGroup.key, "deselect")}>Deselectează</Button></span>
                      </div>
                    ) : null}

                    <div className="mt-4 overflow-hidden rounded-md border border-[var(--border)] bg-surface" role="region" aria-label={`Destinatari pentru ${campaign.name}`}>
                      <div className="grid grid-cols-[2rem_minmax(12rem,1fr)_minmax(13rem,1fr)_7rem] gap-3 border-b border-[var(--border)] bg-surface-muted px-3 py-2 text-[10px] font-bold uppercase tracking-[0.12em] text-muted-foreground"><span aria-hidden="true" /><span>Contact</span><span>Email</span><span>Status</span></div>
                      <div className="max-h-80 overflow-y-hidden pr-1 [scrollbar-gutter:stable] hover:overflow-y-auto focus:overflow-y-auto focus-within:overflow-y-auto" tabIndex={0}>
                        {visibleEligibleRecipients.length > 0 ? (
                          <div className="divide-y divide-[var(--border)]">
                            {visibleEligibleRecipients.map((recipient) => {
                              const checkboxId = `campaign-${campaign.id}-recipient-${recipient.id}`;
                              const delivery = props.getRecipientDelivery(campaign, recipient.id);
                              const deliveryLocked = props.isDeliveryLocked(delivery);
                              const isMember = memberIds.includes(recipient.id);
                              const recipientAction = delivery === "sent"
                                ? "resend"
                                : isMember && (delivery === "not_sent" || delivery === "failed")
                                  ? "send"
                                  : null;
                              const recipientActionLabel = recipientAction === "resend"
                                ? "Retrimite"
                                : "Trimite";
                              return (
                                <Field key={recipient.id} orientation="horizontal" className={cn("group grid grid-cols-[2rem_minmax(12rem,1fr)_minmax(13rem,1fr)_7rem] items-center gap-3 rounded-none px-3 py-2.5 text-xs hover:bg-surface-muted", deliveryLocked && "text-foreground/48")}>
                                  <Checkbox id={checkboxId} checked={memberIds.includes(recipient.id) || deliveryLocked} disabled={deliveryLocked || props.savingMembershipId === campaign.id} onCheckedChange={() => props.toggleMembershipRecipient(campaign, recipient.id)} className="mt-0.5" aria-label={`Include ${recipient.email} în ${campaign.name}`} />
                                  <FieldLabel htmlFor={checkboxId} className="contents cursor-pointer font-normal">
                                    <span className="min-w-0"><span className="block truncate font-semibold text-foreground">{campaignRecipientName(recipient) || recipient.email}</span><span className="mt-0.5 block truncate text-foreground/52">{recipient.company}</span></span>
                                    <span className="truncate font-mono text-[11px] text-foreground/45">{recipient.email}</span>
                                  </FieldLabel>
                                  <span className="relative flex h-7 items-center justify-end">
                                    <span className={cn("w-fit rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider transition-opacity", recipientAction && "group-hover:opacity-0 group-focus-within:opacity-0", delivery === "sent" && "border-emerald-200 bg-emerald-50 text-emerald-700", delivery === "failed" && "border-red-200 bg-red-50 text-red-700", delivery === "queued" && "border-amber-200 bg-amber-50 text-amber-700", delivery === "not_sent" && "border-[var(--border)] bg-surface-muted text-foreground/45")}>{campaignDeliveryLabel(delivery)}</span>
                                    {recipientAction ? (
                                      <Button
                                        type="button"
                                        size="xs"
                                        variant="outline"
                                        disabled={isSending || props.savingMembershipId === campaign.id}
                                        onClick={() => props.sendRecipient(campaign, recipient, recipientAction)}
                                        className="absolute right-0 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100"
                                        aria-label={`${recipientActionLabel} campania ${campaign.name} către ${recipient.email}`}
                                      >
                                        {props.sendingRecipientId === recipient.id ? (
                                          <Loader2Icon aria-hidden="true" className="size-3 animate-spin" />
                                        ) : null}
                                        {recipientActionLabel}
                                      </Button>
                                    ) : null}
                                  </span>
                                </Field>
                              );
                            })}
                          </div>
                        ) : <p className="px-3 py-6 text-center text-xs font-semibold text-foreground/50">{eligibleRecipients.length > 0 ? "Niciun contact nu corespunde căutării." : "Nu există contacte active pentru selecția campaniei."}</p>}
                      </div>
                    </div>
                    {props.savingMembershipId === campaign.id ? <p role="status" className="mt-2 flex items-center justify-end gap-2 text-xs font-medium text-muted-foreground"><Loader2Icon aria-hidden="true" className="size-3.5 animate-spin" strokeWidth={1.8} />Se salvează</p> : null}
                    {props.membershipErrors[campaign.id] ? <InlineFeedback tone="danger" className="mt-3 px-3 py-2" descriptionClassName="text-xs leading-5">{props.membershipErrors[campaign.id]}</InlineFeedback> : null}
                  </div>

                  <aside className="flex min-w-0 flex-col justify-between gap-4 border-t border-[var(--border)] bg-surface-muted p-4 xl:border-l xl:border-t-0">
                    <div className="space-y-3">
                      <dl className="divide-y divide-[var(--border)] text-xs"><div className="flex items-baseline justify-between gap-3 py-2"><dt className="font-semibold text-muted-foreground">În lista de trimitere</dt><dd className="text-xl font-semibold tabular-nums text-foreground">{activeMemberIds.length}</dd></div><div className="flex items-baseline justify-between gap-3 py-2"><dt className="font-semibold text-muted-foreground">Pregătiți de trimis</dt><dd className="text-xl font-semibold tabular-nums text-foreground">{sendableMemberIds.length}</dd></div><div className="flex items-baseline justify-between gap-3 py-2"><dt className="font-semibold text-muted-foreground">Afișați de filtre</dt><dd className="text-xl font-semibold tabular-nums text-foreground">{visibleEligibleRecipients.length}</dd></div></dl>
                      <p className="text-[11px] leading-5 text-muted-foreground">Filtrele schimbă doar contactele afișate, nu lista de trimitere.</p>
                      {latestSendResult ? <p className="rounded-md border border-burgundy/15 bg-burgundy/5 px-3 py-2 text-[11px] font-semibold leading-5 text-burgundy">{campaignSendResultSummary(latestSendResult)}{latestSendFailure ? ` — ${latestSendFailure}` : ""}</p> : null}
                      {readinessError ? <InlineFeedback tone="danger" className="px-3 py-2" descriptionClassName="text-xs leading-5">{readinessError}</InlineFeedback> : null}
                      {sendBlockedReason && !readinessError && !isSending ? <p id={sendBlockedReasonId} className="text-xs font-medium leading-5 text-muted-foreground">{sendBlockedReason}</p> : null}
                      {isSending ? <OperationFeedback title="Trimitem campania" detail={sendFeedbackDetail} /> : null}
                    </div>
                    <div className="flex flex-wrap gap-2 xl:flex-col">
                      <SelectControl
                        label={`Mod trimitere pentru ${campaign.name}`}
                        value={sendMode}
                        onChange={(event) => {
                          const nextMode = event.target.value === "all" ? "all" : "selected";
                          setSendModes((current) => ({ ...current, [campaign.id]: nextMode }));
                        }}
                        disabled={isSending || props.deletingCampaignId === campaign.id}
                        className="h-9 bg-background text-xs"
                      >
                        <option value="selected">Netrimiși din listă ({sendableMemberIds.length})</option>
                        <option value="all">Retrimite tuturor ({activeMemberIds.length})</option>
                      </SelectControl>
                      <Button
                        type="button"
                        size="xs"
                        className="justify-center"
                        disabled={Boolean(sendBlockedReason)}
                        aria-describedby={sendBlockedReason && !readinessError && !isSending ? sendBlockedReasonId : undefined}
                        title={sendBlockedReason ?? undefined}
                        onClick={() => props.sendCampaign(campaign, sendMode)}
                      >
                        {isSending ? <Loader2Icon data-icon="inline-start" aria-hidden="true" className="animate-spin" strokeWidth={1.8} /> : null}
                        {isSending ? "Trimitem campania" : "Trimite campania"}
                      </Button>
                      <div className="flex gap-2 pt-1"><IconButton label={`Editează campania ${campaign.name}`} disabled={isSending || props.deletingCampaignId === campaign.id} onClick={() => props.editCampaign(campaign)}><PencilIcon aria-hidden="true" className="size-4" strokeWidth={1.8} /></IconButton><IconButton label={props.deletingCampaignId === campaign.id ? "Ștergem campania" : `Șterge campania ${campaign.name}`} tone="danger" disabled={isSending || props.deletingCampaignId === campaign.id} onClick={() => props.deleteCampaign(campaign)}><Trash2Icon aria-hidden="true" className="size-4" strokeWidth={1.8} /></IconButton></div>
                    </div>
                  </aside>
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </div>
  );
}
