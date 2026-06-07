import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { CountUp } from "./count-up";
import { EmptyState } from "./empty-state";
import { StatCard } from "./stat-card";

describe("presentation components", () => {
  beforeEach(() => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders count up values immediately for reduced motion", () => {
    render(<CountUp value={42} />);

    expect(screen.getByText("42")).toBeTruthy();
  });

  it("renders empty state content", () => {
    render(<EmptyState title="No data yet" description="This is a placeholder." />);

    expect(screen.getByText("No data yet")).toBeTruthy();
    expect(screen.getByText("This is a placeholder.")).toBeTruthy();
  });

  it("renders stat cards with detail copy", () => {
    render(<StatCard label="Invitations" value={7} detail="Sent to participants." />);

    expect(screen.getByText("Invitations")).toBeTruthy();
    expect(screen.getByText("Sent to participants.")).toBeTruthy();
  });
});
