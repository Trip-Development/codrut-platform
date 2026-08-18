import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "@/api/http";
import { resolveInviteBundle } from "@/api/invites";
import RegisterPage from "./page";

const router = {
  push: vi.fn(),
};

let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => router,
  useSearchParams: () => mockSearchParams,
}));

vi.mock("@/api/http", () => ({
  apiFetch: vi.fn(),
}));

vi.mock("@/api/invites", () => ({
  resolveInviteBundle: vi.fn(),
}));

vi.mock("@/api/runtime", () => ({
  getApiBaseUrl: () => "http://api.test",
  isDemoFallbackEnabled: () => true,
}));

describe("RegisterPage", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    vi.mocked(apiFetch).mockResolvedValue(new Response(null, { status: 204 }));
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows boxed pending feedback and locks account fields while activating", async () => {
    let resolveRegister!: (response: Response) => void;
    const registerPromise = new Promise<Response>((resolve) => {
      resolveRegister = resolve;
    });
    vi.mocked(apiFetch).mockReturnValue(registerPromise);

    render(<RegisterPage />);

    await screen.findByRole("button", { name: "Finalizează înregistrarea" });
    expect(screen.getByRole("heading", { level: 1, name: "Activează accesul permanent." })).toBeDefined();
    fireEvent.change(screen.getByLabelText("Parolă"), {
      target: { value: "o frază lungă și memorabilă" },
    });
    fireEvent.change(screen.getByLabelText("Confirmă parola"), {
      target: { value: "o frază lungă și memorabilă" },
    });
    fireEvent.click(screen.getByLabelText("Accept termenii și politica de confidențialitate."));
    const submitButton = screen.getByRole("button", { name: "Finalizează înregistrarea" });
    const registerForm = submitButton.closest("form");
    expect(registerForm).not.toBeNull();
    fireEvent.submit(registerForm!);
    fireEvent.submit(registerForm!);

    await screen.findByText("Creăm contul Cody");
    expect(apiFetch).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("Parolă")).toHaveProperty("disabled", true);
    expect(screen.getByLabelText("Confirmă parola")).toHaveProperty("disabled", true);
    expect(screen.getByLabelText("Accept termenii și politica de confidențialitate.")).toHaveProperty(
      "disabled",
      true,
    );

    await act(async () => {
      resolveRegister(new Response(null, { status: 204 }));
      await registerPromise;
    });

    await waitFor(() => {
      expect(router.push).toHaveBeenCalledWith("/invite/demo-token");
    });
  });

  it("blocks weak and mismatched passwords before making a request", async () => {
    render(<RegisterPage />);
    await screen.findByRole("button", { name: "Finalizează înregistrarea" });
    const form = screen.getByRole("button", { name: "Finalizează înregistrarea" }).closest("form")!;

    fireEvent.change(screen.getByLabelText("Parolă"), { target: { value: "scurt" } });
    fireEvent.change(screen.getByLabelText("Confirmă parola"), { target: { value: "scurt" } });
    fireEvent.submit(form);
    expect(await screen.findByText(/cel puțin 8 caractere/i)).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Parolă"), { target: { value: "o frază lungă și memorabilă" } });
    fireEvent.change(screen.getByLabelText("Confirmă parola"), { target: { value: "altă frază memorabilă" } });
    fireEvent.submit(form);
    expect(await screen.findByText("Parolele introduse nu coincid.")).toBeTruthy();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("requires consent even when the form is submitted programmatically", async () => {
    render(<RegisterPage />);
    await screen.findByRole("button", { name: "Finalizează înregistrarea" });
    fireEvent.change(screen.getByLabelText("Parolă"), { target: { value: "o frază lungă și memorabilă" } });
    fireEvent.change(screen.getByLabelText("Confirmă parola"), { target: { value: "o frază lungă și memorabilă" } });
    fireEvent.submit(screen.getByRole("button", { name: "Finalizează înregistrarea" }).closest("form")!);

    expect(await screen.findByText(/Trebuie să accepți termenii/i)).toBeTruthy();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("preserves input and exposes a backend registration error", async () => {
    vi.mocked(apiFetch).mockResolvedValue(new Response(JSON.stringify({
      error: { message: "Invitația a fost deja folosită." },
    }), { status: 409, headers: { "Content-Type": "application/json" } }));
    render(<RegisterPage />);
    await screen.findByRole("button", { name: "Finalizează înregistrarea" });
    const password = screen.getByLabelText("Parolă") as HTMLInputElement;
    fireEvent.change(password, { target: { value: "o frază lungă și memorabilă" } });
    fireEvent.change(screen.getByLabelText("Confirmă parola"), { target: { value: "o frază lungă și memorabilă" } });
    fireEvent.click(screen.getByLabelText("Accept termenii și politica de confidențialitate."));
    fireEvent.submit(screen.getByRole("button", { name: "Finalizează înregistrarea" }).closest("form")!);

    expect(await screen.findByText("Invitația a fost deja folosită.")).toBeTruthy();
    expect(password.value).toBe("o frază lungă și memorabilă");
    expect(password.disabled).toBe(false);
  });

  it("uses the invite identity from session storage and clears it after success", async () => {
    window.sessionStorage.setItem("codrut_invite", JSON.stringify({
      email: "lead@example.com",
      token: "invite-token",
      fullName: "Lead Test",
      isLeadership: true,
    }));
    render(<RegisterPage />);
    await screen.findByDisplayValue("lead@example.com");
    fireEvent.change(screen.getByLabelText("Parolă"), { target: { value: "o frază lungă și memorabilă" } });
    fireEvent.change(screen.getByLabelText("Confirmă parola"), { target: { value: "o frază lungă și memorabilă" } });
    fireEvent.click(screen.getByLabelText("Accept termenii și politica de confidențialitate."));
    fireEvent.submit(screen.getByRole("button", { name: "Finalizează înregistrarea" }).closest("form")!);

    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/invite/invite-token"));
    const request = vi.mocked(apiFetch).mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(request.body))).toMatchObject({
      email: "lead@example.com",
      token: "invite-token",
      terms_accepted: true,
    });
    expect(window.sessionStorage.getItem("codrut_invite")).toBeNull();
  });

  it("resolves token from URL query parameter, locks email to invitation, and redirects to invite on success", async () => {
    mockSearchParams = new URLSearchParams({ token: "query-token" });
    vi.mocked(resolveInviteBundle).mockResolvedValue({
      state: "valid",
      token: "query-token",
      projectName: "Michelin Leadership",
      participantEmail: "director@michelin.example",
      participantFullName: "Director Michelin",
      anonymousName: "Leader123",
      isLeadership: true,
      alreadyRegistered: false,
      accountType: "guest",
      accessMode: "secure_link",
      consentCurrent: false,
      deadlineLabel: "15 septembrie 2026",
      tasks: [],
    });

    render(<RegisterPage />);
    await screen.findByDisplayValue("director@michelin.example");
    const emailInput = screen.getByLabelText("Email securizat") as HTMLInputElement;
    expect(emailInput.disabled).toBe(true);
    expect(emailInput.value).toBe("director@michelin.example");

    fireEvent.change(screen.getByLabelText("Parolă"), { target: { value: "o frază lungă și memorabilă" } });
    fireEvent.change(screen.getByLabelText("Confirmă parola"), { target: { value: "o frază lungă și memorabilă" } });
    fireEvent.click(screen.getByLabelText("Accept termenii și politica de confidențialitate."));
    fireEvent.submit(screen.getByRole("button", { name: "Finalizează înregistrarea" }).closest("form")!);

    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/invite/query-token"));
    const request = vi.mocked(apiFetch).mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(request.body))).toMatchObject({
      email: "director@michelin.example",
      token: "query-token",
      terms_accepted: true,
    });
  });

  it("shows error when invite token in URL is expired or invalid", async () => {
    mockSearchParams = new URLSearchParams({ token: "expired-token" });
    vi.mocked(resolveInviteBundle).mockResolvedValue({
      state: "expired",
      token: "expired-token",
      projectName: "Proiect Expirat",
      deadlineLabel: "deadline-ul proiectului",
      message: "Invitația a expirat. Cere un link nou de la trainer.",
    });

    render(<RegisterPage />);
    expect(await screen.findByText("Invitația a expirat. Cere un link nou de la trainer.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Finalizează înregistrarea" })).toHaveProperty("disabled", true);
  });
});
