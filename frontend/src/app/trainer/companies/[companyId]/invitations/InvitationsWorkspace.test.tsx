import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  AssessmentCycle,
  CompanyAssignment,
  CompanyAssignmentPlan,
  CompanyParticipant,
  CompanyProject,
  CompanyTeam,
  ParticipantInvitationStatus,
  RosterInviteResult,
} from "@/api/companies";
import {
  closeAssessmentCycle,
  CompanyMutationError,
  createAssessmentCycle,
  createCompanyAssignment,
  deleteAssessmentCycle,
  getAssessmentCycles,
  getCompanyAssignments,
  getCompanyDefaultAssignmentPlan,
  getCompanyInvitationStatuses,
  resendParticipantInvitation,
  saveCompanyDefaultAssignmentPlan,
  sendParticipantInvitations,
} from "@/api/companies";
import { listQuestionnaireDefinitionStubs } from "@/api/questionnaires";
import { AssignmentWorkspace, buildCyclePreviewPlan } from "./AssignmentWorkspace";
import {
  buildInvitationRows,
  InvitationDeliveryWorkspace,
} from "./InvitationDeliveryWorkspace";

vi.mock("@/api/companies", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/companies")>();
  return {
    ...original,
    closeAssessmentCycle: vi.fn(),
    createAssessmentCycle: vi.fn(),
    createCompanyAssignment: vi.fn(),
    deleteAssessmentCycle: vi.fn(),
    getAssessmentCycles: vi.fn(),
    getCompanyAssignments: vi.fn(),
    getCompanyDefaultAssignmentPlan: vi.fn(),
    getCompanyInvitationStatuses: vi.fn(),
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
    project_type: "team_coaching",
    status: "active",
    starts_at: null,
    due_at: null,
    form_opens_at: null,
    form_closes_at: null,
    created_at: "2026-06-11T09:00:00Z",
    updated_at: "2026-06-11T09:00:00Z",
  },
];

