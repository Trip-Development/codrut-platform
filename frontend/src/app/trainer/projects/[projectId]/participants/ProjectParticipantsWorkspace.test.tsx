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

  it("keeps a linked shadow account temporary while accepting a real linked account", () => {
    const rows = buildProjectParticipantAccessRows(
      [
        {
          ...participants[1],
          id: "shadow-member",
          role_group: "leadership",
          user_id: "shadow-user",
          is_shadow_account: true,
        },
        {
          ...participants[1],
          id: "permanent-member",
          full_name: "Mara Permanentă",
          user_id: "permanent-user",
          is_shadow_account: false,
        },
      ],
      [],
    );

    expect(rows[0]).toMatchObject({
      accountTypeLabel: "Acces temporar",
      accountStateLabel: "Fără cont permanent",
      hasAccount: false,
    });
    expect(rows[1]).toMatchObject({
      accountTypeLabel: "Cont permanent",
      accountStateLabel: "Cont creat",
      hasAccount: true,
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

  it("shows one compact summary and short access statuses", () => {
    renderWorkspace();

    const summary = screen.getByLabelText("Rezumat participanți");
    expect(summary.textContent).toContain("2 participanți");
    expect(summary.textContent).toContain("1 permanent");
    expect(summary.textContent).toContain("1 temporar");
    expect(summary.textContent).toContain("1 link activ");
    expect(screen.getByText("Permanent")).toBeTruthy();
    expect(screen.getByText("Temporar")).toBeTruthy();
    expect(screen.getByText("Cont de creat")).toBeTruthy();
    expect(screen.getByText("Link activ")).toBeTruthy();
  });

  it("uses a bounded roster surface with a stable-width table and horizontal scroller", () => {
    renderWorkspace();

    const rosterSurface = screen.getByRole("region", { name: "Registru participanți" });
    const roster = screen.getByRole("table", { name: "Roster participanți" });
    expect(rosterSurface.className).toContain("rounded-lg");
    expect(rosterSurface.className).toContain("overflow-hidden");
    expect(rosterSurface.contains(roster)).toBe(true);
    expect(roster.tagName).toBe("TABLE");
    expect(roster.className).toContain("min-w-[960px]");
    expect(roster.parentElement?.className).toContain("overflow-x-auto");
    expect(screen.getByLabelText("Caută participant").parentElement?.className).toContain(
      "basis-auto",
    );
    expect(screen.getByLabelText("Caută participant").parentElement?.className).toContain(
      "sm:basis-64",
    );
    expect(within(roster).getByRole("columnheader", { name: "Participant" })).toBeTruthy();
    expect(within(roster).getByRole("columnheader", { name: "Email" })).toBeTruthy();
    expect(within(roster).getByRole("columnheader", { name: "Acces" })).toBeTruthy();
    expect(within(roster).getByRole("columnheader", { name: "Stare" })).toBeTruthy();
  });

  it("combines diacritic-insensitive search with the access filter", () => {
    renderWorkspace();

    fireEvent.change(screen.getByLabelText("Caută participant"), {
      target: { value: "consultant" },
    });
    expect(screen.getByText("Dan Membru")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Ana Manager" })).toBeNull();

    fireEvent.change(screen.getByRole("combobox", { name: "Filtrează după acces" }), {
      target: { value: "permanent" },
    });
    expect(screen.getByText("Niciun participant pentru filtrele curente.")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Caută participant"), {
      target: { value: "" },
    });
    expect(screen.getByRole("link", { name: "Ana Manager" })).toBeTruthy();
    expect(screen.queryByText("Dan Membru")).toBeNull();

    fireEvent.change(screen.getByRole("combobox", { name: "Filtrează după acces" }), {
      target: { value: "temporary" },
    });
    expect(screen.getByText("Dan Membru")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Ana Manager" })).toBeNull();
  });

  it("opens the roster import modal from the project header", () => {
    renderWorkspace();

    fireEvent.click(screen.getByRole("button", { name: "Importă" }));

    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Închide" })).toBeTruthy();
  });

  it("closes the participant edit Sheet with Escape and restores focus", async () => {
    renderWorkspace();

    const editButton = screen.getByRole("button", { name: "Editează Dan Membru" });
    editButton.focus();
    fireEvent.click(editButton);

    expect(await screen.findByRole("dialog", { name: "Editează participantul" })).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Editează participantul" })).toBeNull();
      expect(document.activeElement).toBe(editButton);
    });
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
    expect(screen.getByRole("table", { name: "Roster participanți" })).toBeTruthy();

    const row = screen.getByText("Dan Membru").closest("[data-participant-row]");
    expect(row).toBeTruthy();
    const editButton = within(row as HTMLElement).getByRole("button", { name: "Editează Dan Membru" });
    expect(editButton.textContent).toBe("");
    expect(editButton.getAttribute("title")).toBe("Editează Dan Membru");
    fireEvent.click(editButton);

    const editSheet = await screen.findByRole("dialog", { name: "Editează participantul" });
    expect(editSheet.className).toContain("!max-w-[32rem]");

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
        roleGroup: "member",
      }),
    );
    expect(await screen.findByText("Dan Actualizat")).toBeTruthy();
    expect(screen.queryByRole("dialog", { name: "Editează participantul" })).toBeNull();
  });

  it("persists a manual project leadership override from the edit row", async () => {
    vi.mocked(updateCompanyParticipant).mockResolvedValue({
      ...participants[1],
      role_group: "leadership",
    });

    renderWorkspace();

    const row = screen.getByText("Dan Membru").closest("[data-participant-row]");
    expect(row).toBeTruthy();
    fireEvent.click(within(row as HTMLElement).getByRole("button", { name: "Editează Dan Membru" }));
    fireEvent.click(screen.getByRole("button", { name: "Leadership" }));
    fireEvent.click(screen.getByRole("button", { name: "Salvează" }));

    await waitFor(() =>
      expect(updateCompanyParticipant).toHaveBeenCalledWith("company-1", "member-1", expect.objectContaining({
        projectId: "project-1",
        roleGroup: "leadership",
      })),
    );
  });

  it("shows operation feedback while a participant edit is saving", async () => {
    const updateRequest = createDeferred<Awaited<ReturnType<typeof updateCompanyParticipant>>>();
    vi.mocked(updateCompanyParticipant).mockReturnValue(updateRequest.promise);

    renderWorkspace();

    const row = screen.getByText("Dan Membru").closest("[data-participant-row]");
    expect(row).toBeTruthy();
    fireEvent.click(within(row as HTMLElement).getByRole("button", { name: "Editează Dan Membru" }));
    const saveButton = screen.getByRole("button", { name: "Salvează" });
    fireEvent.click(saveButton);
    fireEvent.click(saveButton);

    expect(await screen.findByText("Salvăm Dan Membru")).toBeTruthy();
    expect(screen.getByText("Actualizăm datele participantului și refacem contextul proiectului.")).toBeTruthy();
    expect(updateCompanyParticipant).toHaveBeenCalledTimes(1);
    expect((screen.getByRole("button", { name: "Importă" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Adaugă" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("combobox", { name: "Filtrează după acces" }) as HTMLSelectElement).disabled).toBe(true);

    updateRequest.resolve({
      ...participants[1],
      full_name: "Dan Membru",
    });

    await waitFor(() => expect(screen.queryByText("Salvăm Dan Membru")).toBeNull());
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

    expect(screen.getByPlaceholderText(/Ana Popescu/).getAttribute("data-slot")).toBe("textarea");
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

  it("shows operation feedback while manual participants are being imported", async () => {
    const importRequest = createDeferred<Awaited<ReturnType<typeof importCompanyRoster>>>();
    vi.mocked(importCompanyRoster).mockReturnValue(importRequest.promise);

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
    const saveParticipantsButton = screen.getByRole("button", { name: "Salvează participanții" });
    fireEvent.click(saveParticipantsButton);
    fireEvent.click(saveParticipantsButton);

    expect((await screen.findAllByText("Salvăm participanții")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Actualizăm rosterul proiectului.")).toBeTruthy();
    expect(importCompanyRoster).toHaveBeenCalledTimes(1);
    expect((screen.getByRole("button", { name: "Importă" }) as HTMLButtonElement).disabled).toBe(true);

    importRequest.resolve({
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

    fireEvent.click(screen.getByRole("button", { name: "Adaugă" }));
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

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });

  return { promise, resolve, reject };
}
