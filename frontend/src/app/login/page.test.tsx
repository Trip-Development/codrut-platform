import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getAuthenticatedSession, loginWithPassword, type SessionState } from "@/api/auth";
import { completeLoginNavigation } from "@/lib/auth-navigation";
import LoginPage from "./page";

const router = {
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

vi.mock("@/api/auth", () => ({
  dashboardHrefForRole: vi.fn((role: "trainer" | "participant") =>
    role === "trainer" ? "/trainer" : "/participant",
  ),
  getAuthenticatedSession: vi.fn(),
  loginWithPassword: vi.fn(),
}));

vi.mock("@/lib/auth-navigation", () => ({
  completeLoginNavigation: vi.fn(),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    vi.mocked(getAuthenticatedSession).mockResolvedValue(null);
    vi.mocked(loginWithPassword).mockResolvedValue({
      state: "authenticated",
      user: {
        id: "participant-1",
        name: "Bianca",
        email: "bianca@example.com",
        role: "participant",
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

    render(<LoginPage />);

    expect(screen.getByRole("heading", { level: 1, name: "Bine ai revenit." })).toBeDefined();

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "bianca@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Parolă"), {
      target: { value: "Aa12345!" },
    });
    const submitButton = screen.getByRole("button", { name: "Intră în cont" });
    const loginForm = submitButton.closest("form");
    expect(loginForm).not.toBeNull();
    fireEvent.submit(loginForm!);
    fireEvent.submit(loginForm!);

    await screen.findByText("Verificăm accesul participant");
    expect(loginWithPassword).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("Email")).toHaveProperty("disabled", true);
    expect(screen.getByLabelText("Parolă")).toHaveProperty("disabled", true);

    await act(async () => {
      resolveLogin({
        state: "authenticated",
        user: {
          id: "participant-1",
          name: "Bianca",
          email: "bianca@example.com",
          role: "participant",
        },
      });
      await loginPromise;
    });

    await waitFor(() => {
      expect(completeLoginNavigation).toHaveBeenCalledWith("/participant");
    });
  });

  it("keeps credentials editable and visible after a failed login", async () => {
    vi.mocked(loginWithPassword).mockRejectedValue(new Error("Email sau parolă incorectă."));
    render(<LoginPage />);

    const email = screen.getByLabelText("Email") as HTMLInputElement;
    const password = screen.getByLabelText("Parolă") as HTMLInputElement;
    fireEvent.change(email, { target: { value: "bianca@example.com" } });
    fireEvent.change(password, { target: { value: "parolă păstrată" } });
    fireEvent.submit(screen.getByRole("button", { name: "Intră în cont" }).closest("form")!);

    expect(await screen.findByText("Email sau parolă incorectă.")).toBeTruthy();
    expect(email.value).toBe("bianca@example.com");
    expect(password.value).toBe("parolă păstrată");
    expect(email.disabled).toBe(false);
    expect(password.disabled).toBe(false);
  });

  it("uses safe fallback copy for non-Error login failures", async () => {
    vi.mocked(loginWithPassword).mockRejectedValue({ reason: "unknown" });
    render(<LoginPage />);
    fireEvent.submit(screen.getByRole("button", { name: "Intră în cont" }).closest("form")!);

    expect(await screen.findByText("Autentificarea a eșuat.")).toBeTruthy();
  });

  it("shows the remembered-session transition before replacing the route", async () => {
    vi.useFakeTimers();
    vi.mocked(getAuthenticatedSession).mockResolvedValue({
      state: "authenticated",
      user: { id: "trainer-1", name: "Andreea", email: "andreea@example.com", role: "trainer" },
    });

    render(<LoginPage />);
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByRole("heading", { name: "Andreea" })).toBeTruthy();

    act(() => { vi.runAllTimers(); });
    expect(router.replace).toHaveBeenCalledWith("/trainer");
    expect(router.refresh).toHaveBeenCalled();
  });

  it("keeps account login available when a secure-link cookie is present", async () => {
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

    render(<LoginPage />);

    expect(await screen.findByRole("heading", { name: "Bine ai revenit." })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Intră în cont" })).toBeTruthy();
    expect(router.replace).not.toHaveBeenCalled();
  });
});
