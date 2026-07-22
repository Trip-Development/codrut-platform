"use client";

import dynamic from "next/dynamic";

import { WorkspaceSkeleton } from "@/components/shell/workspace-skeletons";
import type { CompanySettingsWorkspaceProps } from "./CompanySettingsWorkspace";

const DynamicCompanySettingsWorkspace = dynamic<CompanySettingsWorkspaceProps>(
  () => import("./CompanySettingsWorkspace").then((mod) => mod.CompanySettingsWorkspace),
  {
    loading: () => <WorkspaceSkeleton kind="editor" label="Pregătim setările companiei" />,
    ssr: false,
  },
);

export function LazyCompanySettingsWorkspace(props: CompanySettingsWorkspaceProps) {
  return <DynamicCompanySettingsWorkspace {...props} />;
}
