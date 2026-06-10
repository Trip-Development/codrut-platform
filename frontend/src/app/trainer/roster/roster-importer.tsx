"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import * as XLSX from "xlsx";
import {
  createCompany,
  importCompanyRoster,
  resendParticipantInvitation,
  sendParticipantInvitations,
  type ParticipantInvitationMode,
  type RosterInviteResult,
} from "@/api/companies";
import { normalizeReportsToName } from "@/api/roster-format";

type CompanyOption = {
  id: string;
  name: string;
};

type RosterImporterProps = {
  companies: CompanyOption[];
  defaultCompanyId?: string;
  lockCompany?: boolean;
};

type DbField = "full_name" | "email" | "reports_to_name" | "position" | "location" | "pcm_profile";
type FlowStepKey = "upload" | "review" | "import" | "access";
type FlowStepState = "complete" | "current" | "upcoming" | "error";

const FIELD_LABELS: Record<DbField, string> = {
  full_name: "Nume Complet (Obligatoriu)",
  email: "Adresă Email (Obligatoriu)",
  reports_to_name: "Raportează Către / Manager (Opțional)",
  position: "Poziție / Rol (Opțional)",
  location: "Locație (Opțional)",
  pcm_profile: "Profil PCM (Opțional)",
};

const FIELD_ALIASES: Record<DbField, string[]> = {
  full_name: ["name", "nume", "full name", "nume complet", "participant", "client"],
  email: ["email", "e-mail", "mail", "adresa email", "adresa de email"],
  reports_to_name: ["reports to", "reports_to", "manager", "reports_to_name", "sefi", "boss"],
  position: ["position", "role", "rol", "pozitie", "functie", "job title"],
  location: ["location", "locatie", "oras", "city"],
  pcm_profile: ["profil pcm", "pcm", "pcm profile", "profil_pcm"],
};

