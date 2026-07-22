export type PcmProfileKey = "harmonizer" | "thinker" | "persister" | "imaginer" | "rebel" | "promoter";

export type PcmProfile = {
  key: PcmProfileKey;
  label: string;
  color: string;
  badgeClassName: string;
};

const pcmProfiles: Record<PcmProfileKey, PcmProfile> = {
  harmonizer: {
    key: "harmonizer",
    label: "Armonizator",
    color: "#f97316",
    badgeClassName: "border-orange-200 bg-orange-50 text-orange-800 dark:border-orange-900/55 dark:bg-orange-950/30 dark:text-orange-200",
  },
  thinker: {
    key: "thinker",
    label: "Gânditor",
    color: "#2563eb",
    badgeClassName: "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-900/55 dark:bg-blue-950/30 dark:text-blue-200",
  },
  persister: {
    key: "persister",
    label: "Perseverent",
    color: "#7c3aed",
    badgeClassName: "border-violet-200 bg-violet-50 text-violet-800 dark:border-violet-900/55 dark:bg-violet-950/30 dark:text-violet-200",
  },
  imaginer: {
    key: "imaginer",
    label: "Imaginator",
    color: "#fb923c",
    badgeClassName: "border-[#f2c879] bg-[#fff8df] text-[#8a5b00] dark:border-[#8a5b00]/55 dark:bg-[#8a5b00]/18 dark:text-[#f2c879]",
  },
  rebel: {
    key: "rebel",
    label: "Rebel",
    color: "#eab308",
    badgeClassName: "border-yellow-200 bg-yellow-50 text-yellow-800 dark:border-yellow-900/55 dark:bg-yellow-950/30 dark:text-yellow-200",
  },
  promoter: {
    key: "promoter",
    label: "Promotor",
    color: "#dc2626",
    badgeClassName: "border-red-200 bg-red-50 text-red-800 dark:border-red-900/55 dark:bg-red-950/30 dark:text-red-200",
  },
};

const pcmAliases: Record<string, PcmProfileKey> = {
  armonizator: "harmonizer",
  harmonizer: "harmonizer",
  ganditor: "thinker",
  gânditor: "thinker",
  thinker: "thinker",
  perseverent: "persister",
  persister: "persister",
  imaginator: "imaginer",
  imaginer: "imaginer",
  rebel: "rebel",
  promotor: "promoter",
  promoter: "promoter",
};

export function getPcmProfile(value?: string | null): PcmProfile | null {
  if (!value) return null;
  const normalized = value.trim().toLocaleLowerCase("ro-RO").replaceAll("_", " ");
  const compact = normalized.replace(/\s+/g, "");
  const key = pcmAliases[normalized] ?? pcmAliases[compact];
  return key ? pcmProfiles[key] : null;
}

export function formatPcmLabel(value?: string | null): string {
  const profile = getPcmProfile(value);
  if (profile) return profile.label;
  if (!value) return "Necompletată";
  return value
    .replace(/_/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toLocaleUpperCase("ro-RO") + part.slice(1))
    .join(" ");
}

export function getPcmColor(value?: string | null): string | undefined {
  return getPcmProfile(value)?.color;
}

export function getPcmBadgeClassName(value?: string | null): string {
  return getPcmProfile(value)?.badgeClassName ?? "border-[var(--border)] bg-surface-muted text-foreground/65";
}
