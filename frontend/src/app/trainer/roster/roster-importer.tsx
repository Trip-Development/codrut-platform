"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import * as XLSX from "xlsx";
import { getApiBaseUrl } from "@/api/runtime";
import {
  createCompany,
  importCompanyRoster,
  sendParticipantInvitations,
  type ParticipantInvitationMode,
  type RosterInviteResult,
} from "@/api/companies";

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
      reports_to_name: getVal("reports_to_name"),
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
  const selectedCompanyName = allCompanies.find((company) => company.id === companyId)?.name ?? "Compania curentă";

  const handleCellEditSave = (rowIndex: number, field: DbField, value: string) => {
    setEditedCells((prev) => {
      const rowEdits = prev[rowIndex] || {};
      return {
        ...prev,
        [rowIndex]: {
          ...rowEdits,
          [field]: value.trim(),
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
      const response = await fetch(
        `${getApiBaseUrl()}/companies/${companyId}/participants/${participantId}/resend-invite`,
        { method: "POST", credentials: "include" }
      );
      const data = await response.json();
      const result = data.email_results?.[0];
      if (result) {
        setEmailResults((prev) =>
          prev.map((r) => (r.participant_id === participantId ? { ...r, ...result } : r))
        );
      }
    } catch {
      // leave row in ⚠ state — user can retry
    } finally {
      setResendingId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* File Upload Grid */}
      <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="block">
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold text-foreground">Compania Destinație</span>
              {!lockCompany && (
                <button
                  type="button"
                  onClick={() => setShowAddCompanyModal(true)}
                  className="text-xs font-bold text-burgundy hover:underline"
                >
                  + Companie Nouă
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
            <span className="text-sm font-bold text-foreground">Selectează fișier (Excel sau CSV)</span>
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={handleFileChange}
              className="mt-2 w-full rounded-xl border border-dashed border-burgundy/35 bg-background px-3 py-2 text-sm font-semibold text-foreground file:mr-3 file:rounded-lg file:border-0 file:bg-burgundy file:px-3.5 file:py-2 file:text-xs file:font-bold file:text-white hover:border-burgundy/60"
            />
          </label>
        </div>

        {importState.status === "idle" && (
          <div className="rounded-xl border border-dashed border-[var(--border)] bg-background px-5 py-8 text-center text-foreground/50">
            <p className="text-sm font-semibold">Trageți sau selectați fișierul de import.</p>
            <p className="mt-1 text-xs">Sunt acceptate formatele Microsoft Excel (.xlsx, .xls) și CSV (.csv)</p>
          </div>
        )}

        {importState.status !== "idle" && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] pt-3">
            <p className={`text-xs font-bold uppercase tracking-wider ${
              importState.status === "error" ? "text-red-600" : importState.status === "success" ? "text-green-600" : "text-burgundy"
            }`}>
              Status: {importState.message}
            </p>
            {importState.status === "ready" && (
              <button
                type="button"
                disabled={hasCriticalErrors}
                onClick={handleImport}
                className="tap-soft rounded-xl bg-burgundy px-5 py-2.5 text-xs font-bold text-white hover:bg-burgundy/90 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Importă Roster
              </button>
            )}
          </div>
        )}
      </section>

      {importState.status === "success" && lastImportedParticipantIds.length > 0 && (
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wider text-burgundy">Livrare acces</h3>
              <p className="mt-1 text-sm leading-6 text-foreground/62">
                Rosterul este salvat. Alege dacă participanții primesc email automat sau dacă pregătești linkuri securizate pentru trimitere manuală.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={deliveryState.status === "sending"}
                onClick={() => handleDeliverInvites("email")}
                className="tap-soft rounded-xl bg-burgundy px-4 py-2.5 text-xs font-bold text-white hover:bg-burgundy/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {deliveryState.status === "sending" && deliveryState.mode === "email" ? "Se trimit..." : "Trimite emailuri"}
              </button>
              <button
                type="button"
                disabled={deliveryState.status === "sending"}
                onClick={() => handleDeliverInvites("secure_links")}
                className="tap-soft rounded-xl border border-[var(--border)] bg-background px-4 py-2.5 text-xs font-bold text-foreground hover:border-burgundy/50 hover:text-burgundy disabled:cursor-not-allowed disabled:opacity-50"
              >
                {deliveryState.status === "sending" && deliveryState.mode === "secure_links" ? "Se generează..." : "Generează linkuri"}
              </button>
            </div>
          </div>
          {deliveryState.message && (
            <p className={`mt-3 text-xs font-bold uppercase tracking-wider ${
              deliveryState.status === "error" ? "text-red-600" : deliveryState.status === "success" ? "text-green-600" : "text-burgundy"
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
            <h3 className="text-sm font-bold uppercase tracking-wider text-burgundy">Rezultat livrare acces</h3>
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
                  <tr key={r.participant_id} className="border-b border-[var(--border)] last:border-0 hover:bg-background/50 transition-colors">
                    <td className="px-4 py-2.5 font-semibold text-foreground">{r.full_name}</td>
                    <td className="px-4 py-2.5 text-foreground/70">{r.email}</td>
                    <td className="px-4 py-2.5 text-center">
                      {r.delivery_mode === "secure_links" ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2.5 py-0.5 text-blue-700 font-bold dark:bg-blue-900/30 dark:text-blue-300">
                          Link generat
                        </span>
                      ) : r.email_sent ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2.5 py-0.5 text-green-700 font-bold dark:bg-green-900/30 dark:text-green-400">
                          ✓ Trimis
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-amber-700 font-bold dark:bg-amber-900/30 dark:text-amber-400" title={r.error ?? ""}>
                          ⚠ Eșuat
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
          <h3 className="text-sm font-bold uppercase tracking-wider text-burgundy">Mapare Coloane</h3>
          <p className="text-xs text-foreground/60">
            Asociați coloanele din fișierul dumneavoastră Excel/CSV cu structura de date a platformei.
          </p>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {(Object.keys(FIELD_LABELS) as DbField[]).map((field) => (
              <label key={field} className="block rounded-xl border border-[var(--border)] bg-background p-3">
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
            <section className="rounded-2xl border border-red-200 bg-red-50/50 p-5 shadow-sm space-y-3">
              <h3 className="text-sm font-bold text-red-800 uppercase tracking-wider">
                Erori Critice ({validationErrors.filter((e) => e.type === "critical").length})
              </h3>
              <p className="text-xs text-red-700">
                Următoarele probleme blochează importul. Corectați-le direct în tabelul de mai jos:
              </p>
              <div className="max-h-28 overflow-y-auto space-y-1.5">
                {validationErrors
                  .filter((e) => e.type === "critical")
                  .map((err, i) => (
                    <p key={i} className="text-xs font-semibold text-red-700">
                      · <strong>{err.name}</strong>: {err.error} (Câmpul: <i>{FIELD_LABELS[err.field]}</i>)
                    </p>
                  ))}
              </div>
            </section>
          )}

          {validationErrors.some((e) => e.type === "warning") && (
            <section className="rounded-2xl border border-amber-200 bg-amber-50/50 p-5 shadow-sm space-y-3">
              <h3 className="text-sm font-bold text-amber-800 uppercase tracking-wider">
                Atenționări ({validationErrors.filter((e) => e.type === "warning").length})
              </h3>
              <p className="text-xs text-amber-700">
                Următoarele atenționări nu blochează importul, dar pot afecta generarea automată a evaluărilor:
              </p>
              <div className="max-h-28 overflow-y-auto space-y-1.5">
                {validationErrors
                  .filter((e) => e.type === "warning")
                  .map((err, i) => (
                    <p key={i} className="text-xs font-semibold text-amber-700">
                      · <strong>{err.name}</strong>: {err.error} (Câmpul: <i>{FIELD_LABELS[err.field]}</i>)
                    </p>
                  ))}
              </div>
            </section>
          )}
        </div>
      )}

      {/* Spreadsheet Live Preview & Inline Editing */}
      {processedRows.length > 0 && importState.status === "ready" && (
        <section className="rounded-2xl border border-[var(--border)] bg-surface shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-[var(--border)]">
            <h3 className="text-sm font-bold uppercase tracking-wider text-burgundy">Previzualizare Roster</h3>
            <p className="text-xs text-foreground/60 mt-1">
              Fă dublu-click pe orice celulă pentru a corecta datele în mod direct.
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
                                    {isRequired ? "Lipsă obligatoriu" : "-"}
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
            <h3 className="text-lg font-bold text-foreground">Adaugă Companie Nouă</h3>

            <div className="space-y-1">
              <label className="text-xs font-bold text-foreground/60 font-semibold">Nume Companie / Organizație</label>
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
