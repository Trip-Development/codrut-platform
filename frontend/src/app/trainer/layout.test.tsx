import { renderToStaticMarkup } from "react-dom/server";
import { headers } from "next/headers";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getTrainerSession } from "@/api/auth-server";
import TrainerLayout from "./layout";

vi.mock("next/headers", () => ({
  headers: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  redirect: vi.fn((href: string) => {
    throw new Error(`redirect:${href}`);
  }),
}));

vi.mock("@/api/auth-server", () => ({
  getTrainerSession: vi.fn(),
}));

vi.mock("@/api/auth", () => ({
  canAccessWorkspace: vi.fn(() => true),
  dashboardHrefForRole: vi.fn((role: string) => `/${role}`),
  isAuthRoleMismatchError: vi.fn(() => false),
  isAuthSessionUnavailableError: vi.fn(() => false),
}));

describe("TrainerLayout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(headers).mockResolvedValue(
      new Headers({
        "x-codrut-pathname": "/trainer/projects/project-1",
        "x-codrut-search": "?tab=results",
      }) as never,
    );
    vi.mocked(getTrainerSession).mockRejectedValue(new Error("Sesiune expirată"));
  });

  it("sends a stale or missing session to trainer login and preserves the destination", async () => {
    await expect(
      TrainerLayout({ children: <main>Portal</main> }),
    ).rejects.toThrow(
      "redirect:/trainer/login?returnTo=%2Ftrainer%2Fprojects%2Fproject-1%3Ftab%3Dresults",
    );
  });

  it("renders trainer login only after confirming there is no active session", async () => {
    vi.mocked(headers).mockResolvedValue(
      new Headers({ "x-codrut-pathname": "/trainer/login" }) as never,
    );

    const markup = renderToStaticMarkup(
      await TrainerLayout({ children: <main>Autentificare</main> }),
    );

    expect(markup).toContain("Autentificare");
    expect(getTrainerSession).toHaveBeenCalledTimes(1);
  });

  it("redirects an authenticated trainer away from login exactly once", async () => {
    vi.mocked(headers).mockResolvedValue(
      new Headers({
        "x-codrut-pathname": "/trainer/login",
        "x-codrut-search": "?returnTo=%2Ftrainer%2Fprojects%2Fproject-2",
      }) as never,
    );
    vi.mocked(getTrainerSession).mockResolvedValue({
      state: "authenticated",
      user: {
        id: "trainer-1",
        name: "trainer",
        role: "trainer",
        availableWorkspaces: ["trainer"],
      },
    });

    await expect(
      TrainerLayout({ children: <main>Autentificare</main> }),
    ).rejects.toThrow("redirect:/trainer/projects/project-2");
    expect(getTrainerSession).toHaveBeenCalledTimes(1);
  });
});
