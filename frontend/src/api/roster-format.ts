const TOP_LEVEL_MANAGER_VALUES = new Set([
  "direct manager",
  "radacina",
  "root",
  "top",
  "top level",
  "nivel superior",
  "fara manager",
  "fara sef",
  "line manager",
  "manager",
  "manager direct",
  "none",
  "n/a",
  "na",
  "sef",
  "seful direct",
  "superior",
  "superior direct",
  "-",
  "\u2013",
  "\u2014",
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
  return normalizeReportsToName(value) || "-";
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

export function buildManagerReferenceKeySet(values: Iterable<string | null | undefined>): Set<string> {
  const keys = new Set<string>();
  for (const value of values) {
    const key = managerReferenceKey(value);
    if (key) {
      keys.add(key);
    }
  }
  return keys;
}

function normalizeManagerToken(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}
