import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  CompanyAssignment,
  CompanyParticipant,
  CompanyProject,
  CompanyTeam,
  ParticipantInvitationStatus,
  RosterInviteResult,
} from "@/api/companies";
import {
  createCompanyAssignment,
  getCompanyDefaultAssignmentPlan,
  resendParticipantInvitation,
  saveCompanyDefaultAssignmentPlan,
  sendParticipantInvitations,
} from "@/api/companies";
import { listQuestionnaireDefinitionStubs } from "@/api/questionnaires";
import { buildInvitationRows, InvitationsWorkspace } from "./InvitationsWorkspace";

vi.mock("@/api/companies", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/companies")>();
  return {
    ...original,
    createCompanyAssignment: vi.fn(),
    getCompanyDefaultAssignmentPlan: vi.fn(),
    saveCompanyDefaultAssignmentPlan: vi.fn(),
    sendParticipantInvitations: vi.fn(),
    resendParticipantInvitation: vi.fn(),
  };
});

vi.mock("@/api/questionnaires", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/questionnaires")>();
  return {
    ...original,
    listQuestionnaireDefinitionStubs: vi.fn(),
  };
});

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

const projects: CompanyProject[] = [
  {
    id: "project-1",
    company_id: "company-1",
    name: "Leadership Septembrie",
    description: null,
    status: "active",
    starts_at: null,
    due_at: null,
    created_at: "2026-06-11T09:00:00Z",
    updated_at: "2026-06-11T09:00:00Z",
  },
];

const assignments: CompanyAssignment[] = [
  {
    id: "assignment-1",
    company_id: "company-1",
    project_id: "project-1",
    respondent_profile_id: "andrei",
    questionnaire_key: "lencioni",
    target_type: "self",
    target_person_id: null,
    target_team_id: null,
    status: "invited",
    submitted_at: null,
    scored_at: null,
  },
  {
    id: "assignment-2",
    company_id: "company-1",
    project_id: "project-1",
    respondent_profile_id: "ana",
    questionnaire_key: "lencioni",
    target_type: "self",
    target_person_id: null,
    target_team_id: null,
    status: "assigned",
    submitted_at: null,
    scored_at: null,
  },
];

const teams: CompanyTeam[] = [
  {
    id: "team-1",
    company_id: "company-1",
    name: "Leadership",
    type: "leadership",
  },
];

const invitationStatuses: ParticipantInvitationStatus[] = [
  {
    participant_id: "andrei",
    latest_delivery_mode: "email",
    latest_email_status: "accepted",
    latest_email_error: null,
    last_sent_at: "2026-06-11T12:00:00Z",
    email_send_count: 1,
    has_active_secure_link: true,
    active_secure_link_expires_at: "2026-06-25T12:00:00Z",
    active_secure_link_url: "http://localhost:3000/invite/andrei",
  },
];

