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

  it("renders trainer login without resolving a protected session", async () => {
    vi.mocked(headers).mockResolvedValue(
      new Headers({ "x-codrut-pathname": "/trainer/login" }) as never,
    );

    const markup = renderToStaticMarkup(
      await TrainerLayout({ children: <main>Autentificare</main> }),
    );

    expect(markup).toContain("Autentificare");
    expect(getTrainerSession).not.toHaveBeenCalled();
  });
});
