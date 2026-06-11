import { render, screen, cleanup } from "@testing-library/react";
import React from "react";
import { beforeAll, beforeEach, afterEach, describe, expect, it, vi } from "vitest";

import HomePage from "./page";

describe("HomePage", () => {
  beforeAll(() => {
    const mockIntersectionObserver = vi.fn();
    mockIntersectionObserver.prototype.observe = vi.fn();
    mockIntersectionObserver.prototype.unobserve = vi.fn();
    mockIntersectionObserver.prototype.disconnect = vi.fn();
    vi.stubGlobal("IntersectionObserver", mockIntersectionObserver);
  });

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("renders the business landing and access paths", () => {
    render(<HomePage />);

    expect(screen.getAllByText("Codruț").length).toBeGreaterThan(0);
    expect(screen.getByText("Codruț transformă trainingul în pași clari pentru fiecare om.")).toBeTruthy();
    expect(screen.getByText("Acasă")).toBeTruthy();
    expect(screen.getAllByText("Intră în cont").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Trainer login").length).toBeGreaterThan(0);
    expect(screen.getByText("Link sigur")).toBeTruthy();
    expect(screen.getByText("Continuitate după training, fără follow-up pierdut.")).toBeTruthy();
    expect(screen.queryByText("Tip 4")).toBeNull();
    expect(screen.queryByText("Workflow campanie")).toBeNull();
  });
});
