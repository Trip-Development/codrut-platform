"use client";

import dynamic from "next/dynamic";

import { WorkspaceSkeleton } from "@/components/shell/workspace-skeletons";
import type { EmailWorkspaceProps } from "./EmailWorkspace";

const DynamicEmailWorkspace = dynamic<EmailWorkspaceProps>(
  () => import("./EmailWorkspace").then((mod) => mod.EmailWorkspace),
  {
    loading: () => <WorkspaceSkeleton kind="editor" label="Pregătim spațiul de email" />,
    ssr: false,
  },
);

export function LazyEmailWorkspace(props: EmailWorkspaceProps) {
  return <DynamicEmailWorkspace {...props} />;
}
