const TOP_LEVEL_MANAGER_VALUES = new Set([
  "radacina",
  "root",
  "top",
  "top level",
  "nivel superior",
  "fara manager",
  "fara sef",
  "none",
  "n/a",
  "na",
  "-",
  "—",
]);

export function normalizeReportsToName(value: string | null | undefined): string {
  const cleaned = (value ?? "").trim();
  if (!cleaned) {
    return "";
  }

  return TOP_LEVEL_MANAGER_VALUES.has(normalizeManagerToken(cleaned)) || /^\d+$/.test(cleaned)
    ? ""
    : cleaned;
}

export function displayReportsToName(value: string | null | undefined): string {
  return normalizeReportsToName(value) || "—";
}

export function isExternalMatrixManagerLabel(value: string | null | undefined): boolean {
  const normalized = normalizeManagerToken(value ?? "").replace(/-/g, " ");
  return normalized.split(" ").includes("matrix");
}

export function managerReferenceKey(value: string | null | undefined): string {
  return (value ?? "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/[^\p{Letter}\p{Number}]+/gu, "")
    .toLowerCase();
}

function normalizeManagerToken(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}
