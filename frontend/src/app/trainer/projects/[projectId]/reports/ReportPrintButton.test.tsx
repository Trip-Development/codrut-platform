import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReportPrintButton } from "./ReportPrintButton";

describe("ReportPrintButton", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("opens the browser print dialog", () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);

    render(<ReportPrintButton />);
    fireEvent.click(screen.getByRole("button", { name: "Tipărește" }));

    expect(print).toHaveBeenCalledTimes(1);
  });
});
