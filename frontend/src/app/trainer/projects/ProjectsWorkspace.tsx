"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import type { CompanyProject, CompanyProjectStatus } from "@/api/companies";
import { ProjectCardLink } from "@/components/projects/project-card";
import { useUrlState } from "@/hooks/use-url-state";

type ProjectFilters = {
  q?: string;
  company?: string;
  status?: string;
  type?: string;
};

type ProjectsWorkspaceProps = {
  projects: CompanyProject[];
  initialFilters: ProjectFilters;
  companies: Array<[string, string]>;
  projectTypes: string[];
};

export function ProjectsWorkspace({ projects, initialFilters, companies, projectTypes }: ProjectsWorkspaceProps) {
  const urlState = useUrlState();
  const { get, searchKey, setParam } = urlState;
  const [values, setValues] = useState({
    q: initialFilters.q ?? "",
    company: initialFilters.company ?? "",
    status: initialFilters.status ?? "",
    type: initialFilters.type ?? "",
  });

  useEffect(() => {
    setValues({
      q: get("q") ?? "",
      company: get("company") ?? "",
      status: get("status") ?? "",
      type: get("type") ?? "",
    });
  }, [get, searchKey]);

  const filteredProjects = useMemo(() => {
    const query = values.q.trim().toLowerCase();
    return projects
      .filter((project) => !query || `${project.name} ${project.company_name ?? ""}`.toLowerCase().includes(query))
      .filter((project) => !values.company || project.company_id === values.company)
      .filter((project) => !values.status || project.status === values.status)
      .filter((project) => !values.type || project.project_type === values.type)
      .sort((first, second) => {
        const rankDiff = statusRank(first.status) - statusRank(second.status);
        if (rankDiff !== 0) return rankDiff;
        return (second.updated_at ?? "").localeCompare(first.updated_at ?? "");
      });
  }, [projects, values.company, values.q, values.status, values.type]);

  function updateValue(key: keyof typeof values, value: string) {
    setValues((current) => ({ ...current, [key]: value }));
    setParam(key, value, "replace");
  }

  return (
    <>
      <section className="filter-toolbar">
        <div className="relative w-full md:flex-1">
          <svg className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-foreground/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            name="q"
            value={values.q}
            onChange={(event) => updateValue("q", event.target.value)}
            placeholder="Caută proiect sau companie..."
            className="control-input control-search w-full py-3 pl-12 pr-4"
          />
        </div>
        <select
          name="company"
          value={values.company}
          onChange={(event) => updateValue("company", event.target.value)}
          className="control-input min-h-[3rem] w-full cursor-pointer appearance-none px-4 md:w-auto"
        >
          <option value="">Toate companiile</option>
          {companies.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
        <select
          name="status"
          value={values.status}
          onChange={(event) => updateValue("status", event.target.value)}
          className="control-input min-h-[3rem] w-full cursor-pointer appearance-none px-4 md:w-auto"
        >
          <option value="">Status</option>
          <option value="active">Active</option>
          <option value="draft">În pregătire</option>
          <option value="completed">Finalizate</option>
          <option value="archived">Arhivate</option>
        </select>
        <select
          name="type"
          value={values.type}
          onChange={(event) => updateValue("type", event.target.value)}
          className="control-input min-h-[3rem] w-full cursor-pointer appearance-none px-4 md:w-auto"
        >
          <option value="">Tip proiect</option>
          {projectTypes.map((type) => <option key={type} value={type}>{type}</option>)}
        </select>
      </section>

      {projects.length === 0 ? (
        <section className="surface-panel flex min-h-[40vh] flex-col items-center justify-center border-dashed p-12 text-center">
          <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-xl bg-surface-muted text-foreground/30">
            <svg className="h-10 w-10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2m14 0V9a2 2 0 0 0-2-2M5 11V9a2 2 0 0 1 2-2m0 0V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v2M7 7h10" /></svg>
          </div>
          <p className="font-display text-xl font-bold text-foreground">Nu există proiecte încă.</p>
          <p className="mt-3 max-w-sm text-sm leading-relaxed text-foreground/50">
            Intră într-o companie și creează primul proiect din sumarul ei pentru a începe lucrul cu participanții.
          </p>
          <Link
            href="/trainer/companies"
            className="tap-soft mt-8 inline-flex items-center justify-center rounded-full bg-burgundy px-6 py-3 text-sm font-bold text-white shadow-sm transition-all hover:bg-burgundy/90"
          >
            Deschide companii
          </Link>
        </section>
      ) : filteredProjects.length === 0 ? (
        <section className="surface-panel flex min-h-[18rem] flex-col items-center justify-center p-10 text-center">
          <p className="font-display text-lg font-bold text-foreground">Nu am găsit proiecte pentru filtrul curent.</p>
          <p className="mt-2 max-w-sm text-sm text-foreground/55">Șterge o parte din căutare sau schimbă filtrele.</p>
        </section>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          {filteredProjects.map((project) => (
            <ProjectCardLink key={project.id} project={project} />
          ))}
        </div>
      )}
    </>
  );
}

function statusRank(status: CompanyProjectStatus): number {
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
