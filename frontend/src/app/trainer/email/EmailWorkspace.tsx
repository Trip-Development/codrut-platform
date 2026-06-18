"use client";

import Link from "next/link";
import React, { useCallback, useEffect, useState } from "react";
import {
  listEmailTemplatesOnServer,
  createEmailTemplateOnServer,
  updateEmailTemplateOnServer,
  deleteEmailTemplateOnServer,
  bulkCreateCampaignRecipientsOnServer,
  createCampaignOnServer,
  listCampaignsOnServer,
  type EmailOpsSummary,
  type AssessmentDeliveryRow,
  type EmailCampaign,
  type EmailTemplate
} from "@/api/email";
import * as XLSX from "xlsx";

type TabKey = "delivery" | "campaigns" | "templates";


const MOCK_REPLACEMENTS: Record<string, string> = {
  "{first_name}": "Ioana",
  "{project}": "Intake Iunie",
  "{link_securizat}": "https://app.codrut.ro/auth/seclink-8f2a175",
  "{estimare_timp}": "15",
  "{sarcini_ramase}": "2 chestionare rămase (Lencioni, Distress)",
  "{link_video}": "https://watch.codrut.ro/v/performanta-echipe-2026",
};

function detectedPlaceholders(subject: string, body: string): string[] {
  const placeholderRegex = /\{[a-z0-9_]+\}/gi;
  return Array.from(new Set(`${subject} ${body}`.match(placeholderRegex) || []));
}

type EmailWorkspaceProps = {
  initialSummary: EmailOpsSummary;
};

