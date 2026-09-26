"use client";

import { BriefcaseBusinessIcon } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

import type {
  ParticipantWorkspaceContext,
  ParticipantWorkspaceCycle,
} from "@/api/participants";
import { CycleComparisonToolbar } from "@/components/reports/CycleComparisonToolbar";
import { SearchableCombobox } from "@/components/ui/searchable-combobox";

/**
 * Proiectul ales, ținut minte în browser — plicul 129, partea A.
 *
 * Până azi proiectul trăia NUMAI în adresa din bară (`?project=`). Cât umbli prin meniu se
 * păstrează, fiindcă legăturile îl poartă; orice intrare fără el — adresa scrisă de mână, un
 * favorit, Înapoi din browser — îl pierde, iar butonul „Începe conversația" rămâne gri fără niciun
 * cuvânt. Andrei a dat peste asta pe 22 septembrie, și se întâmplă numai la oamenii cu două
 * proiecte (cu unul singur îl alege serverul).
 *
 * Cheia ține de CONT, nu de calculator: e făcută din profilurile contului ăstuia. Alt cont pe
 * același calculator are alte profiluri, deci altă cheie, deci nu moștenește nimic.
 *
 * Tot ce atinge `localStorage` e învelit în try/catch: într-o fereastră privată, sau cu datele
 * șterse, cititul și scrisul pot să arunce. Atunci totul merge exact ca azi.
 */
function cheiaProiectului(contexts: ParticipantWorkspaceContext[]): string | null {
  const profiluri = contexts
    .map((context) => context.participantProfileId)
    .filter(Boolean)
    .sort();
  return profiluri.length ? `codrut:proiect:${profiluri.join(",")}` : null;
}

function tineMinteProiectul(cheie: string | null, proiectId: string) {
  if (!cheie) return;
  try {
    window.localStorage.setItem(cheie, proiectId);
  } catch {
    // browserul refuză — mergem mai departe fără memorie
  }
}

function proiectulTinutMinte(cheie: string | null): string | null {
  if (!cheie) return null;
  try {
    return window.localStorage.getItem(cheie);
  } catch {
    return null;
  }
}

function uitaProiectul(cheie: string | null) {
  if (!cheie) return;
  try {
    window.localStorage.removeItem(cheie);
  } catch {
    // nimic de făcut
  }
}

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
  // Ține minte ce a ales, și folosește-l la o intrare fără `?project=` — plicul 129, partea A.
  //
  // Hookul stă ÎNAINTE de ieșirea de mai jos, fiindcă hookurile nu au voie să fie sărite: un om cu
  // un singur proiect n-ar mai ajunge niciodată să-și uite alegerea veche.
  useEffect(() => {
    const cheie = cheiaProiectului(contexts);
    if (!cheie) return;
    if (selectedProjectId) {
      tineMinteProiectul(cheie, selectedProjectId);
      return;
    }
    const tinut = proiectulTinutMinte(cheie);
    if (!tinut) return;
    const potrivit = options.find((option) => option.projectId === tinut);
    if (!potrivit) {
      // proiectul ținut minte nu mai e al lui: se uită, și i se cere să aleagă
      uitaProiectul(cheie);
      return;
    }
    const params = new URLSearchParams(searchParams.toString());
    params.set("profile", potrivit.profileId);
    params.set("project", potrivit.projectId);
    // `replace`, nu `push`: altfel butonul Înapoi al browserului l-ar trimite tot aici
    router.replace(`${pathname}?${params.toString()}`);
  }, [contexts, options, pathname, router, searchParams, selectedProjectId]);

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
    tineMinteProiectul(cheiaProiectului(contexts), selected.projectId);
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
