import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

import HomePage from "./page";

describe("HomePage", () => {
  it("renders the business landing and access paths", () => {
    render(<HomePage />);

    expect(screen.getByText("Codrut")).toBeTruthy();
    expect(screen.getByText("Codrut transforma trainingul in actiune masurabila.")).toBeTruthy();
    expect(screen.getAllByText("Am primit invitatie").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Trainer login").length).toBeGreaterThan(0);
    expect(screen.getByText("Link securizat")).toBeTruthy();
    expect(screen.getByText("Campanii video pentru clienti si prospecti.")).toBeTruthy();
    expect(screen.getByText("Tip 4")).toBeTruthy();
  });
});
