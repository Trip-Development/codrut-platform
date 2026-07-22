"use client";

import { useEffect, useState } from "react";

import type {
  CompanyAssignment,
  CompanyParticipant,
  CompanyProject,
  CompanyTeam,
  ParticipantInvitationStatus,
} from "@/api/companies";
import { AssignmentWorkspace } from "./AssignmentWorkspace";
import { InvitationDeliveryWorkspace } from "./InvitationDeliveryWorkspace";

export type InvitationsWorkspaceProps = {
  companyId: string;
  companyName: string;
  projects: CompanyProject[];
  selectedProjectId: string | null;
  participants: CompanyParticipant[];
  assignments: CompanyAssignment[];
  invitationStatuses: ParticipantInvitationStatus[];
  teams: CompanyTeam[];
  mode?: "combined" | "assignments" | "invitations";
  showProjectSelector?: boolean;
};

export { buildInvitationRows } from "./InvitationDeliveryWorkspace";

export function InvitationsWorkspace({
  assignments,
  mode = "combined",
  ...props
}: InvitationsWorkspaceProps) {
  const [assignmentState, setAssignmentState] = useState(assignments);

  useEffect(() => {
    setAssignmentState(assignments);
  }, [assignments]);

  if (mode === "assignments") {
    return (
      <AssignmentWorkspace
        {...props}
        assignments={assignmentState}
        onAssignmentsChange={setAssignmentState}
      />
    );
  }

  if (mode === "invitations") {
    return <InvitationDeliveryWorkspace {...props} assignments={assignmentState} />;
  }

  return (
    <div className="flex flex-col gap-5">
      <InvitationDeliveryWorkspace {...props} assignments={assignmentState} />
      <AssignmentWorkspace
        {...props}
        assignments={assignmentState}
        onAssignmentsChange={setAssignmentState}
      />
    </div>
  );
}
