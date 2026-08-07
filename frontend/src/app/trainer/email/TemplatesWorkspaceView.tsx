"use client";

import type React from "react";
import { ArrowLeftIcon, EyeIcon, InfoIcon, Loader2Icon, MailIcon, PencilIcon, PlusIcon, Trash2Icon } from "lucide-react";

import type { EmailTemplate } from "@/api/email";
import { CatalogCard, CatalogToolbar } from "@/components/presentation/catalog-card";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { SearchField } from "@/components/ui/search-field";
import { SelectControl } from "@/components/ui/select-control";
import { Textarea } from "@/components/ui/textarea";
import { IconButton } from "./EmailWorkspaceControls";
import { DEFAULT_ACTION_TOKEN, DEFAULT_VIDEO_TOKEN, MOCK_REPLACEMENTS, emailTemplateCtaCount, parseEmailTemplateEditorDraft } from "./email-template-domain";

type TemplateOperation = null | "save" | "create" | "version" | "delete";
type Preview = { subject: string; bodyHtml: string };

export type TemplatesWorkspaceViewProps = {
  selectedTemplateId: string;
  selectedTemplate: EmailTemplate | undefined;
  filteredTemplates: EmailTemplate[];
  templateCount: number;
  searchQuery: string;
  isEditing: boolean;
  isLoading: boolean;
  operation: TemplateOperation;
  editSubject: string;
  editHeading: string;
  editBody: string;
  editLane: "transactional" | "campaign";
  preview: Preview;
  previewCalendlyUrl: string;
  validationMessage: string | null;
  onSearchChange: (value: string) => void;
  onSelectTemplate: (id: string) => void;
  onCreate: () => void;
  onSave: () => void;
  onCreateVersion: () => void;
  onDelete: () => void;
  setIsEditing: (value: boolean) => void;
  setEditSubject: (value: string) => void;
  setEditHeading: (value: string) => void;
  setEditBody: React.Dispatch<React.SetStateAction<string>>;
  setEditLane: (value: "transactional" | "campaign") => void;
  setPreviewCalendlyUrl: (value: string) => void;
};