export function RosterImporter({ companies, defaultCompanyId, lockCompany = false }: RosterImporterProps) {
  const router = useRouter();
  const [companyId, setCompanyId] = useState(defaultCompanyId || companies[0]?.id || "");
  const [allCompanies, setAllCompanies] = useState<CompanyOption[]>(companies);
  const [showAddCompanyModal, setShowAddCompanyModal] = useState(false);
  const [newCompanyName, setNewCompanyName] = useState("");
  const [isCreatingCompany, setIsCreatingCompany] = useState(false);

  useEffect(() => {
    if (defaultCompanyId) {
      setCompanyId(defaultCompanyId);
    }
  }, [defaultCompanyId]);

  const handleAddCompany = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCompanyName.trim()) return;

    setIsCreatingCompany(true);
    try {
      const created = await createCompany(newCompanyName.trim());
      const newCompany = { id: created.id, name: created.name };
      setAllCompanies((current) => {
        const map = new Map<string, CompanyOption>();
        current.forEach((c) => map.set(c.id, c));
        map.set(newCompany.id, newCompany);
        return Array.from(map.values());
      });
      setCompanyId(newCompany.id);
      setNewCompanyName("");
      setShowAddCompanyModal(false);
    } catch (error) {
      setImportState({
        status: "error",
        message: error instanceof Error ? error.message : "Compania nu a putut fi creată în backend.",
      });
    } finally {
      setIsCreatingCompany(false);
    }
  };
  const [headers, setHeaders] = useState<string[]>([]);
  const [rawRows, setRawRows] = useState<Record<string, string>[]>([]);
  const [mappings, setMappings] = useState<Record<DbField, string>>({
    full_name: "",
    email: "",
    reports_to_name: "",
    position: "",
    location: "",
    pcm_profile: "",
  });

  const [emailResults, setEmailResults] = useState<RosterInviteResult[]>([]);
  const [lastImportedParticipantIds, setLastImportedParticipantIds] = useState<string[]>([]);
  const [copiedResultId, setCopiedResultId] = useState<string | null>(null);
  const [resendingId, setResendingId] = useState<string | null>(null);
  const [deliveryState, setDeliveryState] = useState<{
    status: "idle" | "sending" | "success" | "error";
    mode: ParticipantInvitationMode | null;
    message: string;
  }>({
    status: "idle",
    mode: null,
    message: "",
  });

  const [importState, setImportState] = useState<{
    status: "idle" | "ready" | "importing" | "success" | "error";
    message: string;
  }>({
    status: "idle",
    message: "Alegeți un fișier CSV sau Excel pentru a începe importul.",
  });

  // State for manual edits made in the preview
  const [editedCells, setEditedCells] = useState<Record<string, Record<string, string>>>({});
  const [editingCellId, setEditingCellId] = useState<{ rowIndex: number; field: DbField } | null>(null);

  // Read Excel/CSV file using SheetJS
  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    setImportState({ status: "importing", message: "Se citește fișierul..." });
    setEmailResults([]);
    setLastImportedParticipantIds([]);
    setDeliveryState({ status: "idle", mode: null, message: "" });
    setCopiedResultId(null);
    setEditedCells({});
    setEditingCellId(null);

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target?.result as ArrayBuffer);
        const workbook = XLSX.read(data, { type: "array" });
        const firstSheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[firstSheetName];

        // Read headers and rows as array of arrays
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const rawSheetData = XLSX.utils.sheet_to_json<any[]>(worksheet, { header: 1 });
        if (rawSheetData.length === 0) {
          setImportState({ status: "error", message: "Fișierul este gol sau invalid." });
          return;
        }

        const rawHeaders = rawSheetData[0].map((h) => String(h).trim()).filter(Boolean);
        const dataRows = rawSheetData.slice(1);

        // Convert rows to key-value objects
        const objects: Record<string, string>[] = dataRows
          .map((row) => {
            const obj: Record<string, string> = {};
            rawHeaders.forEach((header, colIdx) => {
              obj[header] = row[colIdx] !== undefined ? String(row[colIdx]).trim() : "";
            });
            // Only keep rows that have some content
            const hasContent = Object.values(obj).some((val) => val.length > 0);
            return hasContent ? obj : null;
          })
          .filter((row): row is Record<string, string> => row !== null);

        if (objects.length === 0) {
          setImportState({ status: "error", message: "Nu s-au găsit date valide sub rândul de antet." });
          return;
        }

        setHeaders(rawHeaders);
        setRawRows(objects);

        // Auto-detect column mapping
        const detectedMappings: Record<DbField, string> = {
          full_name: "",
          email: "",
          reports_to_name: "",
          position: "",
          location: "",
          pcm_profile: "",
        };

        (Object.keys(FIELD_ALIASES) as DbField[]).forEach((field) => {
          const aliases = FIELD_ALIASES[field];
          const matchedHeader = rawHeaders.find((h) =>
            aliases.some((alias) => h.toLowerCase() === alias.toLowerCase() || h.toLowerCase().includes(alias.toLowerCase()))
          );
          if (matchedHeader) {
            detectedMappings[field] = matchedHeader;
          }
        });

        // Fallbacks: if email/name not matched, grab first/second columns that look reasonable
        if (!detectedMappings.full_name && rawHeaders.length > 0) detectedMappings.full_name = rawHeaders[0];
        if (!detectedMappings.email && rawHeaders.length > 1) {
          const emailCol = rawHeaders.find((h) => h.toLowerCase().includes("email") || h.toLowerCase().includes("mail"));
          detectedMappings.email = emailCol || rawHeaders[1];
        }

        setMappings(detectedMappings);
        setImportState({
          status: "ready",
          message: `Am încărcat ${objects.length} rânduri. Vă rugăm să validați maparea coloanelor și corectitudinea datelor.`,
        });
      } catch (err) {
        console.error(err);
        setImportState({ status: "error", message: "Eroare la procesarea fișierului. Verificați formatul." });
      }
    };
    reader.readAsArrayBuffer(file);
  }

  // Update a single column mapping dropdown
  const handleMappingChange = (field: DbField, column: string) => {
    setMappings((prev) => ({ ...prev, [field]: column }));
  };

  // Convert raw row to Db fields taking manual edits into account
  const getNormalizedRow = useCallback((rawRow: Record<string, string>, rowIndex: number): Record<DbField, string> => {
    const rowEdits = editedCells[rowIndex] || {};

    const getVal = (field: DbField): string => {
      if (rowEdits[field] !== undefined) return rowEdits[field];
      const columnHeader = mappings[field];
      return columnHeader ? (rawRow[columnHeader] ?? "") : "";
    };

    return {
      full_name: getVal("full_name"),
      email: getVal("email"),
      reports_to_name: normalizeReportsToName(getVal("reports_to_name")),
      position: getVal("position"),
      location: getVal("location"),
      pcm_profile: getVal("pcm_profile"),
    };
  }, [editedCells, mappings]);

  // Build full preview lists and validation errors
  const processedRows = useMemo(() => {
    return rawRows.map((rawRow, idx) => getNormalizedRow(rawRow, idx));
  }, [rawRows, getNormalizedRow]);

  const validationErrors = useMemo(() => {
    const errors: { rowIndex: number; name: string; field: DbField; error: string; type: "critical" | "warning" }[] = [];
    
    const emailsInFile = new Map<string, number[]>();
    const namesInFile = new Set<string>();

    processedRows.forEach((row, idx) => {
      if (row.full_name) {
        namesInFile.add(row.full_name.trim().toLowerCase());
      }
      if (row.email) {
        const emailKey = row.email.trim().toLowerCase();
        if (!emailsInFile.has(emailKey)) {
          emailsInFile.set(emailKey, []);
        }
        emailsInFile.get(emailKey)!.push(idx);
      }
    });

    processedRows.forEach((row, idx) => {
      const name = row.full_name || `Rândul ${idx + 2}`;
      if (!row.full_name) {
        errors.push({ rowIndex: idx, name, field: "full_name", error: "Numele este obligatoriu.", type: "critical" });
      }
      if (!row.email) {
        errors.push({ rowIndex: idx, name, field: "email", error: "Emailul este obligatoriu.", type: "critical" });
      } else {
        if (!row.email.includes("@")) {
          errors.push({ rowIndex: idx, name, field: "email", error: "Formatul emailului este invalid.", type: "critical" });
        }
        const dups = emailsInFile.get(row.email.trim().toLowerCase());
        if (dups && dups.length > 1) {
          errors.push({
            rowIndex: idx,
            name,
            field: "email",
            error: `Adresă email duplicată în fișier (rândurile ${dups.map((d) => d + 2).join(", ")}).`,
            type: "critical",
          });
        }
      }
      if (row.reports_to_name) {
        const mgrKey = row.reports_to_name.trim().toLowerCase();
        if (!namesInFile.has(mgrKey)) {
          errors.push({
            rowIndex: idx,
            name,
            field: "reports_to_name",
            error: `Managerul "${row.reports_to_name}" nu se află în lista de participanți.`,
            type: "warning",
          });
        }
      }
      if (!row.pcm_profile) {
        errors.push({
          rowIndex: idx,
          name,
          field: "pcm_profile",
          error: "Profil PCM necompletat (participantul nu va primi evaluări PCM).",
          type: "warning",
        });
      }
    });
    return errors;
  }, [processedRows]);

  const hasCriticalErrors = validationErrors.some((e) => e.type === "critical");
  const criticalErrorCount = validationErrors.filter((error) => error.type === "critical").length;
  const criticalRowCount = new Set(
    validationErrors
      .filter((error) => error.type === "critical")
      .map((error) => error.rowIndex),
  ).size;
  const warningCount = validationErrors.filter((error) => error.type === "warning").length;
  const validRowCount = Math.max(0, processedRows.length - criticalRowCount);
  const selectedCompanyName = allCompanies.find((company) => company.id === companyId)?.name ?? "Compania curentă";
  const activeStep: FlowStepKey =
    importState.status === "success"
      ? "access"
      : importState.status === "importing"
        ? "import"
        : headers.length > 0
          ? "review"
          : "upload";
  const flowSteps: Array<{ key: FlowStepKey; label: string; detail: string; state: FlowStepState }> = [
    {
      key: "upload",
      label: "Alege fișierul",
      detail: companyId ? selectedCompanyName : "Selectează compania",
      state: headers.length > 0 || importState.status === "success" ? "complete" : activeStep === "upload" ? "current" : "upcoming",
    },
    {
      key: "review",
      label: "Revizuiește datele",
      detail:
        processedRows.length > 0
          ? `${processedRows.length} rânduri · ${criticalErrorCount} erori · ${warningCount} atenționări`
          : "Mapează coloanele",
      state:
        criticalErrorCount > 0
          ? "error"
          : importState.status === "success" || importState.status === "importing"
            ? "complete"
            : activeStep === "review"
              ? "current"
              : "upcoming",
    },
    {
      key: "import",
      label: "Salvează rosterul",
      detail:
        importState.status === "success"
          ? `${lastImportedParticipantIds.length} participanți salvați`
          : "Fără emailuri la import",
      state:
        importState.status === "success"
          ? "complete"
          : activeStep === "import"
            ? "current"
            : "upcoming",
    },
    {
      key: "access",
      label: "Alege accesul",
      detail:
        deliveryState.status === "success"
          ? deliveryState.message
          : "Emailuri sau linkuri",
      state: activeStep === "access" ? "current" : "upcoming",
    },
  ];

  const handleCellEditSave = (rowIndex: number, field: DbField, value: string) => {
    setEditedCells((prev) => {
      const rowEdits = prev[rowIndex] || {};
      return {
        ...prev,
        [rowIndex]: {
          ...rowEdits,
          [field]: field === "reports_to_name" ? normalizeReportsToName(value) : value.trim(),
        },
      };
    });
    setEditingCellId(null);
  };

  const handleImport = async () => {
    if (!companyId || processedRows.length === 0 || hasCriticalErrors) return;

    setImportState({ status: "importing", message: "Se importă participanții..." });
    setEmailResults([]);
    setLastImportedParticipantIds([]);
    setDeliveryState({ status: "idle", mode: null, message: "" });
    setCopiedResultId(null);

    try {
      const importResult = await importCompanyRoster(
        companyId,
        processedRows.map((r) => ({
          Name: r.full_name,
          "Reports To": r.reports_to_name,
          Position: r.position,
          Location: r.location,
          email: r.email,
          "Profil PCM": r.pcm_profile,
        })),
      );
      const results = importResult.email_results ?? [];
      setEmailResults(results);
      setLastImportedParticipantIds(importResult.participants.map((participant) => participant.id));
      router.refresh();
      setImportState({
        status: "success",
        message: `Import reușit: ${importResult.total_imported} participanți salvați. Alege mai jos cum trimiți accesul.`,
      });
    } catch (error) {
      setImportState({
        status: "error",
        message: error instanceof Error ? error.message : "Importul rosterului a eșuat în backend.",
      });
    }
  };

  const handleDeliverInvites = async (mode: ParticipantInvitationMode) => {
    if (!companyId || lastImportedParticipantIds.length === 0) return;
    setDeliveryState({
      status: "sending",
      mode,
      message: mode === "email" ? "Se trimit emailurile..." : "Se generează linkurile securizate...",
    });
    setCopiedResultId(null);

    try {
      const result = await sendParticipantInvitations(companyId, {
        participantIds: lastImportedParticipantIds,
        mode,
      });
      setEmailResults(result.results);
      router.refresh();
      setDeliveryState({
        status: "success",
        mode,
        message:
          mode === "email"
            ? `${result.emails_sent}/${result.total} emailuri trimise.`
            : `${result.links_generated} linkuri securizate generate.`,
      });
    } catch (error) {
      setDeliveryState({
        status: "error",
        mode,
        message: error instanceof Error ? error.message : "Livrarea accesului a eșuat.",
      });
    }
  };

  const handleCopyLink = async (result: RosterInviteResult) => {
    if (!result.invite_url || typeof navigator === "undefined") return;
    try {
      await navigator.clipboard.writeText(result.invite_url);
      setCopiedResultId(result.participant_id);
    } catch {
      setDeliveryState({
        status: "error",
        mode: "secure_links",
        message: "Linkul nu a putut fi copiat. Deschideți meniul contextual al browserului și copiați manual.",
      });
    }
  };

  const handleResend = async (participantId: string) => {
    if (!companyId) return;
    setResendingId(participantId);
    try {
      const result = await resendParticipantInvitation(companyId, participantId);
      if (result) {
        setEmailResults((prev) =>
          prev.map((r) => (r.participant_id === participantId ? { ...r, ...result } : r)),
        );
      }
    } catch (error) {
      setDeliveryState({
        status: "error",
        mode: "email",
        message: error instanceof Error ? error.message : "Retrimiterea invitației a eșuat.",
      });
    } finally {
      setResendingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <ImportFlowStepper steps={flowSteps} />

      <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
        <div className="grid gap-0 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <div className="border-b border-[var(--border)] bg-background/55 p-5 lg:border-b-0 lg:border-r">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Import roster</p>
            <h3 className="mt-1 text-lg font-semibold text-foreground">Salvează oamenii înainte de invitații</h3>
            <p className="mt-2 max-w-md text-sm leading-6 text-foreground/62">
              Importul creează rosterul în companie. Abia după confirmare alegi dacă trimiți emailuri sau pregătești linkuri securizate.
            </p>
            <p className="mt-4 inline-flex rounded-full border border-[var(--border)] bg-surface px-3 py-1.5 text-xs font-semibold text-foreground/58">
              Fără trimitere automată la import
            </p>
          </div>

          <div className="grid gap-4 p-5 md:grid-cols-2">
            <div className="block">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-foreground">Companie destinație</span>
                {!lockCompany && (
                  <button
                    type="button"
                    onClick={() => setShowAddCompanyModal(true)}
                    className="tap-soft rounded-full px-2.5 py-1 text-xs font-semibold text-burgundy hover:bg-burgundy/10"
                  >
                    + Companie nouă
                  </button>
                )}
              </div>
              {lockCompany ? (
                <div className="mt-2 rounded-xl border border-[var(--border)] bg-background px-3.5 py-3 text-sm font-semibold text-foreground">
                  {selectedCompanyName}
                </div>
              ) : (
                <select
                  value={companyId}
                  onChange={(e) => setCompanyId(e.target.value)}
                  className="mt-2 w-full rounded-xl border border-[var(--border)] bg-background px-3.5 py-3 text-sm font-semibold text-foreground focus:border-burgundy"
                >
                  {allCompanies.map((company) => (
                    <option key={company.id} value={company.id}>
                      {company.name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <label className="block">
              <span className="text-sm font-semibold text-foreground">Selectează fișier</span>
              <input
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={handleFileChange}
                className="mt-2 w-full rounded-xl border border-dashed border-burgundy/35 bg-background px-3 py-2 text-sm font-semibold text-foreground file:mr-3 file:rounded-lg file:border-0 file:bg-burgundy file:px-3.5 file:py-2 file:text-xs file:font-bold file:text-white hover:border-burgundy/60"
              />
              <span className="mt-2 block text-xs text-foreground/50">Excel (.xlsx, .xls) sau CSV (.csv)</span>
            </label>
          </div>
        </div>

        {importState.status === "idle" && (
          <div className="border-t border-[var(--border)] bg-background/60 px-5 py-5 text-center text-foreground/55">
            <p className="text-sm font-semibold">Aștept fișierul de import.</p>
            <p className="mt-1 text-xs">Acceptă Excel (.xlsx, .xls) și CSV (.csv).</p>
          </div>
        )}

        {importState.status !== "idle" && (
          <div className="flex flex-wrap items-center gap-3 border-t border-[var(--border)] bg-background/60 px-5 py-3">
            <StatusDot tone={importState.status} />
            <p className="text-sm font-semibold text-foreground/68">
              {importState.message}
            </p>
          </div>
        )}
      </section>

      {processedRows.length > 0 && importState.status === "ready" && (
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
          <div className="grid gap-3 sm:grid-cols-4">
            <RosterMetric label="Rânduri citite" value={processedRows.length} />
            <RosterMetric label="Valide pentru import" value={validRowCount} tone={criticalErrorCount > 0 ? "warning" : "success"} />
            <RosterMetric label="Erori critice" value={criticalErrorCount} tone={criticalErrorCount > 0 ? "danger" : "neutral"} />
            <RosterMetric label="Atenționări" value={warningCount} tone={warningCount > 0 ? "warning" : "neutral"} />
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] pt-4">
            <p className="max-w-2xl text-sm leading-6 text-foreground/62">
              Importul salvează doar rosterul. Trimiterea emailurilor sau generarea linkurilor se face separat după confirmare.
            </p>
            <button
              type="button"
              disabled={hasCriticalErrors}
              onClick={handleImport}
              className="tap-soft rounded-xl bg-burgundy px-5 py-2.5 text-xs font-bold text-white hover:bg-burgundy/90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Salvează rosterul
            </button>
          </div>
        </section>
      )}

      {importState.status === "success" && lastImportedParticipantIds.length > 0 && (
        <section className="rounded-2xl border border-burgundy/20 bg-surface p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Acces participanți</p>
              <h3 className="mt-1 text-base font-semibold text-foreground">Roster salvat. Alege livrarea.</h3>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-foreground/62">
                Acesta este un pas separat de import. Poți trimite invitațiile acum sau poți genera linkuri pentru distribuție manuală.
              </p>
            </div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <DeliveryChoice
              title="Trimite emailuri"
              detail="Folosește șablonul activ și salvează statusul de livrare pentru fiecare participant."
              action={deliveryState.status === "sending" && deliveryState.mode === "email" ? "Se trimit..." : "Trimite emailuri"}
              disabled={deliveryState.status === "sending"}
              selected={deliveryState.mode === "email"}
              onClick={() => handleDeliverInvites("email")}
            />
            <DeliveryChoice
              title="Generează linkuri"
              detail="Creează linkuri securizate fără expediere, potrivite pentru trimitere manuală sau test."
              action={deliveryState.status === "sending" && deliveryState.mode === "secure_links" ? "Se generează..." : "Generează linkuri"}
              disabled={deliveryState.status === "sending"}
              selected={deliveryState.mode === "secure_links"}
              onClick={() => handleDeliverInvites("secure_links")}
            />
          </div>
          {deliveryState.message && (
            <p className={`mt-3 rounded-xl px-3 py-2 text-sm font-semibold ${
              deliveryState.status === "error" ? "bg-red-50 text-red-700" : deliveryState.status === "success" ? "bg-green-50 text-green-700" : "bg-burgundy/5 text-burgundy"
            }`}>
              {deliveryState.message}
            </p>
          )}
        </section>
      )}

      {/* Delivery results table */}
      {importState.status === "success" && emailResults.length > 0 && (
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-foreground">Rezultat livrare acces</h3>
            <span className="text-xs text-foreground/50">
              {emailResults.filter((r) => r.email_sent || r.delivery_mode === "secure_links").length}/{emailResults.length} pregătite
            </span>
          </div>
          <div className="overflow-x-auto rounded-xl border border-[var(--border)]">
            <table className="w-full text-xs">
              <thead className="bg-background border-b border-[var(--border)]">
                <tr>
                  <th className="px-4 py-2.5 text-left font-bold text-foreground/70">Participant</th>
                  <th className="px-4 py-2.5 text-left font-bold text-foreground/70">Email</th>
                  <th className="px-4 py-2.5 text-center font-bold text-foreground/70">Status</th>
                  <th className="px-4 py-2.5 text-right font-bold text-foreground/70">Acțiune</th>
                </tr>
              </thead>
              <tbody>
                {emailResults.map((r) => (
                  <tr key={r.participant_id} className="border-b border-[var(--border)] transition-colors last:border-0 hover:bg-surface-muted/50">
                    <td className="px-4 py-2.5 font-semibold text-foreground">{r.full_name}</td>
                    <td className="px-4 py-2.5 text-foreground/70">{r.email}</td>
                    <td className="px-4 py-2.5 text-center">
                      {r.delivery_mode === "secure_links" ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2.5 py-0.5 text-blue-700 font-bold dark:bg-blue-900/30 dark:text-blue-300">
                          Link generat
                        </span>
                      ) : r.email_sent ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2.5 py-0.5 text-green-700 font-bold dark:bg-green-900/30 dark:text-green-400">
                          Trimis
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-amber-700 font-bold dark:bg-amber-900/30 dark:text-amber-400" title={r.error ?? ""}>
                          Eșuat
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {r.delivery_mode === "secure_links" && r.invite_url ? (
                        <button
                          type="button"
                          onClick={() => handleCopyLink(r)}
                          className="rounded-lg border border-[var(--border)] bg-background px-3 py-1.5 text-xs font-bold text-foreground hover:border-burgundy/50 hover:text-burgundy transition-all"
                        >
                          {copiedResultId === r.participant_id ? "Copiat" : "Copiază link"}
                        </button>
                      ) : !r.email_sent ? (
                        <button
                          type="button"
                          disabled={resendingId === r.participant_id}
                          onClick={() => handleResend(r.participant_id)}
                          className="rounded-lg bg-burgundy px-3 py-1.5 text-xs font-bold text-white hover:bg-burgundy/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                        >
                          {resendingId === r.participant_id ? "Se trimite..." : "Retrimite"}
                        </button>
                      ) : (
                        <span className="text-foreground/35">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Roster column mapping */}
      {headers.length > 0 && importState.status === "ready" && (
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm space-y-4">
          <div>
            <h3 className="text-base font-semibold text-foreground">Mapare coloane</h3>
            <p className="mt-1 text-sm leading-6 text-foreground/60">
              Asociază coloanele din fișier cu structura platformei. Detectarea automată poate fi ajustată manual.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {(Object.keys(FIELD_LABELS) as DbField[]).map((field) => (
              <label key={field} className="block rounded-xl border border-[var(--border)] bg-background p-3 transition-colors hover:border-burgundy/25 hover:bg-surface-muted/40">
                <span className="text-xs font-bold text-foreground/70">{FIELD_LABELS[field]}</span>
                <select
                  value={mappings[field]}
                  onChange={(e) => handleMappingChange(field, e.target.value)}
                  className="mt-2 w-full rounded-lg border border-[var(--border)] bg-surface px-2.5 py-1.5 text-xs font-semibold text-foreground focus:border-burgundy"
                >
                  <option value="">-- Ignoră / Fără --</option>
                  {headers.map((h) => (
                    <option key={h} value={h}>
                      {h}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
        </section>
      )}

      {/* Warnings & Errors Panel */}
      {validationErrors.length > 0 && importState.status === "ready" && (
        <div className="space-y-3">
          {validationErrors.some((e) => e.type === "critical") && (
            <section className="rounded-2xl border border-red-200 bg-red-50/60 p-5 shadow-sm space-y-3">
              <h3 className="text-base font-semibold text-red-800">
                Erori critice ({validationErrors.filter((e) => e.type === "critical").length})
              </h3>
              <p className="text-xs text-red-700">
                Problemele de mai jos blochează importul. Corectează-le direct în tabel:
              </p>
              <div className="max-h-28 overflow-y-auto space-y-1.5">
                {validationErrors
                  .filter((e) => e.type === "critical")
                  .map((err, i) => (
                    <p key={i} className="text-xs font-semibold text-red-700">
                      - <strong>{err.name}</strong>: {err.error} (Câmpul: <i>{FIELD_LABELS[err.field]}</i>)
                    </p>
                  ))}
              </div>
            </section>
          )}

          {validationErrors.some((e) => e.type === "warning") && (
            <section className="rounded-2xl border border-amber-200 bg-amber-50/60 p-5 shadow-sm space-y-3">
              <h3 className="text-base font-semibold text-amber-800">
                Atenționări ({validationErrors.filter((e) => e.type === "warning").length})
              </h3>
              <p className="text-xs text-amber-700">
                Nu blochează importul, dar pot afecta generarea automată a evaluărilor:
              </p>
              <div className="max-h-28 overflow-y-auto space-y-1.5">
                {validationErrors
                  .filter((e) => e.type === "warning")
                  .map((err, i) => (
                    <p key={i} className="text-xs font-semibold text-amber-700">
                      - <strong>{err.name}</strong>: {err.error} (Câmpul: <i>{FIELD_LABELS[err.field]}</i>)
                    </p>
                  ))}
              </div>
            </section>
          )}
        </div>
      )}

      {/* Spreadsheet Live Preview & Inline Editing */}
      {processedRows.length > 0 && importState.status === "ready" && (
        <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
          <div className="px-5 py-4 border-b border-[var(--border)]">
            <h3 className="text-base font-semibold text-foreground">Previzualizare roster</h3>
            <p className="mt-1 text-sm leading-6 text-foreground/60">
              Dublu-click pe o celulă pentru corecții rapide înainte de salvare.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-surface-muted text-[10px] font-bold uppercase tracking-wider text-foreground/50 border-b border-[var(--border)]">
                <tr>
                  <th className="px-5 py-3 w-12 text-center">Nr.</th>
                  <th className="px-5 py-3">Nume complet</th>
                  <th className="px-5 py-3">Email</th>
                  <th className="px-5 py-3">Reports To / Manager</th>
                  <th className="px-5 py-3">Poziție / Rol</th>
                  <th className="px-5 py-3">Locație</th>
                  <th className="px-5 py-3">Profil PCM</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {processedRows.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-background/40">
                    <td className="px-5 py-3 font-semibold text-foreground/45 text-center">{rIdx + 1}</td>

                    {/* Render fields with double click inline editing support */}
                    {(Object.keys(FIELD_LABELS) as DbField[]).map((field) => {
                      const isEditing = editingCellId?.rowIndex === rIdx && editingCellId?.field === field;
                      const hasError = validationErrors.some((e) => e.rowIndex === rIdx && e.field === field);
                      const isRequired = field === "full_name" || field === "email";

                      return (
                        <td
                          key={field}
                          className={`px-5 py-3 font-medium transition-colors ${
                            hasError ? "bg-red-50/80 text-red-900 border border-red-200" : "text-foreground"
                          }`}
                          onDoubleClick={() => setEditingCellId({ rowIndex: rIdx, field })}
                        >
                          {isEditing ? (
                            <input
                              type="text"
                              defaultValue={row[field]}
                              autoFocus
                              onBlur={(e) => handleCellEditSave(rIdx, field, e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") {
                                  handleCellEditSave(rIdx, field, e.currentTarget.value);
                                } else if (e.key === "Escape") {
                                  setEditingCellId(null);
                                }
                              }}
                              className="w-full bg-background border border-burgundy focus:ring-1 focus:ring-burgundy rounded px-2 py-1 text-xs text-foreground focus:outline-none"
                            />
                          ) : (
                            <div className="flex items-center justify-between group cursor-pointer">
                              <span>
                                {row[field] ? (
                                  row[field]
                                ) : (
                                  <span className="text-foreground/30 italic">
                                    {isRequired ? "Lipsă obligatoriu" : "—"}
                                  </span>
                                )}
                              </span>
                              <span className="text-[10px] text-burgundy opacity-0 group-hover:opacity-100 ml-2">
                                Editează
                              </span>
                            </div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Add Company Modal */}
      {showAddCompanyModal && !lockCompany && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <form
            onSubmit={handleAddCompany}
            className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-surface p-6 shadow-xl space-y-4"
          >
            <h3 className="text-lg font-semibold text-foreground">Adaugă companie nouă</h3>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-foreground/60">Nume companie / organizație</label>
              <input
                type="text"
                required
                value={newCompanyName}
                onChange={(e) => setNewCompanyName(e.target.value)}
                placeholder="Ex. Acme Corporation SRL"
                className="w-full rounded-xl border border-[var(--border)] bg-background px-3.5 py-2.5 text-sm font-semibold text-foreground focus:border-burgundy focus:outline-none"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-[var(--border)]">
              <button
                type="button"
                onClick={() => {
                  setShowAddCompanyModal(false);
                  setNewCompanyName("");
                }}
                className="tap-soft rounded-lg border border-[var(--border)] bg-background px-4 py-2 text-xs font-bold text-foreground hover:bg-surface-muted"
              >
                Anulează
              </button>
              <button
                type="submit"
                disabled={isCreatingCompany}
                className="tap-soft rounded-lg bg-burgundy px-4 py-2 text-xs font-bold text-white hover:bg-burgundy/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isCreatingCompany ? "Se creează..." : "Adaugă"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function ImportFlowStepper({
  steps,
}: {
  steps: Array<{ key: FlowStepKey; label: string; detail: string; state: FlowStepState }>;
}) {
  return (
    <section className="rounded-2xl border border-[var(--border)] bg-gradient-to-r from-surface via-surface to-surface-muted/50 p-3 shadow-sm">
      <div className="grid gap-1.5 md:grid-cols-4">
        {steps.map((step, index) => (
          <div
            key={step.key}
            className={[
              "group flex items-start gap-3 rounded-xl px-3 py-3 transition-all",
              step.state === "current"
                ? "bg-burgundy/10 text-burgundy shadow-sm"
                : step.state === "complete"
                  ? "text-green-700 hover:bg-green-50/70"
                  : step.state === "error"
                    ? "text-red-700 hover:bg-red-50/70"
                    : "text-foreground/50 hover:bg-background/70",
            ].join(" ")}
          >
            <span
              className={[
                "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold transition-colors",
                step.state === "current"
                  ? "border-burgundy bg-burgundy text-white"
                  : step.state === "complete"
                    ? "border-green-200 bg-green-50 text-green-700"
                    : step.state === "error"
                      ? "border-red-200 bg-red-50 text-red-700"
                      : "border-[var(--border)] bg-background text-foreground/50 group-hover:border-burgundy/25",
              ].join(" ")}
            >
              {index + 1}
            </span>
            <div className="min-w-0">
              <p
                className={[
                  "text-xs font-semibold",
                  step.state === "current"
                    ? "text-burgundy"
                    : step.state === "complete"
                      ? "text-green-700"
                      : step.state === "error"
                        ? "text-red-700"
                        : "text-foreground/58",
                ].join(" ")}
              >
                {step.label.replace(/^\d+\.\s*/, "")}
              </p>
              <p className="mt-1 min-h-8 text-xs leading-4 text-foreground/58">{step.detail}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function StatusDot({ tone }: { tone: "idle" | "ready" | "importing" | "success" | "error" }) {
  const toneClass =
    tone === "error"
      ? "bg-red-500"
      : tone === "success"
        ? "bg-green-500"
        : tone === "importing"
          ? "animate-pulse bg-burgundy"
          : tone === "ready"
            ? "bg-burgundy"
            : "bg-foreground/35";

  return <span className={["h-2.5 w-2.5 rounded-full", toneClass].join(" ")} aria-hidden="true" />;
}

function DeliveryChoice({
  title,
  detail,
  action,
  disabled,
  selected,
  onClick,
}: {
  title: string;
  detail: string;
  action: string;
  disabled: boolean;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={[
        "tap-soft group flex min-h-32 flex-col items-start justify-between rounded-xl border bg-background p-4 text-left transition-all hover:-translate-y-0.5 hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-55",
        selected ? "border-burgundy/45 ring-2 ring-burgundy/10" : "border-[var(--border)] hover:border-burgundy/35",
      ].join(" ")}
    >
      <span>
        <span className="block text-sm font-semibold text-foreground">{title}</span>
        <span className="mt-1 block text-xs leading-5 text-foreground/58">{detail}</span>
      </span>
      <span className="mt-4 inline-flex rounded-lg bg-foreground px-3 py-1.5 text-xs font-bold text-background group-hover:bg-burgundy group-hover:text-white">
        {action}
      </span>
    </button>
  );
}

function RosterMetric({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number;
  tone?: "neutral" | "success" | "warning" | "danger";
}) {
  const toneClass =
    tone === "success"
      ? "text-green-700"
      : tone === "warning"
        ? "text-amber-700"
        : tone === "danger"
          ? "text-red-700"
          : "text-foreground";

  return (
    <div className="rounded-xl border border-[var(--border)] bg-background/80 px-3 py-3 transition-all hover:border-burgundy/20 hover:bg-surface-muted/50 hover:shadow-sm">
      <p className="text-[11px] font-semibold text-foreground/50">{label}</p>
      <p className={["mt-1 text-2xl font-semibold", toneClass].join(" ")}>{value}</p>
    </div>
  );
}
