"use client";

import { useEffect, useState } from "react";
import { type EmailOpsSummary, type AssessmentDeliveryRow, type CampaignRecipientRow } from "@/api/email";

type TabKey = "delivery" | "templates";

type EmailTemplate = {
  id: string;
  baseKey: string;
  version: number;
  name: string;
  subject: string;
  body: string;
  lane: "transactional" | "campaign";
  placeholders: string[];
};

const destructiveButtonClass =
  "tap-soft rounded-lg border border-[#890505]/35 bg-transparent px-3 py-1.5 text-xs font-bold text-[#890505] shadow-none transition hover:bg-[#890505]/10 dark:border-[#e35f5f]/45 dark:text-[#e35f5f] dark:hover:bg-[#890505]/22";

const SEEDED_TEMPLATES: EmailTemplate[] = [
  {
    id: "invitation-secure-link",
    baseKey: "invitation-secure-link",
    version: 1,
    name: "Invitație Assessment (Link Securizat)",
    subject: "Bun venit în programul Codruț, {first_name}",
    lane: "transactional",
    placeholders: ["{first_name}", "{project}", "{link_securizat}", "{estimare_timp}"],
    body: `Salutare {first_name},

Ai fost invitat să participi la evaluarea organizațională pentru echipa **{project}**.

Te rugăm să completezi chestionarele desemnate accesând următorul link securizat:
[{link_securizat}]({link_securizat})

Aceste chestionare vor dura aproximativ **{estimare_timp} minute** în total. Răspunsurile tale individuale sunt complet confidențiale și vor fi agregate în raportul de echipă.

Gânduri bune,
Echipa Codruț`
  },
  {
    id: "reminder-pending",
    baseKey: "reminder-pending",
    version: 1,
    name: "Reminder Completare Evaluare",
    subject: "Reminder: Te rugăm să finalizezi completarea, {first_name}",
    lane: "transactional",
    placeholders: ["{first_name}", "{project}", "{link_securizat}", "{sarcini_ramase}"],
    body: `Salut {first_name},

Acesta este un scurt reminder că evaluarea pentru **{project}** este în curs de desfășurare, iar feedback-ul tău este extrem de valoros.

Te rugăm să accesezi link-ul tău securizat pentru a finaliza răspunsurile:
[{link_securizat}]({link_securizat})

Sarcini rămase de completat: **{sarcini_ramase}**.

Mulțumim pentru implicare și cooperare!

Echipa Codruț`
  },
  {
    id: "video-prospecting",
    baseKey: "video-prospecting",
    version: 1,
    name: "Campanie Video Follow-up",
    subject: "O idee practică pentru echipa ta, {first_name}",
    lane: "campaign",
    placeholders: ["{first_name}", "{link_video}"],
    body: `Salutare {first_name},

Am pregătit un material video scurt despre dinamica echipelor performante și cum putem adresa disfuncțiile comune care blochează progresul în livrare.

Poți viziona clipul accesând link-ul de mai jos:
[Vizualizează Video Codruț]({link_video})

Dacă ți se pare util și aplicabil pentru contextul tău curent, te invit să programăm o scurtă discuție.

Toate cele bune,
Andrei`
  }
];

const MOCK_REPLACEMENTS: Record<string, string> = {
  "{first_name}": "Ioana",
  "{project}": "Intake Iunie",
  "{link_securizat}": "https://app.codrut.ro/auth/seclink-8f2a175",
  "{estimare_timp}": "15",
  "{sarcini_ramase}": "2 chestionare rămase (Lencioni, Distress)",
  "{link_video}": "https://watch.codrut.ro/v/performanta-echipe-2026",
};

function normalizeTemplates(input: EmailTemplate[]): EmailTemplate[] {
  return input.map((template) => ({
    ...template,
    baseKey: template.baseKey ?? template.id.replace(/-v\d+$/, ""),
    version: template.version ?? 1,
  }));
}

