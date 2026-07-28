import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getAuthenticatedSession, loginWithPassword, type SessionState } from "@/api/auth";
import TrainerLoginPage from "./page";

const router = {
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

vi.mock("@/api/auth", () => ({
  canAccessWorkspace: vi.fn(
    (
      user: {
        role: "trainer" | "participant";
        availableWorkspaces?: Array<"trainer" | "participant">;
      },
      workspace: "trainer" | "participant",
    ) => (user.availableWorkspaces ?? [user.role]).includes(workspace),
  ),
  dashboardHrefForRole: vi.fn((role: "trainer" | "participant") =>
    role === "trainer" ? "/trainer" : "/participant",
  ),
  getAuthenticatedSession: vi.fn(),
  loginWithPassword: vi.fn(),
}));

describe("TrainerLoginPage", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/trainer/login");
    vi.mocked(getAuthenticatedSession).mockResolvedValue(null);
    vi.mocked(loginWithPassword).mockResolvedValue({
      state: "authenticated",
      user: {
        id: "trainer-1",
        name: "Andreea",
        email: "andreea@example.com",
        role: "trainer",
      },
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("shows boxed pending feedback and locks credentials while signing in", async () => {
    let resolveLogin!: (session: SessionState) => void;
    const loginPromise = new Promise<SessionState>((resolve) => {
      resolveLogin = resolve;
    });
    vi.mocked(loginWithPassword).mockReturnValue(loginPromise);

    render(<TrainerLoginPage />);

    expect(screen.getByRole("heading", { level: 1, name: "Intră în portal." })).toBeDefined();

    fireEvent.change(screen.getByLabelText("Email trainer"), {
      target: { value: "andreea@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Parolă"), {
      target: { value: "Aa12345!" },
    });
    const submitButton = screen.getByRole("button", { name: "Intră în portal" });
    const loginForm = submitButton.closest("form");
    expect(loginForm).not.toBeNull();
    fireEvent.submit(loginForm!);
    fireEvent.submit(loginForm!);

    await screen.findByText("Verificăm accesul trainer");
    expect(loginWithPassword).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("Email trainer")).toHaveProperty("disabled", true);
    expect(screen.getByLabelText("Parolă")).toHaveProperty("disabled", true);

    await act(async () => {
      resolveLogin({
        state: "authenticated",
        user: {
          id: "trainer-1",
          name: "Andreea",
          email: "andreea@example.com",
          role: "trainer",
        },
      });
      await loginPromise;
    });

    await waitFor(() => {
      expect(router.push).toHaveBeenCalledWith("/trainer");
      expect(router.refresh).toHaveBeenCalled();
    });
  });

  it("returns the trainer to a safe requested route after signing in", async () => {
    window.history.replaceState(
      {},
      "",
      "/trainer/login?returnTo=%2Ftrainer%2Fprojects%2Fproject-1%3Ftab%3Dresults",
    );
    render(<TrainerLoginPage />);

    fireEvent.change(screen.getByLabelText("Email trainer"), {
      target: { value: "andreea@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Parolă"), {
      target: { value: "Aa12345!" },
    });
    fireEvent.submit(screen.getByRole("button", { name: "Intră în portal" }).closest("form")!);

    await waitFor(() => {
      expect(router.push).toHaveBeenCalledWith("/trainer/projects/project-1?tab=results");
    });
  });

  it("rejects participant credentials without losing the form values", async () => {
    vi.mocked(loginWithPassword).mockResolvedValue({
      state: "authenticated",
      user: { id: "participant-1", name: "Bianca", email: "bianca@example.com", role: "participant" },
    });
    render(<TrainerLoginPage />);

    const email = screen.getByLabelText("Email trainer") as HTMLInputElement;
    const password = screen.getByLabelText("Parolă") as HTMLInputElement;
    fireEvent.change(email, { target: { value: "bianca@example.com" } });
    fireEvent.change(password, { target: { value: "parolă păstrată" } });
    fireEvent.submit(screen.getByRole("button", { name: "Intră în portal" }).closest("form")!);

    expect(await screen.findByText("Acest cont nu are acces la portalul de trainer.")).toBeTruthy();
    expect(email.value).toBe("bianca@example.com");
    expect(password.value).toBe("parolă păstrată");
    expect(email.disabled).toBe(false);
  });

  it("uses safe fallback copy for non-Error failures", async () => {
    vi.mocked(loginWithPassword).mockRejectedValue(null);
    render(<TrainerLoginPage />);
    fireEvent.submit(screen.getByRole("button", { name: "Intră în portal" }).closest("form")!);

    expect(await screen.findByText("Autentificarea a eșuat.")).toBeTruthy();
  });

  it("restores a remembered participant session to its own workspace", async () => {
    vi.useFakeTimers();
    vi.mocked(getAuthenticatedSession).mockResolvedValue({
      state: "authenticated",
      user: { id: "participant-1", name: "Bianca", email: "bianca@example.com", role: "participant" },
    });

    render(<TrainerLoginPage />);
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByRole("heading", { name: "Bianca" })).toBeTruthy();
    act(() => { vi.runAllTimers(); });
    expect(router.replace).toHaveBeenCalledWith("/participant");
  });

  it("keeps trainer login available when a secure-link cookie is present", async () => {
    vi.mocked(getAuthenticatedSession).mockResolvedValue({
      state: "authenticated",
      user: {
        id: "participant-1",
        name: "Bianca",
        email: "bianca@example.com",
        role: "participant",
        accessMode: "secure_link",
      },
    });

    render(<TrainerLoginPage />);

    expect(await screen.findByRole("heading", { name: "Intră în portal." })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Intră în portal" })).toBeTruthy();
    expect(router.replace).not.toHaveBeenCalled();
  });
});
