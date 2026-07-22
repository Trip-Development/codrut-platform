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

    expect(screen.getAllByText("Cody").length).toBeGreaterThan(0);
    expect(screen.getByRole("banner")).toBeTruthy();
    expect(screen.getByText("Noul standard în training")).toBeTruthy();
    expect(screen.getByText("Training care continuă după workshopuri.")).toBeTruthy();
    expect(screen.getByText("Proces")).toBeTruthy();
    expect(screen.queryByText("Platformă")).toBeNull();
    expect(screen.getAllByText("Intră în cont").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Autentificare trainer").length).toBeGreaterThan(0);
    expect(screen.getByText("Acces prin link securizat")).toBeTruthy();
    expect(screen.getByText("Raportare pregătită pentru decizie.")).toBeTruthy();
    expect(screen.queryByText("Tip 4")).toBeNull();
    expect(screen.queryByText("Workflow campanie")).toBeNull();
  });
});