function detectedPlaceholders(subject: string, body: string): string[] {
  const placeholderRegex = /\{[a-z0-9_]+\}/gi;
  return Array.from(new Set(`${subject} ${body}`.match(placeholderRegex) || []));
}

type EmailWorkspaceProps = {
  initialSummary: EmailOpsSummary;
};

export function EmailWorkspace({ initialSummary }: EmailWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<TabKey>("delivery");
  const [summary, setSummary] = useState<EmailOpsSummary>(initialSummary);

  // Template Manager States
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("");
  const [isEditing, setIsEditing] = useState(false);

  // Editor fields
  const [editName, setEditName] = useState("");
  const [editSubject, setEditSubject] = useState("");
  const [editBody, setEditBody] = useState("");
  const [editLane, setEditLane] = useState<"transactional" | "campaign">("transactional");

  // Load templates from localStorage or seeds
  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("codrut_email_templates");
      if (stored) {
        try {
          const parsed = normalizeTemplates(JSON.parse(stored) as EmailTemplate[]);
          setTemplates(parsed);
          if (parsed.length > 0) {
            setSelectedTemplateId(parsed[0].id);
          }
          return;
        } catch (e) {
          console.error(e);
        }
      }
      // Fallback/Seed
      const seeded = normalizeTemplates(SEEDED_TEMPLATES);
      setTemplates(seeded);
      localStorage.setItem("codrut_email_templates", JSON.stringify(seeded));
      setSelectedTemplateId(SEEDED_TEMPLATES[0].id);
    }
  }, []);

  // Sync editor fields when selected template changes
  const selectedTemplate = templates.find((t) => t.id === selectedTemplateId);
  useEffect(() => {
    if (selectedTemplate) {
      setEditName(selectedTemplate.name);
      setEditSubject(selectedTemplate.subject);
      setEditBody(selectedTemplate.body);
      setEditLane(selectedTemplate.lane);
    }
  }, [selectedTemplateId, templates]);

  const handleSaveTemplate = () => {
    if (!selectedTemplateId) return;

    const updatedTemplates = templates.map((t) => {
      if (t.id === selectedTemplateId) {
        return {
          ...t,
          name: editName,
          subject: editSubject,
          body: editBody,
          lane: editLane,
          placeholders: detectedPlaceholders(editSubject, editBody),
        };
      }
      return t;
    });

    setTemplates(updatedTemplates);
    localStorage.setItem("codrut_email_templates", JSON.stringify(updatedTemplates));
    setIsEditing(false);
  };

  const handleCreateTemplate = () => {
    const newId = `template-${Date.now()}`;
    const newTemp: EmailTemplate = {
      id: newId,
      baseKey: newId,
      version: 1,
      name: "Șablon Email Nou",
      subject: "Subiectul emailului {first_name}",
      lane: "transactional",
      placeholders: ["{first_name}"],
      body: `Salut {first_name},

Introduceți conținutul noului șablon email aici. Puteți folosi coduri între acolade pentru personalizare.`,
    };

    const updated = [...templates, newTemp];
    setTemplates(updated);
    localStorage.setItem("codrut_email_templates", JSON.stringify(updated));
    setSelectedTemplateId(newId);
    setIsEditing(true);
  };

  const handleCreateTemplateVersion = () => {
    if (!selectedTemplate) return;
    const baseKey = selectedTemplate.baseKey ?? selectedTemplate.id;
    const nextVersion =
      Math.max(
        0,
        ...templates
          .filter((template) => (template.baseKey ?? template.id) === baseKey)
          .map((template) => template.version ?? 1)
      ) + 1;
    const newId = `${baseKey}-v${nextVersion}`;
    const nextTemplate: EmailTemplate = {
      ...selectedTemplate,
      id: newId,
      baseKey,
      version: nextVersion,
      name: selectedTemplate.name,
      placeholders: detectedPlaceholders(selectedTemplate.subject, selectedTemplate.body),
    };
    const updated = [...templates, nextTemplate];
    setTemplates(updated);
    localStorage.setItem("codrut_email_templates", JSON.stringify(updated));
    setSelectedTemplateId(newId);
    setIsEditing(true);
  };

  const handleDeleteTemplate = () => {
    if (templates.length <= 1) {
      alert("Trebuie să păstrați cel puțin un șablon în catalog.");
      return;
    }
    if (!confirm("Sigur doriți să ștergeți acest șablon?")) return;

    const updated = templates.filter((t) => t.id !== selectedTemplateId);
    setTemplates(updated);
    localStorage.setItem("codrut_email_templates", JSON.stringify(updated));
    setSelectedTemplateId(updated[0].id);
    setIsEditing(false);
  };

  // Convert markdown to clean, basic HTML preview
  const getRenderedPreview = (subjectText: string, bodyText: string) => {
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

    return {
      subject: replacedSubject,
      bodyHtml: html,
    };
  };

  const preview = selectedTemplate
    ? getRenderedPreview(
        isEditing ? editSubject : selectedTemplate.subject,
        isEditing ? editBody : selectedTemplate.body
      )
    : { subject: "", bodyHtml: "" };

  return (
    <div className="space-y-6">
      {/* Sub Navigation Tabs */}
      <div className="flex gap-1 border-b border-[var(--border)] pb-px">
        <button
          onClick={() => setActiveTab("delivery")}
          className={`px-4 py-2.5 text-sm font-bold rounded-t-xl transition-all border-b-2 ${
            activeTab === "delivery"
              ? "border-burgundy text-burgundy bg-burgundy/5"
              : "border-transparent text-foreground/60 hover:text-foreground hover:bg-surface-muted/50"
          }`}
        >
          Monitorizare livrare & Monitor
        </button>
        <button
          onClick={() => setActiveTab("templates")}
          className={`px-4 py-2.5 text-sm font-bold rounded-t-xl transition-all border-b-2 ${
            activeTab === "templates"
              ? "border-burgundy text-burgundy bg-burgundy/5"
              : "border-transparent text-foreground/60 hover:text-foreground hover:bg-surface-muted/50"
          }`}
        >
          Catalog Șabloane Email
        </button>
      </div>

      {activeTab === "delivery" && (
        <div className="space-y-5">
          {/* Metrics summary grid */}
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {summary.metrics.map((metric) => (
              <article key={metric.label} className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">{metric.label}</p>
                <p className="mt-3 text-3xl font-semibold text-foreground">{metric.value}</p>
                <p className="mt-2 text-sm leading-6 text-foreground/60">{metric.detail}</p>
              </article>
            ))}
          </div>

          {/* Delivery Queue table */}
          <section className="rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
            <div className="border-b border-[var(--border)] px-5 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Delivery queue</p>
              <h2 className="mt-1 text-xl font-semibold text-foreground">Invitații active assessment</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/62">
                Liderii primesc cont complet, membrii primesc link securizat de completare rapidă.
              </p>
            </div>
            <div className="hidden overflow-x-auto xl:block">
              <table className="min-w-[980px] text-left text-sm">
                <thead className="bg-surface-muted text-xs font-semibold uppercase tracking-[0.1em] text-foreground/50 border-b border-[var(--border)]">
                  <tr>
                    <th className="px-5 py-3">Recipient</th>
                    <th className="px-5 py-3">Acces</th>
                    <th className="px-5 py-3">Sarcini completate</th>
                    <th className="px-5 py-3">Status livrare</th>
                    <th className="px-5 py-3">Planificator reminder</th>
                    <th className="px-5 py-3">Următorul pas operational</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {summary.assessmentRows.map((row) => (
                    <tr key={row.id} className="align-top hover:bg-background/40">
                      <td className="px-5 py-4">
                        <p className="font-semibold text-foreground">{row.participant}</p>
                        <p className="mt-1 text-xs text-foreground/50">{row.email}</p>
                        <p className="mt-1 text-xs font-semibold text-burgundy">{row.project}</p>
                      </td>
                      <td className="px-5 py-4">
                        <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-foreground/60 border border-[var(--border)]">
                          {row.audience === "leadership_account" ? "cont lider" : "link securizat"}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-foreground/62 font-semibold">{row.tasks}</td>
                      <td className="px-5 py-4">
                        <span className={`rounded-full px-2.5 py-1 text-xs font-bold capitalize border ${
                          row.delivery === "delivered" || row.delivery === "opened"
                            ? "bg-green-50 border-green-200 text-green-700"
                            : row.delivery === "failed"
                              ? "bg-red-50 border-red-200 text-red-700"
                              : "bg-surface-muted border-[var(--border)] text-foreground/60"
                        }`}>
                          {row.delivery}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-foreground/60 border border-[var(--border)]">
                          {row.reminder === "today" ? "Azi" : row.reminder === "tomorrow" ? "Mâine" : "Oprit"}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-foreground/62 font-medium">{row.nextAction}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="grid gap-3 p-4 xl:hidden">
              {summary.assessmentRows.map((row) => (
                <article key={row.id} className="rounded-2xl border border-[var(--border)] bg-background p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <p className="font-semibold text-foreground">{row.participant}</p>
                      <p className="mt-1 break-all text-xs text-foreground/50">{row.email}</p>
                      <p className="mt-1 text-xs font-semibold text-burgundy">{row.project}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className="rounded-full border border-[var(--border)] bg-surface px-2.5 py-1 text-xs font-semibold text-foreground/60">
                        {row.audience === "leadership_account" ? "cont lider" : "link securizat"}
                      </span>
                      <span className={`rounded-full px-2.5 py-1 text-xs font-bold capitalize border ${
                        row.delivery === "delivered" || row.delivery === "opened"
                          ? "bg-green-50 border-green-200 text-green-700"
                          : row.delivery === "failed"
                            ? "bg-red-50 border-red-200 text-red-700"
                            : "bg-surface border-[var(--border)] text-foreground/60"
                      }`}>
                        {row.delivery}
                      </span>
                    </div>
                  </div>

                  <dl className="mt-4 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-xl bg-surface px-3 py-2">
                      <dt className="text-[11px] font-bold uppercase tracking-wider text-foreground/45">Sarcini</dt>
                      <dd className="mt-1 text-sm font-semibold text-foreground">{row.tasks}</dd>
                    </div>
                    <div className="rounded-xl bg-surface px-3 py-2">
                      <dt className="text-[11px] font-bold uppercase tracking-wider text-foreground/45">Reminder</dt>
                      <dd className="mt-1 text-sm font-semibold text-foreground">
                        {row.reminder === "today" ? "Azi" : row.reminder === "tomorrow" ? "Mâine" : "Oprit"}
                      </dd>
                    </div>
                    <div className="rounded-xl bg-surface px-3 py-2 sm:col-span-3">
                      <dt className="text-[11px] font-bold uppercase tracking-wider text-foreground/45">Următorul pas</dt>
                      <dd className="mt-1 text-sm font-medium leading-6 text-foreground/68">{row.nextAction}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          </section>

          {/* Quick Actions Panel */}
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
            <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm space-y-4">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Acțiuni rapide expediere</p>
              <div className="grid gap-3 md:grid-cols-3">
                {["Trimite invitații noi", "Trimite remindere azi", "Deblochează adrese email"].map((action) => (
                  <button
                    key={action}
                    type="button"
                    onClick={() => alert(`Simulare actiune: "${action}"`)}
                    className="tap-soft rounded-xl border border-[var(--border)] bg-background px-4 py-3.5 text-sm font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy"
                  >
                    {action}
                  </button>
                ))}
              </div>
            </section>

            <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Reguli livrare</p>
              <div className="mt-4 space-y-2">
                {summary.rules.map((rule) => (
                  <p key={rule} className="rounded-xl bg-surface-muted px-3 py-2.5 text-xs leading-relaxed text-foreground/62 border border-[var(--border)]">
                    {rule}
                  </p>
                ))}
              </div>
            </section>
          </div>

          {/* Campaigns lists */}
          <section className="rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
            <div className="border-b border-[var(--border)] px-5 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Campanii Prospectare</p>
              <h2 className="mt-1 text-xl font-semibold text-foreground">Emailuri personalizate video</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/62">
                Template-uri adresate direct factorilor de decizie cu linkuri de urmărire și vizualizare video.
              </p>
            </div>
            <div className="grid gap-0 divide-y divide-[var(--border)] lg:grid-cols-[20rem_minmax(0,1fr)] lg:divide-x lg:divide-y-0">
              <div className="space-y-4 p-5 bg-surface-muted/30">
                <article className="rounded-xl border border-[var(--border)] bg-background px-4 py-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.1em] text-burgundy/75">Host video</p>
                  <p className="mt-1 text-sm font-semibold text-foreground">{summary.campaign.videoHost.provider}</p>
                  <p className="mt-1 text-xs leading-5 text-foreground/56">{summary.campaign.videoHost.note}</p>
                </article>
                <article className="rounded-xl border border-[var(--border)] bg-background px-4 py-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.1em] text-burgundy/75">Subiect implicit</p>
                  <p className="mt-1 text-sm font-semibold text-foreground">{summary.campaign.template.subject}</p>
                  <p className="mt-1 text-xs leading-5 text-foreground/56">{summary.campaign.template.personalization}</p>
                </article>
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-surface-muted text-xs font-semibold uppercase tracking-[0.1em] text-foreground/50 border-b border-[var(--border)]">
                    <tr>
                      <th className="px-5 py-3">Companie & Contact</th>
                      <th className="px-5 py-3">Tip client</th>
                      <th className="px-5 py-3">Status</th>
                      <th className="px-5 py-3">Rate (Open / Click / View)</th>
                      <th className="px-5 py-3">Rezultat</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {summary.campaign.recipients.map((recipient) => (
                      <tr key={recipient.id} className="hover:bg-background/40">
                        <td className="px-5 py-4">
                          <p className="font-semibold text-foreground">{recipient.company}</p>
                          <p className="mt-1 text-xs text-foreground/50">
                            {[recipient.firstName, recipient.lastName].filter(Boolean).join(" ") || "Contact lipsă"}
                          </p>
                          <p className="mt-1 text-xs text-foreground/50">{recipient.email}</p>
                        </td>
                        <td className="px-5 py-4">
                          <span className="capitalize text-xs font-semibold text-foreground/60">{recipient.clientType.replace("_", " ")}</span>
                        </td>
                        <td className="px-5 py-4">
                          <span className="rounded-full bg-surface-muted px-2 py-1 text-xs font-semibold text-foreground/60 border border-[var(--border)]">
                            {recipient.status}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-foreground/62 font-bold">
                          {recipient.openRate ?? "-"} / {recipient.clickRate ?? "-"} / {recipient.viewRate ?? "-"}
                        </td>
                        <td className="px-5 py-4">
                          <span className="rounded-full bg-burgundy/10 border border-burgundy/20 px-2.5 py-1 text-xs font-bold text-burgundy">
                            {recipient.outcome ?? "pending"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        </div>
      )}

      {activeTab === "templates" && (
        <div className="grid gap-6 lg:grid-cols-[18rem_minmax(0,1fr)]">
          {/* Template Sidebar List */}
          <aside className="space-y-4">
            <div className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
              <div className="flex items-center justify-between gap-3 border-b border-[var(--border)] pb-3">
                <h3 className="text-sm font-bold text-foreground">Șabloane ({templates.length})</h3>
                <button
                  onClick={handleCreateTemplate}
                  className="tap-soft rounded-lg bg-burgundy px-2.5 py-1 text-xs font-bold text-white hover:bg-burgundy/90"
                >
                  + Adaugă
                </button>
              </div>

              <div className="mt-3 space-y-2">
                {templates.map((temp) => (
                  <button
                    key={temp.id}
                    onClick={() => {
                      setSelectedTemplateId(temp.id);
                      setIsEditing(false);
                    }}
                    className={`w-full text-left p-3 rounded-xl border transition-all ${
                      selectedTemplateId === temp.id
                        ? "bg-burgundy/10 border-burgundy/40 text-foreground"
                        : "bg-background border-[var(--border)] text-foreground/70 hover:border-burgundy/30"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-burgundy">
                        {temp.lane === "transactional" ? "Sistem" : "Campanie"}
                      </span>
                      <span className="rounded-full bg-surface-muted px-2 py-0.5 text-[10px] font-bold text-foreground/55">
                        v{temp.version ?? 1}
                      </span>
                    </div>
                    <h4 className="mt-1 font-bold text-xs text-foreground truncate">{temp.name}</h4>
                    <p className="mt-1 text-[11px] text-foreground/50 truncate">
                      Subiect: {temp.subject}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          </aside>

          {/* Template Editor and Preview */}
          {selectedTemplate ? (
            <main className="grid gap-6 xl:grid-cols-2">
              {/* Editor Column */}
              <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm space-y-4">
                <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
                  <div>
                    <h3 className="text-base font-bold text-foreground">
                      {isEditing ? "Editare șablon" : "Detalii șablon"}
                    </h3>
                    <p className="mt-1 text-xs font-semibold text-foreground/50">
                      Versiunea {selectedTemplate.version ?? 1}
                    </p>
                  </div>
                  
                  <div className="flex gap-2">
                    {isEditing ? (
                      <>
                        <button
                          onClick={handleSaveTemplate}
                          className="tap-soft rounded-lg bg-burgundy px-3.5 py-1.5 text-xs font-bold text-white hover:bg-burgundy/90"
                        >
                          Salvează
                        </button>
                        <button
                          onClick={() => setIsEditing(false)}
                          className="tap-soft rounded-lg border border-[var(--border)] bg-background px-3 py-1.5 text-xs font-bold text-foreground hover:bg-surface-muted"
                        >
                          Anulează
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => setIsEditing(true)}
                          className="tap-soft rounded-lg bg-burgundy/10 border border-burgundy/25 px-3.5 py-1.5 text-xs font-bold text-burgundy hover:bg-burgundy/25"
                        >
                          Editează
                        </button>
                        <button
                          onClick={handleCreateTemplateVersion}
                          className="tap-soft rounded-lg border border-[var(--border)] bg-background px-3 py-1.5 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy"
                        >
                          Versiune nouă
                        </button>
                        <button
                          onClick={handleDeleteTemplate}
                          className={destructiveButtonClass}
                        >
                          Șterge șablonul
                        </button>
                      </>
                    )}
                  </div>
                </div>

                <div className="space-y-3">
                  <label className="block">
                    <span className="text-xs font-bold text-foreground/60">Nume Șablon</span>
                    <input
                      type="text"
                      disabled={!isEditing}
                      value={isEditing ? editName : selectedTemplate.name}
                      onChange={(e) => setEditName(e.target.value)}
                      className="mt-2 w-full rounded-xl border border-[var(--border)] bg-background px-3.5 py-2.5 text-sm font-semibold text-foreground focus:border-burgundy disabled:opacity-60"
                    />
                  </label>

                  <div className="grid gap-3 grid-cols-2">
                    <label className="block">
                      <span className="text-xs font-bold text-foreground/60">Tip Canal</span>
                      <select
                        disabled={!isEditing}
                        value={isEditing ? editLane : selectedTemplate.lane}
                        onChange={(e) => setEditLane(e.target.value as "transactional" | "campaign")}
                        className="mt-2 w-full rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-sm font-semibold text-foreground focus:border-burgundy disabled:opacity-60"
                      >
                        <option value="transactional">Tranzacțional (Sistem)</option>
                        <option value="campaign">Campanie Video / Prospectare</option>
                      </select>
                    </label>

                    <div className="block">
                      <span className="text-xs font-bold text-foreground/60">Tag-uri identificate</span>
                      <div className="mt-2 flex flex-wrap gap-1.5 min-h-[2.2rem]">
                        {selectedTemplate.placeholders.map((p) => (
                          <span
                            key={p}
                            className="inline-block rounded-md bg-burgundy/10 border border-burgundy/20 px-2 py-0.5 text-[10px] font-bold text-burgundy"
                          >
                            {p}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  <label className="block">
                    <span className="text-xs font-bold text-foreground/60">Subiect Email</span>
                    <input
                      type="text"
                      disabled={!isEditing}
                      value={isEditing ? editSubject : selectedTemplate.subject}
                      onChange={(e) => setEditSubject(e.target.value)}
                      className="mt-2 w-full rounded-xl border border-[var(--border)] bg-background px-3.5 py-2.5 text-sm font-semibold text-foreground focus:border-burgundy disabled:opacity-60"
                    />
                  </label>

                  <label className="block">
                    <span className="text-xs font-bold text-foreground/60">Corp Email (Markdown acceptat)</span>
                    <textarea
                      disabled={!isEditing}
                      value={isEditing ? editBody : selectedTemplate.body}
                      onChange={(e) => setEditBody(e.target.value)}
                      rows={12}
                      className="mt-2 w-full rounded-xl border border-[var(--border)] bg-background px-4 py-3 text-sm font-semibold text-foreground focus:border-burgundy disabled:opacity-60 font-mono"
                    />
                  </label>
                </div>
              </section>

              {/* Preview Column */}
              <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm space-y-4">
                <h3 className="text-sm font-bold uppercase tracking-wider text-burgundy border-b border-[var(--border)] pb-3">
                  Previzualizare Live (Randare cu date mock)
                </h3>

                <div className="rounded-xl border border-[var(--border)] bg-background overflow-hidden">
                  {/* Simulated Mailbox Header */}
                  <div className="bg-surface-muted/60 p-4 border-b border-[var(--border)] space-y-1.5 text-xs text-foreground/70">
                    <p>
                      <strong>De la:</strong> Echipa Codruț &lt;contact@codrut.ro&gt;
                    </p>
                    <p>
                      <strong>Către:</strong> {MOCK_REPLACEMENTS["{first_name}"]} &lt;{MOCK_REPLACEMENTS["{first_name}"].toLowerCase()}@exemplu-client.ro&gt;
                    </p>
                    <p>
                      <strong>Subiect:</strong> {preview.subject}
                    </p>
                  </div>

                  {/* Rendered HTML Body */}
                  <div
                    className="p-6 text-sm text-foreground/90 leading-relaxed font-sans min-h-[22rem] bg-white text-slate-800"
                    dangerouslySetInnerHTML={{ __html: preview.bodyHtml }}
                  />
                </div>

                <div className="rounded-xl bg-surface-muted p-3.5 border border-[var(--border)]">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-burgundy/80">Sugestie</p>
                  <p className="text-xs text-foreground/60 mt-1 leading-relaxed">
                    Tag-urile ca <code>{"{first_name}"}</code> și <code>{"{link_securizat}"}</code> sunt înlocuite automat cu valorile specifice fiecărui participant la expediere. Puteți edita corpul emailului folosind formatare <strong>bold</strong> (**text**) și [linkuri](url).
                  </p>
                </div>
              </section>
            </main>
          ) : (
            <div className="rounded-2xl border border-[var(--border)] bg-surface p-10 text-center shadow-sm">
              <p className="text-lg font-bold text-foreground">Catalog gol</p>
              <p className="mt-2 text-sm leading-6 text-foreground/62">
                Niciun șablon email disponibil. Faceți clic pe "+ Adaugă" în stânga.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