export function EmailWorkspace({ initialSummary }: EmailWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<TabKey>("templates");
  const [summary, setSummary] = useState<EmailOpsSummary>(initialSummary);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const refreshSummary = async () => {
    setIsRefreshing(true);
    try {
      const { getEmailOpsSummary } = await import("@/api/email");
      const fresh = await getEmailOpsSummary();
      setSummary(fresh);
    } finally {
      setIsRefreshing(false);
    }
  };

  // Template Manager States
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("");
  const [isEditing, setIsEditing] = useState(false);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(false);

  // Editor fields
  const [editName, setEditName] = useState("");
  const [editSubject, setEditSubject] = useState("");
  const [editBody, setEditBody] = useState("");
  const [editLane, setEditLane] = useState<"transactional" | "campaign">("transactional");

  // Campaign Manager States
  const [isUploadingCSV, setIsUploadingCSV] = useState(false);
  const [campaigns, setCampaigns] = useState<EmailCampaign[]>([]);
  const [isLoadingCampaigns, setIsLoadingCampaigns] = useState(false);
  const [isCreatingCampaign, setIsCreatingCampaign] = useState(false);
  const [campaignName, setCampaignName] = useState("Campanie video leadership");
  const [campaignSegment, setCampaignSegment] = useState<"past_customer" | "potential_customer">("potential_customer");
  const [campaignSubject, setCampaignSubject] = useState("O idee practică pentru echipa ta, {first_name}");
  const [campaignVideoUrl, setCampaignVideoUrl] = useState("");
  const [campaignThumbnailUrl, setCampaignThumbnailUrl] = useState("");
  const [campaignLandingUrl, setCampaignLandingUrl] = useState("");
  const [campaignMessage, setCampaignMessage] = useState<string | null>(null);

  // Manual Add State
  const [showManualAddModal, setShowManualAddModal] = useState(false);
  const [manualEmail, setManualEmail] = useState("");
  const [manualName, setManualName] = useState("");
  const [manualCompany, setManualCompany] = useState("");
  const [manualSegment, setManualSegment] = useState<"past_customer" | "potential_customer">("potential_customer");
  const [isAddingManual, setIsAddingManual] = useState(false);

  const handleAddManualContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualEmail.trim()) return;
    setIsAddingManual(true);
    try {
      await bulkCreateCampaignRecipientsOnServer([{
        email: manualEmail.trim(),
        contact_name: manualName.trim() || undefined,
        organization_name: manualCompany.trim() || undefined,
        segment: manualSegment,
      }]);
      alert("Contact adăugat cu succes!");
      setShowManualAddModal(false);
      setManualEmail("");
      setManualName("");
      setManualCompany("");
      refreshSummary();
    } catch {
      alert("Eroare la adăugarea contactului.");
    } finally {
      setIsAddingManual(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploadingCSV(true);
    try {
      const data = await file.arrayBuffer();
      const workbook = XLSX.read(data, { type: "array" });
      const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
      const rows = XLSX.utils.sheet_to_json(firstSheet) as Record<string, string>[];
      
      const payload = rows.map((row) => {
        const email = row["email"] || row["Email"] || row["EMAIL"];
        const name = row["name"] || row["nume"] || row["Name"] || row["Nume"];
        const company = row["company"] || row["companie"] || row["Company"] || row["Companie"];
        const segmentStr = row["segment"] || row["Segment"];
        const segment = segmentStr?.toString().toLowerCase().includes("past") ? "past_customer" : "potential_customer";
        
        return {
          email,
          contact_name: name,
          organization_name: company,
          segment: segment as "past_customer" | "potential_customer",
        };
      }).filter(r => r.email);

      if (payload.length > 0) {
        await bulkCreateCampaignRecipientsOnServer(payload);
        alert(`S-au importat cu succes ${payload.length} contacte!`);
        refreshSummary();
      } else {
        alert("Fișierul nu conține coloana 'email'. Vă rugăm să folosiți un cap de tabel valid.");
      }
    } catch {
      alert("Eroare la procesarea fișierului.");
    } finally {
      setIsUploadingCSV(false);
      e.target.value = "";
    }
  };

  const loadCampaigns = useCallback(async () => {
    setIsLoadingCampaigns(true);
    try {
      setCampaigns(await listCampaignsOnServer());
    } finally {
      setIsLoadingCampaigns(false);
    }
  }, []);

  useEffect(() => {
    loadCampaigns();
  }, [loadCampaigns]);

  const handleCreateCampaign = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedName = campaignName.trim();
    const trimmedVideoUrl = campaignVideoUrl.trim();
    const trimmedThumbnailUrl = campaignThumbnailUrl.trim();
    const trimmedLandingUrl = campaignLandingUrl.trim() || trimmedVideoUrl;

    if (!trimmedName || !trimmedVideoUrl || !trimmedThumbnailUrl || !trimmedLandingUrl) {
      setCampaignMessage("Completează numele, video-ul, thumbnail-ul și pagina de destinație.");
      return;
    }

    setIsCreatingCampaign(true);
    setCampaignMessage(null);
    try {
      await createCampaignOnServer({
        name: trimmedName,
        segment: campaignSegment,
        subject: campaignSubject.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}"),
        html_body: [
          "<p>Bună, ${first_name}.</p>",
          "<p>Am pregătit un material video scurt pentru contextul echipei tale.</p>",
          `<p><a href="${trimmedLandingUrl}">Vezi video-ul</a></p>`,
        ].join(""),
        text_body: `Bună, \${first_name}. Vezi video-ul aici: ${trimmedLandingUrl}`,
        video_url: trimmedVideoUrl,
        thumbnail_url: trimmedThumbnailUrl,
        landing_page_url: trimmedLandingUrl,
      });
      setCampaignMessage("Campania a fost salvată.");
      await loadCampaigns();
    } catch (error) {
      setCampaignMessage(error instanceof Error ? error.message : "Campania nu a putut fi salvată.");
    } finally {
      setIsCreatingCampaign(false);
    }
  };

  // Search state
  const [searchQuery, setSearchQuery] = useState("");

  const filteredTemplates = React.useMemo(() => {
    if (!searchQuery.trim()) return templates;
    const q = searchQuery.toLowerCase();
    return templates.filter((t) => 
      t.name.toLowerCase().includes(q) || 
      t.subject.toLowerCase().includes(q)
    );
  }, [templates, searchQuery]);

  // Load templates from Server
  const loadTemplates = useCallback(async () => {
    setIsLoadingTemplates(true);
    try {
      const list = await listEmailTemplatesOnServer(true);
      setTemplates(list);
    } finally {
      setIsLoadingTemplates(false);
    }
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  // Sync editor fields when selected template changes
  const selectedTemplate = templates.find((t) => t.id === selectedTemplateId);
  useEffect(() => {
    if (selectedTemplate) {
      setEditName(selectedTemplate.name);
      setEditSubject(selectedTemplate.subject);
      setEditBody(selectedTemplate.body);
      setEditLane(selectedTemplate.lane);
    }
  }, [selectedTemplate]);

  const handleSaveTemplate = async () => {
    if (!selectedTemplateId || !selectedTemplate) return;
    setIsLoadingTemplates(true);
    try {
      const updatedTemp: EmailTemplate = {
        ...selectedTemplate,
        subject: editSubject,
        body: editBody,
        lane: editLane,
        placeholders: detectedPlaceholders(editSubject, editBody),
      };
      const saved = await updateEmailTemplateOnServer(updatedTemp);
      setIsEditing(false);
      setSelectedTemplateId(saved.id);
      await loadTemplates();
    } catch (e) {
      alert((e as Error).message ?? "Eroare la salvarea șablonului.");
    } finally {
      setIsLoadingTemplates(false);
    }
  };

  const handleCreateTemplate = async () => {
    const key = `template_${Date.now()}`;
    const newTemp: EmailTemplate = {
      id: key,
      baseKey: key,
      version: 1,
      name: "Șablon Email Nou",
      subject: "Subiectul emailului {first_name}",
      lane: "transactional",
      placeholders: ["{first_name}"],
      body: `Salut {first_name},

Introduceți conținutul noului șablon email aici. Puteți folosi coduri între acolade pentru personalizare.`,
    };
    setIsLoadingTemplates(true);
    try {
      const saved = await createEmailTemplateOnServer(newTemp);
      setSelectedTemplateId(saved.id);
      setIsEditing(true);
      await loadTemplates();
    } catch (e) {
      alert((e as Error).message ?? "Eroare la crearea șablonului.");
    } finally {
      setIsLoadingTemplates(false);
    }
  };

  const handleCreateTemplateVersion = async () => {
    if (!selectedTemplate) return;
    setIsLoadingTemplates(true);
    try {
      const nextTemplate: EmailTemplate = {
        ...selectedTemplate,
        version: selectedTemplate.version + 1,
      };
      const saved = await createEmailTemplateOnServer(nextTemplate);
      setSelectedTemplateId(saved.id);
      setIsEditing(true);
      await loadTemplates();
    } catch (e) {
      alert((e as Error).message ?? "Eroare la crearea versiunii noi.");
    } finally {
      setIsLoadingTemplates(false);
    }
  };

  const handleDeleteTemplate = async () => {
    if (!selectedTemplate) return;
    if (templates.length <= 1) {
      alert("Trebuie să păstrați cel puțin un șablon în catalog.");
      return;
    }
    if (!confirm("Sigur doriți să pensionați acest șablon?")) return;

    setIsLoadingTemplates(true);
    try {
      await deleteEmailTemplateOnServer(selectedTemplate.baseKey); // Fix: Remove version to delete the whole template
      const list = await listEmailTemplatesOnServer(true);
      setTemplates(list);
      const remaining = list.filter((t) => t.id !== selectedTemplateId);
      if (remaining.length > 0) {
        setSelectedTemplateId(remaining[0].id);
      } else if (list.length > 0) {
        setSelectedTemplateId(list[0].id);
      }
      setIsEditing(false);
    } catch (e) {
      alert((e as Error).message ?? "Eroare la pensionarea șablonului.");
    } finally {
      setIsLoadingTemplates(false);
    }
  };

  // Convert markdown to clean, basic HTML preview
  const getRenderedPreview = (subjectText: string, bodyText: string, lane: string) => {
    let replacedSubject = subjectText;
    let replacedBody = bodyText;

    Object.entries(MOCK_REPLACEMENTS).forEach(([key, val]) => {
      replacedSubject = replacedSubject.replace(new RegExp(key, "g"), val);
      replacedBody = replacedBody.replace(new RegExp(key, "g"), val);
    });

    // Basic markdown parsing
    let html = replacedBody
      .replace(/\r?\n/g, "<br />")
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" class="text-burgundy underline font-bold">$1</a>');

    if (lane === "campaign") {
      html += `
        <div style="margin-top:24px;padding-top:24px;border-top:1px solid #eadfdb;font-size:12px;line-height:1.5;color:#8c7e7b;text-align:center;font-family:sans-serif;">
          <p style="margin:0 0 8px;">Ai primit acest email deoarece ești abonat la actualizările noastre sau ești un client.</p>
          <p style="margin:0 0 8px;">
            <a href="https://app.codrut.ro/unsubscribe" style="color:#6d5f5b;text-decoration:underline;">Dezabonare</a>
          </p>
          <p style="margin:0;">Str. Exemplu Nr. 10, București, România</p>
        </div>
      `;
    }

    return {
      subject: replacedSubject,
      bodyHtml: html,
    };
  };

  const preview = selectedTemplate
    ? getRenderedPreview(
        isEditing ? editSubject : selectedTemplate.subject,
        isEditing ? editBody : selectedTemplate.body,
        isEditing ? editLane : selectedTemplate.lane
      )
    : { subject: "", bodyHtml: "" };

  const deliveryLabel = (delivery: AssessmentDeliveryRow["delivery"]) => {
    switch (delivery) {
      case "draft":
        return "Ciornă";
      case "sent":
        return "Trimis";
      case "delivered":
        return "Livrat";
      case "opened":
        return "Deschis";
      case "failed":
        return "Eșuat";
      default:
        return delivery;
    }
  };

  const reminderLabel = (reminder: AssessmentDeliveryRow["reminder"]) => {
    switch (reminder) {
      case "today":
        return "Azi";
      case "tomorrow":
        return "Mâine";
      case "paused":
        return "Oprit";
      default:
        return "Fără";
    }
  };

  return (
    <div className="space-y-8 animate-fade-in-up">
      <div className="flex flex-wrap gap-2 border-b border-[var(--border)] pb-0 relative">
        <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-burgundy/5 via-burgundy/20 to-transparent"></div>
        <button
          onClick={() => setActiveTab("templates")}
          className={`px-6 py-3 text-sm font-bold rounded-t-2xl transition-all border-b-2 relative z-10 ${
            activeTab === "templates"
              ? "border-burgundy text-burgundy bg-surface shadow-[0_-4px_16px_rgba(137,5,5,0.05)]"
              : "border-transparent text-foreground/50 hover:text-foreground hover:bg-surface-muted/50"
          }`}
        >
          Șabloane email
        </button>
        <button
          onClick={() => setActiveTab("delivery")}
          className={`px-6 py-3 text-sm font-bold rounded-t-2xl transition-all border-b-2 relative z-10 ${
            activeTab === "delivery"
              ? "border-burgundy text-burgundy bg-surface shadow-[0_-4px_16px_rgba(137,5,5,0.05)]"
              : "border-transparent text-foreground/50 hover:text-foreground hover:bg-surface-muted/50"
          }`}
        >
          Arhivă globală
        </button>
        <button
          onClick={() => setActiveTab("campaigns")}
          className={`px-6 py-3 text-sm font-bold rounded-t-2xl transition-all border-b-2 relative z-10 ${
            activeTab === "campaigns"
              ? "border-burgundy text-burgundy bg-surface shadow-[0_-4px_16px_rgba(137,5,5,0.05)]"
              : "border-transparent text-foreground/50 hover:text-foreground hover:bg-surface-muted/50"
          }`}
        >
          Campanii
        </button>
      </div>

      {activeTab === "delivery" && (
        <div className="space-y-6">
          <section className="bento-card overflow-hidden relative">
            <div className="absolute top-0 right-0 p-32 bg-burgundy/5 blur-3xl rounded-full -mr-16 -mt-16 pointer-events-none"></div>
            <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between p-8 relative z-10">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80">Context global</p>
                <h2 className="mt-2 font-display text-2xl font-bold text-foreground">Invitațiile live se operează din companie</h2>
                <p className="mt-3 max-w-2xl text-sm leading-relaxed text-foreground/60">
                  Această pagină păstrează o privire agregată și șabloanele. Pentru a trimite emailuri, genera linkuri securizate sau verifica statusul unei persoane, deschide proiectul și tabul Invitații.
                </p>
              </div>
              <Link
                href="/trainer/companies"
                className="btn-premium shrink-0"
              >
                Deschide companii
              </Link>
            </div>
          </section>

          {/* Metrics summary grid */}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {summary.metrics.map((metric) => (
              <article key={metric.label} className="bento-card p-6 relative overflow-hidden group">
                <div className="absolute inset-0 bg-gradient-to-br from-surface to-surface-muted/30 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                <div className="relative z-10">
                  <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-burgundy/70">{metric.label}</p>
                  <p className="mt-3 font-display text-4xl font-bold text-foreground tracking-tight">{metric.value}</p>
                  <p className="mt-2 text-sm leading-relaxed text-foreground/50">{metric.detail}</p>
                </div>
              </article>
            ))}
          </div>

          {/* Delivery Queue table */}
          <section className="bento-card">
            <div className="border-b border-[var(--border)] px-8 py-6 bg-surface-muted/20">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80">Invitații</p>
              <h2 className="mt-2 text-xl font-bold text-foreground">Status acces participanți</h2>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-foreground/60">
                Liderii primesc cont complet, membrii primesc link securizat de completare rapidă.
              </p>
            </div>
            <div className="hidden overflow-x-auto xl:block">
              <table className="min-w-[980px] w-full text-left text-sm">
                <thead className="bg-surface-muted/40 text-[11px] font-bold uppercase tracking-[0.15em] text-foreground/50 border-b border-[var(--border)]">
                  <tr>
                    <th className="px-8 py-4">Recipient</th>
                    <th className="px-8 py-4">Acces</th>
                    <th className="px-8 py-4">Sarcini</th>
                    <th className="px-8 py-4">Status livrare</th>
                    <th className="px-8 py-4">Reminder</th>
                    <th className="px-8 py-4">Următorul pas</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {summary.assessmentRows.map((row) => (
                    <tr key={row.id} className="align-top hover:bg-surface-muted/20 transition-colors">
                      <td className="px-8 py-5">
                        <p className="font-bold text-foreground">{row.participant}</p>
                        <p className="mt-1 text-[11px] text-foreground/50 font-mono">{row.email}</p>
                        <p className="mt-1.5 text-xs font-bold text-burgundy">{row.project}</p>
                      </td>
                      <td className="px-8 py-5">
                        <span className="inline-flex items-center rounded-full bg-surface-muted/80 px-3 py-1 text-xs font-bold text-foreground/70 border border-[var(--border)] shadow-sm whitespace-nowrap">
                          {row.audience === "leadership_account" ? "Cont lider" : "Link securizat"}
                        </span>
                      </td>
                      <td className="px-8 py-5 text-foreground/70 font-bold">{row.tasks}</td>
                      <td className="px-8 py-5">
                        <span className={`inline-flex items-center rounded-full px-3 py-1 text-[11px] font-bold border uppercase tracking-wider whitespace-nowrap shadow-sm ${
                          row.delivery === "delivered" || row.delivery === "opened"
                            ? "bg-green-50 border-green-200 text-green-700"
                            : row.delivery === "failed"
                              ? "bg-red-50 border-red-200 text-red-700"
                              : "bg-surface border-[var(--border)] text-foreground/60"
                        }`}>
                          {deliveryLabel(row.delivery)}
                        </span>
                      </td>
                      <td className="px-8 py-5">
                        <span className="inline-flex items-center rounded-full bg-surface px-3 py-1 text-[11px] font-bold text-foreground/60 border border-[var(--border)] shadow-sm uppercase tracking-wider">
                          {reminderLabel(row.reminder)}
                        </span>
                      </td>
                      <td className="px-8 py-5 text-foreground/60 font-semibold max-w-[200px] leading-relaxed">{row.nextAction}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="grid gap-4 p-6 xl:hidden">
              {summary.assessmentRows.map((row) => (
                <article key={row.id} className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <p className="font-bold text-foreground text-lg">{row.participant}</p>
                      <p className="mt-1 break-all text-xs text-foreground/50 font-mono">{row.email}</p>
                      <p className="mt-2 text-xs font-bold text-burgundy uppercase tracking-wider">{row.project}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className="rounded-full border border-[var(--border)] bg-surface-muted px-3 py-1 text-xs font-bold text-foreground/70 shadow-sm">
                        {row.audience === "leadership_account" ? "Cont lider" : "Link securizat"}
                      </span>
                      <span className={`rounded-full px-3 py-1 text-xs font-bold border uppercase tracking-wider shadow-sm ${
                        row.delivery === "delivered" || row.delivery === "opened"
                          ? "bg-green-50 border-green-200 text-green-700"
                          : row.delivery === "failed"
                            ? "bg-red-50 border-red-200 text-red-700"
                            : "bg-surface border-[var(--border)] text-foreground/60"
                      }`}>
                        {deliveryLabel(row.delivery)}
                      </span>
                    </div>
                  </div>

                  <dl className="mt-5 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-xl bg-surface-muted/30 border border-[var(--border)] px-4 py-3">
                      <dt className="text-[10px] font-bold uppercase tracking-wider text-foreground/50 mb-1">Sarcini</dt>
                      <dd className="text-sm font-bold text-foreground">{row.tasks}</dd>
                    </div>
                    <div className="rounded-xl bg-surface-muted/30 border border-[var(--border)] px-4 py-3">
                      <dt className="text-[10px] font-bold uppercase tracking-wider text-foreground/50 mb-1">Reminder</dt>
                      <dd className="text-sm font-bold text-foreground">{reminderLabel(row.reminder)}</dd>
                    </div>
                    <div className="rounded-xl bg-surface-muted/30 border border-[var(--border)] px-4 py-3 sm:col-span-3">
                      <dt className="text-[10px] font-bold uppercase tracking-wider text-foreground/50 mb-1">Următorul pas</dt>
                      <dd className="text-sm font-semibold leading-relaxed text-foreground/70">{row.nextAction}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          </section>

          {/* Quick Actions Panel */}
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
            <section className="bento-card p-8 flex flex-col justify-center">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80 mb-4">Operare globală</p>
              <div className="grid gap-4 md:grid-cols-2">
                <button
                  type="button"
                  disabled={isRefreshing}
                  onClick={refreshSummary}
                  className="btn-secondary min-h-[3rem] w-full"
                >
                  {isRefreshing ? "Se actualizează..." : "Actualizează starea"}
                </button>
              </div>
            </section>

            <section className="bento-card p-8 bg-surface-muted/10">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80 mb-4">Reguli de livrare</p>
              <div className="space-y-3">
                {summary.rules.map((rule) => (
                  <p key={rule} className="rounded-xl bg-surface px-4 py-3 text-xs font-medium leading-relaxed text-foreground/70 border border-[var(--border)] shadow-sm">
                    {rule}
                  </p>
                ))}
              </div>
            </section>
          </div>
        </div>
      )}

      {activeTab === "campaigns" && (
        <div className="space-y-6 animate-fade-in-up">
          {/* Campaigns header */}
          <section className="bento-card overflow-hidden relative p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="absolute top-0 right-0 p-32 bg-burgundy/5 blur-3xl rounded-full -mr-16 -mt-16 pointer-events-none"></div>
            <div className="relative z-10">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80">Campanii Promoționale</p>
              <h2 className="mt-2 font-display text-2xl font-bold text-foreground">Emailuri video personalizate</h2>
              <p className="mt-3 max-w-2xl text-sm leading-relaxed text-foreground/60">
                Aici poți încărca liste Excel/CSV cu contacte (prospects sau clienți vechi) și să le trimiți automat campanii personalizate bazate pe șabloane.
              </p>
            </div>
            
            <div className="relative z-10 shrink-0">
              <label className="btn-premium cursor-pointer inline-flex items-center gap-2">
                {isUploadingCSV ? (
                  <span>Se încarcă...</span>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
                    Importă contacte
                  </>
                )}
                <input 
                  type="file" 
                  accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel" 
                  className="hidden" 
                  onChange={handleFileUpload}
                  disabled={isUploadingCSV}
                />
              </label>
            </div>
          </section>

          <section className="bento-card">
            <div className="border-b border-[var(--border)] px-8 py-6 bg-surface-muted/20 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80">Date și setări</p>
                <h2 className="mt-2 text-xl font-bold text-foreground">Setări campanie curentă</h2>
              </div>
              <button
                type="button"
                className="btn-secondary text-xs py-2 px-4 whitespace-nowrap"
                onClick={() => setShowManualAddModal(true)}
              >
                + Adaugă contact manual
              </button>
            </div>
            <div className="grid gap-0 divide-y divide-[var(--border)] lg:grid-cols-[22rem_minmax(0,1fr)] lg:divide-x lg:divide-y-0">
              <div className="space-y-4 p-6 bg-surface-muted/10">
                <article className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
                  <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-burgundy/70 mb-2">Host video</p>
                  <p className="text-sm font-bold text-foreground">{summary.campaign.videoHost.provider}</p>
                  <p className="mt-2 text-[11px] font-medium leading-relaxed text-foreground/50">{summary.campaign.videoHost.note}</p>
                </article>
                <form onSubmit={handleCreateCampaign} className="space-y-4 rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-burgundy/70">Campanie video</p>
                    <p className="mt-2 text-[11px] font-medium leading-relaxed text-foreground/50">
                      Standardul curat este thumbnail în email, cu link spre o pagină de vizionare Codruț. Video-ul nu se atașează și nu se redă direct în email.
                    </p>
                  </div>
                  <label className="block">
                    <span className="text-xs font-bold uppercase tracking-wider text-foreground/60 mb-1 block">Nume campanie</span>
                    <input
                      value={campaignName}
                      onChange={(event) => setCampaignName(event.target.value)}
                      className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-medium focus:border-burgundy focus:ring-1 focus:ring-burgundy"
                    />
                  </label>
                  <label className="block">
                    <span className="text-xs font-bold uppercase tracking-wider text-foreground/60 mb-1 block">Segment</span>
                    <select
                      value={campaignSegment}
                      onChange={(event) => setCampaignSegment(event.target.value as "past_customer" | "potential_customer")}
                      className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-medium focus:border-burgundy focus:ring-1 focus:ring-burgundy"
                    >
                      <option value="potential_customer">Prospect / client potențial</option>
                      <option value="past_customer">Client vechi / existent</option>
                    </select>
                  </label>
                  <label className="block">
                    <span className="text-xs font-bold uppercase tracking-wider text-foreground/60 mb-1 block">Subiect</span>
                    <input
                      value={campaignSubject}
                      onChange={(event) => setCampaignSubject(event.target.value)}
                      className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-medium focus:border-burgundy focus:ring-1 focus:ring-burgundy"
                    />
                  </label>
                  <label className="block">
                    <span className="text-xs font-bold uppercase tracking-wider text-foreground/60 mb-1 block">Video URL</span>
                    <input
                      type="url"
                      value={campaignVideoUrl}
                      onChange={(event) => setCampaignVideoUrl(event.target.value)}
                      placeholder="https://video.codrut.ro/..."
                      className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-medium focus:border-burgundy focus:ring-1 focus:ring-burgundy"
                    />
                  </label>
                  <label className="block">
                    <span className="text-xs font-bold uppercase tracking-wider text-foreground/60 mb-1 block">Thumbnail URL</span>
                    <input
                      type="url"
                      value={campaignThumbnailUrl}
                      onChange={(event) => setCampaignThumbnailUrl(event.target.value)}
                      placeholder="https://cdn.codrut.ro/thumb.jpg"
                      className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-medium focus:border-burgundy focus:ring-1 focus:ring-burgundy"
                    />
                  </label>
                  <label className="block">
                    <span className="text-xs font-bold uppercase tracking-wider text-foreground/60 mb-1 block">Landing page URL</span>
                    <input
                      type="url"
                      value={campaignLandingUrl}
                      onChange={(event) => setCampaignLandingUrl(event.target.value)}
                      placeholder="https://app.codrut.ro/watch/..."
                      className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-medium focus:border-burgundy focus:ring-1 focus:ring-burgundy"
                    />
                  </label>
                  <button
                    type="submit"
                    disabled={isCreatingCampaign}
                    className="btn-premium w-full justify-center"
                  >
                    {isCreatingCampaign ? "Se salvează..." : "Creează campanie"}
                  </button>
                  {campaignMessage ? (
                    <p aria-live="polite" className="rounded-xl bg-surface-muted/50 px-3 py-2 text-xs font-semibold text-foreground/62">
                      {campaignMessage}
                    </p>
                  ) : null}
                </form>
                <article className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
                  <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-burgundy/70 mb-2">Campanii salvate</p>
                  {isLoadingCampaigns ? (
                    <p className="text-xs font-medium text-foreground/50">Se încarcă...</p>
                  ) : campaigns.length === 0 ? (
                    <p className="text-xs font-medium text-foreground/50">Nicio campanie salvată încă.</p>
                  ) : (
                    <div className="space-y-2">
                      {campaigns.map((campaign) => (
                        <div key={campaign.id} className="rounded-xl border border-[var(--border)] bg-surface-muted/30 px-3 py-2">
                          <p className="text-xs font-bold text-foreground">{campaign.name}</p>
                          <p className="mt-1 text-[10px] font-semibold uppercase tracking-wider text-foreground/45">{campaign.status}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </article>
              </div>

              <div className="overflow-x-auto p-2">
                <table className="min-w-full text-left text-sm">
                  <thead className="text-[10px] font-bold uppercase tracking-[0.15em] text-foreground/50 border-b border-[var(--border)]">
                    <tr>
                      <th className="px-6 py-4">Companie & Contact</th>
                      <th className="px-6 py-4">Tip client</th>
                      <th className="px-6 py-4">Status</th>
                      <th className="px-6 py-4">Rate (Open/Click/View)</th>
                      <th className="px-6 py-4">Rezultat</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {summary.campaign.recipients.length > 0 ? (
                      summary.campaign.recipients.map((recipient) => (
                        <tr key={recipient.id} className="hover:bg-surface-muted/30 transition-colors">
                          <td className="px-6 py-4">
                            <p className="font-bold text-foreground">{recipient.company}</p>
                            <p className="mt-1 text-xs font-medium text-foreground/60">
                              {[recipient.firstName, recipient.lastName].filter(Boolean).join(" ") || "Contact lipsă"}
                            </p>
                            <p className="mt-1 text-[11px] text-foreground/40 font-mono">{recipient.email}</p>
                          </td>
                          <td className="px-6 py-4">
                            <span className="capitalize text-[11px] font-bold uppercase tracking-wider text-foreground/60">{recipient.clientType.replace("_", " ")}</span>
                          </td>
                          <td className="px-6 py-4">
                            <span className="rounded-full bg-surface px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-foreground/70 border border-[var(--border)] shadow-sm">
                              {recipient.status}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-foreground/70 font-mono text-xs">
                            {recipient.openRate ?? "-"} / {recipient.clickRate ?? "-"} / {recipient.viewRate ?? "-"}
                          </td>
                          <td className="px-6 py-4">
                            <span className="rounded-full bg-burgundy/10 border border-burgundy/20 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-burgundy shadow-sm">
                              {recipient.outcome ?? "pending"}
                            </span>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={5} className="px-6 py-12 text-center text-foreground/50 text-sm font-medium">
                          <p>Niciun contact înregistrat încă.</p>
                          <div className="mt-4 flex items-center justify-center gap-3">
                            <span className="text-foreground/40">Importă un fișier CSV sau</span>
                            <button onClick={() => setShowManualAddModal(true)} className="text-burgundy hover:text-burgundy-dark font-bold underline underline-offset-2">adaugă manual</button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        </div>
      )}

      {activeTab === "templates" && (
        <div className="space-y-6">
          {!selectedTemplateId ? (
            <div className="space-y-6 animate-fade-in-up">
              {/* Action Bar */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                <div className="relative flex-1 max-w-md w-full">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-foreground/40">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                  </div>
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Caută șabloane email..."
                    className="w-full rounded-full border border-[var(--border)] bg-surface py-3 pl-11 pr-4 text-sm font-medium text-foreground focus:border-burgundy/50 focus:ring-2 focus:ring-burgundy/10 shadow-sm transition-all"
                  />
                </div>
                <button
                  onClick={handleCreateTemplate}
                  disabled={isLoadingTemplates}
                  className="btn-premium shrink-0"
                >
                  + Creează șablon
                </button>
              </div>

              {/* Grid */}
              {isLoadingTemplates && templates.length === 0 ? (
                <div className="flex items-center justify-center h-64 rounded-3xl border border-[var(--border)] bg-surface">
                  <p className="text-sm font-bold text-foreground/50">Se încarcă șabloanele...</p>
                </div>
              ) : filteredTemplates.length > 0 ? (
                <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
                  {filteredTemplates.map((temp) => (
                    <button
                      key={temp.id}
                      onClick={() => {
                        setSelectedTemplateId(temp.id);
                        setIsEditing(false);
                      }}
                      className="group flex flex-col text-left p-6 rounded-3xl border border-[var(--border)] bg-surface hover:border-burgundy/30 hover:shadow-[0_8px_30px_-12px_rgba(137,5,5,0.15)] transition-all duration-200 relative overflow-hidden h-full min-h-[220px]"
                    >
                      <div className="absolute top-0 right-0 p-24 bg-burgundy/5 blur-3xl rounded-full -mr-12 -mt-12 pointer-events-none z-0 opacity-0 group-hover:opacity-100 transition-opacity duration-200"></div>
                      <div className="relative z-10 flex flex-col h-full w-full">
                        <div className="flex items-start justify-between mb-4">
                          <span className={`text-[10px] font-bold uppercase tracking-[0.2em] px-3 py-1 rounded-full shadow-sm border ${
                            temp.lane === "transactional"
                              ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-800/50"
                              : "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-800/50"
                          }`}>
                            {temp.lane === "transactional" ? "Sistem" : "Campanie"}
                          </span>
                          <span className="rounded-full bg-surface-muted border border-[var(--border)] px-3 py-1 text-[10px] font-bold text-foreground/60 shadow-sm">
                            v{temp.version ?? 1}
                          </span>
                        </div>
                        <h4 className="font-display font-bold text-xl text-foreground mb-2 group-hover:text-burgundy transition-colors line-clamp-1">
                          {temp.name}
                        </h4>
                        <p className="text-sm font-medium leading-relaxed text-foreground/60 mb-4 line-clamp-2 min-h-[2.5rem]">
                          {temp.subject || "Fără subiect"}
                        </p>
                        
                        <div className="mt-auto pt-4 border-t border-[var(--border)] flex items-center justify-between">
                          <div className="flex flex-wrap gap-1.5">
                            {temp.placeholders.slice(0, 3).map((p, i) => (
                              <div key={i} className="inline-block rounded-md bg-surface-muted/80 px-2 py-1 text-[10px] font-mono font-bold text-foreground/60 border border-[var(--border)] shadow-sm">
                                {p.replace('{', '').replace('}', '')}
                              </div>
                            ))}
                            {temp.placeholders.length > 3 && (
                              <div className="inline-flex items-center justify-center rounded-md bg-surface-muted/80 px-2 py-1 text-[10px] font-bold text-foreground/60 border border-[var(--border)] shadow-sm">
                                +{temp.placeholders.length - 3}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-64 rounded-3xl border border-dashed border-[var(--border)] bg-surface-muted/20 text-center p-6">
                  <div className="w-16 h-16 rounded-full bg-surface flex items-center justify-center mb-4 text-foreground/30 shadow-sm">
                    <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
                  </div>
                  <p className="text-lg font-display font-bold text-foreground mb-1">Niciun șablon găsit</p>
                  <p className="text-sm font-medium text-foreground/50">Modifică termenii de căutare sau creează un șablon nou.</p>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-6 animate-fade-in-up">
              {/* Back to catalog button */}
              <div>
                <button
                  onClick={() => setSelectedTemplateId("")}
                  className="tap-soft inline-flex items-center gap-2 text-sm font-bold text-foreground/60 hover:text-foreground transition-colors bg-surface px-4 py-2 rounded-full border border-[var(--border)] shadow-sm"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
                  Înapoi la catalog
                </button>
              </div>

              {/* Editor View */}
              {selectedTemplate && (
                <main className="grid gap-6 xl:grid-cols-2">
              {/* Editor Column */}
              <section className="bento-card p-6 flex flex-col">
                <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--border)] pb-4 mb-5">
                  <div>
                    <h3 className="text-xl font-bold text-foreground">
                      {isEditing ? "Modificare șablon" : "Detalii șablon"}
                    </h3>
                    <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.15em] text-foreground/50">
                      Versiunea {selectedTemplate.version ?? 1}
                    </p>
                  </div>
                  
                  <div className="flex flex-wrap justify-end gap-2">
                    {isEditing ? (
                      <>
                        <button
                          onClick={handleSaveTemplate}
                          disabled={isLoadingTemplates}
                          className="btn-premium py-1.5 px-4 text-xs"
                        >
                          Salvează
                        </button>
                        <button
                          onClick={() => setIsEditing(false)}
                          disabled={isLoadingTemplates}
                          className="btn-secondary py-1.5 px-4 text-xs"
                        >
                          Anulează
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => setIsEditing(true)}
                          disabled={isLoadingTemplates}
                          className="tap-soft rounded-full bg-burgundy/10 border border-burgundy/20 px-4 py-2 text-xs font-bold text-burgundy hover:bg-burgundy/20 transition-colors"
                        >
                          Editează
                        </button>
                        <button
                          onClick={handleCreateTemplateVersion}
                          disabled={isLoadingTemplates}
                          className="tap-soft rounded-full border border-[var(--border)] bg-surface px-4 py-2 text-xs font-bold text-foreground/70 hover:border-burgundy/40 hover:text-burgundy transition-all shadow-sm"
                        >
                          Versiune nouă
                        </button>
                        <button
                          onClick={handleDeleteTemplate}
                          disabled={isLoadingTemplates}
                          className="tap-soft rounded-full border border-red-200 bg-red-50 px-4 py-2 text-xs font-bold text-red-600 hover:bg-red-100 transition-colors shadow-sm"
                        >
                          Șterge
                        </button>
                      </>
                    )}
                  </div>
                </div>

                <div className="space-y-5 flex-1 flex flex-col">
                  <label className="block">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Nume intern</span>
                    <input
                      type="text"
                      disabled={!isEditing}
                      value={isEditing ? editName : selectedTemplate.name}
                      onChange={(e) => setEditName(e.target.value)}
                      className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-bold text-foreground focus:border-burgundy/50 focus:ring-2 focus:ring-burgundy/10 disabled:opacity-60 disabled:bg-surface-muted/30 transition-all shadow-sm"
                    />
                  </label>

                  <div className="grid gap-5 grid-cols-2">
                    <label className="block">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Canal trimitere</span>
                      <select
                        disabled={!isEditing}
                        value={isEditing ? editLane : selectedTemplate.lane}
                        onChange={(e) => setEditLane(e.target.value as "transactional" | "campaign")}
                        className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-bold text-foreground focus:border-burgundy/50 focus:ring-2 focus:ring-burgundy/10 disabled:opacity-60 disabled:bg-surface-muted/30 transition-all shadow-sm appearance-none"
                      >
                        <option value="transactional">Tranzacțional (Sistem)</option>
                        <option value="campaign">Campanie (Prospectare)</option>
                      </select>
                    </label>

                    <div className="block">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Tag-uri active</span>
                      <div className="flex flex-wrap gap-2 min-h-[3rem] items-center p-2 rounded-xl border border-[var(--border)] bg-surface-muted/20">
                        {selectedTemplate.placeholders.length > 0 ? (
                          selectedTemplate.placeholders.map((p) => (
                            <span
                              key={p}
                              className="inline-flex items-center rounded-md bg-foreground/5 border border-foreground/10 px-2 py-1 text-[10px] font-bold text-foreground/70 font-mono"
                            >
                              {p}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-foreground/40 px-2 font-medium">Niciun tag</span>
                        )}
                      </div>
                    </div>
                  </div>

                  <label className="block">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Subiect email</span>
                    <input
                      type="text"
                      disabled={!isEditing}
                      value={isEditing ? editSubject : selectedTemplate.subject}
                      onChange={(e) => setEditSubject(e.target.value)}
                      className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-bold text-foreground focus:border-burgundy/50 focus:ring-2 focus:ring-burgundy/10 disabled:opacity-60 disabled:bg-surface-muted/30 transition-all shadow-sm"
                    />
                  </label>

                  <label className="block flex-1 flex flex-col">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Corp email (Markdown)</span>
                    <textarea
                      disabled={!isEditing}
                      value={isEditing ? editBody : selectedTemplate.body}
                      onChange={(e) => setEditBody(e.target.value)}
                      className="flex-1 min-h-[200px] w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-4 text-sm text-foreground/90 focus:border-burgundy/50 focus:ring-2 focus:ring-burgundy/10 disabled:opacity-60 disabled:bg-surface-muted/30 transition-all shadow-inner font-mono resize-none leading-relaxed"
                    />
                  </label>
                </div>
              </section>

              {/* Preview Column */}
              <section className="bento-card p-6 flex flex-col">
                <div className="flex items-center gap-3 border-b border-[var(--border)] pb-4 mb-5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-burgundy/10 text-burgundy">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                  </div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-foreground/80">
                    Previzualizare Live
                  </h3>
                </div>

                <div className="rounded-2xl border border-[var(--border)] bg-surface overflow-hidden shadow-sm flex-1 flex flex-col">
                  {/* Simulated Mailbox Header */}
                  <div className="bg-surface-muted/40 p-5 border-b border-[var(--border)] space-y-2 text-xs text-foreground/60">
                    <div className="flex justify-between items-center">
                      <p><strong className="text-foreground/80">De la:</strong> Echipa Codruț</p>
                      <span className="text-[10px] font-mono opacity-50">10:42 AM</span>
                    </div>
                    <p><strong className="text-foreground/80">Către:</strong> {MOCK_REPLACEMENTS["{first_name}"]}</p>
                    <p className="text-sm text-foreground font-bold pt-1">{preview.subject}</p>
                  </div>

                  {/* Rendered HTML Body */}
                  <div
                    className="p-6 text-[15px] leading-relaxed font-sans flex-1 bg-white text-gray-800"
                    dangerouslySetInnerHTML={{ __html: preview.bodyHtml }}
                  />
                </div>

                <div className="mt-5 rounded-xl bg-surface-muted/50 p-4 border border-[var(--border)]">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 text-burgundy/60">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    </div>
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-1">Informație utilă</p>
                      <p className="text-[11px] text-foreground/60 leading-relaxed font-medium">
                        Tag-urile ca <code className="bg-foreground/5 px-1 rounded mx-0.5">{`{first_name}`}</code> sunt înlocuite automat la expediere. Puteți formata corpul emailului folosind <strong className="text-foreground">**text**</strong> pentru bold și <span className="text-burgundy underline">[linkuri](url)</span>.
                      </p>
                    </div>
                  </div>
                </div>
              </section>
                </main>
              )}
            </div>
          )}
        </div>
      )}

      {/* Manual Add Contact Modal */}
      {showManualAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
          <div className="bg-surface rounded-2xl p-6 shadow-xl w-full max-w-md animate-fade-in-up border border-[var(--border)]">
            <h2 className="text-xl font-bold text-foreground mb-4">Adaugă Contact Manual</h2>
            <form onSubmit={handleAddManualContact} className="space-y-4">
              <label className="block">
                <span className="text-xs font-bold uppercase tracking-wider text-foreground/60 mb-1 block">Email</span>
                <input type="email" required value={manualEmail} onChange={e => setManualEmail(e.target.value)} className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-medium focus:border-burgundy focus:ring-1 focus:ring-burgundy" placeholder="exemplu@companie.ro" />
              </label>
              <label className="block">
                <span className="text-xs font-bold uppercase tracking-wider text-foreground/60 mb-1 block">Nume (Opțional)</span>
                <input type="text" value={manualName} onChange={e => setManualName(e.target.value)} className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-medium focus:border-burgundy focus:ring-1 focus:ring-burgundy" placeholder="Nume și prenume" />
              </label>
              <label className="block">
                <span className="text-xs font-bold uppercase tracking-wider text-foreground/60 mb-1 block">Companie (Opțional)</span>
                <input type="text" value={manualCompany} onChange={e => setManualCompany(e.target.value)} className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-medium focus:border-burgundy focus:ring-1 focus:ring-burgundy" placeholder="Numele companiei" />
              </label>
              <label className="block">
                <span className="text-xs font-bold uppercase tracking-wider text-foreground/60 mb-1 block">Segment</span>
                <select value={manualSegment} onChange={e => setManualSegment(e.target.value as "past_customer" | "potential_customer")} className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-medium focus:border-burgundy focus:ring-1 focus:ring-burgundy">
                  <option value="potential_customer">Prospect / Client Potențial</option>
                  <option value="past_customer">Client Existent / Vechi</option>
                </select>
              </label>
              <div className="pt-4 flex justify-end gap-3 border-t border-[var(--border)]">
                <button type="button" onClick={() => setShowManualAddModal(false)} className="px-4 py-2 rounded-lg font-bold text-foreground/60 hover:bg-surface-muted/30">Anulează</button>
                <button type="submit" disabled={isAddingManual} className="btn-primary !px-6 !py-2 !rounded-lg !text-sm">
                  {isAddingManual ? "Se adaugă..." : "Adaugă contact"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
