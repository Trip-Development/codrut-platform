import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CycleComparisonBars, CycleDistributionPies } from "./CycleComparisonBars";

describe("CycleComparisonBars", () => {
  it("plots cycles on one shared scale while keeping every value available as text", () => {
    const { container } = render(
      <CycleComparisonBars
        title="Evoluție"
        max={100}
        suffix="%"
        deltaUnit="pp"
        higherIsBetter
        rows={[{
          id: "trust",
          label: "Încredere",
          values: [
            { cycleId: "one", cycleLabel: "Evaluare inițială", color: "red", value: 62 },
            { cycleId: "two", cycleLabel: "Reevaluare", color: "gold", value: 74 },
          ],
        }]}
      />,
    );

    expect(screen.getByRole("heading", { name: "Evoluție" })).toBeTruthy();
    expect(screen.getByText("Evaluare inițială")).toBeTruthy();
    expect(screen.getByText("62%")).toBeTruthy();
    expect(screen.getByText("Reevaluare")).toBeTruthy();
    expect(screen.getByText("74%")).toBeTruthy();

    const plot = container.querySelector("[data-cycle-comparison-plot]");
    const lines = container.querySelectorAll("[data-cycle-line]");
    const markers = container.querySelectorAll("[data-cycle-marker]");

    expect(plot).toBeTruthy();
    expect(lines).toHaveLength(2);
    expect(markers).toHaveLength(0);
    expect(lines[0].getAttribute("style")).toContain("width: 62%");
    expect(lines[1].getAttribute("style")).toContain("width: 74%");
    expect(lines[0].className).toContain("rounded-full");
    expect(screen.getByText("+12 pp").className).toContain("text-emerald-500");
  });

  it("treats a lower stress-driver score as improvement", () => {
    render(
      <CycleComparisonBars
        title="TA Drivers"
        max={100}
        suffix="%"
        deltaUnit="pp"
        higherIsBetter={false}
        rows={[{
          id: "perfect",
          label: "Fii perfect",
          values: [
            { cycleId: "one", cycleLabel: "Evaluare inițială", color: "#dc3f43", value: 70 },
            { cycleId: "two", cycleLabel: "Reevaluare", color: "#3b82f6", value: 55 },
          ],
        }]}
      />,
    );

    expect(screen.getByText("-15 pp").className).toContain("text-emerald-500");
  });

  it("keeps the short driver status visible and the full interpretation available on demand", () => {
    render(
      <CycleComparisonBars
        title="TA Drivers"
        max={100}
        suffix="%"
        rows={[{
          id: "perfect",
          label: "Fii perfect",
          note: "Pe scurt: standarde foarte ridicate.\n\nStresori probabili: pierderea controlului.",
          values: [{
            cycleId: "one",
            cycleLabel: "Evaluare inițială",
            color: "red",
            value: 70,
            status: "watch",
          }],
        }]}
      />,
    );

    expect(screen.getByText("De urmărit")).toBeTruthy();
    expect(screen.getByText("Vezi interpretarea completă")).toBeTruthy();
    expect(screen.getByText(/Stresori probabili/)).toBeTruthy();
  });

  it("shows comparable distributions as one pie per selected cycle", () => {
    const { container } = render(
      <CycleDistributionPies
        title="Primul driver dominant"
        series={[
          {
            cycleId: "one",
            cycleLabel: "Evaluare inițială",
            segments: [
              { id: "perfect", label: "Fii perfect", value: 2, color: "red" },
              { id: "strong", label: "Fii puternic", value: 1, color: "blue" },
            ],
          },
          {
            cycleId: "two",
            cycleLabel: "Reevaluare",
            segments: [
              { id: "perfect", label: "Fii perfect", value: 3, color: "red" },
              { id: "strong", label: "Fii puternic", value: 1, color: "blue" },
            ],
          },
        ]}
      />,
    );

    expect(screen.getByText("2 participanți · 67%")).toBeTruthy();
    expect(screen.getByText("3 participanți · 75%")).toBeTruthy();
    expect(container.querySelectorAll("[data-distribution-pie]")).toHaveLength(2);
    expect(screen.getByRole("img", { name: /Evaluare inițială\. Fii perfect: 2, 67%/ })).toBeTruthy();
    expect(container.querySelector("[data-distribution-pie=one]")?.getAttribute("style")).toContain("conic-gradient");
  });
});
