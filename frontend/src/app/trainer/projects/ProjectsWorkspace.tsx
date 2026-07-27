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
          "grid min-w-0 gap-3 rounded-lg border bg-surface p-3 shadow-sm lg:grid-cols-2",
          archivedMode
            ? "xl:grid-cols-[minmax(24rem,1fr)_minmax(12rem,14rem)_minmax(11rem,13rem)]"
            : "xl:grid-cols-[minmax(24rem,1fr)_minmax(12rem,14rem)_minmax(11rem,13rem)_minmax(11rem,13rem)]",
        )}
        aria-label="Filtre proiecte"
      >
        <WorkspaceSearchInput
          id="projects-search"
          label="Caută proiect sau companie"
          value={values.q}
          onValueChange={(value) => updateValue("q", value)}
          placeholder="Caută proiect sau companie"
          className="lg:col-span-2 xl:col-span-1"
        />
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
      </section>

      <span className="sr-only" role="status" aria-live="polite">
        {isFilterPending ? "Se actualizează lista" : ""}
      </span>

      {projects.length === 0 ? (
        <Empty className="min-h-[40vh] border bg-surface p-12 shadow-sm">
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
        <Empty className="min-h-[18rem] border bg-surface p-10 shadow-sm">
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
            "min-w-0 overflow-hidden rounded-lg border bg-surface shadow-sm transition-opacity",
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

          <div className="w-full max-w-full overflow-x-auto [scrollbar-width:thin]">
            <table className="w-full min-w-[64rem] text-left text-sm">
              <thead className="bg-muted/60 text-xs font-semibold text-muted-foreground">
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
              <tbody className="divide-y divide-border">
                {filteredProjects.map((project) => (
                  <tr key={project.id} className="transition-colors hover:bg-muted/35">
                    <td className="max-w-[24rem] px-4 py-4">
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
                    <td className="max-w-[14rem] px-4 py-4">
                      <span className="block truncate font-medium text-foreground">{project.company_name ?? "Companie"}</span>
                    </td>
                    <td className="min-w-28 px-4 py-4"><ProjectStatusBadge status={project.status} /></td>
                    <td className="px-4 py-4 font-medium text-foreground">{projectTypeLabel(project.project_type)}</td>
                    <td className="min-w-40 px-4 py-4">
                      <span className="inline-flex items-center gap-2 whitespace-nowrap text-muted-foreground">
                        <CalendarDaysIcon aria-hidden="true" className="size-4 shrink-0" strokeWidth={1.8} />
                        {formatProjectDateRange(project.starts_at, project.due_at)}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-muted-foreground">{formatProjectDate(project.updated_at)}</td>
                    <td className="px-4 py-4">
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
