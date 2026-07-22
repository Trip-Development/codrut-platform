import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { addCompanyTeamMembership, createCompanyTeam, type CompanyParticipant } from "@/api/companies";
import { deriveOrganizationTeams, TeamsWorkspace } from "./TeamsWorkspace";

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
    let resolveMembership!: (value: Awaited<ReturnType<typeof addCompanyTeamMembership>>) => void;
    vi.mocked(addCompanyTeamMembership).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveMembership = resolve;
        }),
    );

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

    expect(screen.getByLabelText("Tip echipă").getAttribute("data-slot")).toBe("select");

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
    expect(within(teamCard).getByLabelText("Participant pentru Leadership septembrie").getAttribute("data-slot")).toBe("select");
    expect(within(teamCard).getByLabelText("Rol în Leadership septembrie").getAttribute("data-slot")).toBe("select");

    const addMemberForm = within(teamCard).getByRole("button", { name: "Adaugă" }).closest("form");
    expect(addMemberForm).toBeTruthy();

    fireEvent.click(within(teamCard).getByRole("button", { name: "Adaugă" }));
    fireEvent.submit(addMemberForm!);

    expect((await within(teamCard).findByRole("status")).textContent).toContain("Adăugăm membrul");
    expect(addCompanyTeamMembership).toHaveBeenCalledTimes(1);

    await waitFor(() =>
      expect(addCompanyTeamMembership).toHaveBeenCalledWith("company-1", "team-1", {
        participantProfileId: "participant-1",
        role: "member",
      }),
    );

    await act(async () => {
      resolveMembership({
        id: "membership-1",
        team_id: "team-1",
        participant_profile_id: "participant-1",
        role: "member",
      });
    });

    expect(await within(teamCard).findByText("Ana Pop")).toBeTruthy();
  });

  it("shows a pending surface while creating a team", async () => {
    let resolveTeam!: (value: Awaited<ReturnType<typeof createCompanyTeam>>) => void;
    vi.mocked(createCompanyTeam).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveTeam = resolve;
        }),
    );

    render(
      <TeamsWorkspace
        companyId="company-1"
        initialTeams={[]}
        participants={[]}
        initialMembershipsByTeam={{}}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("Ex. Leadership septembrie"), {
      target: { value: "Leadership septembrie" },
    });
    const createTeamForm = screen.getByPlaceholderText("Ex. Leadership septembrie").closest("form");
    expect(createTeamForm).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Adaugă" }));
    fireEvent.submit(createTeamForm!);

    expect((await screen.findAllByText("Creăm echipa")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByPlaceholderText("Ex. Leadership septembrie").hasAttribute("disabled")).toBe(true);
    expect(createCompanyTeam).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveTeam({
        id: "team-1",
        company_id: "company-1",
        name: "Leadership septembrie",
        type: "functional",
      });
    });

    expect(await screen.findByText('Echipa "Leadership septembrie" a fost creată.')).toBeTruthy();
  });

  it("derives leadership and manager teams from roster relationships", () => {
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
      {
        id: "mihai",
        full_name: "Mihai Top",
        email: "mihai@example.com",
        reports_to_name: "Rădăcină",
        position: "Director",
        location: "Cluj",
        role_group: "leadership",
        pcm_profile: null,
        user_id: null,
      },
    ];

    const teams = deriveOrganizationTeams(participants, []);

    expect(teams.map((team) => team.name)).toEqual(["Leadership", "Echipa Andrei Manager"]);
    expect(teams.find((team) => team.name === "Echipa Andrei Manager")?.members.map((entry) => entry.participant.full_name)).toEqual([
      "Andrei Manager",
      "Ana Pop",
    ]);
  });

  it("uses roster-style manager keys for compact, punctuation, and diacritic references", () => {
    const participants: CompanyParticipant[] = [
      {
        id: "jerome",
        full_name: "Jérôme Tremblier - Matrix",
        email: "jerome@example.com",
        reports_to_name: null,
        position: "Matrix manager",
        location: "Paris",
        role_group: "leadership",
        pcm_profile: null,
        user_id: null,
      },
      {
        id: "ioana",
        full_name: "Ioana Pop",
        email: "ioana@example.com",
        reports_to_name: "JeromeTremblierMatrix",
        position: "Consultant",
        location: "București",
        role_group: "member",
        pcm_profile: null,
        user_id: null,
      },
      {
        id: "stefan",
        full_name: "Ștefan Lead",
        email: "stefan@example.com",
        reports_to_name: "JEROME TREMBLIER MATRIX",
        position: "Analyst",
        location: "Cluj",
        role_group: "member",
        pcm_profile: null,
        user_id: null,
      },
    ];

    const teams = deriveOrganizationTeams(participants, []);
    const matrixTeam = teams.find((team) => team.name === "Echipa Jérôme Tremblier - Matrix");

    expect(matrixTeam?.members.map((entry) => entry.participant.full_name)).toEqual([
      "Jérôme Tremblier - Matrix",
      "Ioana Pop",
      "Ștefan Lead",
    ]);
  });

  it("shows derived manager teams without persisting synthetic teams", () => {
    render(
      <TeamsWorkspace
        companyId="company-1"
        initialTeams={[
          {
            id: "leadership-team",
            company_id: "company-1",
            name: "Leadership",
            type: "leadership",
          },
        ]}
        participants={[
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
        ]}
        initialMembershipsByTeam={{ "leadership-team": [] }}
      />,
    );

    const derivedSection = screen.getByText("Structură din roster").closest("section");
    expect(derivedSection).toBeTruthy();
    expect(within(derivedSection as HTMLElement).getByText("Echipa Andrei Manager")).toBeTruthy();
    expect(within(derivedSection as HTMLElement).getAllByText("Ana Pop").length).toBeGreaterThan(0);
    expect(createCompanyTeam).not.toHaveBeenCalled();
  });
});
