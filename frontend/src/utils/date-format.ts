export const APP_DISPLAY_TIME_ZONE = "Europe/Bucharest";

type RomanianDateOptions = {
  fallback?: string;
  includeYear?: boolean;
};

const shortDateFormatter = new Intl.DateTimeFormat("ro-RO", {
  day: "2-digit",
  month: "short",
  timeZone: APP_DISPLAY_TIME_ZONE,
});

const fullDateFormatter = new Intl.DateTimeFormat("ro-RO", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  timeZone: APP_DISPLAY_TIME_ZONE,
});

const inputDateFormatter = new Intl.DateTimeFormat("en-CA", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: APP_DISPLAY_TIME_ZONE,
});

export function formatRomanianDate(value: string | null | undefined, options: RomanianDateOptions = {}): string {
  const { fallback = "Fără dată", includeYear = true } = options;
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return fallback;
  return (includeYear ? fullDateFormatter : shortDateFormatter).format(date);
}

export function formatRomanianDateTime(value: string | null | undefined, fallback = "dată indisponibilă"): string {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return fallback;
  return new Intl.DateTimeFormat("ro-RO", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
    timeZone: APP_DISPLAY_TIME_ZONE,
    year: "numeric",
  }).format(date);
}

export function formatDateInputValue(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return inputDateFormatter.format(date);
}
