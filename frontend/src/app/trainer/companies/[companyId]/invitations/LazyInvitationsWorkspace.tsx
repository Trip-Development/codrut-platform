"use client";

import dynamic from "next/dynamic";

import { WorkspaceSkeleton } from "@/components/shell/workspace-skeletons";
import type { AssignmentWorkspaceProps } from "./AssignmentWorkspace";
import type { InvitationDeliveryWorkspaceProps } from "./InvitationDeliveryWorkspace";
import type { InvitationsWorkspaceProps } from "./InvitationsWorkspace";

const DynamicInvitationsWorkspace = dynamic<InvitationsWorkspaceProps>(
  () => import("./InvitationsWorkspace").then((mod) => mod.InvitationsWorkspace),
  {
    loading: () => <WorkspaceSkeleton kind="split" label="Pregătim invitațiile" />,
    ssr: false,
  },
);

export function LazyInvitationsWorkspace(props: InvitationsWorkspaceProps) {
  return <DynamicInvitationsWorkspace {...props} />;
}

const DynamicAssignmentWorkspace = dynamic<AssignmentWorkspaceProps>(
  () => import("./AssignmentWorkspace").then((mod) => mod.AssignmentWorkspace),
  {
    loading: () => <WorkspaceSkeleton kind="table" label="Pregătim asignările" />,
    ssr: false,
  },
);

export function LazyAssignmentWorkspace(props: AssignmentWorkspaceProps) {
  return <DynamicAssignmentWorkspace {...props} />;
}

const DynamicInvitationDeliveryWorkspace = dynamic<InvitationDeliveryWorkspaceProps>(
  () => import("./InvitationDeliveryWorkspace").then((mod) => mod.InvitationDeliveryWorkspace),
  {
    loading: () => <WorkspaceSkeleton kind="table" label="Pregătim invitațiile" />,
    ssr: false,
  },
);

export function LazyInvitationDeliveryWorkspace(props: InvitationDeliveryWorkspaceProps) {
  return <DynamicInvitationDeliveryWorkspace {...props} />;
}
