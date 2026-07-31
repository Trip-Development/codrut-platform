import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { IcarePerspectiveTabs } from "./IcarePerspectiveTabs";

const perspectives = [
  {
    id: "direct_team",
    label: "Cum vede echipa leadershipul",
    tabLabel: "Echipa",
    responseCount: 1,
    content: <p>Rezultatul echipei</p>,
  },
  {
    id: "leadership_peers",
    label: "Cum se văd colegii din leadership",
    tabLabel: "Colegii din leadership",
    responseCount: 2,
    content: <p>Rezultatul colegilor</p>,
  },
  {
    id: "self",
    label: "Cum se evaluează liderii",
    tabLabel: "Autoevaluare",
    responseCount: 1,
    content: <p>Rezultatul autoevaluării</p>,
  },
];

describe("IcarePerspectiveTabs", () => {
  afterEach(cleanup);

  it("keeps one perspective visible and exposes the full approved labels", () => {
    render(<IcarePerspectiveTabs perspectives={perspectives} />);

    const teamTab = screen.getByRole("tab", { name: "Cum vede echipa leadershipul: 1 răspuns" });
    const peersTab = screen.getByRole("tab", { name: "Cum se văd colegii din leadership: 2 răspunsuri" });
    expect(teamTab.getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("tabpanel").textContent).toContain("Rezultatul echipei");

    fireEvent.click(peersTab);

    expect(peersTab.getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("tabpanel").textContent).toContain("Rezultatul colegilor");
  });

  it("supports arrows, Home, and End without tabbing through inactive controls", () => {
    render(<IcarePerspectiveTabs perspectives={perspectives} />);

    const teamTab = screen.getByRole("tab", { name: "Cum vede echipa leadershipul: 1 răspuns" });
    const peersTab = screen.getByRole("tab", { name: "Cum se văd colegii din leadership: 2 răspunsuri" });
    const selfTab = screen.getByRole("tab", { name: "Cum se evaluează liderii: 1 răspuns" });

    fireEvent.keyDown(teamTab, { key: "ArrowRight" });
    expect(peersTab.getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(peersTab);

    fireEvent.keyDown(peersTab, { key: "End" });
    expect(selfTab.getAttribute("aria-selected")).toBe("true");

    fireEvent.keyDown(selfTab, { key: "Home" });
    expect(teamTab.getAttribute("aria-selected")).toBe("true");
    expect(teamTab.getAttribute("tabindex")).toBe("0");
    expect(peersTab.getAttribute("tabindex")).toBe("-1");
  });
});
