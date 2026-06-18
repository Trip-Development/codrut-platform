"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import * as XLSX from "xlsx";
import {
  createCompany,
  importCompanyRoster,
  sendParticipantInvitations,
  type CompanyParticipant,
  type CompanyProject,
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
  existingParticipants?: Pick<CompanyParticipant, "id" | "full_name" | "email">[];
  projects?: Pick<CompanyProject, "id" | "name" | "status">[];
  defaultProjectId?: string | null;
  requireProject?: boolean;
};

type DbField = "full_name" | "email" | "reports_to_name" | "position" | "location" | "pcm_profile" | "pcm_base" | "pcm_phase";
type FlowStepKey = "upload" | "review" | "import" | "access";
type FlowStepState = "complete" | "current" | "upcoming" | "error";
const MAPPING_FIELDS: DbField[] = ["full_name", "email", "reports_to_name", "position", "location"];
const PREVIEW_FIELDS: DbField[] = ["full_name", "email", "reports_to_name", "position", "location", "pcm_base", "pcm_phase"];

const FIELD_LABELS: Record<DbField, string> = {
  full_name: "Nume Complet (Obligatoriu)",
  email: "Adresă Email (Obligatoriu)",
  reports_to_name: "Raportează Către / Manager (Opțional)",
  position: "Poziție / Rol (Opțional)",
  location: "Locație (Opțional)",
  pcm_profile: "Profil PCM",
  pcm_base: "PCM Bază (din matrice)",
  pcm_phase: "PCM Fază (din matrice)",
};

const FIELD_ALIASES: Record<DbField, string[]> = {
  full_name: ["name", "nume", "full name", "nume complet", "participant", "client", "nume si prenume", "nume participant"],
  email: ["email", "e-mail", "mail", "adresa email", "adresa de email"],
  reports_to_name: ["reports to", "reports_to", "manager", "reports_to_name", "sefi", "boss", "raporteaza catre", "manager direct"],
  position: ["position", "role", "rol", "pozitie", "functie", "job title", "post", "titlu"],
  location: ["location", "locatie", "oras", "city", "site", "punct lucru"],
  pcm_profile: [],
  pcm_base: [],
  pcm_phase: [],
};

const PCM_TYPE_VALUES = [
  "ganditor",
  "perseverent",
  "promotor",
  "empatic",
  "imaginator",
  "rebel",
] as const;

const PCM_DISPLAY_BY_VALUE: Record<string, string> = {
  ganditor: "Gânditor",
  perseverent: "Perseverent",
  promotor: "Promotor",
  empatic: "Empatic",
  imaginator: "Imaginator",
  rebel: "Rebel",
};

const LEGEND_ROW_LABELS = new Set(["legend", "base", "base & phase", "base si phase", "base and phase", "phase", "stage"]);

function normalizeHeader(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[()]/g, "")
    .trim();
}

function buildRosterHeaders(headerRow: unknown[], rows: unknown[][]): string[] {
  const maxCols = Math.max(headerRow.length, ...rows.map((row) => row.length));
  const headers: string[] = [];
  let pcmMatrixColumnCount = 0;
  let afterPcmProfile = false;

  for (let colIdx = 0; colIdx < maxCols; colIdx += 1) {
    const rawHeader = String(headerRow[colIdx] ?? "").trim();
    if (rawHeader) {
      headers.push(rawHeader);
      afterPcmProfile = normalizeHeader(rawHeader) === "profil pcm";
      continue;
    }

    if (afterPcmProfile) {
      pcmMatrixColumnCount += 1;
      headers.push(`PCM ${pcmMatrixColumnCount}`);
    } else {
      headers.push(`Coloana ${colIdx + 1}`);
    }
  }

  return headers;
}