const assignments: CompanyAssignment[] = [
  {
    id: "assignment-1",
    company_id: "company-1",
    project_id: "project-1",
    assessment_cycle_id: "cycle-1",
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
    assessment_cycle_id: "cycle-1",
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

const initialCycle: AssessmentCycle = {
  id: "cycle-1",
  company_id: "company-1",
  project_id: "project-1",
  sequence: 1,
  name: "Evaluare inițială",
  status: "active",
  source_cycle_id: null,
  starts_at: "2026-06-11T09:00:00Z",
  due_at: null,
  closed_at: null,
  created_by_user_id: "trainer-1",
  created_at: "2026-06-11T09:00:00Z",
  updated_at: "2026-06-11T09:00:00Z",
  questionnaires: [
    {
      id: "cycle-questionnaire-1",
      questionnaire_definition_id: "definition-1",
      questionnaire_key: "lencioni",
      display_order: 0,
    },
  ],
};

describe("buildInvitationRows", () => {
  beforeEach(() => {
    vi.mocked(getAssessmentCycles).mockResolvedValue([initialCycle]);
    vi.mocked(getCompanyAssignments).mockResolvedValue(assignments);
    vi.mocked(getCompanyInvitationStatuses).mockResolvedValue(invitationStatuses);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("summarizes delivery, signup, and task state per company participant", () => {
    const rows = buildInvitationRows(participants, assignments, invitationStatuses, new Map());

    expect(rows[0]).toMatchObject({
      deliveryLabel: "Acceptat de furnizor",
      signedUp: true,
      completionLabel: "0/1",
    });
    expect(rows[1]).toMatchObject({
      deliveryLabel: "Pregătit, netrimis",
      signedUp: false,
      nextAction: "Trimite invitația",
    });
  });

  it("does not treat a secure-link shadow user as signed up", () => {
    const shadowParticipant: CompanyParticipant = {
      ...participants[1],
      user_id: "shadow-user",
      is_shadow_account: true,
    };

    const rows = buildInvitationRows(
      [shadowParticipant],
      assignments.filter((assignment) => assignment.respondent_profile_id === shadowParticipant.id),
      invitationStatuses,
      new Map(),
    );

    expect(rows[0]).toMatchObject({ signedUp: false });
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
      deliveryLabel: "Acceptat de furnizor",
      deliveryTone: "success",
    });
  });

  it("shows dispatching delivery as pending instead of sent", () => {
    const rows = buildInvitationRows(
      participants,
      assignments,
      [
        {
          ...invitationStatuses[0],
          participant_id: "ana",
          latest_email_status: "dispatching",
        },
      ],
      new Map(),
    );

    expect(rows[1]).toMatchObject({
      deliveryLabel: "Trimitere în curs",
      deliveryTone: "warning",
      deliveryState: "pending",
      nextAction: "În curs de trimitere",
    });
  });

  it("shows indeterminate delivery as an explicit reconciliation error", () => {
    const rows = buildInvitationRows(
      participants,
      assignments,
      [
        {
          ...invitationStatuses[0],
          participant_id: "ana",
          latest_email_status: "indeterminate",
          latest_email_error: null,
        },
      ],
      new Map(),
    );

    expect(rows[1]).toMatchObject({
      deliveryLabel: "Livrare neconfirmată",
      deliveryTone: "danger",
      deliveryState: "danger",
      deliveryError: "Verifică starea livrării înainte de retrimitere.",
      nextAction: "Verifică livrarea",
    });
  });

  it.each([
    ["queued", "Email în coadă", "warning", "pending"],
    ["accepted", "Acceptat de furnizor", "success", "success"],
    ["delivered", "Email livrat", "success", "success"],
    ["opened", "Email deschis", "success", "success"],
    ["clicked", "Link accesat", "success", "success"],
    ["failed", "Trimitere eșuată", "danger", "danger"],
    ["bounced", "Email respins", "danger", "danger"],
    ["cancelled", "Trimitere anulată", "danger", "danger"],
  ])("maps persisted %s delivery truthfully", (status, label, tone, state) => {
    const rows = buildInvitationRows(
      participants,
      assignments,
      [
        {
          ...invitationStatuses[0],
          participant_id: "ana",
          latest_email_status: status,
        },
      ],
      new Map(),
    );

    expect(rows[1]).toMatchObject({
      deliveryLabel: label,
      deliveryTone: tone,
      deliveryState: state,
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

  it("keeps assignment names collapsed until the task count is opened", () => {
    render(
      <InvitationDeliveryWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={assignments}
        invitationStatuses={invitationStatuses}
        initialAssessmentCycles={[initialCycle]}
        initialSelectedCycleId={initialCycle.id}
        teams={teams}
      />,
    );

    expect(screen.queryByText("Lencioni - evaluare echipă · autoevaluare")).toBeNull();
    const taskCounts = screen.getAllByRole("button", { name: "0/1 finalizate" });
    fireEvent.click(taskCounts[0]);

    expect(screen.getByText("Lencioni - evaluare echipă · autoevaluare")).toBeTruthy();
    expect(taskCounts[0].getAttribute("aria-expanded")).toBe("true");
  });

  it("keeps failed persisted deliveries in the error state without provider detail", () => {
    const rows = buildInvitationRows(
      participants,
      assignments,
      [
        {
          participant_id: "ana",
          latest_delivery_mode: "email",
          latest_email_status: "bounced",
          latest_email_error: null,
          last_sent_at: "2026-06-25T12:00:00Z",
          email_send_count: 1,
          has_active_secure_link: false,
          active_secure_link_expires_at: null,
          active_secure_link_url: null,
        },
      ],
      new Map(),
    );

    expect(rows[1]).toMatchObject({
      deliveryLabel: "Email respins",
      deliveryTone: "danger",
    });
  });

  it("creates an individual assignment with the existing backend payload", async () => {
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
      <AssignmentWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={[]}
        initialAssessmentCycles={[initialCycle]}
        initialSelectedCycleId={initialCycle.id}
        teams={teams}
      />,
    );

    expect(screen.queryByRole("heading", { name: "Livrare invitații" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Asignare individuală" }));
    await screen.findByRole("option", { name: "Boss 360" });

    expect(screen.getByLabelText("Respondent").getAttribute("data-slot")).toBe("select");

    fireEvent.change(screen.getByLabelText("Respondent"), { target: { value: "ana" } });
    fireEvent.click(screen.getByRole("button", { name: "Persoană" }));
    expect(screen.getByLabelText("Persoana evaluată").getAttribute("data-slot")).toBe("select");
    fireEvent.change(screen.getByLabelText("Persoana evaluată"), { target: { value: "andrei" } });
    fireEvent.click(screen.getByRole("button", { name: "Creează asignarea" }));

    await waitFor(() => {
      expect(createCompanyAssignment).toHaveBeenCalledWith("company-1", {
        projectId: "project-1",
        assessmentCycleId: "cycle-1",
        respondentProfileId: "ana",
        questionnaireKey: "boss_360",
        targetType: "person",
        targetPersonId: "andrei",
        targetTeamId: null,
      });
    });

    expect(await screen.findByText(/Asignare creată pentru Ana Pop/)).toBeTruthy();
    expect(screen.getByText("iCARE 360 pentru manager")).toBeTruthy();
    expect(screen.getByText("Andrei Manager")).toBeTruthy();
  });

  it("keeps individual assignment creation unavailable without participants", async () => {
    vi.mocked(listQuestionnaireDefinitionStubs).mockResolvedValue([]);

    render(
      <AssignmentWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={[]}
        assignments={[]}
        initialAssessmentCycles={[initialCycle]}
        initialSelectedCycleId={initialCycle.id}
        teams={[]}
      />,
    );

    const advancedButton = screen.getByRole("button", { name: "Asignare individuală" });
    expect(advancedButton.hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("heading", { name: "Plan de asignări" })).toBeTruthy();
    expect(screen.queryByText("Configurează asignările înainte de trimitere")).toBeNull();
  });

  it("offers plan regeneration after assignments already exist", async () => {
    vi.mocked(listQuestionnaireDefinitionStubs).mockResolvedValue([]);

    render(
      <AssignmentWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={assignments}
        initialAssessmentCycles={[initialCycle]}
        initialSelectedCycleId={initialCycle.id}
        teams={teams}
      />,
    );

    expect(screen.getByText("2 salvate")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Generează plan" })).toBeNull();
    expect(screen.getByRole("button", { name: "Regenerează planul" }).hasAttribute("disabled")).toBe(false);
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
      <AssignmentWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={[]}
        initialAssessmentCycles={[initialCycle]}
        initialSelectedCycleId={initialCycle.id}
        teams={teams}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Generează plan" }));

    const leadershipGroup = await screen.findByRole("region", { name: "Leadership" });
    expect(within(leadershipGroup).getByText("Echipă de leadership")).toBeTruthy();
    expect(within(leadershipGroup).getAllByText("2 asignări")).toHaveLength(2);
    const leadershipTarget = within(leadershipGroup).getByRole("region", {
      name: "Țintă Echipă: Leadership",
    });
    expect(within(leadershipTarget).getByText("Andrei Manager")).toBeTruthy();
    expect(within(leadershipTarget).getByText("Ana Pop")).toBeTruthy();
    expect(getCompanyDefaultAssignmentPlan).toHaveBeenCalledWith("company-1", {}, {
      projectId: "project-1",
      assessmentCycleId: "cycle-1",
    });
    expect(screen.getByText("Andrei Manager")).toBeTruthy();
    expect(screen.getByText("Ana Pop")).toBeTruthy();
    expect(screen.getAllByText("Lencioni - evaluare echipă")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "Generează plan" })).toBeNull();

    fireEvent.click(screen.getByLabelText("Selectează asignarea pentru Ana Pop"));
    fireEvent.click(screen.getByRole("button", { name: "Salvează 1 asignare" }));

    await waitFor(() => {
      expect(saveCompanyDefaultAssignmentPlan).toHaveBeenCalledWith("company-1", [
        expect.objectContaining({
          respondent_profile_id: "andrei",
          questionnaire_key: "lencioni",
          target_type: "team",
        }),
      ], "project-1", "cycle-1");
    });
    expect(await screen.findByText("1 create, 0 deja existente.")).toBeTruthy();
    expect(screen.getAllByText("Salvată").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: "Regenerează planul" }).hasAttribute("disabled")).toBe(false);
    expect(screen.queryByRole("button", { name: "Salvează 0 asignări" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Regenerează planul" }));
    await waitFor(() => expect(getCompanyDefaultAssignmentPlan).toHaveBeenCalledTimes(2));
  });

  it("separates self and person targets inside the same plan scope", async () => {
    vi.mocked(listQuestionnaireDefinitionStubs).mockResolvedValue([]);
    const groupedPlan: CompanyAssignmentPlan = {
      project_id: "project-1",
      scopes: [
        {
          id: "manager-andrei",
          name: "Andrei Manager",
          type: "manager",
          participant_ids: ["andrei", "ana"],
        },
      ],
      assignments: [
        {
          key: "manager-andrei:andrei:distress:self",
          scope_id: "manager-andrei",
          scope_name: "Andrei Manager",
          scope_type: "manager",
          respondent_profile_id: "andrei",
          respondent_name: "Andrei Manager",
          questionnaire_key: "distress_drivers",
          target_type: "self",
          target_person_id: null,
          target_person_name: null,
          target_team_id: null,
          target_team_name: null,
          target_team_type: null,
          target_team_member_ids: [],
          target_team_leader_id: null,
          visibility_policy: "trainer_raw_review",
          selected: true,
          existing_assignment_id: "saved-distress",
        },
        {
          key: "manager-andrei:andrei:pcm:self",
          scope_id: "manager-andrei",
          scope_name: "Andrei Manager",
          scope_type: "manager",
          respondent_profile_id: "andrei",
          respondent_name: "Andrei Manager",
          questionnaire_key: "pcm_base",
          target_type: "self",
          target_person_id: null,
          target_person_name: null,
          target_team_id: null,
          target_team_name: null,
          target_team_type: null,
          target_team_member_ids: [],
          target_team_leader_id: null,
          visibility_policy: "trainer_raw_review",
          selected: true,
          existing_assignment_id: null,
        },
        {
          key: "manager-andrei:ana:boss-360:person:andrei",
          scope_id: "manager-andrei",
          scope_name: "Andrei Manager",
          scope_type: "manager",
          respondent_profile_id: "ana",
          respondent_name: "Ana Pop",
          questionnaire_key: "boss_360",
          target_type: "person",
          target_person_id: "andrei",
          target_person_name: "Andrei Manager",
          target_team_id: null,
          target_team_name: null,
          target_team_type: null,
          target_team_member_ids: [],
          target_team_leader_id: null,
          visibility_policy: "trainer_raw_review",
          selected: true,
          existing_assignment_id: null,
        },
      ],
      suggested_count: 2,
      existing_count: 1,
    };
    vi.mocked(getCompanyDefaultAssignmentPlan).mockResolvedValue(groupedPlan);

    render(
      <AssignmentWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={assignments.slice(0, 1)}
        initialAssessmentCycles={[initialCycle]}
        initialSelectedCycleId={initialCycle.id}
        teams={teams}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Regenerează planul" }));

    const managerScope = await screen.findByRole("region", { name: "Andrei Manager" });
    const selfTarget = within(managerScope).getByRole("region", {
      name: "Țintă Autoevaluare: Andrei Manager",
    });
    const personTarget = within(managerScope).getByRole("region", {
      name: "Țintă Persoană: Andrei Manager",
    });

    expect(within(selfTarget).getByText("Driveri de stres TA")).toBeTruthy();
    expect(within(selfTarget).getByText("Baza și faza PCM")).toBeTruthy();
    expect(within(personTarget).getByText("Ana Pop")).toBeTruthy();
    expect(within(personTarget).getByText("iCARE 360 pentru manager")).toBeTruthy();
    expect(within(selfTarget).getAllByText("Grup").length).toBeGreaterThan(0);
    expect(within(selfTarget).getAllByLabelText("Selectează asignarea pentru Andrei Manager")[0]?.hasAttribute("disabled")).toBe(true);

    fireEvent.click(within(personTarget).getByLabelText("Selectează asignarea pentru Ana Pop"));
    expect(screen.getByRole("button", { name: "Salvează 1 asignare" })).toBeTruthy();
  });

  it("scopes assignment loading and plan generation to the selected assessment cycle", async () => {
    vi.mocked(listQuestionnaireDefinitionStubs).mockResolvedValue([]);
    vi.mocked(getAssessmentCycles).mockResolvedValue([initialCycle]);
    vi.mocked(getCompanyAssignments).mockResolvedValue(
      assignments.map((assignment) => ({ ...assignment, assessment_cycle_id: initialCycle.id })),
    );
    vi.mocked(getCompanyDefaultAssignmentPlan).mockResolvedValue({
      project_id: "project-1",
      assessment_cycle_id: initialCycle.id,
      scopes: [],
      assignments: [],
      suggested_count: 0,
      existing_count: 0,
    });

    render(
      <AssignmentWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={assignments}
        teams={teams}
      />,
    );

    await waitFor(() => {
      expect(getCompanyAssignments).toHaveBeenCalledWith("company-1", {}, {
        projectId: "project-1",
        assessmentCycleId: "cycle-1",
      });
    });
    fireEvent.click(screen.getByRole("button", { name: "Regenerează planul" }));
    await waitFor(() => {
      expect(getCompanyDefaultAssignmentPlan).toHaveBeenCalledWith("company-1", {}, {
        projectId: "project-1",
        assessmentCycleId: "cycle-1",
      });
    });
  });

  it("reviews the pinned questionnaire set before creating a follow-up draft", async () => {
    const closedCycle = { ...initialCycle, status: "closed" as const, closed_at: "2026-06-30T12:00:00Z" };
    const createdCycle: AssessmentCycle = {
      ...initialCycle,
      id: "cycle-2",
      sequence: 2,
      name: "Reevaluare 1",
      status: "draft",
      source_cycle_id: initialCycle.id,
      starts_at: null,
      closed_at: null,
    };
    vi.mocked(listQuestionnaireDefinitionStubs).mockResolvedValue([]);
    vi.mocked(getAssessmentCycles).mockResolvedValue([closedCycle]);
    vi.mocked(getCompanyAssignments).mockResolvedValue(
      assignments.map((assignment) => ({ ...assignment, assessment_cycle_id: closedCycle.id })),
    );
    const followupPreviewPlan = buildCyclePreviewPlan(
      assignments,
      new Map(participants.map((participant) => [participant.id, participant])),
      new Map(teams.map((team) => [team.id, team])),
    );
    expect(followupPreviewPlan.assignments).toHaveLength(2);
    vi.mocked(getCompanyDefaultAssignmentPlan).mockResolvedValue({
      ...followupPreviewPlan,
      assessment_cycle_id: null,
      source_cycle_id: closedCycle.id,
    });
    vi.mocked(createAssessmentCycle).mockResolvedValue(createdCycle);

    render(
      <AssignmentWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={assignments}
        initialAssessmentCycles={[closedCycle]}
        initialSelectedCycleId={closedCycle.id}
        teams={teams}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Reevaluare nouă" }));
    const previewContinue = screen.getByRole("button", { name: "Continuă" });
    await waitFor(() => expect(previewContinue.hasAttribute("disabled")).toBe(false));
    fireEvent.click(previewContinue);
    expect(await screen.findByText("Chestionare repetate")).toBeTruthy();
    await waitFor(() => {
      expect(getCompanyDefaultAssignmentPlan).toHaveBeenCalledWith("company-1", {}, {
        projectId: "project-1",
        sourceCycleId: "cycle-1",
      });
    });
    await waitFor(() => {
      expect(screen.getAllByText("Lencioni - evaluare echipă").length).toBeGreaterThanOrEqual(3);
    });
    const confirmationContinue = screen.getByRole("button", { name: "Continuă" });
    await waitFor(() => expect(confirmationContinue.hasAttribute("disabled")).toBe(false));
    fireEvent.click(confirmationContinue);
    const assignmentSummary = screen.getByText("Asignări propuse").parentElement;
    expect(assignmentSummary && within(assignmentSummary).getByText("2")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Creează draftul" }));

    await waitFor(() => {
      expect(createAssessmentCycle).toHaveBeenCalledWith("company-1", "project-1", {
        name: "Reevaluare 1",
        sourceCycleId: "cycle-1",
        dueAt: null,
      });
    });
    expect(await screen.findByText("Reevaluare 1 a fost creată ca draft.")).toBeTruthy();
  });

  it("closes an active cycle and makes its assignment plan read-only", async () => {
    const closedCycle = {
      ...initialCycle,
      status: "closed" as const,
      closed_at: "2026-07-22T12:00:00Z",
    };
    vi.mocked(closeAssessmentCycle).mockResolvedValue(closedCycle);

    render(
      <AssignmentWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={assignments}
        initialAssessmentCycles={[initialCycle]}
        initialSelectedCycleId={initialCycle.id}
        teams={teams}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Închide evaluarea" }));

    await waitFor(() => {
      expect(closeAssessmentCycle).toHaveBeenCalledWith("company-1", "project-1", "cycle-1");
    });
    expect(await screen.findByText("Evaluare inițială a fost închisă.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Asignare individuală" }).hasAttribute("disabled")).toBe(true);
  });

  it("confirms cancellation of unfinished assignments before forcing cycle close", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const closedCycle = {
      ...initialCycle,
      status: "closed" as const,
      closed_at: "2026-07-22T12:00:00Z",
    };
    vi.mocked(closeAssessmentCycle)
      .mockRejectedValueOnce(new CompanyMutationError(
        "Există asignări nefinalizate.",
        "assessment_cycle_has_unfinished_assignments",
      ))
      .mockResolvedValueOnce(closedCycle);

    render(
      <AssignmentWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={assignments}
        initialAssessmentCycles={[initialCycle]}
        initialSelectedCycleId={initialCycle.id}
        teams={teams}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Închide evaluarea" }));

    await waitFor(() => expect(closeAssessmentCycle).toHaveBeenCalledTimes(2));
    expect(closeAssessmentCycle).toHaveBeenLastCalledWith("company-1", "project-1", "cycle-1", true);
    expect(confirm).toHaveBeenCalledWith(
      "Evaluarea are asignări nefinalizate. Le anulezi și închizi evaluarea?",
    );
    expect(await screen.findByText("Evaluare inițială a fost închisă.")).toBeTruthy();
  });

  it("keeps a failed forced close recoverable and deletes only a confirmed draft", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(closeAssessmentCycle)
      .mockRejectedValueOnce(new CompanyMutationError(
        "Există asignări nefinalizate.",
        "assessment_cycle_has_unfinished_assignments",
      ))
      .mockRejectedValueOnce(new Error("Închiderea nu a putut fi salvată."));

    const { unmount } = render(
      <AssignmentWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={assignments}
        initialAssessmentCycles={[initialCycle]}
        initialSelectedCycleId={initialCycle.id}
        teams={teams}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Închide evaluarea" }));
    expect(await screen.findByText("Închiderea nu a putut fi salvată.")).toBeTruthy();
    unmount();

    const draftCycle = { ...initialCycle, status: "draft" as const, starts_at: null };
    vi.mocked(deleteAssessmentCycle).mockResolvedValue(undefined);
    render(
      <AssignmentWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={assignments}
        initialAssessmentCycles={[draftCycle]}
        initialSelectedCycleId={draftCycle.id}
        teams={teams}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Șterge draftul" }));

    await waitFor(() => {
      expect(deleteAssessmentCycle).toHaveBeenCalledWith("company-1", "project-1", "cycle-1");
    });
    expect(confirm).toHaveBeenLastCalledWith("Ștergi draftul „Evaluare inițială”?");
    expect(await screen.findByText("Draftul a fost șters.")).toBeTruthy();
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
      emails_queued: 0,
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
      <InvitationDeliveryWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={assignments}
        invitationStatuses={invitationStatuses}
        initialAssessmentCycles={[initialCycle]}
        initialSelectedCycleId={initialCycle.id}
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
        assessmentCycleId: "cycle-1",
        targetMode: "selected",
      });
    });
    expect(await screen.findByText("1/1 linkuri securizate generate.")).toBeTruthy();

    const copyButtons = await screen.findAllByRole("button", { name: "Copiază link" });
    fireEvent.click(copyButtons.at(-1)!);

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith("http://localhost:3000/invite/ana-token");
    });
    expect(await screen.findByText("Link securizat copiat pentru Ana Pop.")).toBeTruthy();
  });

  it("keeps invitation delivery scoped to the selected assessment cycle", async () => {
    vi.mocked(listQuestionnaireDefinitionStubs).mockResolvedValue([]);
    vi.mocked(getAssessmentCycles).mockResolvedValue([initialCycle]);
    vi.mocked(getCompanyAssignments).mockResolvedValue(
      assignments.map((assignment) => ({ ...assignment, assessment_cycle_id: initialCycle.id })),
    );
    vi.mocked(getCompanyInvitationStatuses).mockResolvedValue(invitationStatuses);
    vi.mocked(sendParticipantInvitations).mockResolvedValue({
      total: 1,
      emails_sent: 1,
      emails_failed: 0,
      links_generated: 0,
      results: [{
        participant_id: "ana",
        email: "ana@example.com",
        full_name: "Ana Pop",
        delivery_mode: "email",
        email_sent: true,
        error: null,
        invite_url: null,
      }],
    });

    render(
      <InvitationDeliveryWorkspace
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

    await waitFor(() => {
      expect(getCompanyInvitationStatuses).toHaveBeenCalledWith("company-1", {}, {
        projectId: "project-1",
        assessmentCycleId: "cycle-1",
      });
    });
    fireEvent.click(screen.getByLabelText("Selectează Ana Pop"));
    fireEvent.click(screen.getByRole("button", { name: "Trimite email invitații" }));
    await waitFor(() => {
      expect(sendParticipantInvitations).toHaveBeenCalledWith("company-1", {
        mode: "email",
        participantIds: ["ana"],
        projectId: "project-1",
        assessmentCycleId: "cycle-1",
        targetMode: "selected",
      });
    });
  });

  it("shows operation feedback while selected email invitations are pending", async () => {
    let resolveSend!: (value: Awaited<ReturnType<typeof sendParticipantInvitations>>) => void;
    vi.mocked(listQuestionnaireDefinitionStubs).mockResolvedValue([]);
    vi.mocked(sendParticipantInvitations).mockImplementation(
      () => new Promise((resolve) => {
        resolveSend = resolve;
      }),
    );

    render(
      <InvitationDeliveryWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={assignments}
        invitationStatuses={invitationStatuses}
        initialAssessmentCycles={[initialCycle]}
        initialSelectedCycleId={initialCycle.id}
        teams={teams}
      />,
    );

    fireEvent.click(screen.getByLabelText("Selectează Ana Pop"));
    expect(screen.getByRole("region", { name: "Acțiuni pentru persoanele selectate" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Plan de asignări" })).toBeNull();
    const selectedSendButton = screen.getByRole("button", { name: "Trimite email invitații" });
    fireEvent.click(selectedSendButton);
    fireEvent.click(selectedSendButton);

    expect(await screen.findByRole("button", { name: "Trimitem emailurile" })).toBeTruthy();
    expect(sendParticipantInvitations).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Trimite tuturor" })).toBeTruthy();
    expect((await screen.findByRole("status")).textContent).toContain("Trimitem emailurile selectate");
    expect(screen.getByText("1 persoane.")).toBeTruthy();

    await act(async () => {
      resolveSend({
        total: 1,
        emails_sent: 1,
        emails_failed: 0,
        links_generated: 0,
        results: [
          {
            participant_id: "ana",
            email: "ana@example.com",
            full_name: "Ana Pop",
            delivery_mode: "email",
            email_sent: true,
            error: null,
            invite_url: null,
          },
        ],
      });
    });

    expect(await screen.findByText("1 acceptate de furnizor, 0 în coadă, 0 eșuate.")).toBeTruthy();
  });

  it("shows queued API results immediately without claiming delivery", async () => {
    vi.mocked(listQuestionnaireDefinitionStubs).mockResolvedValue([]);
    vi.mocked(sendParticipantInvitations).mockResolvedValue({
      total: 1,
      emails_sent: 0,
      emails_queued: 1,
      emails_failed: 0,
      links_generated: 0,
      results: [
        {
          participant_id: "ana",
          email: "ana@example.com",
          full_name: "Ana Pop",
          delivery_mode: "email",
          email_sent: false,
          email_queued: true,
          error: null,
          invite_url: null,
        },
      ],
    });

    render(
      <InvitationDeliveryWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={assignments}
        invitationStatuses={invitationStatuses}
        initialAssessmentCycles={[initialCycle]}
        initialSelectedCycleId={initialCycle.id}
        teams={teams}
      />,
    );

    fireEvent.click(screen.getByLabelText("Selectează Ana Pop"));
    fireEvent.click(screen.getByRole("button", { name: "Trimite email invitații" }));

    expect(await screen.findByText("0 acceptate de furnizor, 1 în coadă, 0 eșuate.")).toBeTruthy();
    expect(screen.getByText("Email în coadă")).toBeTruthy();
    expect(screen.queryByText("Email trimis")).toBeNull();
  });

  it("marks only the all-email invitation action as pending", async () => {
    let resolveSend!: (value: Awaited<ReturnType<typeof sendParticipantInvitations>>) => void;
    vi.mocked(listQuestionnaireDefinitionStubs).mockResolvedValue([]);
    vi.mocked(sendParticipantInvitations).mockImplementation(
      () => new Promise((resolve) => {
        resolveSend = resolve;
      }),
    );

    render(
      <InvitationDeliveryWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={assignments}
        invitationStatuses={invitationStatuses}
        initialAssessmentCycles={[initialCycle]}
        initialSelectedCycleId={initialCycle.id}
        teams={teams}
      />,
    );

    const allSendButton = screen.getByRole("button", { name: "Trimite tuturor" });
    fireEvent.click(allSendButton);
    fireEvent.click(allSendButton);

    expect(await screen.findByRole("button", { name: "Trimitem tuturor" })).toBeTruthy();
    expect(sendParticipantInvitations).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Trimite email netrimișilor" })).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain("Trimitem emailurile tuturor");

    await act(async () => {
      resolveSend({
        total: 2,
        emails_sent: 2,
        emails_failed: 0,
        links_generated: 0,
        results: [
          {
            participant_id: "andrei",
            email: "andrei@example.com",
            full_name: "Andrei Manager",
            delivery_mode: "email",
            email_sent: true,
            error: null,
            invite_url: null,
          },
          {
            participant_id: "ana",
            email: "ana@example.com",
            full_name: "Ana Pop",
            delivery_mode: "email",
            email_sent: true,
            error: null,
            invite_url: null,
          },
        ],
      });
    });

    expect(await screen.findByText("2 acceptate de furnizor, 0 în coadă, 0 eșuate.")).toBeTruthy();
  });

  it("sends email invites to all participants with saved assignments from the invited people tab", async () => {
    vi.mocked(listQuestionnaireDefinitionStubs).mockResolvedValue([]);
    vi.mocked(sendParticipantInvitations).mockResolvedValue({
      total: 2,
      emails_sent: 2,
      emails_failed: 0,
      links_generated: 0,
      results: [
        {
          participant_id: "andrei",
          email: "andrei@example.com",
          full_name: "Andrei Manager",
          delivery_mode: "email",
          email_sent: true,
          error: null,
          invite_url: null,
        },
        {
          participant_id: "ana",
          email: "ana@example.com",
          full_name: "Ana Pop",
          delivery_mode: "email",
          email_sent: true,
          error: null,
          invite_url: null,
        },
      ],
    });

    render(
      <InvitationDeliveryWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={assignments}
        invitationStatuses={invitationStatuses}
        initialAssessmentCycles={[initialCycle]}
        initialSelectedCycleId={initialCycle.id}
        teams={teams}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Trimite tuturor" }));

    await waitFor(() => {
      expect(sendParticipantInvitations).toHaveBeenCalledWith("company-1", {
        mode: "email",
        participantIds: ["andrei", "ana"],
        projectId: "project-1",
        assessmentCycleId: "cycle-1",
        targetMode: "all",
      });
    });
    expect(await screen.findByText("2 acceptate de furnizor, 0 în coadă, 0 eșuate.")).toBeTruthy();
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
      <InvitationDeliveryWorkspace
        companyId="company-1"
        companyName="Michelin"
        projects={projects}
        selectedProjectId="project-1"
        participants={participants}
        assignments={assignments}
        invitationStatuses={invitationStatuses}
        initialAssessmentCycles={[initialCycle]}
        initialSelectedCycleId={initialCycle.id}
        teams={teams}
      />,
    );

    const resendButton = screen.getByRole("button", { name: "Retrimite" });
    fireEvent.click(resendButton);
    fireEvent.click(resendButton);

    await waitFor(() => {
      expect(resendParticipantInvitation).toHaveBeenCalledWith(
        "company-1",
        "ana",
        "project-1",
        { assessmentCycleId: "cycle-1" },
      );
    });
    expect(resendParticipantInvitation).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("Emailul nu a fost retrimis către ana@example.com: provider unavailable")).toBeTruthy();
    expect(screen.getByText("Trimitere eșuată")).toBeTruthy();
  });
});
