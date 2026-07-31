import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { DonutChart, ParticipantFrequencyPie, ScaledBar } from "./native-charts";

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

  it("renders participant counts and count-derived shares with an accessible summary", () => {
    render(
      <ParticipantFrequencyPie
        title="Primul driver dominant"
        totalPeople={3}
        data={[
          { id: "be_perfect", label: "Fii perfect", value: 2 },
          { id: "hurry_up", label: "Grăbește-te", value: 1 },
          { id: "zero", label: "Fără răspuns", value: 0 },
        ]}
      />,
    );

    expect(screen.getByText("3 persoane incluse")).toBeTruthy();
    expect(screen.getByText("2 persoane · 67%")).toBeTruthy();
    expect(screen.getByText("1 persoană · 33%")).toBeTruthy();
    expect(screen.queryByText("Fără răspuns")).toBeNull();
    expect(
      screen.getByRole("img", {
        name: "Primul driver dominant. 3 persoane incluse. Fii perfect: 2 persoane, 67%; Grăbește-te: 1 persoană, 33%.",
      }),
    ).toBeTruthy();
  });

  it("renders one included participant as a full 100% slice", () => {
    render(
      <ParticipantFrequencyPie
        title="Al doilea driver dominant"
        totalPeople={1}
        data={[{ id: "try_hard", label: "Străduiește-te", value: 1 }]}
      />,
    );

    expect(screen.getByText("1 persoană inclusă")).toBeTruthy();
    expect(screen.getByText("1 persoană · 100%")).toBeTruthy();
    expect(
      screen.getByRole("img", {
        name: /Al doilea driver dominant\. 1 persoană inclusă\..*100%/,
      }),
    ).toBeTruthy();
  });

  it("uses the same driver color across both frequency pies", () => {
    render(
      <>
        <ParticipantFrequencyPie
          title="Primul driver dominant"
          totalPeople={2}
          data={[
            { id: "be_perfect", label: "Fii perfect", value: 1 },
            { id: "hurry_up", label: "Grăbește-te", value: 1 },
          ]}
        />
        <ParticipantFrequencyPie
          title="Al doilea driver dominant"
          totalPeople={2}
          data={[
            { id: "try_hard", label: "Străduiește-te", value: 1 },
            { id: "be_perfect", label: "Fii perfect", value: 1 },
          ]}
        />
      </>,
    );

    const perfectLabels = screen.getAllByText("Fii perfect");
    expect(perfectLabels).toHaveLength(2);
    const firstSwatch = perfectLabels[0].previousElementSibling as HTMLElement;
    const secondSwatch = perfectLabels[1].previousElementSibling as HTMLElement;
    expect(firstSwatch.style.backgroundColor).not.toBe("");
    expect(firstSwatch.style.backgroundColor).toBe(secondSwatch.style.backgroundColor);
    expect(
      (screen.getByRole("img", { name: /Primul driver dominant/ }) as HTMLElement)
        .style.printColorAdjust,
    ).toBe("exact");
  });

  it("uses an honest zero-result state without implying a privacy threshold", () => {
    render(
      <ParticipantFrequencyPie
        title="Primul driver dominant"
        totalPeople={0}
        data={[]}
      />,
    );

    expect(screen.getByText("0 persoane incluse")).toBeTruthy();
    expect(screen.getByText("Nu există încă rezultate TA finalizate pentru această evaluare.")).toBeTruthy();
    expect(
      screen.getByRole("img", {
        name: /0 persoane incluse.*Nu există încă rezultate TA finalizate/,
      }),
    ).toBeTruthy();
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
