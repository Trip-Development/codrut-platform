import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AssessmentCycle, AssessmentCycleStatus } from "@/api/companies";
import { CycleComparisonControls } from "./CycleComparisonControls";

const navigation = vi.hoisted(() => ({
  push: vi.fn(),
  pathname: "/trainer/projects/project-1/reports",
  search: "cycle=cycle-2&baseline=cycle-1&compare=dimensions&source=menu",
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
  useRouter: () => ({ push: navigation.push }),
  useSearchParams: () => new URLSearchParams(navigation.search),
}));

function cycle(
  id: string,
  name: string,
  sequence: number,
  status: AssessmentCycleStatus,
): AssessmentCycle {
  return {
    id,
    company_id: "company-1",
    project_id: "project-1",
    sequence,
    name,
    status,
    source_cycle_id: null,
    starts_at: null,
    due_at: null,
    closed_at: null,
    created_by_user_id: null,
    created_at: "2026-07-01T00:00:00Z",
    updated_at: "2026-07-01T00:00:00Z",
    questionnaires: [],
  };
}

describe("CycleComparisonControls", () => {
  afterEach(() => {
    cleanup();
    navigation.push.mockReset();
  });

  it("labels cycle state clearly and removes stale comparison parameters", () => {
    render(
      <CycleComparisonControls
        cycles={[
          cycle("cycle-1", "Evaluare inițială", 1, "closed"),
          cycle("cycle-2", "Reevaluare", 2, "active"),
          cycle("cycle-3", "Evaluare viitoare", 3, "draft"),
        ]}
        cycleId="cycle-2"
      />,
    );

    fireEvent.click(screen.getByRole("combobox", { name: "Evaluare" }));

    expect(screen.getByRole("option", { name: "Evaluare inițială · Finalizată" })).toBeDefined();
    expect(screen.getByRole("option", { name: "Reevaluare · În desfășurare" })).toBeDefined();
    expect(screen.getByRole("option", { name: "Evaluare viitoare · În pregătire" })).toBeDefined();

    fireEvent.click(screen.getByRole("option", { name: "Evaluare inițială · Finalizată" }));

    expect(navigation.push).toHaveBeenCalledWith(
      "/trainer/projects/project-1/reports?cycle=cycle-1&source=menu",
    );
  });
});
