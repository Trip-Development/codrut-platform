"use client";

import Image from "next/image";
import type React from "react";
import { ChevronDownIcon, Loader2Icon, UploadIcon } from "lucide-react";

import type { EmailCampaign, EmailTemplate } from "@/api/email";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { Button } from "@/components/ui/button";
import { disclosureTriggerClassName } from "@/components/ui/disclosure";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ModalCloseButton, ModalLayer } from "@/components/ui/modal-layer";
import { SelectControl } from "@/components/ui/select-control";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/utils/cn";
import type { CampaignSegmentKey, CampaignTargetSegment } from "./campaign-domain";
import type { CampaignFieldErrors, CampaignFieldName, CampaignSaveFailure } from "./campaign-validation";
import {
  buildStyledEmailTemplateBody,
  MOCK_REPLACEMENTS,
  parseEmailTemplateEditorDraft,
} from "./email-template-domain";

type CampaignPreview = { subject: string; bodyHtml: string };

export type CampaignEditorModalProps = {
  open: boolean;
  editingCampaign: EmailCampaign | null;
  campaignName: string;
  campaignSegment: CampaignTargetSegment;
  campaignTemplateId: string;
  campaignTemplates: EmailTemplate[];
  campaignSubject: string;
  campaignBody: string;
  campaignPlainBody: string;
  campaignVideoUrl: string;
  campaignLandingUrl: string;
  campaignThumbnailUrl: string;
  campaignFieldErrors: CampaignFieldErrors;
  campaignAssetMessage: string | null;
  hasPendingAssetCleanup: boolean;
  isRetryingAssetCleanup: boolean;
  campaignAssetPreviewUrl: string | null;
  campaignMediaHasChanges: boolean;
  campaignPreview: CampaignPreview;
  campaignMessage: string | null;
  campaignSaveFailure: CampaignSaveFailure | null;
  isSaving: boolean;
  isUploadingAsset: boolean;
  assetInputRef: React.RefObject<HTMLInputElement | null>;
  onClose: () => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  onAssetChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  clearPendingAsset: () => void;
  retryAssetCleanup: () => void;
  clearFieldError: (field: CampaignFieldName) => void;
  setCampaignName: (value: string) => void;
  setCampaignSegment: (value: CampaignTargetSegment) => void;
  setCampaignTemplateId: (value: string) => void;
  setCampaignSubject: (value: string) => void;
  setCampaignBody: (value: string) => void;
  setCampaignPlainBody: (value: string) => void;
  setCampaignVideoUrl: (value: string) => void;
  setCampaignLandingUrl: (value: string) => void;
  setCampaignThumbnailUrl: (value: string) => void;
  setCampaignAssetMessage: (value: string | null) => void;
};

const CAMPAIGN_FIELD_SUMMARY: Array<{ field: CampaignFieldName; id: string; label: string }> = [
  { field: "name", id: "campaign-name", label: "Nume campanie" },
  { field: "subject", id: "campaign-subject", label: "Subiect" },
  { field: "body", id: "campaign-plain-body", label: "Mesaj email" },
  { field: "videoUrl", id: "campaign-video-url", label: "Link video" },
  { field: "thumbnailUrl", id: "campaign-thumbnail-url", label: "Imagine campanie" },
  { field: "landingUrl", id: "campaign-landing-url", label: "Landing page" },
];

