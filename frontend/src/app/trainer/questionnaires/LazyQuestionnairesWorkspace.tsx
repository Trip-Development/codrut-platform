"use client";

import dynamic from "next/dynamic";

import { WorkspaceSkeleton } from "@/components/shell/workspace-skeletons";

const DynamicQuestionnairesWorkspace = dynamic(
  () => import("./QuestionnairesWorkspace").then((mod) => mod.QuestionnairesWorkspace),
  {
    loading: () => <WorkspaceSkeleton kind="editor" label="Pregătim catalogul de chestionare" />,
    ssr: false,
  },
);

export function LazyQuestionnairesWorkspace() {
  return <DynamicQuestionnairesWorkspace />;
}
