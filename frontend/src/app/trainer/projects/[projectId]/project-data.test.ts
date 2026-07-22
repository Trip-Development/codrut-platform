import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getAssessmentCycles: vi.fn(),
  getCompanyAssignments: vi.fn(),
  getCompanyInvitationStatuses: vi.fn(),
  getCompanyProjectById: vi.fn(),
  getCompanyReportAggregate: vi.fn(),
  getCompanyTeams: vi.fn(),
  getProjectParticipants: vi.fn(),
}));

vi.mock("@/api/companies", () => api);
vi.mock("next/navigation", () => ({ notFound: vi.fn() }));

import {
  getProjectAssignmentWorkspaceData,
  getProjectAssessmentCyclesData,
  getProjectInvitationWorkspaceData,
  getProjectReportAggregateData,
  getProjectReportWorkspaceData,
  resolveProjectAssessmentCycle,
} from "./project-data";

const requestOptions = { headers: { cookie: "session=test" } };
const project = {
  id: "project-1",
  company_id: "company-1",
  name: "Program leadership",
};
const assessmentCycles = [
  { id: "cycle-1", name: "Evaluare initiala" },
  { id: "cycle-2", name: "Reevaluare 1" },
];

describe("project report data", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getCompanyProjectById.mockResolvedValue(project);
    api.getAssessmentCycles.mockResolvedValue(assessmentCycles);
    api.getCompanyAssignments.mockResolvedValue([]);
    api.getCompanyReportAggregate.mockResolvedValue({ questionnaire_count: 0 });
    api.getProjectParticipants.mockResolvedValue([]);
    api.getCompanyTeams.mockResolvedValue([]);
    api.getCompanyInvitationStatuses.mockResolvedValue([]);
  });

  it("resolves an explicit cycle, then the latest open cycle, then the latest historical cycle", () => {
    const cycles = [
      { id: "cycle-1", sequence: 1, status: "closed" },
      { id: "cycle-2", sequence: 2, status: "active" },
      { id: "cycle-3", sequence: 3, status: "closed" },
    ] as never[];
    expect(resolveProjectAssessmentCycle(cycles, "cycle-1")?.id).toBe("cycle-1");
    expect(resolveProjectAssessmentCycle(cycles, "missing")?.id).toBe("cycle-2");
    expect(resolveProjectAssessmentCycle(cycles.slice(0, 1))?.id).toBe("cycle-1");
    expect(resolveProjectAssessmentCycle([])).toBeNull();
  });

  it("loads assignment and invitation workspaces against the resolved cycle", async () => {
    api.getAssessmentCycles.mockResolvedValue([
      { id: "cycle-1", sequence: 1, status: "closed" },
      { id: "cycle-2", sequence: 2, status: "active" },
    ]);

    const assignmentData = await getProjectAssignmentWorkspaceData(project.id, requestOptions, {
      assessmentCycleId: "missing",
    });
    const invitationData = await getProjectInvitationWorkspaceData(project.id, requestOptions, {
      assessmentCycleId: "cycle-1",
    });
    const cycleData = await getProjectAssessmentCyclesData(project.id, requestOptions);

    expect(assignmentData.selectedAssessmentCycleId).toBe("cycle-2");
    expect(api.getCompanyAssignments).toHaveBeenNthCalledWith(1, project.company_id, requestOptions, {
      projectId: project.id,
      assessmentCycleId: "cycle-2",
    });
    expect(invitationData.selectedAssessmentCycleId).toBe("cycle-1");
    expect(api.getCompanyInvitationStatuses).toHaveBeenCalledWith(project.company_id, requestOptions, {
      projectId: project.id,
      assessmentCycleId: "cycle-1",
    });
    expect(cycleData).toMatchObject({ project, assessmentCycles: expect.any(Array) });
  });

  it("scopes aggregate report data to the selected assessment cycle", async () => {
    const result = await getProjectReportAggregateData(
      project.id,
      requestOptions,
      { assessmentCycleId: "cycle-2" },
    );

    expect(api.getCompanyReportAggregate).toHaveBeenCalledWith(
      project.company_id,
      requestOptions,
      { projectId: project.id, assessmentCycleId: "cycle-2" },
    );
    expect(api.getAssessmentCycles).toHaveBeenCalledWith(
      project.company_id,
      project.id,
      requestOptions,
    );
    expect(result.assessmentCycles).toBe(assessmentCycles);
  });

  it("scopes report assignments and aggregate while preserving the legacy default", async () => {
    const selected = await getProjectReportWorkspaceData(
      project.id,
      requestOptions,
      { assessmentCycleId: "cycle-2" },
    );

    expect(api.getCompanyAssignments).toHaveBeenLastCalledWith(
      project.company_id,
      requestOptions,
      { projectId: project.id, assessmentCycleId: "cycle-2" },
    );
    expect(api.getCompanyReportAggregate).toHaveBeenLastCalledWith(
      project.company_id,
      requestOptions,
      { projectId: project.id, assessmentCycleId: "cycle-2" },
    );
    expect(selected.assessmentCycles).toBe(assessmentCycles);

    await getProjectReportWorkspaceData(project.id, requestOptions);

    expect(api.getCompanyAssignments).toHaveBeenLastCalledWith(
      project.company_id,
      requestOptions,
      { projectId: project.id, assessmentCycleId: undefined },
    );
    expect(api.getCompanyReportAggregate).toHaveBeenLastCalledWith(
      project.company_id,
      requestOptions,
      { projectId: project.id, assessmentCycleId: undefined },
    );
  });
});
