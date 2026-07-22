"use client";

import dynamic from "next/dynamic";

import { WorkspaceSkeleton } from "@/components/shell/workspace-skeletons";
import type { CompaniesWorkspaceProps } from "./CompaniesWorkspace";

const DynamicCompaniesWorkspace = dynamic<CompaniesWorkspaceProps>(
  () => import("./CompaniesWorkspace").then((mod) => mod.CompaniesWorkspace),
  {
    loading: () => <WorkspaceSkeleton kind="table" label="Se încarcă lista companiilor" />,
    ssr: false,
  },
);

export function LazyCompaniesWorkspace(props: CompaniesWorkspaceProps) {
  return <DynamicCompaniesWorkspace {...props} />;
}
