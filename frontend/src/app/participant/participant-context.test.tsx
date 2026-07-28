import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getParticipantWorkspaceSummary } from "@/api/participants";
import { ParticipantContextSelector } from "./ParticipantContextSelector";
import { ParticipantResultCycleControls } from "./ParticipantContextSelector";
import {
  participantScopeParams,
  participantScopedHref,
  participantWorkspaceRequestOptions,
} from "./participant-context";

const navigation = vi.hoisted(() => ({
  push: vi.fn(),
  pathname: "/participant/questionnaires",
  search: "source=menu",
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
  useRouter: () => ({ push: navigation.push }),
  useSearchParams: () => new URLSearchParams(navigation.search),
}));

describe("participant workspace context", () => {
  beforeEach(() => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    navigation.push.mockReset();
    delete process.env.CODRUT_FRONTEND_DEMO_FALLBACK;
    delete process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK;
  });

  it("sends the selected profile, project, and cycle to the backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        participant_profile_id: "profile-2",
        participant_full_name: "Ana Participant",
        participant_email: "ana@example.com",
        company_id: "company-1",
        company_name: "Atlas",
        project_id: "project-2",
        project_name: "Program avansat",
        assessment_cycle_id: "cycle-2",
        context_selection_required: false,
        contexts: [],
        cycles: [{
          id: "cycle-2",
          project_id: "project-2",
          sequence: 2,
          name: "Reevaluare 1",
          status: "active",
        }],
        projects: [],
        deadline_label: "15 august",
        tasks: [],
        results: [],
        received_feedback_groups: [],
        cards: [],
        empty_state: { title: "Fără sarcini", description: "" },
      }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const summary = await getParticipantWorkspaceSummary({
      participantProfileId: "profile-2",
      projectId: "project-2",
      cycleId: "cycle-2",
    });

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      "participant_profile_id=profile-2&project_id=project-2&cycle_id=cycle-2",
    );
    expect(summary).toMatchObject({
      participantProfileId: "profile-2",
      projectId: "project-2",
      assessmentCycleId: "cycle-2",
      cycles: [{ id: "cycle-2", name: "Reevaluare 1" }],
    });
  });

  it("keeps the selected context in participant route links", () => {
    const params = participantScopeParams({
      participantProfileId: "profile-1",
      projectId: "project-1",
      assessmentCycleId: "cycle-1",
    });
    expect(participantScopedHref("/participant/results", params)).toBe(
      "/participant/results?profile=profile-1&project=project-1&cycle=cycle-1",
    );
    expect(participantWorkspaceRequestOptions(undefined, {
      profile: ["profile-1", "ignored"],
      project: "project-1",
      cycle: "cycle-1",
    })).toMatchObject({
      participantProfileId: "profile-1",
      projectId: "project-1",
      cycleId: "cycle-1",
    });
  });

  it("shows one Program selector only when multiple programs exist", async () => {
    const contexts = [{
      participantProfileId: "profile-1",
      participantFullName: "Ana Participant",
      companyId: "company-1",
      companyName: "Atlas",
      projects: [
        { id: "project-1", name: "Program inițial", deadlineLabel: "1 august", cycles: [] },
        { id: "project-2", name: "Program avansat", deadlineLabel: "15 august", cycles: [{
          id: "cycle-2",
          projectId: "project-2",
          sequence: 2,
          name: "Reevaluare 1",
          status: "active" as const,
        }] },
      ],
    }];
    render(
      <ParticipantContextSelector
        contexts={contexts}
        selectedProfileId="profile-1"
        selectedProjectId="project-1"
      />,
    );

    fireEvent.click(screen.getByRole("combobox", { name: "Program" }));
    await waitFor(() => expect(screen.getByRole("searchbox", { name: "Caută în program" })).toBeDefined());
    fireEvent.click(screen.getByRole("option", { name: /Program avansat/ }));

    expect(navigation.push).toHaveBeenCalledWith(
      "/participant/questionnaires?source=menu&profile=profile-1&project=project-2&cycle=cycle-2",
    );
  });

  it("removes a stale cycle when switching to a program without cycles", async () => {
    navigation.search = "cycle=old&baseline=older&compare=old&source=menu";
    render(
      <ParticipantContextSelector
        contexts={[
          {
            participantProfileId: "profile-1",
            participantFullName: "Ana Participant",
            companyId: "company-1",
            companyName: "Atlas",
            projects: [{ id: "project-1", name: "Program inițial", deadlineLabel: "", cycles: [] }],
          },
          {
            participantProfileId: "profile-2",
            participantFullName: "Ana Participant",
            companyId: "company-2",
            companyName: "Meridian",
            projects: [{ id: "project-2", name: "Program nou", deadlineLabel: "", cycles: [] }],
          },
        ]}
        selectedProfileId="profile-1"
        selectedProjectId="project-1"
      />,
    );

    fireEvent.click(screen.getByRole("combobox", { name: "Program" }));
    await waitFor(() => expect(screen.getByRole("searchbox", { name: "Caută în program" })).toBeDefined());
    fireEvent.click(screen.getByRole("option", { name: /Meridian · Program nou/ }));

    const destination = String(navigation.push.mock.calls[0]?.[0]);
    expect(destination).toContain("profile=profile-2&project=project-2");
    expect(destination).not.toContain("cycle=");
    expect(destination).not.toContain("baseline=");
    expect(destination).not.toContain("compare=");
  });

  it("groups current programs separately from read-only history", async () => {
    render(
      <ParticipantContextSelector
        contexts={[{
          participantProfileId: "profile-1",
          participantFullName: "Ana Participant",
          companyId: "company-1",
          companyName: "Atlas",
          projects: [
            {
              id: "history-project",
              name: "Program finalizat",
              status: "completed",
              historyBucket: "history",
              deadlineLabel: "",
              cycles: [],
            },
            {
              id: "current-project",
              name: "Program curent",
              status: "active",
              historyBucket: "current",
              deadlineLabel: "",
              cycles: [],
            },
          ],
        }]}
        selectedProfileId="profile-1"
        selectedProjectId="current-project"
      />,
    );

    fireEvent.click(screen.getByRole("combobox", { name: "Program" }));

    expect(await screen.findByText("În desfășurare")).toBeDefined();
    expect(screen.getByText("Istoric")).toBeDefined();
    const options = screen.getAllByRole("option");
    expect(options[1]?.textContent).toContain("Program curent");
    expect(options[2]?.textContent).toContain("Program finalizat");
    fireEvent.keyDown(screen.getByRole("searchbox"), { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("searchbox")).toBeNull());
  });

  it("enters, changes, and closes a two-cycle comparison", async () => {
    navigation.search = "profile=profile-1&project=project-1";
    const cycles = [
      { id: "cycle-1", projectId: "project-1", sequence: 1, name: "Evaluare inițială", status: "closed" as const },
      { id: "cycle-2", projectId: "project-1", sequence: 2, name: "Reevaluare 1", status: "closed" as const },
      { id: "cycle-3", projectId: "project-1", sequence: 3, name: "Reevaluare 2", status: "active" as const },
    ];
    const { rerender } = render(
      <ParticipantResultCycleControls
        cycles={cycles}
        currentCycleId="cycle-2"
        canCompare
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Vezi evoluția" }));
    expect(navigation.push).toHaveBeenCalledWith(
      "/participant/questionnaires?profile=profile-1&project=project-1&baseline=cycle-1&compare=cycle-2&cycle=cycle-2",
    );

    navigation.push.mockReset();
    rerender(
      <ParticipantResultCycleControls
        cycles={cycles}
        currentCycleId="cycle-3"
        baselineCycleId="cycle-1"
        comparisonCycleId="cycle-3"
        canCompare
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Închide comparația" }));
    expect(navigation.push).toHaveBeenCalledWith(
      "/participant/questionnaires?profile=profile-1&project=project-1",
    );
  });

  it("hides context and comparison controls when they cannot change the view", () => {
    const { container, rerender } = render(
      <ParticipantContextSelector
        contexts={[{
          participantProfileId: "profile-1",
          participantFullName: "Ana Participant",
          companyId: "company-1",
          companyName: "Atlas",
          projects: [{ id: "project-1", name: "Program unic", deadlineLabel: "", cycles: [] }],
        }]}
        selectedProfileId="profile-1"
        selectedProjectId="project-1"
      />,
    );
    expect(container.childElementCount).toBe(0);

    rerender(
      <ParticipantResultCycleControls
        cycles={[{ id: "cycle-1", projectId: "project-1", sequence: 1, name: "Inițial", status: "active" }]}
        currentCycleId="cycle-1"
        canCompare={false}
      />,
    );
    expect(container.childElementCount).toBe(0);
  });
});
