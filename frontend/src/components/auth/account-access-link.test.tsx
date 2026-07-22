import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getAuthenticatedSession } from "@/api/auth";
import { AccountAccessLink } from "./account-access-link";

vi.mock("@/api/auth", () => ({
  dashboardHrefForRole: (role: "trainer" | "participant") => (role === "trainer" ? "/trainer" : "/participant"),
  getAuthenticatedSession: vi.fn(),
}));

type DeferredSession = {
  promise: ReturnType<typeof getAuthenticatedSession>;
  resolve: (value: Awaited<ReturnType<typeof getAuthenticatedSession>>) => void;
};

function createDeferredSession(): DeferredSession {
  let resolve: DeferredSession["resolve"] | undefined;
  const promise = new Promise<Awaited<ReturnType<typeof getAuthenticatedSession>>>((resolver) => {
    resolve = resolver;
  });
  return {
    promise,
    resolve: (value) => resolve?.(value),
  };
}

describe("AccountAccessLink", () => {
  beforeEach(() => {
    (globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("deduplicates simultaneous remembered-session checks across repeated links", async () => {
    const session = createDeferredSession();
    vi.mocked(getAuthenticatedSession).mockReturnValue(session.promise);

    render(
      <>
        <AccountAccessLink>Intră în cont</AccountAccessLink>
        <AccountAccessLink>Intră în cont</AccountAccessLink>
      </>,
    );

    expect(getAuthenticatedSession).toHaveBeenCalledTimes(1);

    await act(async () => {
      session.resolve({
        state: "authenticated",
        user: {
          id: "trainer-1",
          name: "Andrei",
          email: "andrei@example.com",
          role: "trainer",
        },
      });
      await session.promise;
    });

    await waitFor(() => {
      const links = screen.getAllByRole("link", { name: "Continuă în cont" });
      expect(links).toHaveLength(2);
      expect(links.every((link) => link.getAttribute("href") === "/trainer")).toBe(true);
    });
  });

  it("rechecks the session for later mounts after the in-flight probe settles", async () => {
    vi.mocked(getAuthenticatedSession).mockResolvedValue(null);

    const firstRender = render(<AccountAccessLink>Intră în cont</AccountAccessLink>);
    await waitFor(() => {
      expect(getAuthenticatedSession).toHaveBeenCalledTimes(1);
    });
    firstRender.unmount();

    render(<AccountAccessLink>Intră în cont</AccountAccessLink>);

    await waitFor(() => {
      expect(getAuthenticatedSession).toHaveBeenCalledTimes(2);
    });
  });
});
