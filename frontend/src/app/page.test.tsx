import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

import HomePage from "./page";

describe("HomePage", () => {
  it("renders the scaffold status", () => {
    render(<HomePage />);

    expect(screen.getByText("Codrut Platform")).toBeTruthy();
    expect(screen.getAllByText("Trainer dashboard").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Participant workspace").length).toBeGreaterThan(0);
  });
});
