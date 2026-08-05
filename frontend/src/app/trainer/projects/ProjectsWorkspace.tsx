"use client";

import Link from "next/link";
import {
  ArrowRightIcon,
  BriefcaseBusinessIcon,
  Building2Icon,
  CalendarDaysIcon,
  FilterIcon,
  FolderArchiveIcon,
  FolderPlusIcon,
  FolderOpenIcon,
  Loader2Icon,
  RotateCcwIcon,
  SearchIcon,
  XIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useDeferredValue, useEffect, useMemo, useState } from "react";

import { restoreCompanyProject, type CompanyProject } from "@/api/companies";
import {
  formatProjectDate,
  formatProjectDateRange,
  ProjectStatusBadge,
  projectTypeLabel,
  statusRank,
} from "@/components/projects/project-display";
import { Button } from "@/components/ui/button";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Sheet, SheetBody, SheetFooter, SheetHeader } from "@/components/ui/sheet";
import { useUrlState } from "@/hooks/use-url-state";
import { cn } from "@/utils/cn";
import {
  normalizeWorkspaceSearch,
  SearchableProjectFilter,
  WorkspaceSearchInput,
} from "./project-workspace-controls";

type ProjectFilters = {
  q?: string;
  company?: string;
  status?: string;
  type?: string;
};

export type ProjectsWorkspaceProps = {
  projects: CompanyProject[];
  initialFilters: ProjectFilters;
  companies: Array<[string, string]>;
  projectTypes: string[];
  archivedMode?: boolean;
};

