"use client";

import { useMemo, useState } from "react";

import { getApiBaseUrl } from "@/api/runtime";

type CompanyOption = {
  id: string;
  name: string;
};

type RosterImporterProps = {
  companies: CompanyOption[];
};

type RosterRow = {
  "Name": string;
  "Reports To"?: string;
  "Position"?: string;
  "Location"?: string;
  "email": string;
  "Profil PCM"?: string;
};

type ImportState =
  | { status: "idle"; message: string }
  | { status: "ready"; message: string }
  | { status: "importing"; message: string }
  | { status: "success"; message: string }
  | { status: "error"; message: string };

const aliases: Record<keyof RosterRow, string[]> = {
  "Name": ["Name", "name", "full_name", "nume"],
  "Reports To": ["Reports To", "reports_to", "reports_to_name", "manager", "manager_email"],
  "Position": ["Position", "position", "role", "rol"],
  "Location": ["Location", "location", "locatie"],
  "email": ["email", "Email", "adresa email", "adresa de email"],
  "Profil PCM": ["Profil PCM", "pcm_profile", "profil pcm", "PCM"],
};

export function RosterImporter({ companies }: RosterImporterProps) {
  const [companyId, setCompanyId] = useState(companies[0]?.id ?? "");
  const [rows, setRows] = useState<RosterRow[]>([]);
  const [state, setState] = useState<ImportState>({
    status: "idle",
    message: "Alege un fisier CSV cu cel putin Name si email.",
  });

  const preview = useMemo(() => rows.slice(0, 6), [rows]);
  const canImport = companyId && rows.length > 0 && state.status !== "importing";

  async function handleFile(file: File | null) {
    if (!file) return;
    const text = await file.text();
    const parsed = parseRosterCsv(text);
    if ("error" in parsed) {
      setRows([]);
      setState({ status: "error", message: parsed.error });
      return;
    }

    setRows(parsed.rows);
    setState({
      status: "ready",
      message: `${parsed.rows.length} randuri pregatite pentru import.`,
    });
  }

  async function importRows() {
    if (!canImport) return;
    setState({ status: "importing", message: "Import in curs..." });

    try {
      const response = await fetch(`${getApiBaseUrl()}/companies/${companyId}/participants/roster`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ rows }),
      });

      if (!response.ok) {
        const body = await response.text();
        setState({
          status: "error",
          message: body || "Importul a fost respins de server.",
        });
        return;
      }

      const imported = (await response.json()) as unknown[];
      setState({
        status: "success",
        message: `${imported.length} participanti importati.`,
      });
    } catch {
      setState({
        status: "error",
        message: "Nu am putut contacta backend-ul pentru import.",
      });
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_16rem]">
          <label className="block">
            <span className="text-sm font-bold text-foreground">Companie</span>
            <select
              value={companyId}
              onChange={(event) => setCompanyId(event.target.value)}
              className="mt-2 w-full rounded-xl border border-[var(--border)] bg-background px-3 py-3 text-sm font-semibold text-foreground"
            >
              {companies.length === 0 ? <option value="">Nicio companie</option> : null}
              {companies.map((company) => (
                <option key={company.id} value={company.id}>
                  {company.name}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-bold text-foreground">Fisier CSV</span>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => handleFile(event.target.files?.[0] ?? null)}
              className="mt-2 w-full rounded-xl border border-dashed border-burgundy/35 bg-background px-3 py-3 text-sm font-semibold text-foreground file:mr-3 file:rounded-lg file:border-0 file:bg-burgundy file:px-3 file:py-2 file:text-sm file:font-bold file:text-white"
            />
          </label>
        </div>

        <div
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            handleFile(event.dataTransfer.files.item(0));
          }}
          className="mt-5 rounded-2xl border border-dashed border-[var(--border)] bg-background px-5 py-10 text-center"
        >
          <p className="text-lg font-bold text-foreground">Trage fisierul aici</p>
          <p className="mt-2 text-sm leading-6 text-foreground/60">
            Coloane acceptate: Name, Reports To, Position, Location, email, Profil PCM.
          </p>
        </div>

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
          <p className={statusClassName(state.status)}>{state.message}</p>
          <button
            type="button"
            disabled={!canImport}
            onClick={importRows}
            className="tap-soft rounded-xl bg-burgundy px-5 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-45"
          >
            Importa roster
          </button>
        </div>
      </section>

      <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
        <p className="text-xs font-bold uppercase tracking-[0.12em] text-burgundy/75">Preview</p>
        {preview.length === 0 ? (
          <p className="mt-4 text-sm leading-6 text-foreground/58">
            Inca nu exista randuri incarcate. Preview-ul apare dupa validarea fisierului.
          </p>
        ) : (
          <div className="mt-4 space-y-3">
            {preview.map((row) => (
              <article key={`${row.email}-${row.Name}`} className="rounded-xl bg-background px-3 py-3">
                <p className="text-sm font-bold text-foreground">{row.Name}</p>
                <p className="mt-1 text-xs leading-5 text-foreground/55">
                  {row.Position || "Fara pozitie"} · {row.email}
                </p>
                {row["Reports To"] ? (
                  <p className="mt-1 text-xs font-semibold text-burgundy">
                    Raporteaza catre {row["Reports To"]}
                  </p>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function parseRosterCsv(text: string): { rows: RosterRow[] } | { error: string } {
  const [headerLine, ...lines] = text.split(/\r?\n/).filter((line) => line.trim().length > 0);
  if (!headerLine) return { error: "Fisierul este gol." };

  const headers = parseCsvLine(headerLine);
  const headerMap = buildHeaderMap(headers);
  const missing = ["Name", "email"].filter((key) => !headerMap[key]);
  if (missing.length > 0) {
    return { error: `Lipsesc coloanele obligatorii: ${missing.join(", ")}.` };
  }

  const rows = lines.map(parseCsvLine).map((cells) => normalizeRow(headers, cells, headerMap));
  const invalid = rows.find((row) => !row.Name || !row.email || !row.email.includes("@"));
  if (invalid) return { error: "Exista randuri fara Name sau email valid." };

  return { rows };
}

function buildHeaderMap(headers: string[]): Record<string, string> {
  return Object.fromEntries(
    Object.entries(aliases).flatMap(([target, options]) => {
      const matched = headers.find((header) =>
        options.some((option) => option.toLowerCase() === header.trim().toLowerCase()),
      );
      return matched ? [[target, matched]] : [];
    }),
  );
}

function normalizeRow(headers: string[], cells: string[], headerMap: Record<string, string>): RosterRow {
  const source = Object.fromEntries(headers.map((header, index) => [header, cells[index]?.trim() ?? ""]));

  return {
    "Name": source[headerMap["Name"]],
    "Reports To": source[headerMap["Reports To"]] || undefined,
    "Position": source[headerMap["Position"]] || undefined,
    "Location": source[headerMap["Location"]] || undefined,
    "email": source[headerMap["email"]],
    "Profil PCM": source[headerMap["Profil PCM"]] || undefined,
  };
}

function parseCsvLine(line: string): string[] {
  const cells: string[] = [];
  let current = "";
  let quoted = false;

  for (const char of line) {
    if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      cells.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }

  cells.push(current.trim());
  return cells;
}

function statusClassName(status: ImportState["status"]) {
  if (status === "error") return "text-sm font-bold text-red-700";
  if (status === "success") return "text-sm font-bold text-green-700";
  return "text-sm font-semibold text-foreground/62";
}
