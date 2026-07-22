import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useUrlState } from "./use-url-state";

const navigationMocks = vi.hoisted(() => ({
  pathname: "/trainer/email",
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigationMocks.pathname,
  useSearchParams: () => new URLSearchParams(window.location.search),
}));

function UrlStateProbe() {
  const { setParam } = useUrlState();

  return (
    <>
      <button type="button" onClick={() => setParam("modal", "new-campaign")}>
        Open campaign
      </button>
      <button type="button" onClick={() => setParam("modal", null, "replace")}>
        Close campaign
      </button>
      <button type="button" onClick={() => setParam("view", "contacts", "replace")}>
        Show contacts
      </button>
      <button type="button" onClick={() => setParam("modal", "new-contact")}>
        Open contact
      </button>
    </>
  );
}

describe("useUrlState", () => {
  afterEach(cleanup);

  beforeEach(() => {
    navigationMocks.pathname = "/trainer/email";
    window.history.replaceState(null, "", "/trainer/email?view=campaigns");
  });

  it("does not drop a rapid close while the open navigation is still pending", () => {
    render(<UrlStateProbe />);

    fireEvent.click(screen.getByRole("button", { name: "Open campaign" }));
    expect(`${window.location.pathname}${window.location.search}`).toBe(
      "/trainer/email?view=campaigns&modal=new-campaign",
    );
    fireEvent.click(screen.getByRole("button", { name: "Close campaign" }));
    expect(`${window.location.pathname}${window.location.search}`).toBe(
      "/trainer/email?view=campaigns",
    );
  });

  it("preserves earlier requested parameters across consecutive updates", () => {
    render(<UrlStateProbe />);

    fireEvent.click(screen.getByRole("button", { name: "Show contacts" }));
    expect(`${window.location.pathname}${window.location.search}`).toBe(
      "/trainer/email?view=contacts",
    );
    fireEvent.click(screen.getByRole("button", { name: "Open contact" }));
    expect(`${window.location.pathname}${window.location.search}`).toBe(
      "/trainer/email?view=contacts&modal=new-contact",
    );
  });
});
