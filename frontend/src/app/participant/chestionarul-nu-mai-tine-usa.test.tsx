/**
 * Chestionarul PCM nu mai ține ușa închisă — plicul 127.
 *
 * Hotărârea lui Andrei, 22 septembrie: „Am partea de chestionare, și am partea de exersează cu
 * Cody. Ce treabă are una cu alta?" Până azi, un om fără PCM completat era **trimis forțat** la
 * chestionar (`redirect(onboarding.href)`) și n-avea altă ușă. Iar dacă cererea de onboarding
 * pica, cădea toată pagina — asta a văzut Andrei pe 22 septembrie, `Ref: 3146487137`.
 *
 * De azi: chestionarul se **cere**, nu se **impune**.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getParticipantWorkspaceSummary: vi.fn(),
  getParticipantOnboardingState: vi.fn(),
  redirect: vi.fn(),
}));

vi.mock("@/api/participants", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/participants")>();
  return { ...original, getParticipantWorkspaceSummary: api.getParticipantWorkspaceSummary };
});
vi.mock("@/api/participant-onboarding", () => ({
  getParticipantOnboardingState: api.getParticipantOnboardingState,
}));
vi.mock("@/api/auth-server", () => ({
  getParticipantSession: vi.fn(async () => ({
    state: "authenticated",
    user: { id: "user-1", name: "Andrei", role: "participant" },
  })),
}));
vi.mock("@/api/server-request", () => ({
  getServerApiRequestOptions: vi.fn(async () => ({ headers: { cookie: "session=test" } })),
}));
vi.mock("next/navigation", () => ({ redirect: api.redirect }));

// Spațiul întreg e greu și nu el se judecă aici. Ce se judecă: pagina NU mai redirecționează, și
// anunțul ajunge până la spațiu.
vi.mock("./ParticipantClientWorkspace", () => ({
  ParticipantClientWorkspace: ({ onboardingHref }: { onboardingHref?: string | null }) => (
    <main>
      <p>spațiul participantului</p>
      {onboardingHref ? <a href={onboardingHref}>Ai un chestionar de completat</a> : null}
    </main>
  ),
}));
vi.mock("../ParticipantClientWorkspace", () => ({
  ParticipantClientWorkspace: ({ onboardingHref }: { onboardingHref?: string | null }) => (
    <main>
      <p>spațiul participantului</p>
      {onboardingHref ? <a href={onboardingHref}>Ai un chestionar de completat</a> : null}
    </main>
  ),
}));

import ParticipantDashboardPage from "./dashboard/page";
import ParticipantWorkspacePage from "./page";

const sumar = {
  participantProfileId: "profile-1",
  participantFullName: "Andrei Participant",
  projectId: "project-1",
  projectName: "Repetiție Michelin 28 sept",
  contexts: [],
  cycles: [],
  tasks: [],
  results: [],
  projects: [],
  questionnaireProjects: [],
  receivedFeedback: null,
  receivedFeedbackGroups: [],
  pcmBase: null,
  pcmPhase: null,
};

const PAGINI = [
  ["/participant", ParticipantWorkspacePage],
  ["/participant/dashboard", ParticipantDashboardPage],
] as const;

describe("chestionarul PCM nu mai ține ușa închisă", () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    api.getParticipantWorkspaceSummary.mockResolvedValue(sumar);
  });

  for (const [cale, Pagina] of PAGINI) {
    it(`${cale}: chestionar cerut → spațiul se deschide, cu anunț, FĂRĂ redirecționare`, async () => {
      api.getParticipantOnboardingState.mockResolvedValue({
        required: true,
        questionnaire_key: "pcm_base",
        assignment_id: "a-1",
        href: "/participant/onboarding",
      });

      render(await Pagina({ searchParams: Promise.resolve({}) }));

      expect(api.redirect).not.toHaveBeenCalled();
      expect(screen.getByText("spațiul participantului")).toBeTruthy();
      const legatura = screen.getByRole("link", { name: "Ai un chestionar de completat" });
      expect(legatura.getAttribute("href")).toBe("/participant/onboarding");
    });

    it(`${cale}: niciun chestionar cerut → spațiul, fără anunț`, async () => {
      api.getParticipantOnboardingState.mockResolvedValue({
        required: false,
        questionnaire_key: null,
        assignment_id: null,
        href: null,
      });

      render(await Pagina({ searchParams: Promise.resolve({}) }));

      expect(api.redirect).not.toHaveBeenCalled();
      expect(screen.getByText("spațiul participantului")).toBeTruthy();
      expect(screen.queryByRole("link", { name: "Ai un chestionar de completat" })).toBeNull();
    });

    // Cazul „onboardingul pică" se judecă la cererea în sine — `participant-onboarding.test.ts`:
    // acolo o eroare devine „nu e cerut nimic", iar de acolo încolo e chiar testul de mai sus.
  }
});
