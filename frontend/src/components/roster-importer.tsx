"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  createCompany,
  importCompanyRoster,
  sendParticipantInvitations,
  type CompanyParticipant,
  type CompanyProject,
  type ParticipantInvitationMode,
  type RosterInviteResult,
} from "@/api/companies";
import { buildManagerReferenceKeySet, managerReferenceKey, normalizeReportsToName } from "@/api/roster-format";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { ModalLayer } from "@/components/ui/modal-layer";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldGroup, FieldLabel, FieldTitle } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { SelectControl } from "@/components/ui/select-control";
import { cn } from "@/utils/cn";
import { readSpreadsheetFile, type SpreadsheetCell } from "@/utils/spreadsheet-import";

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
  compact?: boolean;
};

type DbField = "full_name" | "email" | "reports_to_name" | "position" | "location" | "role_group" | "pcm_profile" | "pcm_base" | "pcm_phase";
type FlowStepKey = "upload" | "review" | "import" | "access";
type FlowStepState = "complete" | "current" | "upcoming" | "error";
const MAPPING_FIELDS: DbField[] = ["full_name", "email", "reports_to_name", "position", "location"];
const PREVIEW_FIELDS: DbField[] = ["full_name", "email", "reports_to_name", "position", "location", "role_group", "pcm_base", "pcm_phase"];
const MANUAL_HEADERS = ["Name", "email", "Reports To", "Position", "Location"];
const MANUAL_MAPPINGS: Record<DbField, string> = {
  full_name: "Name",
  email: "email",
  reports_to_name: "Reports To",
  position: "Position",
  location: "Location",
  role_group: "",
  pcm_profile: "",
  pcm_base: "",
  pcm_phase: "",
};

const FIELD_LABELS: Record<DbField, string> = {
  full_name: "Nume Complet (Obligatoriu)",
  email: "Adresă Email (opțională)",
  reports_to_name: "Raportează Către / Manager (Opțional)",
  position: "Poziție / Rol (Opțional)",
  location: "Locație (Opțional)",
  role_group: "Leadership",
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
  role_group: [],
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
const importerShellClass =
  "overflow-hidden rounded-lg border border-border bg-surface text-foreground shadow-[0_1px_0_rgba(24,24,27,0.04)]";
const importerMutedClass = "border-border bg-muted/75";
const compactInputClass =
  "h-9 rounded-lg border-border bg-surface px-3 text-xs font-semibold";
const warningPanelClass = "rounded-lg status-warning";

function normalizeHeader(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[()]/g, "")
    .trim();
}

function normalizeRosterRole(value: string | null | undefined): "leadership" | "member" | null {
  const normalized = (value ?? "").trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (!normalized) return null;
  if (["leadership", "leader", "manager", "management"].includes(normalized)) return "leadership";
  if (["member", "team", "team_member", "non_leadership", "not_leadership"].includes(normalized)) return "member";
  return null;
}

