import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { CompanyParticipant } from "@/api/companies";
import { buildOrgChartModel } from "./org-chart-model";
import { OrgChartTree } from "./OrgChartTree";

describe("trainer project org chart", () => {
  afterEach(() => {
    cleanup();
  });

  it("promotes numeric manager markers to root nodes and orders executive roots first", () => {
    const model = buildOrgChartModel([
      participant("contributor", "Zed Contributor", { reports_to_name: null, position: "Specialist" }),
      participant("member", "Ana Analyst", { reports_to_name: "Mara CEO" }),
      participant("ceo", "Mara CEO", { reports_to_name: "001", position: "CEO" }),
      participant("lead", "Bogdan Lead", { reports_to_name: "Mara CEO" }),
    ]);

    expect(model.roots.map((root) => root.fullName)).toEqual(["Mara CEO", "Zed Contributor"]);
    expect(model.roots[0].children.map((child) => child.fullName)).toEqual(["Ana Analyst", "Bogdan Lead"]);
    expect(model.warnings).toEqual([]);
  });

  it("renders unresolved manager references in the warning panel instead of the tree", () => {
    const model = buildOrgChartModel([
      participant("ceo", "Mara CEO", { reports_to_name: null, position: "CEO" }),
      participant("orphan", "Ioana Orfan", { reports_to_name: "External Manager" }),
    ]);

    render(<OrgChartTree model={model} />);

    const warnings = screen.getByRole("region", { name: "Atenționări organigramă (1)" });
    expect(within(warnings).getByText("Ioana Orfan")).toBeTruthy();
    expect(within(warnings).getByText("External Manager")).toBeTruthy();

    const tree = screen.getByRole("list", { name: "Organigramă proiect" });
    expect(within(tree).getByText("Mara CEO")).toBeTruthy();
    expect(within(tree).queryByText("Ioana Orfan")).toBeNull();
    expect(within(tree).queryByText("External Manager")).toBeNull();
  });

  it("collapses dense branches while keeping the manager context visible", () => {
    const model = buildOrgChartModel([
      participant("ceo", "Mara CEO", { reports_to_name: null, position: "CEO" }),
      participant("lead", "Bogdan Lead", { reports_to_name: "Mara CEO" }),
      participant("member", "Ana Analyst", { reports_to_name: "Bogdan Lead" }),
    ]);

    render(<OrgChartTree model={model} />);

    expect(screen.getByText("Mara CEO")).toBeTruthy();
    expect(screen.getByText("Bogdan Lead")).toBeTruthy();
    expect(screen.getByText("Ana Analyst")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Ascunde raportorii pentru Mara CEO" }));

    expect(screen.getByText("Mara CEO")).toBeTruthy();
    expect(screen.getByText("2 raportori ascunși sub Mara CEO.")).toBeTruthy();
    expect(screen.queryByText("Bogdan Lead")).toBeNull();
    expect(screen.queryByText("Ana Analyst")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Arată raportorii pentru Mara CEO" }));

    expect(screen.getByText("Bogdan Lead")).toBeTruthy();
    expect(screen.getByText("Ana Analyst")).toBeTruthy();
  });
});

function participant(
  id: string,
  fullName: string,
  overrides: Partial<CompanyParticipant> = {},
): CompanyParticipant {
  return {
    id,
    full_name: fullName,
    email: `${id}@example.test`,
    reports_to_name: null,
    position: "Consultant",
    location: "București",
    role_group: null,
    pcm_profile: null,
    user_id: null,
    ...overrides,
  };
}