export function CampaignEditorModal(props: CampaignEditorModalProps) {
  if (!props.open) return null;
  const {
    editingCampaign,
    campaignName,
    campaignSegment,
    campaignTemplateId,
    campaignTemplates,
    campaignSubject,
    campaignBody,
    campaignPlainBody,
    campaignVideoUrl,
    campaignLandingUrl,
    campaignThumbnailUrl,
    campaignFieldErrors,
    campaignAssetMessage,
    hasPendingAssetCleanup,
    isRetryingAssetCleanup,
    campaignAssetPreviewUrl,
    campaignMediaHasChanges,
    campaignPreview,
    campaignMessage,
    campaignSaveFailure,
    isSaving,
    isUploadingAsset,
    assetInputRef,
  } = props;
  const invalidFields = CAMPAIGN_FIELD_SUMMARY.filter(({ field }) => Boolean(campaignFieldErrors[field]));

  return (
    <ModalLayer
      labelledBy="campaign-modal-title"
      onClose={() => { if (!isSaving) props.onClose(); }}
      closeOnBackdrop={!isSaving}
      panelClassName="flex h-[88vh] max-w-6xl flex-col overflow-hidden p-0"
    >
      <div className="border-b border-border bg-surface-raised px-4 py-4 sm:px-6">
        <div className="flex items-start justify-between gap-4">
          <h2 id="campaign-modal-title" className="text-xl font-semibold text-foreground">
            {editingCampaign ? campaignName || "Editează campania" : "Campanie nouă"}
          </h2>
          <ModalCloseButton
            onClick={props.onClose}
            disabled={isSaving}
          />
        </div>
      </div>

      <form onSubmit={props.onSubmit} noValidate className="flex min-h-0 flex-1 flex-col" aria-busy={isSaving}>
        <div className="min-h-0 flex-1 overflow-y-auto bg-background px-4 py-5 sm:px-6">
          {invalidFields.length > 1 ? (
            <InlineFeedback tone="danger" className="mb-4 px-3 py-2" descriptionClassName="text-xs leading-5" id="campaign-error-summary">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span>Corectează {invalidFields.length} câmpuri înainte de salvare:</span>
                {invalidFields.map(({ field, id, label }) => (
                  <button
                    key={field}
                    type="button"
                    className="font-semibold underline underline-offset-2"
                    onClick={() => document.getElementById(id)?.focus()}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </InlineFeedback>
          ) : null}
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,0.82fr)]">
            <div className="overflow-hidden rounded-lg border border-border bg-surface">
              <section className="p-4 sm:p-5" aria-label="Configurare campanie">
                <FieldGroup className="grid gap-4 md:grid-cols-2">
                  <Field data-disabled={isSaving || undefined} data-invalid={campaignFieldErrors.name ? true : undefined}>
                    <FieldLabel htmlFor="campaign-name">Nume campanie</FieldLabel>
                    <Input
                      id="campaign-name"
                      value={campaignName}
                      onChange={(event) => {
                        props.setCampaignName(event.target.value);
                        props.clearFieldError("name");
                      }}
                      disabled={isSaving}
                      aria-invalid={Boolean(campaignFieldErrors.name)}
                      aria-describedby={campaignFieldErrors.name ? "campaign-name-error" : undefined}
                      className="py-3"
                    />
                    <FieldError id="campaign-name-error">{campaignFieldErrors.name}</FieldError>
                  </Field>
                  <Field data-disabled={isSaving || undefined}>
                    <FieldLabel htmlFor="campaign-segment">Segment</FieldLabel>
                    <SelectControl
                      id="campaign-segment"
                      label="Segment campanie"
                      value={campaignSegment ?? ""}
                      onChange={(event) => {
                        props.setCampaignSegment(event.target.value ? event.target.value as CampaignSegmentKey : null);
                        props.setCampaignTemplateId("");
                      }}
                      disabled={isSaving}
                      className="bg-surface-elevated py-3"
                    >
                      <option value="">Fără grup preselectat</option>
                      <option value="potential_customer">Prospect / client potențial</option>
                      <option value="past_customer">Client vechi / existent</option>
                    </SelectControl>
                  </Field>
                </FieldGroup>

                <Field className="mt-4" data-disabled={isSaving || undefined}>
                  <FieldLabel htmlFor="campaign-template">Șablon email</FieldLabel>
                  <SelectControl
                    id="campaign-template"
                    label="Șablon email"
                    value={campaignTemplateId}
                    onChange={(event) => {
                      const nextTemplate = campaignTemplates.find((template) => template.id === event.target.value);
                      props.setCampaignTemplateId(event.target.value);
                      if (nextTemplate) {
                        const editorDraft = parseEmailTemplateEditorDraft(nextTemplate.body, "");
                        props.setCampaignSubject(nextTemplate.subject);
                        props.clearFieldError("subject");
                        props.setCampaignBody(nextTemplate.body);
                        props.setCampaignPlainBody(editorDraft.body);
                      }
                    }}
                    disabled={isSaving}
                    className="bg-surface-elevated py-3"
                  >
                    <option value="">Alege șablonul pentru segment</option>
                    {campaignTemplates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}
                  </SelectControl>
                </Field>
              </section>

              <section className="border-t border-border p-4 sm:p-5" aria-label="Conținut email">
                <Field data-disabled={isSaving || undefined} data-invalid={campaignFieldErrors.subject ? true : undefined}>
                  <FieldLabel htmlFor="campaign-subject">Subiect</FieldLabel>
                  <Input
                    id="campaign-subject"
                    value={campaignSubject}
                    onChange={(event) => {
                      props.setCampaignSubject(event.target.value);
                      props.clearFieldError("subject");
                    }}
                    disabled={isSaving}
                    aria-invalid={Boolean(campaignFieldErrors.subject)}
                    aria-describedby={campaignFieldErrors.subject ? "campaign-subject-error" : undefined}
                    className="py-3"
                  />
                  <FieldError id="campaign-subject-error">{campaignFieldErrors.subject}</FieldError>
                </Field>

                <div className="mt-4 border-t border-border pt-4">
                  <Field data-disabled={isSaving || undefined} data-invalid={campaignFieldErrors.body ? true : undefined}>
                    <span className="block text-xs font-medium text-brand-text">Andrei Văcaru</span>
                    <FieldLabel htmlFor="campaign-plain-body">Mesaj email</FieldLabel>
                    <Textarea
                      id="campaign-plain-body"
                      value={campaignPlainBody}
                      onChange={(event) => {
                        const editorDraft = parseEmailTemplateEditorDraft(campaignBody, "");
                        props.setCampaignPlainBody(event.target.value);
                        props.setCampaignBody(buildStyledEmailTemplateBody({
                          heading: editorDraft.heading,
                          body: event.target.value,
                          lane: "campaign",
                        }));
                        props.clearFieldError("body");
                      }}
                      disabled={isSaving}
                      aria-invalid={Boolean(campaignFieldErrors.body)}
                      aria-describedby={campaignFieldErrors.body ? "campaign-body-error" : undefined}
                      rows={8}
                      placeholder="Scrie mesajul emailului aici. Folosește rânduri libere pentru paragrafe."
                      className="mt-2 min-h-[13rem] resize-y py-3 font-medium"
                    />
                    <FieldError id="campaign-body-error">{campaignFieldErrors.body}</FieldError>
                  </Field>
                  <details className="group mt-3">
                    <summary className={cn(disclosureTriggerClassName, "flex items-center justify-between px-2 py-2 text-xs font-semibold text-muted-foreground hover:text-foreground")}>
                      <span>Editor HTML avansat</span>
                      <ChevronDownIcon aria-hidden="true" className="size-3.5 text-muted-foreground transition-transform duration-150 group-open:rotate-180" strokeWidth={1.8} />
                    </summary>
                    <Field className="mt-3" data-disabled={isSaving || undefined}>
                      <FieldLabel htmlFor="campaign-html-body">Corp email</FieldLabel>
                      <Textarea
                        id="campaign-html-body"
                        value={campaignBody}
                        onChange={(event) => {
                          props.setCampaignBody(event.target.value);
                          props.setCampaignPlainBody(
                            parseEmailTemplateEditorDraft(event.target.value, "").body,
                          );
                          props.clearFieldError("body");
                        }}
                        disabled={isSaving}
                        rows={7}
                        placeholder="Alege un șablon sau scrie corpul emailului."
                        className="max-h-[18rem] min-h-[11rem] resize-y py-3 font-mono text-xs leading-relaxed"
                      />
                    </Field>
                  </details>
                </div>
              </section>

              <section className="border-t border-border p-4 sm:p-5" aria-label="Media campanie">
                <FieldGroup className="grid gap-4 md:grid-cols-2">
                  <Field data-disabled={isSaving || undefined} data-invalid={campaignFieldErrors.videoUrl ? true : undefined}>
                    <FieldLabel htmlFor="campaign-video-url">Link video (opțional)</FieldLabel>
                    <Input
                      id="campaign-video-url"
                      type="url"
                      value={campaignVideoUrl}
                      onChange={(event) => { props.setCampaignVideoUrl(event.target.value); props.clearFieldError("videoUrl"); }}
                      disabled={isSaving}
                      aria-invalid={Boolean(campaignFieldErrors.videoUrl)}
                      aria-describedby={campaignFieldErrors.videoUrl ? "campaign-video-url-error" : undefined}
                      placeholder="https://vimeo.com/123456789"
                      className="py-3"
                    />
                    <FieldError id="campaign-video-url-error">{campaignFieldErrors.videoUrl}</FieldError>
                  </Field>
                  <Field data-disabled={isSaving || undefined} data-invalid={campaignFieldErrors.landingUrl ? true : undefined}>
                    <FieldLabel htmlFor="campaign-landing-url">Landing page Cody (opțional)</FieldLabel>
                    <Input
                      id="campaign-landing-url"
                      type="url"
                      value={campaignLandingUrl}
                      onChange={(event) => { props.setCampaignLandingUrl(event.target.value); props.clearFieldError("landingUrl"); }}
                      disabled={isSaving}
                      aria-invalid={Boolean(campaignFieldErrors.landingUrl)}
                      aria-describedby={campaignFieldErrors.landingUrl ? "campaign-landing-url-error" : undefined}
                      placeholder="Gol = direct la Vimeo"
                      className="py-3"
                    />
                    <FieldError id="campaign-landing-url-error">{campaignFieldErrors.landingUrl}</FieldError>
                  </Field>
                </FieldGroup>

                <div className="mt-4">
                  <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                    <span className="block text-xs font-bold uppercase tracking-wider text-foreground/60">Imagine campanie</span>
                    <Button type="button" variant="outline" size="sm" onClick={() => assetInputRef.current?.click()} disabled={isUploadingAsset || isSaving}>
                      {isUploadingAsset
                        ? <Loader2Icon data-icon="inline-start" aria-hidden="true" className="animate-spin" strokeWidth={1.8} />
                        : <UploadIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />}
                      {isUploadingAsset ? "Încărcăm imaginea" : "Alege imagine"}
                    </Button>
                    <Input
                      ref={assetInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp,image/gif"
                      className="sr-only !size-px !min-w-0 !border-0 !p-0"
                      tabIndex={-1}
                      disabled={isUploadingAsset || isSaving}
                      onChange={props.onAssetChange}
                    />
                  </div>
                  <Field className="mt-3" data-disabled={isSaving || undefined} data-invalid={campaignFieldErrors.thumbnailUrl ? true : undefined}>
                    <FieldLabel htmlFor="campaign-thumbnail-url">Imagine campanie</FieldLabel>
                    <Input
                      id="campaign-thumbnail-url"
                      type="url"
                      value={campaignThumbnailUrl}
                      onChange={(event) => {
                        props.clearPendingAsset();
                        props.setCampaignAssetMessage(null);
                        props.setCampaignThumbnailUrl(event.target.value);
                        props.clearFieldError("thumbnailUrl");
                      }}
                      disabled={isSaving}
                      aria-invalid={Boolean(campaignFieldErrors.thumbnailUrl)}
                      aria-describedby={campaignFieldErrors.thumbnailUrl ? "campaign-thumbnail-url-error" : undefined}
                      placeholder="https://cody.andreivacaru.ro/api/campaign-assets/thumbnail.jpg"
                      className="py-3"
                    />
                    <FieldError id="campaign-thumbnail-url-error">{campaignFieldErrors.thumbnailUrl}</FieldError>
                  </Field>
                  {campaignAssetMessage ? (
                    <InlineFeedback
                      tone={hasPendingAssetCleanup ? "danger" : "neutral"}
                      className="mt-2 px-3 py-2"
                      descriptionClassName="text-xs leading-5"
                    >
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <span>{campaignAssetMessage}</span>
                        {hasPendingAssetCleanup ? (
                          <Button
                            type="button"
                            size="xs"
                            variant="outline"
                            disabled={isRetryingAssetCleanup}
                            className="shrink-0"
                            onClick={props.retryAssetCleanup}
                          >
                            {isRetryingAssetCleanup ? "Eliminăm imaginea" : "Reîncearcă eliminarea"}
                          </Button>
                        ) : null}
                      </div>
                    </InlineFeedback>
                  ) : null}
                </div>
              </section>
            </div>

            <aside className="flex flex-col gap-4 lg:sticky lg:top-0 lg:self-start">
              <section className="rounded-lg border border-border bg-surface p-4">
                <h3 className="text-sm font-semibold text-foreground">Media</h3>
                {campaignAssetPreviewUrl || campaignThumbnailUrl ? (
                  <div className="relative mt-3 overflow-hidden rounded-lg border border-[var(--border)] bg-surface">
                    <Image
                      src={campaignAssetPreviewUrl || campaignThumbnailUrl}
                      alt="Previzualizare imagine campanie"
                      width={640}
                      height={320}
                      unoptimized
                      className="h-36 w-full object-cover"
                    />
                    {campaignVideoUrl.trim() ? (
                      <div aria-hidden="true" className="absolute inset-0 flex items-center justify-center bg-black/15">
                        <span className="flex size-11 items-center justify-center rounded-md bg-black/65 text-white shadow-sm">
                          <span className="ml-0.5 block h-0 w-0 border-y-[7px] border-l-[11px] border-y-transparent border-l-white" />
                        </span>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="mt-3 flex h-36 items-center justify-center rounded-lg border border-[var(--border)] bg-surface text-xs font-semibold text-foreground/45">Fără media</div>
                )}
                {campaignMediaHasChanges ? <InlineFeedback className="mt-3 px-3 py-2" descriptionClassName="text-xs leading-5">Modificări nesalvate</InlineFeedback> : null}
              </section>

              <section className="rounded-lg border border-border bg-surface p-4">
                <h3 className="text-sm font-semibold text-foreground">Previzualizare email</h3>
                <div className="mt-3 overflow-hidden rounded-lg border border-[var(--border)] bg-surface shadow-sm">
                  <div className="border-b border-[var(--border)] bg-surface-muted px-4 py-3">
                    <p className="text-[11px] font-semibold text-foreground/50">Către: {MOCK_REPLACEMENTS["{first_name}"]}</p>
                    <p className="mt-1 text-sm font-bold leading-5 text-foreground">{campaignPreview.subject || "Subiect campanie"}</p>
                  </div>
                  <div className="max-h-[20rem] overflow-y-auto p-4 text-sm leading-relaxed text-foreground" dangerouslySetInnerHTML={{ __html: campaignPreview.bodyHtml }} />
                </div>
              </section>
            </aside>
          </div>
        </div>

        {campaignMessage ? <InlineFeedback className="mx-6 mb-3 px-3 py-2" descriptionClassName="text-xs leading-5">{campaignMessage}</InlineFeedback> : null}
        {campaignSaveFailure ? (
          <InlineFeedback tone="danger" className="mx-6 mb-3 px-3 py-2" descriptionClassName="text-xs leading-5">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <span>{campaignSaveFailure.message}</span>
              {campaignSaveFailure.retryable ? (
                <Button type="submit" size="xs" variant="outline" disabled={isSaving} className="shrink-0">
                  Reîncearcă salvarea
                </Button>
              ) : null}
            </div>
          </InlineFeedback>
        ) : null}
        {isSaving ? (
          <OperationFeedback
            title={editingCampaign ? "Salvăm modificările campaniei" : "Salvăm campania"}
            detail={editingCampaign ? "Actualizăm conținutul și media pentru trimiterile viitoare." : "Pregătim campania pentru selectarea destinatarilor."}
            className="mx-6 mb-3"
          />
        ) : null}
        <div className="flex shrink-0 justify-end gap-3 border-t border-border bg-surface-raised px-4 py-4 sm:px-6">
          <Button type="button" onClick={props.onClose} variant="ghost" disabled={isSaving}>Anulează</Button>
          <Button type="submit" disabled={isSaving}>
            {isSaving ? <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" /> : null}
            {isSaving ? (editingCampaign ? "Salvăm modificările" : "Salvăm campania") : editingCampaign ? "Salvează modificările" : "Salvează campania"}
          </Button>
        </div>
      </form>
    </ModalLayer>
  );
}
