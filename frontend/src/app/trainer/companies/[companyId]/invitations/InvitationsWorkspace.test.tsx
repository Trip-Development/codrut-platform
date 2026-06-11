import { describe, expect, it } from "vitest";

import type { CompanyAssignment, CompanyParticipant, RosterInviteResult } from "@/api/companies";
import { buildInvitationRows } from "./InvitationsWorkspace";

const participants: CompanyParticipant[] = [
  {
    id: "andrei",
    full_name: "Andrei Manager",
    email: "andrei@example.com",
    reports_to_name: null,
    position: "Manager",
    location: "București",
    role_group: "leadership",
    pcm_profile: null,
    user_id: "user-1",
  },
  {
    id: "ana",
    full_name: "Ana Pop",
    email: "ana@example.com",
    reports_to_name: "Andrei Manager",
    position: "Consultant",
    location: "București",
    role_group: "member",
    pcm_profile: null,
    user_id: null,
  },
];

const assignments: CompanyAssignment[] = [
  {
    id: "assignment-1",
    company_id: "company-1",
    respondent_profile_id: "andrei",
    questionnaire_key: "lencioni",
    target_type: "self",
    status: "invited",
    submitted_at: null,
    scored_at: null,
  },
  {
    id: "assignment-2",
    company_id: "company-1",
    respondent_profile_id: "ana",
    questionnaire_key: "lencioni",
    target_type: "self",
    status: "assigned",
    submitted_at: null,
    scored_at: null,
  },
];

describe("buildInvitationRows", () => {
  it("summarizes delivery, signup, and task state per company participant", () => {
    const rows = buildInvitationRows(participants, assignments, new Map());

    expect(rows[0]).toMatchObject({
      deliveryLabel: "Invitație activă",
      signedUp: true,
      completionLabel: "0/1",
    });
    expect(rows[1]).toMatchObject({
      deliveryLabel: "Pregătit, netrimis",
      signedUp: false,
      nextAction: "Trimite invitația",
    });
  });

  it("uses fresh delivery results when an invite action runs in the current session", () => {
    const result: RosterInviteResult = {
      participant_id: "ana",
      email: "ana@example.com",
      full_name: "Ana Pop",
      delivery_mode: "email",
      email_sent: true,
      error: null,
      invite_url: null,
    };

    const rows = buildInvitationRows(participants, assignments, new Map([["ana", result]]));

    expect(rows[1]).toMatchObject({
      deliveryLabel: "Email trimis",
      deliveryTone: "success",
    });
  });
});
