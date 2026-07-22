import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { acceptCurrentTerms } from "@/api/auth";
import { ConsentForm } from "./ConsentForm";

vi.mock("@/api/auth", () => ({ acceptCurrentTerms: vi.fn() }));

describe("ConsentForm", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("requires explicit consent and saves it once", async () => {
    vi.mocked(acceptCurrentTerms).mockImplementation(() => new Promise<void>(() => undefined));
    render(<ConsentForm />);

    const button = screen.getByRole("button", { name: "Continuă" });
    expect(button).toHaveProperty("disabled", true);

    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(button);
    fireEvent.click(button);

    expect(acceptCurrentTerms).toHaveBeenCalledTimes(1);
    expect(await screen.findByRole("button", { name: "Salvăm acordul" })).toHaveProperty("disabled", true);
  });

  it("keeps a failed save recoverable", async () => {
    vi.mocked(acceptCurrentTerms).mockRejectedValue(new Error("Conexiunea a fost întreruptă."));
    render(<ConsentForm />);

    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Continuă" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Conexiunea a fost întreruptă.");
    expect(screen.getByRole("button", { name: "Continuă" })).toHaveProperty("disabled", false);
  });
});
