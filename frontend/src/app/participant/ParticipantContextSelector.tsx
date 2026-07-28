"use client";

import { BriefcaseBusinessIcon, HistoryIcon, XIcon } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import type {
  ParticipantWorkspaceContext,
  ParticipantWorkspaceCycle,
} from "@/api/participants";
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
        };
      }),
    )
    .sort((left, right) => {
      if (left.group !== right.group) {
        return left.group === "În desfășurare" ? -1 : 1;
      }
      return left.label.localeCompare(right.label, "ro");
    });
  if (options.length <= 1) return null;

  const selectedValue = selectedProjectId
    ? options.find(
        (option) =>
          option.projectId === selectedProjectId &&
          (!selectedProfileId || option.profileId === selectedProfileId),
      )?.value ?? ""
    : "";

  function selectProgram(value: string) {
    const selected = options.find((option) => option.value === value);
    if (!selected) return;
    const params = new URLSearchParams(searchParams.toString());
    params.set("profile", selected.profileId);
    params.set("project", selected.projectId);
    if (selected.cycleId) params.set("cycle", selected.cycleId);
    else params.delete("cycle");
    params.delete("baseline");
    params.delete("compare");
    router.push(`${pathname}?${params.toString()}`);
  }

  return (
    <div className="mb-6 w-full max-w-sm">
      <SearchableCombobox
        icon={BriefcaseBusinessIcon}
        label="Program"
        value={selectedValue}
        allLabel="Alege programul"
        options={options.map(({ value, label, group }) => ({ value, label, group }))}
        onValueChange={selectProgram}
        size="sm"
      />
    </div>
  );
}

export function ParticipantResultCycleControls({
  cycles,
  currentCycleId,
  baselineCycleId,
  comparisonCycleId,
  canCompare,
}: {
  cycles: ParticipantWorkspaceCycle[];
  currentCycleId?: string | null;
  baselineCycleId?: string | null;
  comparisonCycleId?: string | null;
  canCompare: boolean;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const ordered = [...cycles].sort((left, right) => left.sequence - right.sequence);
  const options = ordered.map((cycle) => ({ value: cycle.id, label: cycle.name }));
  const comparing = Boolean(baselineCycleId && comparisonCycleId);

  function navigate(mutator: (params: URLSearchParams) => void) {
    const params = new URLSearchParams(searchParams.toString());
    mutator(params);
    router.push(`${pathname}?${params.toString()}`);
  }

  if (ordered.length <= 1) return null;

  if (!comparing) {
    return (
      <div className="mb-7 flex flex-wrap items-center gap-3">
        <SearchableCombobox
          icon={HistoryIcon}
          label="Evaluare"
          value={currentCycleId ?? ""}
          allLabel="Alege evaluarea"
          options={options}
          onValueChange={(value) =>
            navigate((params) => {
              params.set("cycle", value);
              params.delete("baseline");
              params.delete("compare");
            })
          }
          className="w-56"
          size="sm"
        />
        {canCompare ? (
          <button
            type="button"
            onClick={() =>
              navigate((params) => {
                const currentIndex = ordered.findIndex((cycle) => cycle.id === currentCycleId);
                const comparisonIndex = currentIndex > 0 ? currentIndex : ordered.length - 1;
                params.set("baseline", ordered[comparisonIndex - 1].id);
                params.set("compare", ordered[comparisonIndex].id);
                params.set("cycle", ordered[comparisonIndex].id);
              })
            }
            className="h-9 rounded-md px-3 text-sm font-semibold text-burgundy transition-colors hover:bg-burgundy/8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/35"
          >
            Vezi evoluția
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="mb-7 flex flex-wrap items-end gap-3 border-b border-border pb-5">
      <div className="w-52">
        <SearchableCombobox
          icon={HistoryIcon}
          label="Referință"
          value={baselineCycleId ?? ""}
          allLabel="Alege referința"
          options={options.filter((option) => option.value !== comparisonCycleId)}
          onValueChange={(value) => navigate((params) => params.set("baseline", value))}
          size="sm"
        />
      </div>
      <div className="w-52">
        <SearchableCombobox
          icon={HistoryIcon}
          label="Comparație"
          value={comparisonCycleId ?? ""}
          allLabel="Alege comparația"
          options={options.filter((option) => option.value !== baselineCycleId)}
          onValueChange={(value) =>
            navigate((params) => {
              params.set("compare", value);
              params.set("cycle", value);
            })
          }
          size="sm"
        />
      </div>
      <button
        type="button"
        aria-label="Închide comparația"
        title="Închide comparația"
        onClick={() =>
          navigate((params) => {
            params.delete("baseline");
            params.delete("compare");
          })
        }
        className="flex size-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/35"
      >
        <XIcon aria-hidden="true" className="size-4" />
      </button>
    </div>
  );
}
