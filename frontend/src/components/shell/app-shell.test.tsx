import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { apiFetch as apiFetchType } from "@/api/http";
import { apiFetch, ensureCsrfToken } from "@/api/http";
import { AppShell, clearAppShellIdentityCache, profilePalette } from "./app-shell";

const navigationState = vi.hoisted(() => ({ pathname: "/trainer" }));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    onClick,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a
      href={href}
      onClick={(event) => {
        event.preventDefault();
        onClick?.(event);
      }}
      {...props}
    >
      {children}
    </a>
  ),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigationState.pathname,
}));

vi.mock("@/api/http", () => ({
  apiFetch: vi.fn(),
  ensureCsrfToken: vi.fn(),
}));

vi.mock("@/api/runtime", () => ({
  getApiBaseUrl: () => "http://localhost:8000/api",
}));

beforeEach(() => {
  clearAppShellIdentityCache();
  navigationState.pathname = "/trainer";
  vi.mocked(apiFetch).mockReset();
  vi.mocked(ensureCsrfToken).mockReset();
  vi.mocked(ensureCsrfToken).mockResolvedValue("csrf-token");
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("AppShell", () => {
  it("uses the destination pathname when a parent loading shell still points home", () => {
    navigationState.pathname = "/trainer/projects/project-1/participants";

    render(
      <AppShell
        audience="trainer"
        title="Proiecte"
        activeHref="/trainer"
        navItems={[
          { href: "/trainer", label: "Acasă" },
          { href: "/trainer/projects", label: "Proiecte" },
        ]}
      >
        <p>Conținut</p>
      </AppShell>,
    );

    expect(screen.getByRole("link", { name: "Proiecte" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Acasă" }).getAttribute("aria-current")).toBeNull();
  });

  it("highlights a clicked destination before navigation commits", () => {
    render(
      <AppShell
        audience="trainer"
        title="Acasă"
        activeHref="/trainer"
        navItems={[
          { href: "/trainer", label: "Acasă" },
          { href: "/trainer/projects", label: "Proiecte" },
        ]}
      >
        <p>Conținut</p>
      </AppShell>,
    );

    fireEvent.click(screen.getByRole("link", { name: "Proiecte" }));

    expect(screen.getByRole("link", { name: "Proiecte" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Acasă" }).getAttribute("aria-current")).toBeNull();
  });

  it("keeps the account menu wide enough for the theme selector when the sidebar is expanded", () => {
    render(
      <AppShell
        audience="participant"
        title="Acasă"
        activeHref="/participant"
        userLabel="Andrei"
        navItems={[{ href: "/participant", label: "Acasă" }]}
      >
        <p>Conținut</p>
      </AppShell>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Andrei" }));

    const accountMenu = document.querySelector("[data-sidebar-account-menu]");
    expect(accountMenu).not.toBeNull();
    expect(accountMenu?.className).toContain("w-64");
    expect(screen.getAllByRole("combobox", { name: "Temă" })[0]?.className).toContain("w-full");
  });

  it("keeps the generated avatar stable when page copy changes and varies it by account id", () => {
    const session = {
      state: "authenticated" as const,
      user: {
        id: "participant-1",
        name: "Andrei",
        role: "participant" as const,
      },
    };
    const view = render(
      <AppShell
        audience="participant"
        title="Acasă"
        activeHref="/participant"
        userLabel="Andrei"
        session={session}
        navItems={[{ href: "/participant", label: "Acasă" }]}
      >
        <p>Conținut</p>
      </AppShell>,
    );
    const initialAvatarStyle = document.querySelector("[data-profile-avatar]")?.getAttribute("style");

    view.rerender(
      <AppShell
        audience="participant"
        title="Chestionare"
        activeHref="/participant"
        userLabel="Participant"
        session={session}
        navItems={[{ href: "/participant", label: "Acasă" }]}
      >
        <p>Conținut</p>
      </AppShell>,
    );
    expect(document.querySelector("[data-profile-avatar]")?.getAttribute("style")).toBe(initialAvatarStyle);

    view.rerender(
      <AppShell
        audience="participant"
        title="Chestionare"
        activeHref="/participant"
        userLabel="Participant"
        session={{
          ...session,
          user: { ...session.user, id: "participant-2" },
        }}
        navItems={[{ href: "/participant", label: "Acasă" }]}
      >
        <p>Conținut</p>
      </AppShell>,
    );
    expect(document.querySelector("[data-profile-avatar]")?.getAttribute("style")).not.toBe(initialAvatarStyle);
  });

  it("uses the persisted palette across account contexts and keeps assigned palettes distinct", () => {
    const trainerPalette = profilePalette("trainer:user-1", 12_345);
    const invitePalette = profilePalette("participant:different-seed", 12_345);
    const differentUserPalette = profilePalette("trainer:user-2", 12_346);

    expect(invitePalette).toEqual(trainerPalette);
    expect(differentUserPalette).not.toEqual(trainerPalette);

    render(
      <AppShell
        audience="trainer"
        title="Acasă"
        activeHref="/trainer"
        session={{
          state: "authenticated",
          user: {
            id: "user-1",
            name: "Andrei",
            role: "trainer",
            avatarPaletteKey: 12_345,
          },
        }}
        navItems={[{ href: "/trainer", label: "Acasă" }]}
      >
        <p>Conținut</p>
      </AppShell>,
    );

    expect(
      document.querySelector("[data-profile-avatar]")?.getAttribute("data-avatar-palette-key"),
    ).toBe("12345");
  });

  it.each([null, -1, 1.5, 55_520_640])(
    "falls back to the stable account seed for an invalid palette key (%s)",
    (paletteKey) => {
      expect(profilePalette("trainer:user-1", paletteKey)).toEqual(
        profilePalette("trainer:user-1"),
      );
    },
  );

  it("retains the session identity when a route loading shell replaces the page shell", () => {
    const view = render(
      <AppShell
        audience="participant"
        title="Acasă"
        activeHref="/participant"
        session={{
          state: "authenticated",
          user: {
            id: "participant-1",
            name: "Andrei din sesiune",
            role: "participant",
            avatarPaletteKey: 54_321,
          },
        }}
        navItems={[{ href: "/participant", label: "Acasă" }]}
      >
        <p>Conținut</p>
      </AppShell>,
    );

    expect(screen.getByRole("button", { name: "Andrei din sesiune" })).toBeTruthy();
    const initialAvatarStyle = document.querySelector("[data-profile-avatar]")?.getAttribute("style");
    expect(
      document.querySelector("[data-profile-avatar]")?.getAttribute("data-avatar-palette-key"),
    ).toBe("54321");
    view.unmount();

    render(
      <AppShell
        audience="participant"
        title="Acasă"
        activeHref="/participant"
        accountIdentityPending
        navItems={[{ href: "/participant", label: "Acasă" }]}
      >
        <p>Conținut</p>
      </AppShell>,
    );

    expect(screen.queryByLabelText("Se încarcă identitatea contului")).toBeNull();
    expect(screen.getByRole("button", { name: "Andrei din sesiune" })).toBeTruthy();
    expect(document.querySelector("[data-profile-avatar]")?.getAttribute("style")).toBe(initialAvatarStyle);
    expect(
      document.querySelector("[data-profile-avatar]")?.getAttribute("data-avatar-palette-key"),
    ).toBe("54321");
    fireEvent.click(screen.getByRole("button", { name: "Andrei din sesiune" }));
    expect(screen.getAllByText("Andrei din sesiune")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Deschide meniul de navigare" }));
    expect(screen.getAllByText("Andrei din sesiune")).toHaveLength(3);
  });

  it("renders neutral identity placeholders when no authenticated identity is known", () => {
    render(
      <AppShell
        audience="participant"
        title="Acasă"
        activeHref="/participant"
        accountIdentityPending
        navItems={[{ href: "/participant", label: "Acasă" }]}
      >
        <p>Conținut</p>
      </AppShell>,
    );

    expect(screen.getAllByLabelText("Se încarcă identitatea contului")).toHaveLength(1);
    expect(document.querySelector("[data-profile-avatar]")).toBeNull();
  });

  it("locks logout while the request is pending without adding explanatory copy", async () => {
    const logoutRequest = createDeferred<Awaited<ReturnType<typeof apiFetchType>>>();
    vi.mocked(apiFetch).mockReturnValue(logoutRequest.promise);

    render(
      <AppShell
        audience="trainer"
        eyebrow="Trainer"
        title="Acasă"
        description=""
        activeHref="/trainer"
        userLabel="Ana Trainer"
        navItems={[{ href: "/trainer", label: "Acasă" }]}
      >
        <p>Conținut</p>
      </AppShell>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Ana Trainer" }));
    const logoutButton = screen.getByRole("button", { name: "Deconectare" });
    fireEvent.click(logoutButton);
    fireEvent.click(logoutButton);

    expect(screen.getByRole("button", { name: "Închidem sesiunea" })).toHaveProperty("disabled", true);
    expect(screen.queryByText("Curățăm accesul curent și revenim la pagina publică.")).toBeNull();
    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));

    logoutRequest.resolve(new Response(null, { status: 204 }));

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith("http://localhost:8000/api/auth/logout", {
        method: "POST",
        credentials: "include",
      });
    });
  });
});

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}
