import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { IcarePerspectiveGrid } from "./IcarePerspectiveGrid";

const perspectives = [
  {
    id: "direct_team",
    label: "Cum vede echipa leadershipul",
    responseCount: 1,
    content: <p>Rezultatul echipei</p>,
  },
  {
    id: "leadership_peers",
    label: "Cum se văd colegii din leadership",
    responseCount: 2,
    content: <p>Rezultatul colegilor</p>,
  },
  {
    id: "self",
    label: "Cum se evaluează liderii",
    responseCount: 1,
    content: <p>Rezultatul autoevaluării</p>,
  },
];

describe("IcarePerspectiveGrid", () => {
  afterEach(cleanup);

  it("shows all three perspectives together without navigation controls", () => {
    render(<IcarePerspectiveGrid perspectives={perspectives} />);

    const region = screen.getByRole("region", { name: "Perspective iCARE" });
    expect(region.textContent).toContain("Rezultatul echipei");
    expect(region.textContent).toContain("Rezultatul colegilor");
    expect(region.textContent).toContain("Rezultatul autoevaluării");
    expect(screen.getAllByRole("group")).toHaveLength(3);
    expect(screen.queryByRole("tab")).toBeNull();
  });
});