function inferredRosterRole(
  row: Record<DbField, string>,
  managerNames: Set<string>,
): "leadership" | "member" {
  const explicitRole = normalizeRosterRole(row.role_group);
  if (explicitRole) return explicitRole;
  if (!row.reports_to_name) return "leadership";
  if (managerNames.has(managerReferenceKey(row.full_name))) return "leadership";
  return "member";
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
  cells: SpreadsheetCell[][],
  headers: string[],
  row: unknown[],
  zeroBasedSheetRowIndex: number,
): { base: string; phase: string } {
  let base = "";
  let phase = "";
  const maxCols = Math.max(headers.length, row.length);
  for (let colIdx = 0; colIdx < maxCols; colIdx += 1) {
    const cell = cells[zeroBasedSheetRowIndex]?.[colIdx];
    const rgb = cell?.rgb;
    const normalizedCell = normalizeHeader(
      cell?.text ?? row[colIdx]?.toString() ?? "",
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
  compact = false,
}: RosterImporterProps) {
  const router = useRouter();
  const [companyId, setCompanyId] = useState(defaultCompanyId || companies[0]?.id || "");
  const [projectId, setProjectId] = useState(defaultProjectId ?? projects[0]?.id ?? "");
  const [allCompanies, setAllCompanies] = useState<CompanyOption[]>(companies);
  const [showAddCompanyModal, setShowAddCompanyModal] = useState(false);
  const [newCompanyName, setNewCompanyName] = useState("");
  const [isCreatingCompany, setIsCreatingCompany] = useState(false);
  const companyCreatingRef = useRef(false);
  const fileProcessingRef = useRef(false);
  const rosterImportingRef = useRef(false);
  const accessSendingRef = useRef(false);
  const copyingAccessLinkIdsRef = useRef<Set<string>>(new Set());
  const companySelectId = useId();
  const projectSelectId = useId();
  const rosterFileInputId = useId();
  const newCompanyNameInputId = useId();

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
    if (companyCreatingRef.current) return;
    if (!newCompanyName.trim()) return;

    companyCreatingRef.current = true;
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
      companyCreatingRef.current = false;
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
    role_group: "",
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
  const [copyingParticipantId, setCopyingParticipantId] = useState<string | null>(null);

  const [importState, setImportState] = useState<{
    status: "idle" | "ready" | "importing" | "success" | "error";
    message: string;
  }>({
    status: "idle",
    message: "Alegeți un fișier CSV sau Excel pentru a începe importul.",
  });
  const [importOperationMode, setImportOperationMode] = useState<"file" | "save" | null>(null);

  // State for manual edits made in the preview
  const [editedCells, setEditedCells] = useState<Record<string, Record<string, string>>>({});
  const [editingCellId, setEditingCellId] = useState<{ rowIndex: number; field: DbField } | null>(null);

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (fileProcessingRef.current || rosterImportingRef.current) {
      event.target.value = "";
      return;
    }

    fileProcessingRef.current = true;
    setImportOperationMode("file");
    setImportState({ status: "importing", message: "Citim fișierul" });
    setLastImportedParticipantIds([]);
    resetAccessState();
    setEditedCells({});
    setEditingCellId(null);

    try {
      const { rows: rawSheetData, cells } = await readSpreadsheetFile(file);
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
          const pcmFromMatrix = inferPcmFromMatrix(
            cells,
            rawHeaders,
            row,
            firstDataSheetRowIndex + rowOffset,
          );
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
          role_group: "",
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
    } finally {
      fileProcessingRef.current = false;
      setImportOperationMode(null);
      event.target.value = "";
    }
  }

  // Update a single column mapping dropdown
  const handleMappingChange = (field: DbField, column: string) => {
    setMappings((prev) => ({ ...prev, [field]: column }));
  };

  const handleAddManualParticipant = () => {
    if (fileProcessingRef.current || rosterImportingRef.current) return;

    const nextIndex = rawRows.length;
    const emptyRow = Object.fromEntries(MANUAL_HEADERS.map((header) => [header, ""])) as Record<string, string>;

    setHeaders((current) => (current.length > 0 ? Array.from(new Set([...current, ...MANUAL_HEADERS])) : MANUAL_HEADERS));
    setMappings((current) => ({
      ...current,
      ...Object.fromEntries(
        Object.entries(MANUAL_MAPPINGS).map(([field, manualHeader]) => [
          field,
          current[field as DbField] || manualHeader,
        ]),
      ) as Record<DbField, string>,
    }));
    setRawRows((current) => [...current, emptyRow]);
    setEditingCellId({ rowIndex: nextIndex, field: "full_name" });
    setLastImportedParticipantIds([]);
    resetAccessState();
    setImportState({
      status: "ready",
      message: "Completează participantul manual în tabel, apoi salvează participanții.",
    });
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
      role_group: normalizeRosterRole(getVal("role_group")) ?? "",
      pcm_profile: getVal("pcm_profile"),
      pcm_base: getVal("pcm_base"),
      pcm_phase: getVal("pcm_phase"),
    };
  }, [editedCells, mappings]);

  // Build full preview lists and validation errors
  const processedRows = useMemo(() => {
    return rawRows.map((rawRow, idx) => getNormalizedRow(rawRow, idx));
  }, [rawRows, getNormalizedRow]);
  const referencedManagerNameKeys = useMemo(
    () => buildManagerReferenceKeySet(processedRows.map((row) => row.reports_to_name)),
    [processedRows],
  );

  const validationErrors = useMemo(() => {
    const errors: { rowIndex: number; name: string; field: DbField; error: string; type: "critical" | "warning" }[] = [];
    
    const emailsInFile = new Map<string, number[]>();
    const namesInFile = buildManagerReferenceKeySet(processedRows.map((row) => row.full_name));
    const existingEmails = new Set(
      existingParticipants
        .map((participant) => participant.email?.trim().toLowerCase())
        .filter((email): email is string => Boolean(email)),
    );
    const existingNames = new Set(existingParticipants.map((participant) => participant.full_name.trim().toLowerCase()));

    processedRows.forEach((row, idx) => {
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
        errors.push({
          rowIndex: idx,
          name,
          field: "email",
          error: "Email lipsă. Rândul va fi salvat fără invitații email până completezi adresa.",
          type: "warning",
        });
      } else {
        if (!row.email.includes("@")) {
          errors.push({
            rowIndex: idx,
            name,
            field: "email",
            error: "Format email invalid. Rândul va fi salvat, dar invitațiile email vor rămâne blocate.",
            type: "warning",
          });
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
        const mgrKey = managerReferenceKey(row.reports_to_name);
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
  const isProjectFixed = Boolean(defaultProjectId) && projects.length === 1 && projects[0]?.id === defaultProjectId;
  const canImportRows = !hasCriticalErrors && (!projectRequired || Boolean(selectedProject));
  const isRosterBusy = importState.status === "importing";
  const isFileProcessing = isRosterBusy && importOperationMode === "file";
  const isSavingRoster = isRosterBusy && importOperationMode === "save";
  const isAccessSending = accessState.status === "sending";
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
          [field]: field === "reports_to_name"
            ? normalizeReportsToName(value)
            : field === "role_group"
              ? normalizeRosterRole(value) ?? ""
              : value.trim(),
        },
      };
    });
    setEditingCellId(null);
  };

  const handleImport = async () => {
    if (rosterImportingRef.current) return;
    if (!companyId || processedRows.length === 0 || !canImportRows) return;

    rosterImportingRef.current = true;
    setImportOperationMode("save");
    setImportState({ status: "importing", message: "Importăm participanții" });
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
          "Role Group": r.role_group,
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
    } finally {
      rosterImportingRef.current = false;
      setImportOperationMode(null);
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
    setCopyingParticipantId(null);
    copyingAccessLinkIdsRef.current.clear();
  };

  const handleSendAccess = async (mode: ParticipantInvitationMode) => {
    if (accessSendingRef.current) return;
    if (!companyId || lastImportedParticipantIds.length === 0) return;

    accessSendingRef.current = true;
    setAccessState({
      status: "sending",
      mode,
      message: mode === "email" ? "Trimitem invitațiile email" : "Generăm linkurile securizate",
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
    } finally {
      accessSendingRef.current = false;
    }
  };

  const handleCopyAccessLink = async (result: RosterInviteResult) => {
    if (!result.invite_url || typeof navigator === "undefined") return;
    if (copyingAccessLinkIdsRef.current.has(result.participant_id)) return;

    copyingAccessLinkIdsRef.current.add(result.participant_id);
    setCopyingParticipantId(result.participant_id);
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
    } finally {
      copyingAccessLinkIdsRef.current.delete(result.participant_id);
      setCopyingParticipantId((current) => (current === result.participant_id ? null : current));
    }
  };

  const activeImportFeedback =
    importState.status === "importing"
      ? importOperationMode === "file"
        ? {
            title: "Citim fișierul",
            detail: "Extragem coloanele, rândurile și marcajele PCM înainte de validarea listei.",
          }
        : {
            title: "Salvăm participanții",
            detail: "Trimitem lista validată către companie și legăm participanții de proiectul selectat.",
          }
      : null;

  const activeAccessFeedback =
    accessState.status === "sending"
      ? accessState.mode === "email"
        ? {
            title: "Trimitem invitațiile",
            detail: "Pregătim emailurile doar pentru participanții salvați în acest import.",
          }
        : {
            title: "Generăm linkurile",
            detail: "Creăm acces securizat pentru participanții importați acum.",
          }
      : null;

  return (
    <div className="flex flex-col gap-5">
      {!compact ? <ImportFlowStepper steps={flowSteps} /> : null}

      <section className={importerShellClass}>
        {compact ? (
          <div className={cn("border-b px-5 py-4", importerMutedClass)}>
            <p className="text-sm font-semibold text-foreground">Import participanți</p>
          </div>
        ) : null}

        <div className={compact ? "" : "grid gap-0 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]"}>
          {!compact ? (
            <div className={cn("border-b p-5 lg:border-b-0 lg:border-r", importerMutedClass)}>
              <h3 className="text-lg font-semibold text-foreground">Import roster</h3>
              <p className="mt-2 inline-flex rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-muted-foreground">
                Fără trimitere automată la import
              </p>
            </div>
          ) : null}

          <div className="grid gap-4 p-5 md:grid-cols-2">
            <Field data-disabled={isRosterBusy ? true : undefined}>
              <div className="flex items-center justify-between">
                <FieldLabel htmlFor={lockCompany ? undefined : companySelectId}>
                  Companie destinație
                </FieldLabel>
                {!lockCompany && (
                  <Button
                    type="button"
                    onClick={() => setShowAddCompanyModal(true)}
                    variant="ghost"
                    size="xs"
                    disabled={isRosterBusy}
                    className="text-burgundy hover:bg-burgundy/10 hover:text-burgundy"
                  >
                    Companie nouă
                  </Button>
                )}
              </div>
              {lockCompany ? (
                <div className="mt-2 rounded-lg border border-border bg-surface px-3.5 py-3 text-sm font-semibold text-foreground">
                  {selectedCompanyName}
                </div>
              ) : (
                <SelectControl
                  id={companySelectId}
                  label="Companie destinație"
                  value={companyId}
                  disabled={isRosterBusy}
                  onChange={(e) => setCompanyId(e.target.value)}
                >
                  {allCompanies.map((company) => (
                    <option key={company.id} value={company.id}>
                      {company.name}
                    </option>
                  ))}
                </SelectControl>
              )}
            </Field>

            {isProjectFixed && selectedProject ? (
              <div className="rounded-lg border border-border bg-surface px-3.5 py-3">
                <FieldTitle>Proiect</FieldTitle>
                <p className="mt-2 text-sm font-bold text-foreground">{selectedProject.name}</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  Participanții importați sunt legați automat de acest proiect. Invitațiile se trimit separat din tabul Invitații.
                </p>
              </div>
            ) : projects.length > 0 ? (
              <Field data-disabled={isRosterBusy ? true : undefined}>
                <FieldLabel htmlFor={projectSelectId}>Proiect destinație</FieldLabel>
                <SelectControl
                  id={projectSelectId}
                  label="Proiect destinație"
                  value={projectId}
                  disabled={isRosterBusy}
                  onChange={(event) => setProjectId(event.target.value)}
                >
                  <option value="" disabled>
                    Alege proiectul pentru import
                  </option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </SelectControl>
                <FieldDescription>
                  Invitațiile, linkurile și asignările se lucrează pe proiectul ales.
                </FieldDescription>
              </Field>
            ) : requireProject ? (
              <div className={cn(warningPanelClass, "px-3.5 py-3 text-sm font-semibold leading-6")}>
                Creează un proiect înainte de import ca invitațiile și rapoartele să fie corect încapsulate.
              </div>
            ) : null}

            <Field data-disabled={isRosterBusy ? true : undefined}>
              <FieldLabel htmlFor={rosterFileInputId}>Participanți</FieldLabel>
              <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                <Input
                  id={rosterFileInputId}
                  type="file"
                  accept=".csv,.xlsx"
                  onChange={handleFileChange}
                  disabled={isRosterBusy}
                  className="min-w-0 flex-1 rounded-lg border border-burgundy/35 bg-surface px-3 py-2 text-sm font-semibold text-foreground file:mr-3 file:rounded-md file:border-0 file:bg-burgundy file:px-3.5 file:py-2 file:text-xs file:font-bold file:text-white hover:border-burgundy/60"
                />
                <Button
                  type="button"
                  onClick={handleAddManualParticipant}
                  variant="outline"
                  size="sm"
                  disabled={isRosterBusy}
                  className="border-border bg-surface text-foreground hover:border-burgundy/45 hover:text-burgundy"
                >
                  {isFileProcessing ? "Se citește fișierul" : "Participant manual"}
                </Button>
              </div>
              <FieldDescription>Excel (.xlsx), CSV (.csv) sau introducere manuală</FieldDescription>
            </Field>
          </div>
        </div>

        {importState.status === "idle" && (
          <div className="border-t border-border bg-muted/75 px-5 py-5 text-center text-muted-foreground">
            <p className="text-sm font-semibold">Aștept fișierul de import.</p>
            <p className="mt-1 text-xs">Acceptă Excel (.xlsx) și CSV (.csv).</p>
          </div>
        )}

        {activeImportFeedback ? (
          <div className="border-t border-border bg-muted/75 px-5 py-4">
            <OperationFeedback
              title={activeImportFeedback.title}
              detail={activeImportFeedback.detail}
            />
          </div>
        ) : null}

        {importState.status !== "idle" && !activeImportFeedback && (
          <div className="flex flex-wrap items-center gap-3 border-t border-border bg-muted/75 px-5 py-3">
            <StatusDot tone={importState.status} />
            <p className="text-sm font-semibold text-muted-foreground">
              {importState.message}
            </p>
          </div>
        )}
      </section>

      {processedRows.length > 0 && importState.status === "ready" && (
        <section className="rounded-lg border border-border bg-surface p-5 shadow-[0_1px_0_rgba(24,24,27,0.04)]">
          <div className="grid gap-3 sm:grid-cols-4">
            <RosterMetric label="Rânduri citite" value={processedRows.length} />
            <RosterMetric label="Valide pentru import" value={validRowCount} tone={criticalErrorCount > 0 ? "warning" : "success"} />
            <RosterMetric label="Erori critice" value={criticalErrorCount} tone={criticalErrorCount > 0 ? "danger" : "neutral"} />
            <RosterMetric label="Atenționări" value={warningCount} tone={warningCount > 0 ? "warning" : "neutral"} />
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
            <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
              Importul salvează doar participanții. Trimiterea emailurilor sau generarea linkurilor se face separat după confirmare.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                onClick={handleAddManualParticipant}
                variant="outline"
                size="sm"
                disabled={isRosterBusy}
                className="border-border bg-surface text-foreground hover:border-burgundy/45 hover:text-burgundy"
              >
                Participant manual
              </Button>
              <Button
                type="button"
                disabled={!canImportRows || isSavingRoster}
                onClick={handleImport}
                size="sm"
              >
                {isSavingRoster ? "Salvăm participanții" : "Salvează participanții"}
              </Button>
            </div>
          </div>
        </section>
      )}

      {importState.status === "success" && lastImportedParticipantIds.length > 0 && (
        <section className="rounded-lg border border-burgundy/20 bg-surface p-5 shadow-[0_1px_0_rgba(24,24,27,0.04)]">
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,0.7fr)]">
            <div className="min-w-0">
              <h3 className="text-base font-semibold text-foreground">Participanți salvați</h3>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
                Am importat {lastImportedParticipantIds.length} participanți fără trimitere automată. Poți genera linkuri securizate pentru verificare manuală sau poți trimite invitații email doar către această listă importată acum.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button
                  type="button"
                  disabled={isAccessSending}
                  onClick={() => handleSendAccess("secure_links")}
                >
                  {isAccessSending && accessState.mode === "secure_links"
                    ? "Generăm linkurile"
                    : "Generează linkuri securizate"}
                </Button>
                <Button
                  type="button"
                  disabled={isAccessSending}
                  onClick={() => handleSendAccess("email")}
                  variant="outline"
                  className="border-border bg-surface text-foreground hover:border-burgundy/45 hover:text-burgundy"
                >
                  {isAccessSending && accessState.mode === "email"
                    ? "Trimitem invitațiile"
                    : "Trimite invitații email"}
                </Button>
              </div>
              {activeAccessFeedback ? (
                <OperationFeedback
                  title={activeAccessFeedback.title}
                  detail={activeAccessFeedback.detail}
                  className="mt-4"
                />
              ) : null}
            </div>

            <div className="rounded-lg border border-border bg-muted/75 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-foreground">Status acces</p>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    Statusul complet, retrimiterile și istoricul rămân în tabul Invitații.
                  </p>
                </div>
                <Button
                  type="button"
                  onClick={() => router.push(selectedProject ? `/trainer/projects/${selectedProject.id}/invitations` : `/trainer/companies/${companyId}/invitations`)}
                  variant="outline"
                  size="xs"
                  className="shrink-0 border-border bg-surface text-foreground hover:border-burgundy/45 hover:text-burgundy"
                >
                  Invitații
                </Button>
              </div>

              {accessState.message && !activeAccessFeedback ? (
                <InlineFeedback
                  tone={accessState.status === "error" ? "danger" : "neutral"}
                  className={cn("mt-3 px-3 py-2", accessState.status === "success" ? "status-success" : "")}
                  descriptionClassName="text-xs leading-5"
                >
                  {accessState.message}
                </InlineFeedback>
              ) : (
                <p className="mt-3 rounded-lg border border-border bg-surface px-3 py-2 text-xs font-semibold text-muted-foreground">
                  Nicio livrare pornită încă.
                </p>
              )}

              {accessState.results.length > 0 ? (
                <div className="mt-3 flex max-h-52 flex-col gap-2 overflow-y-auto pr-1">
                  {accessState.results.map((result) => (
                    <div
                      key={result.participant_id}
                      className="rounded-lg border border-border bg-surface px-3 py-2"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-foreground">{result.full_name}</p>
                          <p className="truncate text-xs text-muted-foreground">{result.email}</p>
                          <p
                            className={cn(
                              "mt-1 text-xs font-semibold",
                              result.error ? "text-destructive" : "text-success-ink",
                            )}
                          >
                            {result.error
                              ? result.error
                              : result.email_sent
                                ? "Email trimis"
                                : "Link securizat pregătit"}
                          </p>
                        </div>
                        {result.invite_url ? (
                          <Button
                            type="button"
                            onClick={() => handleCopyAccessLink(result)}
                            variant="outline"
                            size="xs"
                            disabled={copyingParticipantId === result.participant_id}
                            className="shrink-0 border-border bg-surface text-foreground hover:border-burgundy/45 hover:text-burgundy"
                          >
                            {copyingParticipantId === result.participant_id
                              ? "Copiem"
                              : copiedParticipantId === result.participant_id
                                ? "Copiat"
                                : "Copiază"}
                          </Button>
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
        <section className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-5 shadow-[0_1px_0_rgba(24,24,27,0.04)]">
          <div>
            <h3 className="text-base font-semibold text-foreground">Mapare coloane</h3>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              Asociază coloanele din fișier cu structura platformei. Detectarea automată poate fi ajustată manual.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {MAPPING_FIELDS.map((field) => (
              <div key={field} className="block rounded-lg border border-border bg-muted/75 p-3 transition-colors hover:border-burgundy/25 hover:bg-surface">
                <span className="text-xs font-bold text-muted-foreground">{FIELD_LABELS[field]}</span>
                <SelectControl
                  label={`Coloană pentru ${FIELD_LABELS[field]}`}
                  wrapperClassName="mt-2"
                  value={mappings[field]}
                  disabled={isRosterBusy}
                  onChange={(e) => handleMappingChange(field, e.target.value)}
                >
                  <option value="">Ignoră / Fără</option>
                  {headers.map((h) => (
                    <option key={h} value={h}>
                      {h}
                    </option>
                  ))}
                </SelectControl>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Warnings & Errors Panel */}
      {validationErrors.length > 0 && importState.status === "ready" && (
        <div className="flex flex-col gap-3">
          {validationErrors.some((e) => e.type === "critical") && (
            <InlineFeedback tone="danger" className="p-5" descriptionClassName="flex flex-col gap-3 text-xs leading-5">
              <h3 className="text-base font-semibold">
                Erori critice ({validationErrors.filter((e) => e.type === "critical").length})
              </h3>
              <p>
                Problemele de mai jos blochează importul. Corectează-le direct în tabel:
              </p>
              <div className="flex max-h-28 flex-col gap-1.5 overflow-y-auto">
                {validationErrors
                  .filter((e) => e.type === "critical")
                  .map((err, i) => (
                    <p key={i} className="text-xs font-semibold">
                      - <strong>{err.name}</strong>: {err.error} (Câmpul: <i>{FIELD_LABELS[err.field]}</i>)
                    </p>
                  ))}
              </div>
            </InlineFeedback>
          )}

          {validationErrors.some((e) => e.type === "warning") && (
            <section className={cn(warningPanelClass, "flex flex-col gap-3 p-5")}>
              <h3 className="text-base font-semibold">
                Atenționări ({validationErrors.filter((e) => e.type === "warning").length})
              </h3>
              <p className="text-xs">
                Nu blochează importul, dar pot afecta generarea automată a evaluărilor:
              </p>
              <div className="flex max-h-28 flex-col gap-1.5 overflow-y-auto">
                {validationErrors
                  .filter((e) => e.type === "warning")
                  .map((err, i) => (
                    <p key={i} className="text-xs font-semibold text-warning-ink">
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
        <section className="overflow-hidden rounded-lg border border-border bg-surface shadow-[0_1px_0_rgba(24,24,27,0.04)]">
          <div className="border-b border-border px-5 py-4">
            <h3 className="text-base font-semibold text-foreground">Previzualizare participanți</h3>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              Dublu-click pe o celulă pentru corecții rapide înainte de salvare.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-[980px] text-left text-xs">
              <thead className="border-b border-border bg-muted text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
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
              <tbody className="divide-y divide-border">
                {processedRows.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-muted/70">
                    <td className="px-5 py-3 text-center font-semibold text-muted-foreground">{rIdx + 1}</td>

                    {/* Render fields with double click inline editing support */}
                    {PREVIEW_FIELDS.map((field) => {
                      if (field === "role_group") {
                        const effectiveRole = inferredRosterRole(row, referencedManagerNameKeys);
                        const explicitRole = normalizeRosterRole(row.role_group);
                        return (
                          <td key={field} className="px-5 py-3">
                            <button
                              type="button"
                              onClick={() => handleCellEditSave(rIdx, field, effectiveRole === "leadership" ? "member" : "leadership")}
                              className={`tap-soft rounded-full border px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider transition ${
                                effectiveRole === "leadership"
                                  ? "border-emerald-500/35 bg-emerald-500/12 text-emerald-700"
                                  : "border-[var(--border)] bg-background text-foreground/55 hover:border-burgundy/35 hover:text-burgundy"
                              }`}
                              aria-pressed={effectiveRole === "leadership"}
                              aria-label={`Setează ${row.full_name || `rândul ${rIdx + 1}`} ca ${effectiveRole === "leadership" ? "membru" : "leadership"}`}
                            >
                              {effectiveRole === "leadership" ? "Leadership" : "Membru"}
                            </button>
                            <span className="mt-1 block text-[10px] font-medium text-foreground/42">
                              {explicitRole ? "setat manual" : "inferat automat"}
                            </span>
                          </td>
                        );
                      }
                      const isEditing = editingCellId?.rowIndex === rIdx && editingCellId?.field === field;
                      const hasError = validationErrors.some((e) => e.rowIndex === rIdx && e.field === field);
                      const isRequired = field === "full_name" || field === "email";

                      return (
                        <td
                          key={field}
                          className={cn(
                            "px-5 py-3 font-medium transition-colors",
                            hasError
                              ? "border border-destructive/25 bg-destructive/10 text-destructive"
                              : "text-foreground",
                          )}
                          onDoubleClick={() => setEditingCellId({ rowIndex: rIdx, field })}
                        >
                          {isEditing ? (
                            <Input
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
                              className={compactInputClass}
                            />
                          ) : (
                            <div className="flex items-center justify-between group cursor-pointer">
                              <span>
                                {row[field] ? (
                                  row[field]
                                ) : (
                                  <span className="text-muted-foreground italic">
                                    {isRequired ? "Lipsă obligatoriu" : "Fără date"}
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
        <ModalLayer
          labelledBy="roster-add-company-title"
          onClose={() => {
            if (!isCreatingCompany) {
              setShowAddCompanyModal(false);
              setNewCompanyName("");
            }
          }}
          closeOnBackdrop={!isCreatingCompany}
          panelClassName="max-w-md"
        >
          <form
            onSubmit={handleAddCompany}
            className="flex flex-col gap-4"
            aria-busy={isCreatingCompany}
          >
            <h3 id="roster-add-company-title" className="text-lg font-semibold text-foreground">Adaugă companie nouă</h3>

            <FieldGroup className="gap-3">
              <Field data-disabled={isCreatingCompany ? true : undefined}>
                <FieldLabel htmlFor={newCompanyNameInputId}>Nume companie / organizație</FieldLabel>
                <Input
                  id={newCompanyNameInputId}
                  type="text"
                  required
                  value={newCompanyName}
                  onChange={(event) => setNewCompanyName(event.target.value)}
                  disabled={isCreatingCompany}
                  placeholder="Ex. Atlas Mobility SRL"
                />
              </Field>
            </FieldGroup>

            <div className="flex justify-end gap-2 border-t border-border pt-2">
              <Button
                type="button"
                onClick={() => {
                  setShowAddCompanyModal(false);
                  setNewCompanyName("");
                }}
                variant="outline"
                size="sm"
                disabled={isCreatingCompany}
                className="border-border bg-surface text-foreground hover:bg-muted/70"
              >
                Anulează
              </Button>
              <Button
                type="submit"
                disabled={isCreatingCompany}
                size="sm"
              >
                {isCreatingCompany ? "Creăm compania" : "Adaugă"}
              </Button>
            </div>
            {isCreatingCompany ? (
              <OperationFeedback
                title="Creăm compania"
                detail={`Pregătim spațiul pentru ${newCompanyName.trim() || "compania nouă"}.`}
              />
            ) : null}
          </form>
        </ModalLayer>
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
    <section className="rounded-lg border border-border bg-surface p-3 shadow-[0_1px_0_rgba(24,24,27,0.04)]">
      <div className="grid gap-1.5 md:grid-cols-4">
        {steps.map((step, index) => (
          <div
            key={step.key}
            className={[
              "group flex items-start gap-3 rounded-lg px-3 py-3 transition-colors",
              step.state === "current"
                ? "bg-burgundy/10 text-burgundy"
                : step.state === "complete"
                  ? "text-success-ink hover:bg-success/10"
                : step.state === "error"
                  ? "text-destructive hover:bg-destructive/10"
                    : "text-muted-foreground hover:bg-muted/70",
            ].join(" ")}
          >
            <span
              className={[
                "mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md border text-xs font-semibold transition-colors",
                step.state === "current"
                  ? "border-burgundy bg-burgundy text-white"
                  : step.state === "complete"
                    ? "status-success"
                    : step.state === "error"
                      ? "border-destructive/25 bg-destructive/10 text-destructive"
                      : "border-border bg-surface text-muted-foreground group-hover:border-burgundy/25",
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
                      ? "text-success-ink"
                      : step.state === "error"
                        ? "text-destructive"
                        : "text-muted-foreground",
                ].join(" ")}
              >
                {step.label.replace(/^\d+\.\s*/, "")}
              </p>
              <p className="mt-1 min-h-8 text-xs leading-4 text-muted-foreground">{step.detail}</p>
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
      ? "bg-destructive"
      : tone === "success"
        ? "bg-success-ink"
        : tone === "importing"
          ? "bg-burgundy ring-2 ring-burgundy/20"
          : tone === "ready"
            ? "bg-burgundy"
            : "bg-foreground/35";

  return <span className={["size-2.5 rounded-full", toneClass].join(" ")} aria-hidden="true" />;
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
      ? "text-success-ink"
      : tone === "warning"
        ? "text-warning-ink"
        : tone === "danger"
          ? "text-destructive"
      : "text-foreground";

  return (
    <div className="rounded-lg border border-border bg-muted/75 px-3 py-3 transition-colors hover:border-burgundy/20 hover:bg-surface">
      <p className="text-[11px] font-semibold text-muted-foreground">{label}</p>
      <p className={["mt-1 text-2xl font-semibold tabular-nums", toneClass].join(" ")}>{value}</p>
    </div>
  );
}
