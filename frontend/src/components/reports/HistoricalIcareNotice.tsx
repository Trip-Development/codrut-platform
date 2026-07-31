import { InfoIcon } from "lucide-react";

type HistoricalIcareNoticeProps = {
  count: number;
  reason?: "historical_cohort_unavailable" | null;
};

export function HistoricalIcareNotice({ count, reason }: HistoricalIcareNoticeProps) {
  if (count <= 0 || reason !== "historical_cohort_unavailable") return null;

  const opening = count === 1
    ? "Un răspuns mai vechi nu apare în perspectivele de mai jos."
    : `${count} răspunsuri mai vechi nu apar în perspectivele de mai jos.`;
  const closing = count === 1
    ? "Îl păstrăm separat, fără să ghicim perspectiva."
    : "Le păstrăm separat, fără să ghicim perspectiva.";

  return (
    <aside
      role="note"
      aria-label="Despre răspunsurile iCARE mai vechi"
      className="flex gap-3 rounded-lg border border-border bg-muted/45 px-4 py-3"
    >
      <InfoIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-burgundy" strokeWidth={1.8} />
      <div>
        <p className="text-sm font-semibold text-foreground">Răspunsuri iCARE mai vechi</p>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          {opening} La momentul completării, relația necesară pentru încadrare nu a fost păstrată. {closing}
        </p>
      </div>
    </aside>
  );
}