function isLegendOnlyRow(row: unknown[], headers: string[]): boolean {
  const nameIndex = headers.findIndex((header) => ["name", "nume", "nume complet"].includes(normalizeHeader(header)));
  const emailIndex = headers.findIndex((header) => ["email", "e-mail", "mail", "adresa email", "adresa de email"].includes(normalizeHeader(header)));
  const firstCell = normalizeHeader(String(row[0] ?? ""));
  const hasName = nameIndex >= 0 && String(row[nameIndex] ?? "").trim().length > 0;
  const hasEmail = emailIndex >= 0 && String(row[emailIndex] ?? "").trim().length > 0;

  if (firstCell && LEGEND_ROW_LABELS.has(firstCell)) return true;
  if (hasName || hasEmail) return false;

  return row.some((cell) => LEGEND_ROW_LABELS.has(normalizeHeader(String(cell ?? ""))));
}

function inferPcmFromMatrix(
  worksheet: XLSX.WorkSheet,
  headers: string[],
  row: unknown[],
  zeroBasedSheetRowIndex: number,
): { base: string; phase: string } {
  let base = "";
  let phase = "";
  const maxCols = Math.max(headers.length, row.length);
  for (let colIdx = 0; colIdx < maxCols; colIdx += 1) {
    const address = XLSX.utils.encode_cell({ r: zeroBasedSheetRowIndex, c: colIdx });
    const cell = worksheet[address] as (XLSX.CellObject & { s?: { fill?: { fgColor?: { rgb?: string }; patternType?: string } } }) | undefined;
    const rgb = cell?.s?.fill?.fgColor?.rgb?.replace(/^FF/i, "").toUpperCase();
    const normalizedCell = normalizeHeader(
      cell?.w ?? cell?.v?.toString() ?? row[colIdx]?.toString() ?? "",
    );
    const normalizedHeader = normalizeHeader(headers[colIdx] ?? "");
    const pcmKey =
      PCM_TYPE_VALUES.find((value) => normalizedCell.startsWith(value)) ??
      PCM_TYPE_VALUES.find((value) => normalizedHeader === value);
    if (!pcmKey) continue;
    const pcmLabel = PCM_DISPLAY_BY_VALUE[pcmKey];

    if (!rgb) continue;
    const isCyanBase = rgb.startsWith("00B0F0") || rgb.startsWith("00AEEF") || rgb.startsWith("00BFFF");
    const isGreenBoth = rgb.startsWith("92D050") || rgb.startsWith("A9D18E") || rgb.startsWith("70AD47");
    const isYellowPhase = rgb.startsWith("FFFF00") || rgb.startsWith("FFF200") || rgb.startsWith("FFD966");

    if (isGreenBoth) {
      base = pcmLabel;
      phase = pcmLabel;
    } else if (isCyanBase) {
      base = pcmLabel;
    } else if (isYellowPhase) {
      phase = pcmLabel;
    }
  }
  return { base, phase };
}

