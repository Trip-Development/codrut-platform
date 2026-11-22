import { beforeEach, describe, expect, it, vi } from "vitest";

// Plicul 244: „Exersează pe obiectiv” trimite `pe_obiectiv: true`; altfel corpul e cel de azi,
// octet cu octet (fără cheia nouă).
const http = vi.hoisted(() => ({ apiFetch: vi.fn() }));
vi.mock("./http", () => http);
vi.mock("./runtime", () => ({ getApiBaseUrl: () => "http://test.local/api" }));

const SESIUNE = {
  id: "s-1",
  participant_profile_id: "pp-1",
  program_settings_id: "ps-1",
  scenario_id: null,
  kind: "roleplay",
  state: "open",
  turn_count: 1,
  started_at: "2026-11-22T08:00:00Z",
  first_turn: null,
};

function raspuns(corp: unknown) {
  return { ok: true, json: async () => corp } as Response;
}

function corpulTrimis(): string {
  const [, init] = http.apiFetch.mock.calls[0];
  return (init as RequestInit).body as string;
}

beforeEach(() => {
  http.apiFetch.mockReset();
  http.apiFetch.mockResolvedValue(raspuns(SESIUNE));
});

describe("startPracticeSession, pe obiectiv", () => {
  it("fără peObiectiv corpul e exact cel de azi", async () => {
    const { startPracticeSession } = await import("./practice");
    await startPracticeSession({ projectId: "p", kind: "roleplay" });
    expect(corpulTrimis()).toBe(
      JSON.stringify({ project_id: "p", kind: "roleplay", scenario_id: undefined }),
    );
    expect(JSON.parse(corpulTrimis())).not.toHaveProperty("pe_obiectiv");
  });

  it("cu scenariu, fără peObiectiv: aceleași trei chei ca azi", async () => {
    const { startPracticeSession } = await import("./practice");
    await startPracticeSession({ projectId: "p", kind: "knowledge", scenarioId: "sc-1" });
    expect(corpulTrimis()).toBe(
      JSON.stringify({ project_id: "p", kind: "knowledge", scenario_id: "sc-1" }),
    );
  });

  it("peObiectiv: false nu adaugă cheia", async () => {
    const { startPracticeSession } = await import("./practice");
    await startPracticeSession({ projectId: "p", kind: "roleplay", peObiectiv: false });
    expect(JSON.parse(corpulTrimis())).not.toHaveProperty("pe_obiectiv");
  });

  it("cu peObiectiv: true → \"pe_obiectiv\": true", async () => {
    const { startPracticeSession } = await import("./practice");
    await startPracticeSession({ projectId: "p", kind: "roleplay", peObiectiv: true });
    expect(JSON.parse(corpulTrimis())).toEqual({
      project_id: "p",
      kind: "roleplay",
      pe_obiectiv: true,
    });
  });
});
