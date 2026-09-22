/**
 * O eroare la onboarding nu mai dărâmă pagina — plicul 127.
 *
 * Pe 22 septembrie, `Ref: 3146487137`: cererea a răspuns 400 (definiția de chestionar lipsea din
 * baza de probă), funcția a aruncat, și spațiul participantului a căzut întreg — „Nu am putut
 * încărca pagina". Un chestionar care nu se poate cere nu are voie să închidă tot.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./server-request", () => ({
  getServerApiRequestOptions: vi.fn(async () => ({ headers: { cookie: "session=test" } })),
}));
vi.mock("./runtime", () => ({ getApiBaseUrl: () => "http://backend/api" }));

import { getParticipantOnboardingState } from "./participant-onboarding";

const GOL = { required: false, questionnaire_key: null, assignment_id: null, href: null };

describe("cererea de onboarding", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.unstubAllGlobals());

  it("400 → nu e cerut nimic, fără să arunce", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 400 }) as unknown as Response));

    await expect(getParticipantOnboardingState("profile-1")).resolves.toEqual(GOL);
  });

  it("cererea nu ajunge deloc → tot nu e cerut nimic", async () => {
    // backendul repornit, reteaua cazuta: `fetch` ARUNCA, nu intoarce un raspuns.
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error("ECONNREFUSED");
    }));

    await expect(getParticipantOnboardingState("profile-1")).resolves.toEqual(GOL);
  });

  it("răspuns bun → se citește ca până acum", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        required: true,
        questionnaire_key: "pcm_base",
        assignment_id: "a-1",
        href: "/participant/onboarding",
      }),
    }) as unknown as Response));

    await expect(getParticipantOnboardingState("profile-1")).resolves.toEqual({
      required: true,
      questionnaire_key: "pcm_base",
      assignment_id: "a-1",
      href: "/participant/onboarding",
    });
  });

  it("fără profil → nu se cheamă serverul deloc", async () => {
    const f = vi.fn();
    vi.stubGlobal("fetch", f);

    await expect(getParticipantOnboardingState(null)).resolves.toEqual(GOL);
    expect(f).not.toHaveBeenCalled();
  });
});
