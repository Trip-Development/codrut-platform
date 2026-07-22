import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmptyState } from "./empty-state";
import { InlineFeedback } from "./inline-feedback";

describe("presentation components", () => {
  it("renders empty state content", () => {
    render(<EmptyState title="No data yet" description="This is a placeholder." />);

    expect(screen.getByText("No data yet")).toBeTruthy();
    expect(screen.getByText("This is a placeholder.")).toBeTruthy();
  });

  it("renders neutral and danger inline feedback with the right live roles", () => {
    const { rerender } = render(<InlineFeedback>Saved.</InlineFeedback>);

    expect(screen.getByRole("status").textContent).toContain("Saved.");

    rerender(<InlineFeedback tone="danger">Could not save.</InlineFeedback>);

    expect(screen.getByRole("alert").textContent).toContain("Could not save.");
  });

  it("allows compact inline feedback descriptions", () => {
    render(<InlineFeedback descriptionClassName="text-xs">Filtering.</InlineFeedback>);

    expect(screen.getByText("Filtering.").className).toContain("text-xs");
  });
});