export function RosterImporter({
  companies,
  defaultCompanyId,
  lockCompany = false,
  existingParticipants = [],
  projects = [],
  defaultProjectId = null,
  requireProject = false,
}: RosterImporterProps) {
  const router = useRouter();
  const [companyId, setCompanyId] = useState(defaultCompanyId || companies[0]?.id || "");
  const [projectId, setProjectId] = useState(defaultProjectId ?? projects[0]?.id ?? "");
  const [allCompanies, setAllCompanies] = useState<CompanyOption[]>(companies);
  const [showAddCompanyModal, setShowAddCompanyModal] = useState(false);
  const [newCompanyName, setNewCompanyName] = useState("");
  const [isCreatingCompany, setIsCreatingCompany] = useState(false);

  useEffect(() => {
    if (defaultCompanyId) {
      setCompanyId(defaultCompanyId);
    }
  }, [defaultCompanyId]);

  useEffect(() => {
    if (defaultProjectId) {
      setProjectId(defaultProjectId);
    } else if (!projectId && projects[0]?.id) {
      setProjectId(projects[0].id);
    }
  }, [defaultProjectId, projectId, projects]);

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
        message: error instanceof Error ? error.message : "Compania nu a putut fi creată în sistem.",
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
    pcm_base: "",
    pcm_phase: "",
  });

  const [lastImportedParticipantIds, setLastImportedParticipantIds] = useState<string[]>([]);
  const [accessState, setAccessState] = useState<{
    status: "idle" | "sending" | "success" | "error";
    mode: ParticipantInvitationMode | null;
    message: string | null;
    results: RosterInviteResult[];
  }>({
    status: "idle",
    mode: null,
    message: null,
    results: [],
  });
  const [copiedParticipantId, setCopiedParticipantId] = useState<string | null>(null);

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
    setLastImportedParticipantIds([]);
    resetAccessState();
    setEditedCells({});
    setEditingCellId(null);

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target?.result as ArrayBuffer);
        const workbook = XLSX.read(data, { type: "array", cellStyles: true });
        const firstSheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[firstSheetName];

        // Read headers and rows as array of arrays
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const rawSheetData = XLSX.utils.sheet_to_json<any[]>(worksheet, { header: 1 });
        if (rawSheetData.length === 0) {
          setImportState({ status: "error", message: "Fișierul este gol sau invalid." });
          return;
        }

        let rawHeaders = buildRosterHeaders(rawSheetData[0], rawSheetData.slice(1));
        let dataRows = rawSheetData.slice(1);
        let firstDataSheetRowIndex = 1;
        const startsWithPcmTitle =
          rawHeaders.filter((header) => !header.startsWith("Coloana ")).length <= 1 && normalizeHeader(rawHeaders[0] ?? "") === "profil pcm";
        if (startsWithPcmTitle) {
          const possibleHeaders = buildRosterHeaders(rawSheetData[1] ?? [], rawSheetData.slice(2));
          const hasRosterHeader = possibleHeaders.some((header) =>
            ["email", "e-mail", "mail", "name", "nume"].includes(normalizeHeader(header)),
          );
          if (hasRosterHeader) {
            rawHeaders = possibleHeaders;
            dataRows = rawSheetData.slice(2);
            firstDataSheetRowIndex = 2;
          } else {
            rawHeaders = ["Name", "PCM 1", "PCM 2", "PCM 3", "PCM 4", "PCM 5", "PCM 6"];
            dataRows = rawSheetData.slice(1);
            firstDataSheetRowIndex = 1;
          }
        }

        // Convert rows to key-value objects
        const objects: Record<string, string>[] = [];
        for (let rowOffset = 0; rowOffset < dataRows.length; rowOffset += 1) {
          const row = dataRows[rowOffset];
          if (isLegendOnlyRow(row, rawHeaders)) {
            continue;
          }

          const obj: Record<string, string> = {};
          rawHeaders.forEach((header, colIdx) => {
            obj[header] = row[colIdx] !== undefined ? String(row[colIdx]).trim() : "";
          });
          const pcmFromMatrix = inferPcmFromMatrix(worksheet, rawHeaders, row, firstDataSheetRowIndex + rowOffset);
          if (pcmFromMatrix.base) obj["PCM Bază"] = pcmFromMatrix.base;
          if (pcmFromMatrix.phase) obj["PCM Fază"] = pcmFromMatrix.phase;
          // Only keep rows that have some content
          const hasContent = Object.values(obj).some((val) => val.length > 0);
          if (hasContent) {
            objects.push(obj);
          }
        }

        if (objects.length === 0) {
          setImportState({ status: "error", message: "Nu s-au găsit date valide sub rândul de antet." });
          return;
        }

        const derivedHeaders = Array.from(new Set([...rawHeaders, "PCM Bază", "PCM Fază"]));
        setHeaders(derivedHeaders);
        setRawRows(objects);

        // Auto-detect column mapping
        const detectedMappings: Record<DbField, string> = {
          full_name: "",
          email: "",
          reports_to_name: "",
          position: "",
          location: "",
          pcm_profile: "",
          pcm_base: "",
          pcm_phase: "",
        };

        MAPPING_FIELDS.forEach((field) => {
          const aliases = FIELD_ALIASES[field];
          const matchedHeader = derivedHeaders.find((header) =>
            aliases.some((alias) => {
              const normalizedHeader = normalizeHeader(header).replace(/[_/.-]+/g, " ");
              const normalizedAlias = normalizeHeader(alias).replace(/[_/.-]+/g, " ");
              return normalizedHeader === normalizedAlias || normalizedHeader.includes(normalizedAlias);
            })
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
        detectedMappings.pcm_base = "PCM Bază";
        detectedMappings.pcm_phase = "PCM Fază";

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
      pcm_base: getVal("pcm_base"),
      pcm_phase: getVal("pcm_phase"),
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
    const existingEmails = new Set(existingParticipants.map((participant) => participant.email.trim().toLowerCase()));
    const existingNames = new Set(existingParticipants.map((participant) => participant.full_name.trim().toLowerCase()));

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
        if (existingEmails.has(row.email.trim().toLowerCase())) {
          errors.push({
            rowIndex: idx,
            name,
            field: "email",
            error: "Există deja un participant cu acest email în companie.",
            type: "critical",
          });
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
      if (row.full_name && existingNames.has(row.full_name.trim().toLowerCase())) {
        errors.push({
          rowIndex: idx,
          name,
          field: "full_name",
          error: "Există deja un participant cu acest nume în companie. Verifică dacă este aceeași persoană.",
          type: "warning",
        });
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
      if (!row.pcm_base || !row.pcm_phase) {
        errors.push({
          rowIndex: idx,
          name,
          field: !row.pcm_base ? "pcm_base" : "pcm_phase",
          error: "PCM bază/fază este incomplet. Participantul poate completa chestionarul PCM ulterior.",
          type: "warning",
        });
      }
    });
    return errors;
  }, [existingParticipants, processedRows]);

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
  const projectRequired = requireProject;
  const selectedProject = projects.find((project) => project.id === projectId) ?? null;
  const canImportRows = !hasCriticalErrors && (!projectRequired || Boolean(selectedProject));
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
      label: "Salvează participanții",
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
      detail: "Din tabul Invitații",
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
    if (!companyId || processedRows.length === 0 || !canImportRows) return;

    setImportState({ status: "importing", message: "Se importă participanții..." });
    setLastImportedParticipantIds([]);
    resetAccessState();

    try {
      const importResult = await importCompanyRoster(
        companyId,
        processedRows.map((r) => ({
          Name: r.full_name,
          "Reports To": r.reports_to_name,
          Position: r.position,
          Location: r.location,
          email: r.email,
          "Profil PCM": "",
          "PCM Bază": r.pcm_base,
          "PCM Fază": r.pcm_phase,
        })),
        { projectId: selectedProject?.id ?? null },
      );
      setLastImportedParticipantIds(importResult.participants.map((participant) => participant.id));
      router.refresh();
      setImportState({
        status: "success",
        message: `Import reușit: ${importResult.total_imported} participanți salvați. Continuă în tabul Invitații pentru emailuri sau linkuri securizate.`,
      });
    } catch (error) {
      setImportState({
        status: "error",
        message: error instanceof Error ? error.message : "Importul listei de participanți a eșuat în sistem.",
      });
    }
  };

  const resetAccessState = () => {
    setAccessState({
      status: "idle",
      mode: null,
      message: null,
      results: [],
    });
    setCopiedParticipantId(null);
  };

  const handleSendAccess = async (mode: ParticipantInvitationMode) => {
    if (!companyId || lastImportedParticipantIds.length === 0) return;

    setAccessState({
      status: "sending",
      mode,
      message: mode === "email" ? "Se trimit invitațiile email..." : "Se generează linkurile securizate...",
      results: [],
    });
    setCopiedParticipantId(null);

    try {
      const result = await sendParticipantInvitations(companyId, {
        participantIds: lastImportedParticipantIds,
        projectId: selectedProject?.id ?? null,
        mode,
      });
      setAccessState({
        status: "success",
        mode,
        message:
          mode === "email"
            ? `${result.emails_sent}/${result.total} emailuri trimise. ${result.emails_failed} eșuate.`
            : `${result.links_generated}/${result.total} linkuri securizate generate.`,
        results: result.results,
      });
      router.refresh();
    } catch (error) {
      setAccessState({
        status: "error",
        mode,
        message: error instanceof Error ? error.message : "Accesul participanților nu a putut fi pregătit.",
        results: [],
      });
    }
  };

  const handleCopyAccessLink = async (result: RosterInviteResult) => {
    if (!result.invite_url || typeof navigator === "undefined") return;
    try {
      await navigator.clipboard.writeText(result.invite_url);
      setCopiedParticipantId(result.participant_id);
      setAccessState((current) => ({
        ...current,
        message: `Link securizat copiat pentru ${result.full_name}.`,
      }));
    } catch {
      setAccessState((current) => ({
        ...current,
        message: "Linkul nu a putut fi copiat automat. Copiază-l din tabul Invitații.",
      }));
    }
  };

  return (
    <div className="space-y-6">
      <ImportFlowStepper steps={flowSteps} />

      <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
        <div className="grid gap-0 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <div className="border-b border-[var(--border)] bg-background/55 p-5 lg:border-b-0 lg:border-r">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Import participanți</p>
            <h3 className="mt-1 text-lg font-semibold text-foreground">Salvează oamenii înainte de invitații</h3>
            <p className="mt-2 max-w-md text-sm leading-6 text-foreground/62">
              Importul creează lista de participanți în companie. După confirmare, tabul Invitații este singurul loc pentru emailuri, retrimiteri și linkuri securizate.
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

            {projects.length > 0 ? (
              <label className="block">
                <span className="text-sm font-semibold text-foreground">Proiect destinație</span>
                <select
                  value={projectId}
                  onChange={(event) => setProjectId(event.target.value)}
                  className="mt-2 min-h-11 w-full rounded-xl border border-[var(--border)] bg-background px-3.5 py-2 text-sm font-semibold text-foreground outline-none focus:border-burgundy/45 focus:ring-2 focus:ring-burgundy/10"
                >
                  <option value="" disabled>
                    Alege proiectul pentru import
                  </option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
                <span className="mt-2 block text-xs leading-5 text-foreground/52">
                  Invitațiile, linkurile și asignările se lucrează pe proiectul ales.
                </span>
              </label>
            ) : requireProject ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-3 text-sm leading-6 text-amber-900">
                Creează un proiect înainte de import ca invitațiile și rapoartele să fie corect încapsulate.
              </div>
            ) : null}

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
              Importul salvează doar participanții. Trimiterea emailurilor sau generarea linkurilor se face separat după confirmare.
            </p>
            <button
              type="button"
              disabled={!canImportRows}
              onClick={handleImport}
              className="tap-soft rounded-xl bg-burgundy px-5 py-2.5 text-xs font-bold text-white hover:bg-burgundy/90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Salvează participanții
            </button>
          </div>
        </section>
      )}

      {importState.status === "success" && lastImportedParticipantIds.length > 0 && (
        <section className="rounded-2xl border border-burgundy/20 bg-surface p-5 shadow-sm">
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,0.7fr)]">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Acces participanți</p>
              <h3 className="mt-1 text-base font-semibold text-foreground">Participanți salvați. Alege cum le dai acces.</h3>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-foreground/62">
                Am importat {lastImportedParticipantIds.length} participanți fără trimitere automată. Poți genera linkuri securizate pentru verificare manuală sau poți trimite invitații email doar către această listă importată acum.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={accessState.status === "sending"}
                  onClick={() => handleSendAccess("secure_links")}
                  className="tap-soft rounded-xl bg-burgundy px-4 py-2.5 text-sm font-bold text-white hover:bg-burgundy-700 disabled:cursor-not-allowed disabled:opacity-45"
                >
                  {accessState.status === "sending" && accessState.mode === "secure_links"
                    ? "Se generează..."
                    : "Generează linkuri securizate"}
                </button>
                <button
                  type="button"
                  disabled={accessState.status === "sending"}
                  onClick={() => handleSendAccess("email")}
                  className="tap-soft rounded-xl border border-[var(--border)] bg-background px-4 py-2.5 text-sm font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy disabled:cursor-not-allowed disabled:opacity-45"
                >
                  {accessState.status === "sending" && accessState.mode === "email"
                    ? "Se trimit..."
                    : "Trimite invitații email"}
                </button>
              </div>
            </div>

            <div className="rounded-2xl border border-[var(--border)] bg-background p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-foreground">Status acces</p>
                  <p className="mt-1 text-xs leading-5 text-foreground/56">
                    Statusul complet, retrimiterile și istoricul rămân în tabul Invitații.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => router.push(selectedProject ? `/trainer/projects/${selectedProject.id}/invitations` : `/trainer/companies/${companyId}`)}
                  className="tap-soft shrink-0 rounded-lg border border-[var(--border)] bg-surface px-3 py-1.5 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy"
                >
                  Invitații
                </button>
              </div>

              {accessState.message ? (
                <p
                  className={`mt-3 rounded-xl border px-3 py-2 text-xs font-semibold ${
                    accessState.status === "error"
                      ? "border-red-200 bg-red-50 text-red-800"
                      : "border-success/25 bg-success/10 text-success-ink"
                  }`}
                >
                  {accessState.message}
                </p>
              ) : (
                <p className="mt-3 rounded-xl border border-[var(--border)] bg-surface-muted/45 px-3 py-2 text-xs font-semibold text-foreground/56">
                  Nicio livrare pornită încă.
                </p>
              )}

              {accessState.results.length > 0 ? (
                <div className="mt-3 max-h-52 space-y-2 overflow-y-auto pr-1">
                  {accessState.results.map((result) => (
                    <div
                      key={result.participant_id}
                      className="rounded-xl border border-[var(--border)] bg-surface px-3 py-2"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-foreground">{result.full_name}</p>
                          <p className="truncate text-xs text-foreground/50">{result.email}</p>
                          <p
                            className={`mt-1 text-xs font-semibold ${
                              result.error ? "text-red-700" : "text-success-ink"
                            }`}
                          >
                            {result.error
                              ? result.error
                              : result.email_sent
                                ? "Email trimis"
                                : "Link securizat pregătit"}
                          </p>
                        </div>
                        {result.invite_url ? (
                          <button
                            type="button"
                            onClick={() => handleCopyAccessLink(result)}
                            className="tap-soft shrink-0 rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy"
                          >
                            {copiedParticipantId === result.participant_id ? "Copiat" : "Copiază"}
                          </button>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </section>
      )}

      {/* Participant column mapping */}
      {headers.length > 0 && importState.status === "ready" && (
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm space-y-4">
          <div>
            <h3 className="text-base font-semibold text-foreground">Mapare coloane</h3>
            <p className="mt-1 text-sm leading-6 text-foreground/60">
              Asociază coloanele din fișier cu structura platformei. Detectarea automată poate fi ajustată manual.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {MAPPING_FIELDS.map((field) => (
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
            <h3 className="text-base font-semibold text-foreground">Previzualizare participanți</h3>
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
                  <th className="px-5 py-3">PCM bază</th>
                  <th className="px-5 py-3">PCM fază</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {processedRows.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-background/40">
                    <td className="px-5 py-3 font-semibold text-foreground/45 text-center">{rIdx + 1}</td>

                    {/* Render fields with double click inline editing support */}
                    {PREVIEW_FIELDS.map((field) => {
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40-sm p-4">
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
