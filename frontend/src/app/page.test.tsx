import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

import HomePage from "./page";

describe("HomePage", () => {
  it("renders the business landing and access paths", () => {
    render(<HomePage />);

    expect(screen.getAllByText("Codrut").length).toBeGreaterThan(0);
    expect(screen.getByText("Codrut transforma trainingul in pasi clari pentru fiecare om.")).toBeTruthy();
    expect(screen.getAllByText("Intră în cont").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Trainer login").length).toBeGreaterThan(0);
    expect(screen.getByText("Link sigur")).toBeTruthy();
    expect(screen.getByText("Continuitate dupa training, fara follow-up pierdut.")).toBeTruthy();
    expect(screen.queryByText("Tip 4")).toBeNull();
    expect(screen.queryByText("Workflow campanie")).toBeNull();
  });
});
