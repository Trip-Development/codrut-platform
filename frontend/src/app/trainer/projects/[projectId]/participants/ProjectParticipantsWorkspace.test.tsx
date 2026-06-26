import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { CompanyParticipant, ParticipantInvitationStatus } from "@/api/companies";
import {
  buildProjectParticipantAccessRows,
  ProjectParticipantsWorkspace,
} from "./ProjectParticipantsWorkspace";

const participants: CompanyParticipant[] = [
  {
    id: "manager-1",
    full_name: "Ana Manager",
    email: "ana.manager@example.test",
    reports_to_name: null,
    position: "Manager Operațional",
    location: "București",
    role_group: "leadership",
    pcm_profile: null,
    user_id: "user-1",
  },
  {
    id: "member-1",
    full_name: "Dan Membru",
    email: "dan.membru@example.test",
    reports_to_name: "Ana Manager",
    position: "Consultant",
    location: "Cluj-Napoca",
    role_group: "member",
    pcm_profile: null,
    user_id: null,
  },
];

const invitationStatuses: ParticipantInvitationStatus[] = [
  {
    participant_id: "member-1",
    latest_delivery_mode: "secure_links",
    latest_email_status: null,
    latest_email_error: null,
    last_sent_at: "2026-06-26T07:00:00Z",
    email_send_count: 0,
    has_active_secure_link: true,
    active_secure_link_expires_at: "2026-07-03T07:00:00Z",
    active_secure_link_url: "https://codrut.example.test/invite/token",
  },
];

describe("ProjectParticipantsWorkspace", () => {
  afterEach(() => cleanup());

  it("derives permanent manager access and temporary secure-link access", () => {
    const rows = buildProjectParticipantAccessRows(participants, invitationStatuses);

    expect(rows[0]).toMatchObject({
      internalRoleLabel: "Manager / leadership",
      accountTypeLabel: "Cont permanent",
      accountStateLabel: "Cont creat",
      deliveryLabel: "Nepregătit",
    });
    expect(rows[1]).toMatchObject({
      internalRoleLabel: "Membru",
      accountTypeLabel: "Acces temporar",
      accountStateLabel: "Fără cont permanent",
      deliveryLabel: "Link securizat activ",
    });
  });

  it("shows the internal access tab with account type counts", () => {
    render(
      <ProjectParticipantsWorkspace
        participants={participants}
        invitationStatuses={invitationStatuses}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "Acces intern" }));

    expect(screen.getAllByText("Cont permanent")).toHaveLength(2);
    expect(screen.getAllByText("Acces temporar")).toHaveLength(2);
    expect(screen.getByText("Ana Manager")).toBeTruthy();
    expect(screen.getByText("Dan Membru")).toBeTruthy();
    expect(screen.getByText("Link securizat activ")).toBeTruthy();
  });
});
