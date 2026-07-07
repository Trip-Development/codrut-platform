import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  importCompanyRoster,
  updateCompanyParticipant,
  type CompanyParticipant,
  type CompanyProject,
  type ParticipantInvitationStatus,
} from "@/api/companies";
import {
  buildProjectParticipantAccessRows,
  ProjectParticipantsWorkspace,
} from "./ProjectParticipantsWorkspace";

vi.mock("@/api/companies", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/companies")>();
  return {
    ...original,
    importCompanyRoster: vi.fn(),
    updateCompanyParticipant: vi.fn(),
  };
});

const participants: CompanyParticipant[] = [
  {
    id: "manager-1",
    full_name: "Ana Manager",
    email: "ana.manager@example.test",
    reports_to_name: null,
    position: "Manager Operațional",
    location: "București",
    role_group: null,
    pcm_profile: null,
    user_id: null,
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

const project: CompanyProject = {
  id: "project-1",
  company_id: "company-1",
  company_name: "Michelin",
  name: "Leadership Septembrie",
  description: null,
  project_type: "team_coaching",
  status: "active",
  starts_at: null,
  due_at: null,
  form_opens_at: null,
  form_closes_at: null,
  created_at: "2026-06-11T09:00:00Z",
  updated_at: "2026-06-11T09:00:00Z",
};

describe("ProjectParticipantsWorkspace", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("derives permanent manager access and temporary secure-link access", () => {
    const rows = buildProjectParticipantAccessRows(participants, invitationStatuses);

    expect(rows[0]).toMatchObject({
      internalRoleLabel: "Manager / leadership",
      accountTypeLabel: "Cont permanent",
      accountStateLabel: "Cont de creat",
      deliveryLabel: "Nepregătit",
    });
    expect(rows[1]).toMatchObject({
      internalRoleLabel: "Membru",
      accountTypeLabel: "Acces temporar",
      accountStateLabel: "Fără cont permanent",
      deliveryLabel: "Link securizat activ",
    });
  });

  it("derives permanent manager access from compact reports-to keys", () => {
    const rows = buildProjectParticipantAccessRows(
      [
        participants[0],
        {
          ...participants[1],
          reports_to_name: "AnaManager",
        },
      ],
      [],
    );

    expect(rows[0]).toMatchObject({
      internalRoleLabel: "Manager / leadership",
      accountTypeLabel: "Cont permanent",
    });
    expect(rows[1]).toMatchObject({
      internalRoleLabel: "Membru",
      accountTypeLabel: "Acces temporar",
    });
  });

  it("shows the internal access tab with account type counts", () => {
    render(
      <ProjectParticipantsWorkspace
        companyId="company-1"
        projectId="project-1"
        companyName="Michelin"
        project={project}
        participants={participants}
        invitationStatuses={invitationStatuses}
      />,
    );

    expect(screen.getByText("cont permanent")).toBeTruthy();
    expect(screen.getByText("invitație temporară activă")).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "Acces intern" }));

    expect(screen.getAllByText("Cont permanent")).toHaveLength(2);
    expect(screen.getAllByText("Acces temporar")).toHaveLength(2);
    expect(screen.getByText("Ana Manager")).toBeTruthy();
    expect(screen.getByText("Dan Membru")).toBeTruthy();
    expect(screen.getByText("Link securizat activ")).toBeTruthy();
  });

  it("opens the roster import modal from the project header", () => {
    renderWorkspace();

    fireEvent.click(screen.getByRole("button", { name: "Importă participanți" }));

    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Închide" })).toBeTruthy();
  });

  it("keeps the roster read-only until a row is explicitly edited", async () => {
    vi.mocked(updateCompanyParticipant).mockResolvedValue({
      ...participants[1],
      full_name: "Dan Actualizat",
      email: "dan.actualizat@example.test",
      reports_to_name: "Ana Manager",
      position: "Consultant senior",
      location: "Cluj-Napoca",
      role_group: "member",
    });

    renderWorkspace();

    expect(screen.queryByDisplayValue("Dan Membru")).toBeNull();

    const row = screen.getByText("Dan Membru").closest("tr");
    expect(row).toBeTruthy();
    fireEvent.click(within(row as HTMLTableRowElement).getByRole("button", { name: "Editează" }));

    fireEvent.change(screen.getByDisplayValue("Dan Membru"), {
      target: { value: "Dan Actualizat" },
    });
    fireEvent.change(screen.getByDisplayValue("Consultant"), {
      target: { value: "Consultant senior" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvează" }));

    await waitFor(() =>
      expect(updateCompanyParticipant).toHaveBeenCalledWith("company-1", "member-1", {
        projectId: "project-1",
        fullName: "Dan Actualizat",
        email: "dan.membru@example.test",
        reportsToName: "Ana Manager",
        position: "Consultant senior",
        location: "Cluj-Napoca",
      }),
    );
    expect(await screen.findByText("Dan Actualizat")).toBeTruthy();
  });

  it("adds pasted participants through the roster import endpoint", async () => {
    vi.mocked(importCompanyRoster).mockResolvedValue({
      participants: [
        {
          ...participants[1],
          id: "member-2",
          full_name: "Ioana Nouă",
          email: "ioana@example.test",
          position: "Designer",
          reports_to_name: null,
        },
      ],
      email_results: [],
      total_imported: 1,
      emails_sent: 0,
      emails_failed: 0,
    });

    render(
      <ProjectParticipantsWorkspace
        companyId="company-1"
        projectId="project-1"
        companyName="Michelin"
        project={project}
        participants={[]}
        invitationStatuses={[]}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText(/Ana Popescu/), {
      target: { value: "Ioana Nouă, ioana@example.test, Designer, -" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvează participanții" }));

    await waitFor(() =>
    expect(importCompanyRoster).toHaveBeenCalledWith(
      "company-1",
        [
          {
            Name: "Ioana Nouă",
            "Reports To": "",
            Position: "Designer",
            Location: "",
            email: "ioana@example.test",
            "Profil PCM": "",
          },
        ],
        { projectId: "project-1" },
      ),
    );
    expect(await screen.findByText("Ioana Nouă")).toBeTruthy();
  });

  it("keeps existing participants visible when manual import returns only changed rows", async () => {
    vi.mocked(importCompanyRoster).mockResolvedValue({
      participants: [
        {
          ...participants[1],
          id: "member-2",
          full_name: "Ioana Nouă",
          email: "ioana@example.test",
          position: "Designer",
          reports_to_name: null,
        },
      ],
      email_results: [],
      total_imported: 1,
      emails_sent: 0,
      emails_failed: 0,
    });

    renderWorkspace();

    fireEvent.click(screen.getByRole("button", { name: "Adaugă manual" }));
    fireEvent.change(screen.getByPlaceholderText(/Ana Popescu/), {
      target: { value: "Ioana Nouă, ioana@example.test, Designer, -" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvează participanții" }));

    expect(await screen.findByText("Ioana Nouă")).toBeTruthy();
    expect(screen.getAllByText("Ana Manager").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Dan Membru")).toBeTruthy();
  });
});

function renderWorkspace() {
  render(
    <ProjectParticipantsWorkspace
      companyId="company-1"
      projectId="project-1"
      companyName="Michelin"
      project={project}
      participants={participants}
      invitationStatuses={invitationStatuses}
    />,
  );
}
