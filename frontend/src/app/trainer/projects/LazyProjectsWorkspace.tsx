"use client";

import dynamic from "next/dynamic";

import { WorkspaceSkeleton } from "@/components/shell/workspace-skeletons";
import type { ProjectsWorkspaceProps } from "./ProjectsWorkspace";

const DynamicProjectsWorkspace = dynamic<ProjectsWorkspaceProps>(
  () => import("./ProjectsWorkspace").then((mod) => mod.ProjectsWorkspace),
  {
    loading: () => <WorkspaceSkeleton kind="table" label="Se încarcă lista proiectelor" />,
    ssr: false,
  },
);

export function LazyProjectsWorkspace(props: ProjectsWorkspaceProps) {
  return <DynamicProjectsWorkspace {...props} />;
}
