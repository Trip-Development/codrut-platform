"use client";

import dynamic from "next/dynamic";

import { WorkspaceSkeleton } from "@/components/shell/workspace-skeletons";
import type { ProjectParticipantsWorkspaceProps } from "./ProjectParticipantsWorkspace";

const DynamicProjectParticipantsWorkspace = dynamic<ProjectParticipantsWorkspaceProps>(
  () => import("./ProjectParticipantsWorkspace").then((mod) => mod.ProjectParticipantsWorkspace),
  {
    loading: () => <WorkspaceSkeleton kind="table" label="Pregătim participanții" />,
    ssr: false,
  },
);

export function LazyProjectParticipantsWorkspace(props: ProjectParticipantsWorkspaceProps) {
  return <DynamicProjectParticipantsWorkspace {...props} />;
}
