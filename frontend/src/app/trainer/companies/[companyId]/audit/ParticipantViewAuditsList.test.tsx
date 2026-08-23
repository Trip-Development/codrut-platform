import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ParticipantViewAuditsList } from "./ParticipantViewAuditsList";

describe("ParticipantViewAuditsList", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders audit table with participant access logs and no delete buttons", () => {
    const audits = [
      {
        id: "audit-1",
        companyId: "company-100",
        trainerUserId: "trainer-1",
        trainerEmail: "trainer@example.com",
        participantProfileId: "participant-1",
        participantName: "Radu Participant",
        screen: "workspace",
        createdAt: "2026-08-23T10:00:00Z",
      },
    ];

    render(<ParticipantViewAuditsList companyId="company-100" audits={audits} />);

    expect(screen.getByText("Jurnal de acces: Vizualizări participanți")).toBeTruthy();
    expect(screen.getByText("Radu Participant")).toBeTruthy();
    expect(screen.getByText("trainer@example.com")).toBeTruthy();
    expect(screen.getByText("workspace")).toBeTruthy();
    expect(screen.getByText(/Înregistrat \(Read-only\)/i)).toBeTruthy();

    // Verify there are no delete buttons / forms anywhere
    expect(screen.queryByRole("button", { name: /șterge/i })).toBeNull();
  });

  it("renders empty state when there are no audits", () => {
    render(<ParticipantViewAuditsList companyId="company-100" audits={[]} />);

    expect(screen.getByText("Nu există accesări înregistrate")).toBeTruthy();
  });
});