describe("buildInvitationRows", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("summarizes delivery, signup, and task state per company participant", () => {
    const rows = buildInvitationRows(participants, assignments, invitationStatuses, new Map());

    expect(rows[0]).toMatchObject({
      deliveryLabel: "Email trimis",
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

    const rows = buildInvitationRows(participants, assignments, invitationStatuses, new Map([["ana", result]]));

    expect(rows[1]).toMatchObject({
      deliveryLabel: "Email trimis",
      deliveryTone: "success",
    });
  });

  it("uses persisted secure-link status when no email send exists", () => {
    const rows = buildInvitationRows(
      participants,
      assignments,
      [
        {
          participant_id: "ana",
          latest_delivery_mode: "secure_links",
          latest_email_status: null,
          latest_email_error: null,
          last_sent_at: null,
          email_send_count: 0,
          has_active_secure_link: true,
          active_secure_link_expires_at: "2026-06-25T12:00:00Z",
          active_secure_link_url: "http://localhost:3000/invite/ana",
        },
      ],
      new Map(),
    );

    expect(rows[1]).toMatchObject({
      deliveryLabel: "Link securizat activ",
      deliveryTone: "success",
      secureLinkUrl: "http://localhost:3000/invite/ana",
    });
  });

  it("creates a company assignment and updates the delivery table", async () => {
    vi.mocked(listQuestionnaireDefinitionStubs).mockResolvedValue([
      {
        id: "boss_360",
        name: "Boss 360",
        description: "Feedback pentru manager.",
        status: "active",
        version: 1,
        audience: "participant",
      },
    ]);
    vi.mocked(createCompanyAssignment).mockResolvedValue({
      id: "assignment-3",
      company_id: "company-1",
      project_id: "project-1",
      respondent_profile_id: "ana",
      questionnaire_key: "boss_360",
      target_type: "person",
      target_person_id: "andrei",
      target_team_id: null,
      status: "assigned",
      submitted_at: null,
      scored_at: null,
    });

    render(
      <InvitationsWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={[]}
        invitationStatuses={[]}
        teams={teams}
      />,
    );

    await screen.findByRole("option", { name: "Boss 360" });

    fireEvent.change(screen.getByLabelText("Persoană"), { target: { value: "ana" } });
    fireEvent.click(screen.getByRole("button", { name: /^Persoană/ }));
    fireEvent.change(screen.getByLabelText("Persoana evaluată"), { target: { value: "andrei" } });
    fireEvent.click(screen.getByRole("button", { name: "Creează asignarea" }));

    await waitFor(() => {
      expect(createCompanyAssignment).toHaveBeenCalledWith("company-1", {
        projectId: "project-1",
        respondentProfileId: "ana",
        questionnaireKey: "boss_360",
        targetType: "person",
        targetPersonId: "andrei",
        targetTeamId: null,
      });
    });

    expect(await screen.findByText(/Asignare creată pentru Ana Pop/)).toBeTruthy();
    expect(screen.getByText("Feedback 360 iCARE · despre Andrei Manager")).toBeTruthy();
  });

  it("generates a default assignment plan and saves only selected rows", async () => {
    vi.mocked(listQuestionnaireDefinitionStubs).mockResolvedValue([]);
    vi.mocked(getCompanyDefaultAssignmentPlan).mockResolvedValue({
      project_id: "project-1",
      scopes: [
        {
          id: "leadership",
          name: "Leadership",
          type: "leadership_team",
          participant_ids: ["andrei", "ana"],
        },
      ],
      assignments: [
        {
          key: "leadership:andrei:lencioni:team:Leadership",
          scope_id: "leadership",
          scope_name: "Leadership",
          scope_type: "leadership_team",
          respondent_profile_id: "andrei",
          respondent_name: "Andrei Manager",
          questionnaire_key: "lencioni",
          target_type: "team",
          target_person_id: null,
          target_person_name: null,
          target_team_id: null,
          target_team_name: "Leadership",
          target_team_type: "leadership",
          target_team_member_ids: ["andrei", "ana"],
          target_team_leader_id: null,
          visibility_policy: "trainer_raw_review",
          selected: true,
          existing_assignment_id: null,
        },
        {
          key: "leadership:ana:lencioni:team:Leadership",
          scope_id: "leadership",
          scope_name: "Leadership",
          scope_type: "leadership_team",
          respondent_profile_id: "ana",
          respondent_name: "Ana Pop",
          questionnaire_key: "lencioni",
          target_type: "team",
          target_person_id: null,
          target_person_name: null,
          target_team_id: null,
          target_team_name: "Leadership",
          target_team_type: "leadership",
          target_team_member_ids: ["andrei", "ana"],
          target_team_leader_id: null,
          visibility_policy: "trainer_raw_review",
          selected: true,
          existing_assignment_id: null,
        },
      ],
      suggested_count: 2,
      existing_count: 0,
    });
    vi.mocked(saveCompanyDefaultAssignmentPlan).mockResolvedValue({
      created_count: 1,
      existing_count: 0,
      assignments: [
        {
          id: "assignment-3",
          company_id: "company-1",
          project_id: "project-1",
          respondent_profile_id: "andrei",
          questionnaire_key: "lencioni",
          target_type: "team",
          target_person_id: null,
          target_team_id: null,
          status: "assigned",
          submitted_at: null,
          scored_at: null,
        },
      ],
    });

    render(
      <InvitationsWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={[]}
        invitationStatuses={[]}
        teams={teams}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Generează plan de asignări" }));

    expect(await screen.findAllByText("Leadership")).toHaveLength(3);
    expect(getCompanyDefaultAssignmentPlan).toHaveBeenCalledWith("company-1", {}, { projectId: "project-1" });
    expect(screen.getAllByText("Andrei Manager").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Ana Pop").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Lencioni - evaluare echipă")).toHaveLength(2);

    fireEvent.click(screen.getByLabelText("Selectează asignarea pentru Ana Pop"));
    fireEvent.click(screen.getByRole("button", { name: "Salvează asignările bifate (1)" }));

    await waitFor(() => {
      expect(saveCompanyDefaultAssignmentPlan).toHaveBeenCalledWith("company-1", [
        expect.objectContaining({
          respondent_profile_id: "andrei",
          questionnaire_key: "lencioni",
          target_type: "team",
        }),
      ], "project-1");
    });
    expect(await screen.findByText("1 asignări create, 0 deja existente.")).toBeTruthy();
    expect(screen.getByText("Lencioni - evaluare echipă · echipa selectată")).toBeTruthy();
  });

  it("generates secure links, updates participant rows, and copies the active link", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    vi.mocked(listQuestionnaireDefinitionStubs).mockResolvedValue([]);
    vi.mocked(sendParticipantInvitations).mockResolvedValue({
      total: 1,
      emails_sent: 0,
      emails_failed: 0,
      links_generated: 1,
      results: [
        {
          participant_id: "ana",
          email: "ana@example.com",
          full_name: "Ana Pop",
          delivery_mode: "secure_links",
          email_sent: false,
          error: null,
          invite_url: "http://localhost:3000/invite/ana-token",
        },
      ],
    });

    render(
      <InvitationsWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={assignments}
        invitationStatuses={invitationStatuses}
        teams={teams}
      />,
    );

    fireEvent.click(screen.getByLabelText("Selectează Ana Pop"));
    fireEvent.click(screen.getByRole("button", { name: "Generează linkuri securizate" }));

    await waitFor(() => {
      expect(sendParticipantInvitations).toHaveBeenCalledWith("company-1", {
        mode: "secure_links",
        participantIds: ["ana"],
        projectId: "project-1",
      });
    });
    expect(await screen.findByText("1/1 linkuri securizate generate pentru persoanele selectate.")).toBeTruthy();

    const copyButtons = await screen.findAllByRole("button", { name: "Copiază link" });
    fireEvent.click(copyButtons.at(-1)!);

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith("http://localhost:3000/invite/ana-token");
    });
    expect(await screen.findByText("Link securizat copiat pentru Ana Pop.")).toBeTruthy();
  });

  it("resends one participant invitation and surfaces backend delivery failures", async () => {
    vi.mocked(listQuestionnaireDefinitionStubs).mockResolvedValue([]);
    vi.mocked(resendParticipantInvitation).mockResolvedValue({
      participant_id: "ana",
      email: "ana@example.com",
      full_name: "Ana Pop",
      delivery_mode: "email",
      email_sent: false,
      error: "provider unavailable",
      invite_url: null,
    });

    render(
      <InvitationsWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={assignments}
        invitationStatuses={invitationStatuses}
        teams={teams}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Retrimite" }));

    await waitFor(() => {
      expect(resendParticipantInvitation).toHaveBeenCalledWith("company-1", "ana", "project-1");
    });
    expect(await screen.findByText("Emailul nu a fost retrimis către ana@example.com: provider unavailable")).toBeTruthy();
    expect(screen.getByText("Eroare trimitere")).toBeTruthy();
  });
});