export function ProjectsWorkspace({
  projects,
  initialFilters,
  companies,
  projectTypes,
  archivedMode = false,
}: ProjectsWorkspaceProps) {
  const router = useRouter();
  const { get, searchKey, isPending: isUrlPending, setParam, setParams } = useUrlState();
  const [values, setValues] = useState({
    q: initialFilters.q ?? "",
    company: initialFilters.company ?? "",
    status: archivedMode ? "" : (initialFilters.status ?? ""),
    type: initialFilters.type ?? "",
  });
  const [restoringProjectId, setRestoringProjectId] = useState<string | null>(null);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const deferredQuery = useDeferredValue(values.q);
  const isFilterPending = isUrlPending || values.q !== deferredQuery;

  useEffect(() => {
    setValues({
      q: get("q") ?? "",
      company: get("company") ?? "",
      status: archivedMode ? "" : (get("status") ?? ""),
      type: get("type") ?? "",
    });
  }, [archivedMode, get, searchKey]);

  const filteredProjects = useMemo(() => {
    const query = normalizeWorkspaceSearch(deferredQuery);

    return projects
      .filter((project) =>
        archivedMode
          ? project.status === "archived"
          : project.status !== "archived",
      )
      .filter((project) => {
        if (!query) return true;
        return normalizeWorkspaceSearch(
          `${project.name} ${project.company_name ?? ""} ${project.description ?? ""} ${projectTypeLabel(project.project_type)}`,
        ).includes(query);
      })
      .filter((project) => !values.company || project.company_id === values.company)
      .filter((project) => !values.status || project.status === values.status)
      .filter((project) => !values.type || project.project_type === values.type)
      .sort((first, second) => {
        const rankDifference = statusRank(first.status) - statusRank(second.status);
        if (rankDifference !== 0) return rankDifference;
        return (second.updated_at ?? "").localeCompare(first.updated_at ?? "");
      });
  }, [archivedMode, deferredQuery, projects, values.company, values.status, values.type]);

  const activeCount = filteredProjects.filter((project) => project.status === "active").length;
  const draftCount = filteredProjects.filter((project) => project.status === "draft").length;
  const completedCount = filteredProjects.filter((project) => project.status === "completed").length;
  const hasActiveFilters = Boolean(values.q || values.company || values.status || values.type);
  const activeFilterCount = [values.company, values.status, values.type].filter(Boolean).length;

  function updateValue(key: keyof typeof values, value: string) {
    setValues((current) => ({ ...current, [key]: value }));
    setParam(key, value, "replace");
  }

  function resetFilters() {
    setValues({ q: "", company: "", status: "", type: "" });
    setParams(
      {
        q: null,
        company: null,
        status: null,
        type: null,
        view: archivedMode ? "archived" : null,
      },
      "replace",
    );
  }

  async function restoreProject(project: CompanyProject) {
    if (restoringProjectId) return;
    setRestoringProjectId(project.id);
    setRestoreError(null);
    try {
      await restoreCompanyProject(project.company_id, project.id);
      router.refresh();
    } catch (error) {
      setRestoreError(
        error instanceof Error ? error.message : "Proiectul nu a putut fi restaurat.",
      );
      setRestoringProjectId(null);
    }
  }

  function renderFilterControls() {
    return (
      <>
        <SearchableProjectFilter
          icon={Building2Icon}
          label="Companie"
          value={values.company}
          allLabel="Toate companiile"
          options={companies.map(([value, label]) => ({ value, label }))}
          onValueChange={(value) => updateValue("company", value)}
        />
        {!archivedMode ? (
          <SearchableProjectFilter
            icon={FilterIcon}
            label="Status"
            value={values.status}
            allLabel="Toate statusurile"
            options={[
              { value: "active", label: "Active" },
              { value: "draft", label: "În pregătire" },
              { value: "completed", label: "Finalizate" },
            ]}
            onValueChange={(value) => updateValue("status", value)}
          />
        ) : null}
        <SearchableProjectFilter
          icon={BriefcaseBusinessIcon}
          label="Tip proiect"
          value={values.type}
          allLabel="Toate tipurile"
          options={projectTypes.map((type) => ({ value: type, label: projectTypeLabel(type) }))}
          onValueChange={(value) => updateValue("type", value)}
        />
      </>
    );
  }

  return (
    <div className="flex min-w-0 flex-col gap-5">
      <nav className="flex flex-wrap items-center gap-2" aria-label="Vizualizare proiecte">
        <Button asChild variant={archivedMode ? "ghost" : "secondary"} size="sm">
          <Link href="/trainer/projects">
            <FolderOpenIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
            Proiecte curente
          </Link>
        </Button>
        <Button asChild variant={archivedMode ? "secondary" : "ghost"} size="sm">
          <Link href="/trainer/projects?view=archived">
            <FolderArchiveIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
            Arhivă
          </Link>
        </Button>
      </nav>

      {restoreError ? <InlineFeedback tone="danger">{restoreError}</InlineFeedback> : null}

      <section
        className={cn(
          "grid min-w-0 gap-3 rounded-lg border bg-surface p-3 lg:grid-cols-2",
          archivedMode
            ? "xl:grid-cols-[minmax(24rem,1fr)_minmax(12rem,14rem)_minmax(11rem,13rem)]"
            : "xl:grid-cols-[minmax(24rem,1fr)_minmax(12rem,14rem)_minmax(11rem,13rem)_minmax(11rem,13rem)]",
        )}
        aria-label="Filtre proiecte"
      >
        <div className="flex min-w-0 items-center gap-2 lg:contents">
          <WorkspaceSearchInput
            id="projects-search"
            label="Caută proiect sau companie"
            value={values.q}
            onValueChange={(value) => updateValue("q", value)}
            placeholder="Caută proiecte"
            className="min-w-0 flex-1 lg:col-span-2 xl:col-span-1"
          />
          <Button
            type="button"
            variant="outline"
            className="lg:hidden"
            aria-haspopup="dialog"
            aria-label={activeFilterCount > 0 ? `Filtre, ${activeFilterCount} active` : "Filtre"}
            onClick={() => setFiltersOpen(true)}
          >
            <FilterIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
            Filtre{activeFilterCount > 0 ? ` (${activeFilterCount})` : ""}
          </Button>
        </div>
        <div className="hidden lg:contents">{renderFilterControls()}</div>
      </section>

      <Sheet
        open={filtersOpen}
        onOpenChange={setFiltersOpen}
        labelledBy="project-filters-title"
        describedBy="project-filters-description"
      >
        <SheetHeader className="flex items-start justify-between gap-4">
          <div>
            <h2 id="project-filters-title" className="text-lg font-semibold text-foreground">Filtre</h2>
            <p id="project-filters-description" className="mt-1 text-sm text-muted-foreground">
              Restrânge lista fără să pierzi căutarea curentă.
            </p>
          </div>
          <Button type="button" variant="ghost" size="icon-sm" aria-label="Închide filtrele" onClick={() => setFiltersOpen(false)}>
            <XIcon aria-hidden="true" strokeWidth={1.8} />
          </Button>
        </SheetHeader>
        <SheetBody className="flex flex-col gap-4">{filtersOpen ? renderFilterControls() : null}</SheetBody>
        <SheetFooter className="flex items-center justify-between gap-3">
          <Button type="button" variant="ghost" onClick={resetFilters}>Resetează</Button>
          <Button type="button" onClick={() => setFiltersOpen(false)}>Gata</Button>
        </SheetFooter>
      </Sheet>

      <span className="sr-only" role="status" aria-live="polite">
        {isFilterPending ? "Se actualizează lista" : ""}
      </span>

      {projects.length === 0 ? (
        <Empty className="min-h-[40vh] border bg-surface p-12">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <FolderPlusIcon aria-hidden="true" strokeWidth={1.8} />
            </EmptyMedia>
            <EmptyTitle>{archivedMode ? "Arhiva este goală" : "Nu există proiecte încă"}</EmptyTitle>
            <EmptyDescription>
              {archivedMode
                ? "Proiectele arhivate vor apărea aici și pot fi restaurate."
                : "Creează primul proiect din spațiul unei companii."}
            </EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            {archivedMode ? (
              <Button asChild variant="outline">
                <Link href="/trainer/projects">Vezi proiectele curente</Link>
              </Button>
            ) : (
              <Button asChild>
                <Link href="/trainer/companies">Deschide companii</Link>
              </Button>
            )}
          </EmptyContent>
        </Empty>
      ) : filteredProjects.length === 0 ? (
        <Empty className="min-h-[18rem] border bg-surface p-10">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <SearchIcon aria-hidden="true" strokeWidth={1.8} />
            </EmptyMedia>
            <EmptyTitle>Niciun proiect găsit</EmptyTitle>
            <EmptyDescription>Schimbă căutarea sau filtrele active.</EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button type="button" variant="outline" onClick={resetFilters}>
              <XIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
              Resetează filtrele
            </Button>
          </EmptyContent>
        </Empty>
      ) : (
        <section
          aria-label="Lista proiectelor"
          aria-busy={isFilterPending}
          className={cn(
            "min-w-0 overflow-hidden rounded-lg border bg-surface transition-opacity",
            isFilterPending && "opacity-70",
          )}
        >
          <div className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
            <p className="text-sm text-muted-foreground">
              <span className="font-semibold text-foreground">{filteredProjects.length}</span> {filteredProjects.length === 1 ? "proiect" : "proiecte"}
              {archivedMode ? (
                <span> în arhivă</span>
              ) : (
                <>
                  <span aria-hidden="true"> · </span>{activeCount} {activeCount === 1 ? "activ" : "active"}
                  <span aria-hidden="true"> · </span>{draftCount} de configurat
                  <span aria-hidden="true"> · </span>{completedCount} {completedCount === 1 ? "finalizat" : "finalizate"}
                </>
              )}
            </p>
            {hasActiveFilters ? (
              <Button type="button" variant="ghost" size="sm" onClick={resetFilters}>
                <XIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
                Resetează
              </Button>
            ) : null}
          </div>

          <div className="w-full max-w-full md:overflow-x-auto md:[scrollbar-width:thin]">
            <table className="block w-full text-left text-sm md:table md:min-w-[64rem] xl:min-w-0 xl:table-fixed">
              <colgroup>
                <col className="w-[22%]" />
                <col className="w-[15%]" />
                <col className="w-[11%]" />
                <col className="w-[13%]" />
                <col className="w-[15%]" />
                <col className="w-[10%]" />
                <col className="w-[14%]" />
              </colgroup>
              <thead className="hidden bg-muted/60 text-xs font-semibold text-muted-foreground md:table-header-group">
                <tr>
                  <th scope="col" className="min-w-64 px-4 py-3">Proiect</th>
                  <th scope="col" className="min-w-44 px-4 py-3">Companie</th>
                  <th scope="col" className="min-w-28 px-4 py-3">Status</th>
                  <th scope="col" className="min-w-36 px-4 py-3">Tip</th>
                  <th scope="col" className="min-w-40 px-4 py-3">Calendar</th>
                  <th scope="col" className="px-4 py-3">Actualizat</th>
                  <th scope="col" className="min-w-40 px-4 py-3">Următorul pas</th>
                </tr>
              </thead>
              <tbody className="block divide-y divide-border md:table-row-group">
                {filteredProjects.map((project) => (
                  <tr key={project.id} className="grid grid-cols-2 gap-x-4 gap-y-3 px-4 py-4 transition-colors hover:bg-muted/35 md:table-row md:px-0 md:py-0">
                    <td className="col-span-2 row-start-1 min-w-0 md:max-w-[24rem] md:px-4 md:py-4">
                      <Link
                        href={`/trainer/projects/${project.id}`}
                        className="group inline-flex max-w-full flex-col gap-1 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45"
                      >
                        <span className="truncate font-semibold text-foreground group-hover:text-primary">{project.name}</span>
                        {project.description ? (
                          <span className="line-clamp-1 text-xs leading-5 text-muted-foreground">{project.description}</span>
                        ) : null}
                      </Link>
                    </td>
                    <td className="col-start-1 row-start-2 min-w-0 md:max-w-[14rem] md:px-4 md:py-4">
                      <span className="mb-1 block text-xs font-medium text-muted-foreground md:hidden">Companie</span>
                      <span className="block truncate font-medium text-foreground">{project.company_name ?? "Companie"}</span>
                    </td>
                    <td className="col-start-2 row-start-2 justify-self-end md:min-w-28 md:justify-self-auto md:px-4 md:py-4"><ProjectStatusBadge status={project.status} /></td>
                    <td className="col-start-1 row-start-3 font-medium text-foreground md:px-4 md:py-4">
                      <span className="mb-1 block text-xs font-medium text-muted-foreground md:hidden">Tip</span>
                      {projectTypeLabel(project.project_type)}
                    </td>
                    <td className="col-span-2 row-start-4 md:min-w-40 md:px-4 md:py-4">
                      <span className="mb-1 block text-xs font-medium text-muted-foreground md:hidden">Calendar</span>
                      <span className="inline-flex items-center gap-2 whitespace-nowrap text-muted-foreground">
                        <CalendarDaysIcon aria-hidden="true" className="size-4 shrink-0" strokeWidth={1.8} />
                        {formatProjectDateRange(project.starts_at, project.due_at)}
                      </span>
                    </td>
                    <td className="col-start-2 row-start-3 justify-self-end text-right text-muted-foreground md:justify-self-auto md:px-4 md:py-4 md:text-left">
                      <span className="mb-1 block text-xs font-medium md:hidden">Actualizat</span>
                      {formatProjectDate(project.updated_at)}
                    </td>
                    <td className="col-span-2 row-start-5 border-t pt-3 md:border-0 md:px-4 md:py-4">
                      {archivedMode ? (
                        <div className="flex items-center gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={Boolean(restoringProjectId)}
                            onClick={() => restoreProject(project)}
                          >
                            {restoringProjectId === project.id ? (
                              <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" />
                            ) : (
                              <RotateCcwIcon data-icon="inline-start" aria-hidden="true" />
                            )}
                            Restaurează
                          </Button>
                          <Link
                            href={`/trainer/projects/${project.id}/settings`}
                            className="font-semibold text-foreground hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45"
                          >
                            Detalii
                          </Link>
                        </div>
                      ) : (
                        <Link
                          href={`/trainer/projects/${project.id}`}
                          className="inline-flex items-center gap-1.5 font-semibold text-foreground hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45"
                        >
                          {projectActionLabel(project)}
                          <ArrowRightIcon aria-hidden="true" className="size-3.5" strokeWidth={1.8} />
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

function projectActionLabel(project: CompanyProject): string {
  switch (project.status) {
    case "draft":
      return "Continuă configurarea";
    case "active":
      return "Urmărește progresul";
    case "completed":
      return "Deschide raportul";
    case "archived":
      return "Consultă istoricul";
  }
}
