import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PracticeWorkspace } from "./PracticeWorkspace";

// Plicul 247: nota vine în fundal. Cât nu e gata, sub replica lui Cody stă „Nota ta este…”
// (textul lui Andrei, 21 nov 19:27); ecranul întreabă serverul la 2 s, cel mult 45 s.

vi.mock("@/hooks/useVoiceToText", () => ({
  useVoiceToText: () => ({
    isListening: false,
    isTranscribing: false,
    startListening: vi.fn(),
    stopListening: vi.fn(),
    error: null,
  }),
}));

const api = vi.hoisted(() => ({
  getPracticeConsent: vi.fn(),
  givePracticeConsent: vi.fn(),
  startPracticeSession: vi.fn(),
  submitPracticeTurn: vi.fn(),
  endPracticeSession: vi.fn(),
  getConversatiaNeincheiata: vi.fn(),
  getPracticeSessionHistory: vi.fn(),
}));

const { PracticeError } = vi.hoisted(() => ({
  PracticeError: class extends Error {
    code = "x";
    details = {};
  },
}));

vi.mock("@/api/practice", () => ({ ...api, PracticeError }));

const TEXT = "Nota ta este…";
const SALUT = {
  id: "cody-1",
  sessionId: "sesiune-1",
  ordinal: 1,
  role: "actor" as const,
  text: "Salut. Ești gata să începem un joc de rol?",
  createdAt: "2026-11-22T09:59:00Z",
  expiresAt: "2026-12-22T09:59:00Z",
};
const OMUL = {
  ...SALUT,
  id: "om-2",
  ordinal: 2,
  role: "participant" as const,
  text: "Înțeleg ce spui.",
};
const PERSONAJ = {
  ...SALUT,
  id: "cody-3",
  ordinal: 3,
  text: "Ana: Bine, dar până vineri trebuie gata.",
  evaluareVine: true,
};
const CU_NOTA = {
  ...PERSONAJ,
  text: "Ana: Bine, dar până vineri trebuie gata.\n\n***\n\nNota: 7/10.",
  evaluareVine: false,
};

function istoric(replica: typeof PERSONAJ | typeof CU_NOTA) {
  return {
    session: { id: "sesiune-1", kind: "roleplay", state: "open", turnCount: 3 },
    turns: [SALUT, OMUL, replica],
  };
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
  for (const f of Object.values(api)) f.mockReset();
  api.getPracticeConsent.mockResolvedValue({ acordat: true, amprenta: "a" });
  api.getConversatiaNeincheiata.mockResolvedValue(null);
  api.startPracticeSession.mockResolvedValue({
    id: "sesiune-1",
    kind: "roleplay",
    state: "open",
    turnCount: 1,
    firstTurn: SALUT,
  });
});

afterEach(() => {
  vi.useRealTimers();
  cleanup();
});

async function trimite(actorTurn: typeof PERSONAJ | typeof SALUT) {
  api.submitPracticeTurn.mockResolvedValue({
    participantTurn: OMUL,
    actorTurn,
    sessionState: "open",
  });
  render(<PracticeWorkspace projectId="proiect-1" />);
  fireEvent.click(screen.getByRole("button", { name: "Începe conversația" }));
  const caseta = (await screen.findByPlaceholderText(/Scrie un mesaj/)) as HTMLTextAreaElement;
  vi.useFakeTimers({
    shouldAdvanceTime: true,
    toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval", "Date"],
  });
  fireEvent.change(caseta, { target: { value: "Înțeleg ce spui." } });
  fireEvent.click(screen.getByRole("button", { name: "Trimite" }));
  await waitFor(() => expect(api.submitPracticeTurn).toHaveBeenCalledTimes(1));
  await screen.findByText(/Ana: Bine/);
  return caseta;
}

async function treci(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("nota vine în fundal (plicul 247)", () => {
  it("F1 · „Nota ta este…” sub replica lui Cody, iar caseta rămâne activă", async () => {
    api.getPracticeSessionHistory.mockResolvedValue(istoric(PERSONAJ));
    const caseta = await trimite(PERSONAJ);
    expect(screen.getByText(TEXT)).toBeTruthy();
    expect(screen.getByText(TEXT).closest('[role="status"]')).toBeTruthy();
    expect(caseta.disabled).toBe(false);
    fireEvent.change(caseta, { target: { value: "Încă ceva." } });
    expect((screen.getByRole("button", { name: "Trimite" }) as HTMLButtonElement).disabled).toBe(
      false,
    );
  });

  it("F2 · nota venită înlocuiește textul bulei; întrebările se opresc", async () => {
    api.getPracticeSessionHistory
      .mockResolvedValueOnce(istoric(PERSONAJ))
      .mockResolvedValue(istoric(CU_NOTA));
    await trimite(PERSONAJ);
    await treci(2100);
    await treci(2100);
    await waitFor(() => expect(screen.getByText(/Nota: 7\/10\./)).toBeTruthy());
    expect(screen.queryByText(TEXT)).toBeNull();
    const chemari = api.getPracticeSessionHistory.mock.calls.length;
    await treci(10000);
    expect(api.getPracticeSessionHistory.mock.calls.length).toBe(chemari);
    expect(api.getPracticeSessionHistory).toHaveBeenCalledWith("sesiune-1");
  });

  it("F3 · întrebările care aruncă: se încearcă mai departe, după 45 s se oprește", async () => {
    api.getPracticeSessionHistory.mockRejectedValue(new Error("rețea"));
    await trimite(PERSONAJ);
    await treci(6100);
    expect(api.getPracticeSessionHistory.mock.calls.length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText(TEXT)).toBeTruthy();
    await treci(45000);
    expect(screen.queryByText(TEXT)).toBeNull();
    expect(screen.getByText(/Ana: Bine/)).toBeTruthy();
    const chemari = api.getPracticeSessionHistory.mock.calls.length;
    await treci(10000);
    expect(api.getPracticeSessionHistory.mock.calls.length).toBe(chemari);
  });

  it("F4 · fără nicio replică „vine”, serverul nu e întrebat", async () => {
    await trimite({ ...PERSONAJ, evaluareVine: false } as typeof PERSONAJ);
    await treci(10000);
    expect(api.getPracticeSessionHistory).not.toHaveBeenCalled();
    expect(screen.queryByText(TEXT)).toBeNull();
  });

  it("F5 · serverul dă mereu aceeași replică tot „vine”: după 45 s întrebările se opresc", async () => {
    api.getPracticeSessionHistory.mockResolvedValue(istoric(PERSONAJ));
    await trimite(PERSONAJ);
    await treci(20000);
    expect(api.getPracticeSessionHistory.mock.calls.length).toBeGreaterThanOrEqual(8);
    await treci(30000);
    expect(screen.queryByText(TEXT)).toBeNull();
    const chemari = api.getPracticeSessionHistory.mock.calls.length;
    expect(chemari).toBeLessThanOrEqual(26);
    await treci(10000);
    expect(api.getPracticeSessionHistory.mock.calls.length).toBe(chemari);
  });
});
