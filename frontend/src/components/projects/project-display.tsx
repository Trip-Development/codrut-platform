import type { CompanyProjectStatus } from "@/api/companies";
import { cn } from "@/utils/cn";
import { formatRomanianDate } from "@/utils/date-format";

const projectTypeLabels: Record<string, string> = {
  team_coaching: "Coaching de echipă",
  individual_coaching: "Coaching individual",
  leadership_program: "Program de leadership",
  cohort_program: "Program de cohortă",
  custom: "Personalizat",
};

export function ProjectStatusBadge({
  status,
  className,
}: {
  status: CompanyProjectStatus;
  className?: string;
}) {
  const statusClassName = {
    active: "text-primary",
    archived: "text-muted-foreground",
    completed: "text-foreground",
    draft: "text-foreground/70",
  }[status];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 whitespace-nowrap text-xs font-semibold",
        statusClassName,
        className,
      )}
    >
      <span className="size-1.5 rounded-full bg-current" />
      {statusLabel(status)}
    </span>
  );
}

export function statusRank(status: CompanyProjectStatus): number {
  switch (status) {
    case "active":
      return 0;
    case "draft":
      return 1;
    case "completed":
      return 2;
    case "archived":
      return 3;
    default:
      return 4;
  }
}

export function statusLabel(status: CompanyProjectStatus): string {
  switch (status) {
    case "draft":
      return "În pregătire";
    case "active":
      return "Activ";
    case "completed":
      return "Finalizat";
    case "archived":
      return "Arhivat";
    default:
      return status;
  }
}

export function projectTypeLabel(value: string | null): string {
  if (!value) return "General";
  return projectTypeLabels[value] ?? value;
}

export function formatProjectDate(value: string | null | undefined): string {
  return formatRomanianDate(value, { fallback: "Fără dată", includeYear: false });
}

export function formatProjectDateRange(start: string | null, end: string | null): string {
  const startLabel = formatProjectDate(start);
  const endLabel = formatProjectDate(end);
  if (start && end) return `${startLabel} - ${endLabel}`;
  if (start) return `Din ${startLabel}`;
  if (end) return `Până la ${endLabel}`;
  return "Fără dată";
}
