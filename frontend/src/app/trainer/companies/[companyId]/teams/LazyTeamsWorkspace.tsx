"use client";

import dynamic from "next/dynamic";

import { WorkspaceSkeleton } from "@/components/shell/workspace-skeletons";
import type { TeamsWorkspaceProps } from "./TeamsWorkspace";

const DynamicTeamsWorkspace = dynamic<TeamsWorkspaceProps>(
  () => import("./TeamsWorkspace").then((mod) => mod.TeamsWorkspace),
  {
    loading: () => <WorkspaceSkeleton kind="table" label="Pregătim echipele" />,
    ssr: false,
  },
);

export function LazyTeamsWorkspace(props: TeamsWorkspaceProps) {
  return <DynamicTeamsWorkspace {...props} />;
}
