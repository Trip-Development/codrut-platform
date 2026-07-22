"use client";

import dynamic from "next/dynamic";

import { WorkspaceSkeleton } from "@/components/shell/workspace-skeletons";
import type { ProjectSettingsFormProps } from "./ProjectSettingsForm";

const DynamicProjectSettingsForm = dynamic<ProjectSettingsFormProps>(
  () => import("./ProjectSettingsForm").then((mod) => mod.ProjectSettingsForm),
  {
    loading: () => <WorkspaceSkeleton kind="editor" label="Pregătim setările proiectului" />,
    ssr: false,
  },
);

export function LazyProjectSettingsForm(props: ProjectSettingsFormProps) {
  return <DynamicProjectSettingsForm {...props} />;
}
