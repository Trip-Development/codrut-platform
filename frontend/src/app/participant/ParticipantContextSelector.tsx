"use client";

import { BriefcaseBusinessIcon } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import type {
  ParticipantWorkspaceContext,
  ParticipantWorkspaceCycle,
} from "@/api/participants";
import { CycleComparisonToolbar } from "@/components/reports/CycleComparisonToolbar";
import { SearchableCombobox } from "@/components/ui/searchable-combobox";

export function ParticipantContextSelector({
  contexts,
  selectedProfileId,
  selectedProjectId,
}: {
  contexts: ParticipantWorkspaceContext[];
  selectedProfileId?: string;
  selectedProjectId?: string | null;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const options = contexts
    .flatMap((context) =>
      context.projects.map((project) => {
        const projectCycles = project.cycles ?? [];
        const preferredCycle =
          projectCycles.find((cycle) => cycle.status === "active") ??
          [...projectCycles].sort((left, right) => right.sequence - left.sequence)[0];
        return {
          value: `${context.participantProfileId}:${project.id}`,
          label: [
            contexts.length > 1 ? context.companyName : null,
            project.name,
          ].filter(Boolean).join(" · "),
          group: project.historyBucket === "history" ? "Istoric" : "În desfășurare",
          profileId: context.participantProfileId,
          projectId: project.id,
          cycleId: preferredCycle?.id,
          recency: Date.parse(
            preferredCycle?.dueAt
            ?? preferredCycle?.closedAt
            ?? project.deadlineAt
            ?? preferredCycle?.startsAt
            ?? "",
          ) || 0,
        };
      }),
    )
    .sort((left, right) => {
      if (left.group !== right.group) {
        return left.group === "În desfășurare" ? -1 : 1;
      }
      return right.recency - left.recency || left.label.localeCompare(right.label, "ro");
    });
  if (options.length <= 1) return null;

  const selectedValue = selectedProjectId
    ? options.find(
        (option) =>
          option.projectId === selectedProjectId &&
          (!selectedProfileId || option.profileId === selectedProfileId),
      )?.value ?? ""
    : "";

  function selectProject(value: string) {
    const selected = options.find((option) => option.value === value);
    if (!selected) return;
    const params = new URLSearchParams(searchParams.toString());
    params.set("profile", selected.profileId);
    params.set("project", selected.projectId);
    params.delete("cycle");
    params.delete("baseline");
    params.delete("compare");
    router.push(`${pathname}?${params.toString()}`);
  }

  return (
    <div className="mb-6 w-full max-w-sm">
      <SearchableCombobox
        icon={BriefcaseBusinessIcon}
        label="Proiect"
        value={selectedValue}
        allLabel="Alege proiectul"
        options={options.map(({ value, label, group }) => ({ value, label, group }))}
        onValueChange={selectProject}
        size="sm"
      />
    </div>
  );
}

export function ParticipantResultCycleControls({
  cycles,
  cycleId,
  baselineId,
  compareId,
}: {
  cycles: ParticipantWorkspaceCycle[];
  cycleId?: string | null;
  baselineId: string;
  compareId: string;
}) {
  return (
    <CycleComparisonToolbar
      cycles={cycles}
      cycleId={cycleId}
      baselineId={baselineId}
      compareId={compareId}
      className="mb-8"
    />
  );
}
