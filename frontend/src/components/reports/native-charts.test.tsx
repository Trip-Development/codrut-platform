import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { DonutChart, ScaledBar } from "./native-charts";

afterEach(cleanup);

describe("native report charts", () => {
  it("renders an accessible empty donut state", () => {
    render(<DonutChart title="Distribuție PCM" data={[{ id: "empty", label: "Fără date", value: 0 }]} />);

    expect(screen.getByRole("img", { name: "Distribuție PCM" })).toBeTruthy();
    expect(screen.getByText("Nu există date")).toBeTruthy();
    expect(screen.getByText("0")).toBeTruthy();
  });

  it("renders positive segments, ignores zero values, and honors custom colors", () => {
    const { container } = render(
      <DonutChart
        title="Profil echipă"
        data={[
          { id: "thinker", label: "Gânditor", value: 2, color: "rgb(10, 20, 30)" },
          { id: "persister", label: "Perseverent", value: 1 },
          { id: "zero", label: "Absent", value: 0 },
        ]}
      />,
    );

    expect(screen.getByText("3")).toBeTruthy();
    expect(screen.getByText("Gânditor")).toBeTruthy();
    expect(screen.getByText("Perseverent")).toBeTruthy();
    expect(screen.queryByText("Absent")).toBeNull();
    expect(container.querySelectorAll("svg circle")).toHaveLength(3);
    expect((screen.getByText("Gânditor").previousElementSibling as HTMLElement).style.backgroundColor).toBe("rgb(10, 20, 30)");
  });

  it("clamps scale widths and handles a zero maximum", () => {
    const { container, rerender } = render(<ScaledBar value={130} max={100} colorClassName="bg-test" />);
    expect((container.querySelector(".bg-test") as HTMLElement).style.width).toBe("100%");

    rerender(<ScaledBar value={-12} max={100} />);
    expect((container.querySelector(".bg-burgundy") as HTMLElement).style.width).toBe("0%");

    rerender(<ScaledBar value={12} max={0} />);
    expect((container.querySelector(".bg-burgundy") as HTMLElement).style.width).toBe("0%");
  });
});