export function TemplatesWorkspaceView(props: TemplatesWorkspaceViewProps) {
  const selectedTemplate = props.selectedTemplate;
  if (!props.selectedTemplateId) {
    return (
      <div className="flex flex-col gap-6">
        <CatalogToolbar>
          <SearchField
            id="email-template-search"
            label="Caută șabloane"
            value={props.searchQuery}
            onValueChange={props.onSearchChange}
            placeholder="Caută șabloane"
            className="w-full md:flex-1"
          />
          <Button type="button" onClick={props.onCreate} disabled={props.isLoading} className="shrink-0">
            {props.operation === "create" ? <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" /> : <PlusIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />}
            {props.operation === "create" ? "Creăm șablonul" : "Creează șablon"}
          </Button>
        </CatalogToolbar>

        {props.isLoading && props.templateCount === 0 ? (
          <div className="flex min-h-64 items-center justify-center rounded-lg border border-[var(--border)] bg-surface p-6 text-foreground">
            <OperationFeedback
              className="w-full max-w-md"
              title={props.operation === "create" ? "Creăm șablonul" : "Încărcăm șabloanele"}
              detail={props.operation === "create" ? "Salvăm o primă versiune și pregătim editorul." : "Pregătim versiunile de email și conținutul salvat."}
            />
          </div>
        ) : props.filteredTemplates.length > 0 ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {props.filteredTemplates.map((template) => (
              <CatalogCard
                key={template.id}
                onClick={() => { props.onSelectTemplate(template.id); props.setIsEditing(false); }}
                aria-label={`Deschide șablon ${template.name}`}
                eyebrow={template.lane === "transactional" ? "Sistem" : "Campanie"}
                version={`v${template.version ?? 1}`}
                title={template.name}
                description={template.subject || "Fără subiect"}
                metadata={
                  <span className="font-medium tabular-nums">
                    {template.placeholders.length} {template.placeholders.length === 1 ? "variabilă" : "variabile"}
                  </span>
                }
              />
            ))}
          </div>
        ) : (
          <div className="flex h-64 flex-col items-center justify-center rounded-lg border border-[var(--border)] bg-surface-muted p-6 text-center">
            <MailIcon aria-hidden="true" className="mb-4 size-9 text-muted-foreground" strokeWidth={1.8} />
            <p className="mb-1 text-lg font-bold text-foreground">Niciun șablon găsit</p>
            <p className="text-sm font-medium text-foreground/50">Modifică termenii de căutare sau creează un șablon nou.</p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="-ml-1">
        <Button type="button" variant="ghost" size="icon-sm" onClick={() => props.onSelectTemplate("")} disabled={props.isLoading} aria-label="Înapoi la catalog" title="Înapoi la catalog" className="text-foreground/62 hover:text-foreground">
          <ArrowLeftIcon aria-hidden="true" strokeWidth={1.8} />
        </Button>
      </div>
      {selectedTemplate ? (
        <main className="grid gap-5 xl:grid-cols-[minmax(0,1.05fr)_minmax(22rem,0.95fr)]">
          <section className="flex min-w-0 flex-col rounded-lg border border-border bg-surface p-4 text-foreground md:p-5">
            <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
              <div><h3 className="text-xl font-semibold text-foreground">{props.isEditing ? "Modificare șablon" : "Detalii șablon"}</h3><p className="mt-1 text-xs font-medium tabular-nums text-muted-foreground">Versiunea {selectedTemplate.version ?? 1}</p></div>
              <div className="flex flex-wrap justify-end gap-2">
                {props.isEditing ? (
                  <>
                    <Button type="button" size="sm" onClick={props.onSave} disabled={props.isLoading || Boolean(props.validationMessage)}>{props.isLoading ? <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" /> : null}{props.isLoading ? "Salvăm" : "Salvează"}</Button>
                    <Button type="button" size="sm" variant="outline" onClick={() => props.setIsEditing(false)} disabled={props.isLoading}>Anulează</Button>
                  </>
                ) : (
                  <>
                    <IconButton label="Editează șablonul" onClick={() => props.setIsEditing(true)} disabled={props.isLoading}><PencilIcon aria-hidden="true" className="size-4" strokeWidth={1.8} /></IconButton>
                    <Button type="button" size="sm" variant="outline" onClick={props.onCreateVersion} disabled={props.isLoading}><PlusIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />Versiune nouă</Button>
                    <IconButton label="Șterge șablonul" tone="danger" onClick={props.onDelete} disabled={props.isLoading}><Trash2Icon aria-hidden="true" className="size-4" strokeWidth={1.8} /></IconButton>
                  </>
                )}
              </div>
            </div>
            {props.isLoading ? (
              <OperationFeedback
                className="mb-5"
                title={props.operation === "version" ? "Creăm versiunea nouă" : props.operation === "delete" ? "Pensionăm șablonul" : "Actualizăm șablonul"}
                detail={props.operation === "version" ? "Clonăm conținutul curent într-o versiune nouă editabilă." : props.operation === "delete" ? "Scoatem șablonul din catalog și păstrăm campaniile existente." : "Sincronizăm conținutul, versiunea și previzualizarea emailului."}
              />
            ) : null}
            {props.isEditing && props.validationMessage ? (
              <div
                role="alert"
                className="mb-5 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm font-medium leading-6 text-foreground"
              >
                {props.validationMessage}
              </div>
            ) : null}
            <FieldGroup className="flex-1">
              <Field data-disabled>
                <FieldLabel htmlFor="template-internal-name">Nume intern</FieldLabel>
                <Input id="template-internal-name" type="text" disabled readOnly value={selectedTemplate.name} className="py-3 disabled:opacity-60" />
                <FieldDescription>Numele este derivat din cheia șablonului și rămâne stabil între versiuni.</FieldDescription>
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field data-disabled={!props.isEditing || props.isLoading ? true : undefined}>
                  <FieldLabel htmlFor="template-send-lane">Canal trimitere</FieldLabel>
                  <SelectControl id="template-send-lane" label="Canal trimitere" disabled={!props.isEditing || props.isLoading} value={props.isEditing ? props.editLane : selectedTemplate.lane} onChange={(event) => props.setEditLane(event.target.value as "transactional" | "campaign")} className="bg-surface-elevated py-3 disabled:opacity-60">
                    <option value="transactional">Tranzacțional (Sistem)</option><option value="campaign">Campanie (Prospectare)</option>
                  </SelectControl>
                </Field>
                <Field>
                  <FieldLabel>Tag-uri active</FieldLabel>
                  <div className="flex min-h-11 flex-wrap items-center gap-x-3 gap-y-1.5 rounded-md bg-surface-muted px-3 py-2">
                    {selectedTemplate.placeholders.length > 0 ? selectedTemplate.placeholders.map((placeholder) => <span key={placeholder} className="font-mono text-xs font-medium text-muted-foreground">{placeholder}</span>) : <span className="text-xs font-medium text-muted-foreground">Niciun tag</span>}
                  </div>
                </Field>
              </div>
              <Field data-disabled={!props.isEditing || props.isLoading ? true : undefined}>
                <FieldLabel htmlFor="template-email-subject">Subiect email</FieldLabel>
                <Input id="template-email-subject" type="text" disabled={!props.isEditing || props.isLoading} value={props.isEditing ? props.editSubject : selectedTemplate.subject} onChange={(event) => props.setEditSubject(event.target.value)} aria-invalid={props.isEditing && !props.editSubject.trim() ? true : undefined} className="py-3 disabled:opacity-60" />
              </Field>
              <Field data-disabled={!props.isEditing || props.isLoading ? true : undefined}>
                <FieldLabel htmlFor="template-email-heading">Titlu mare în email</FieldLabel>
                <Input id="template-email-heading" type="text" disabled={!props.isEditing || props.isLoading} value={props.isEditing ? props.editHeading : parseEmailTemplateEditorDraft(selectedTemplate.body, selectedTemplate.subject).heading} onChange={(event) => props.setEditHeading(event.target.value)} className="py-3 disabled:opacity-60" />
              </Field>
              <Field className="flex-1" data-disabled={!props.isEditing || props.isLoading ? true : undefined}>
                <FieldLabel htmlFor="template-email-body">Corp email</FieldLabel>
                {props.isEditing ? (
                  <div className="mb-2 flex flex-wrap gap-2">
                    <Button type="button" variant="outline" size="xs" onClick={() => props.setEditBody((current) => `${current.trim() ? `${current.trim()}\n\n` : ""}${DEFAULT_ACTION_TOKEN}`)} disabled={props.isLoading || emailTemplateCtaCount(props.editBody) >= 1}>Adaugă buton link</Button>
                    <Button type="button" variant="outline" size="xs" onClick={() => props.setEditBody((current) => `${current.trim() ? `${current.trim()}\n\n` : ""}${DEFAULT_VIDEO_TOKEN}`)} disabled={props.isLoading}>Adaugă video</Button>
                  </div>
                ) : null}
                <Textarea id="template-email-body" disabled={!props.isEditing || props.isLoading} value={props.isEditing ? props.editBody : parseEmailTemplateEditorDraft(selectedTemplate.body, selectedTemplate.subject).body} onChange={(event) => props.setEditBody(event.target.value)} aria-invalid={props.isEditing && !props.editBody.trim() ? true : undefined} className="min-h-[200px] flex-1 resize-none py-4 font-mono leading-relaxed disabled:opacity-60" />
              </Field>
            </FieldGroup>
          </section>

          <section className="flex min-w-0 flex-col rounded-lg border border-border bg-surface-muted p-4 text-foreground md:p-5">
            <div className="mb-4 flex items-center gap-2.5"><EyeIcon aria-hidden="true" className="size-4 text-muted-foreground" strokeWidth={1.8} /><h3 className="text-sm font-semibold text-foreground">Previzualizare email</h3></div>
            <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-border bg-surface">
              <div className="flex flex-col gap-2 border-b border-[var(--border)] bg-surface-muted p-5 text-xs text-foreground/60">
                <div className="flex items-center justify-between"><p><strong className="text-foreground/80">De la:</strong> Andrei Văcaru</p><span className="font-mono text-[10px] opacity-50">10:42 AM</span></div>
                <p><strong className="text-foreground/80">Către:</strong> {MOCK_REPLACEMENTS["{first_name}"]}</p><p className="pt-1 text-sm font-bold text-foreground">{props.preview.subject}</p>
              </div>
              <div className="flex-1 bg-surface p-6 font-sans text-[15px] leading-relaxed text-foreground" dangerouslySetInnerHTML={{ __html: props.preview.bodyHtml }} />
            </div>
            <Field className="mt-5 border-t border-border pt-4">
              <FieldLabel htmlFor="template-preview-calendly-url">Link Calendly pentru previzualizare</FieldLabel>
              <Input id="template-preview-calendly-url" type="url" value={props.previewCalendlyUrl} onChange={(event) => props.setPreviewCalendlyUrl(event.target.value)} className="py-3 font-mono text-xs" placeholder="https://calendly.com/andreivacaru/intalnire-de-apropiere" />
              <FieldDescription className="text-[11px] leading-relaxed">Folosit pentru tag-ul <code className="rounded bg-foreground/5 px-1">{`{calendly_url}`}</code> în previzualizare. La trimitere, backendul inserează linkul real configurat pentru campanii.</FieldDescription>
            </Field>
            <div className="mt-4 flex items-start gap-2.5 px-1 text-muted-foreground">
              <InfoIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0" strokeWidth={1.8} /><p className="text-xs leading-5">Tag-urile ca <code className="rounded bg-foreground/5 px-1">{`{first_name}`}</code> și <code className="rounded bg-foreground/5 px-1">{`{calendly_url}`}</code> sunt înlocuite automat la expediere. Formatarea acceptă <strong className="text-foreground">**text**</strong> și <span className="text-brand-text underline">[linkuri](url)</span>.</p>
            </div>
          </section>
        </main>
      ) : null}
    </div>
  );
}
