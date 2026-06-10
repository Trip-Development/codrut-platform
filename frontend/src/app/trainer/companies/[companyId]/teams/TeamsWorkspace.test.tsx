import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { addCompanyTeamMembership, createCompanyTeam } from "@/api/companies";
import { TeamsWorkspace } from "./TeamsWorkspace";

vi.mock("@/api/companies", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/companies")>();
  return {
    ...original,
    addCompanyTeamMembership: vi.fn(),
    createCompanyTeam: vi.fn(),
  };
});

describe("TeamsWorkspace", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("creates teams and adds members through backend actions", async () => {
    vi.mocked(createCompanyTeam).mockResolvedValue({
      id: "team-1",
      company_id: "company-1",
      name: "Leadership septembrie",
      type: "leadership",
    });
    vi.mocked(addCompanyTeamMembership).mockResolvedValue({
      id: "membership-1",
      team_id: "team-1",
      participant_profile_id: "participant-1",
      role: "member",
    });

    render(
      <TeamsWorkspace
        companyId="company-1"
        initialTeams={[]}
        participants={[
          {
            id: "participant-1",
            full_name: "Ana Pop",
            email: "ana@example.com",
            reports_to_name: null,
            position: "Manager",
            location: "București",
            role_group: "leadership",
            pcm_profile: null,
            user_id: null,
          },
        ]}
        initialMembershipsByTeam={{}}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("Ex. Leadership septembrie"), {
      target: { value: "Leadership septembrie" },
    });
    fireEvent.change(screen.getByDisplayValue("Funcțională"), {
      target: { value: "leadership" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Adaugă" }));

    await waitFor(() =>
      expect(createCompanyTeam).toHaveBeenCalledWith("company-1", {
        name: "Leadership septembrie",
        type: "leadership",
      }),
    );
    const teamCard = await screen.findByRole("article");
    expect(within(teamCard).getByText("Leadership septembrie")).toBeTruthy();
    expect(within(teamCard).getByText("Niciun membru adăugat încă.")).toBeTruthy();

    fireEvent.click(within(teamCard).getByRole("button", { name: "Adaugă" }));

    await waitFor(() =>
      expect(addCompanyTeamMembership).toHaveBeenCalledWith("company-1", "team-1", {
        participantProfileId: "participant-1",
        role: "member",
      }),
    );
    expect(await within(teamCard).findByText("Ana Pop")).toBeTruthy();
  });
});
