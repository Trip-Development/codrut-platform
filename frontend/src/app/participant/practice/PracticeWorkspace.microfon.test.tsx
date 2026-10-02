/**
 * Plicul 176 — microfonul doar scrie în casetă; omul citește, corectează și apasă Trimite.
 *
 * Ecranul întreg, cu cârligul ADEVĂRAT al microfonului (nemockuit). Fals e numai browserul:
 * `MediaRecorder`, `getUserMedia`, `AudioContext`. Analizorul dă linie dreaptă (tăcere), deci
 * oprirea pe tăcere a aplicației pornește singură după 6 s. Analizorul n-are citirea în virgulă
 * mobilă, deci pragul plicului 174 cade deschis („trimite la transcriere”) — nu e un ocol al lui
 * 174: aici se verifică ce face ecranul cu textul, nu dacă e vorbire.
 */
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TEXTE_MICROFON } from "@/hooks/useVoiceToText";
import { PracticeWorkspace } from "./PracticeWorkspace";

const api = vi.hoisted(() => ({
  getPracticeConsent: vi.fn(),
  givePracticeConsent: vi.fn(),
  startPracticeSession: vi.fn(),
  submitPracticeTurn: vi.fn(),
  endPracticeSession: vi.fn(),
  transcribeAudio: vi.fn(),
}));

const { PracticeError } = vi.hoisted(() => ({
  PracticeError: class extends Error {
    code = "";
    details: Record<string, unknown> = {};
  },
}));

vi.mock("@/api/practice", () => ({ ...api, PracticeError }));

const VORBIT = "Bună ziua, aș vrea să discutăm despre termenul de predare.";
const SALUT = {
  id: "cody-1", sessionId: "sesiune-1", ordinal: 1, role: "actor" as const,
  text: "Salut! Ești gata să începem un joc de rol?",
  createdAt: "2026-09-04T09:59:00Z", expiresAt: "2026-10-04T09:59:00Z",
};

function pregatesteBrowserul() {
  let onstop: (() => void) | null = null;
  class RecorderFals {
    state = "recording";
    ondataavailable: ((e: { data: Blob }) => void) | null = null;
    set onstop(f: () => void) {
      onstop = f;
    }
    start() {}
    stop() {
      this.state = "inactive";
      onstop?.();
    }
    static isTypeSupported() {
      return true;
    }
  }
  vi.stubGlobal("MediaRecorder", RecorderFals);
  vi.stubGlobal("Blob", class extends Blob {
    get size() {
      return 5000;
    }
  });
  vi.stubGlobal("navigator", {
    ...navigator,
    mediaDevices: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [] }) },
  });
  vi.stubGlobal("AudioContext", class {
    state = "running";
    currentTime = 0;
    createAnalyser() {
      // 128 = linie dreaptă = tăcere → pornește oprirea automată (6 s)
      return { fftSize: 512, frequencyBinCount: 256, getByteTimeDomainData: (a: Uint8Array) => a.fill(128), connect: () => {} };
    }
    createMediaStreamSource() {
      return { connect: () => {} };
    }
    createOscillator() {
      return { type: "", frequency: { setValueAtTime: () => {} }, connect: () => {}, start: () => {}, stop: () => {} };
    }
    createGain() {
      return { gain: { setValueAtTime: () => {}, exponentialRampToValueAtTime: () => {} }, connect: () => {} };
    }
    close() {
      return Promise.resolve();
    }
    get destination() {
      return {};
    }
  });
  vi.stubGlobal("requestAnimationFrame", () => 1);
  vi.stubGlobal("cancelAnimationFrame", () => {});
}

function raspunsAmanat() {
  let rezolva!: (valoare: unknown) => void;
  const promisiune = new Promise((ok) => {
    rezolva = ok;
  });
  return { promisiune, rezolva };
}

function raspunsCu(text: string) {
  return {
    participantTurn: {
      id: "om-salvat", sessionId: "sesiune-1", ordinal: 2, role: "participant" as const,
      text, createdAt: "2026-09-19T10:00:00Z", expiresAt: "2026-10-19T10:00:00Z",
    },
    actorTurn: {
      id: "cody-2", sessionId: "sesiune-1", ordinal: 3, role: "actor" as const,
      text: "Replica lui Cody.", createdAt: "2026-09-19T10:00:05Z", expiresAt: "2026-10-19T10:00:05Z",
    },
    sessionState: "open" as const,
  };
}

async function porneste(firstTurn?: typeof SALUT) {
  api.startPracticeSession.mockResolvedValue({
    id: "sesiune-1", kind: "roleplay", state: "open", turnCount: 0, ...(firstTurn ? { firstTurn } : {}),
  });
  render(<PracticeWorkspace projectId="proiect-1" />);
  fireEvent.click(screen.getByRole("button", { name: "Începe conversația" }));
  await waitFor(() => expect(api.startPracticeSession).toHaveBeenCalled());
  return (await screen.findByPlaceholderText(/Scrie un mesaj/)) as HTMLTextAreaElement;
}

async function pornesteMicrofonul() {
  await act(async () => {
    fireEvent.click(screen.getByTitle("Vorbește (microfon)"));
  });
  await waitFor(() => expect(screen.getByTitle("Oprește înregistrarea")).toBeTruthy());
}

/** Taci: oprirea pe tăcere a aplicației, după 6 s (ceas fals, apoi înapoi la cel adevărat). */
async function taci() {
  await act(() => vi.advanceTimersByTimeAsync(6000));
  vi.useRealTimers();
}

beforeEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  Element.prototype.scrollIntoView = vi.fn();
  for (const f of Object.values(api)) f.mockReset();
  api.getPracticeConsent.mockResolvedValue({ acordat: true });
  api.transcribeAudio.mockResolvedValue({ text: VORBIT, estimated_usd: 0 });
  api.submitPracticeTurn.mockImplementation(async (_id: string, text: string) => raspunsCu(text));
  pregatesteBrowserul();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  cleanup();
});

describe("microfonul doar scrie în casetă (plicul 176)", () => {
  it("1 · oprit singur pe tăcere: textul se adaugă la ce era scris, nimic nu pleacă, cursorul la capăt", async () => {
    const caseta = await porneste();
    fireEvent.change(caseta, { target: { value: "Am o întrebare." } });

    vi.useFakeTimers({ shouldAdvanceTime: true, toFake: ["setTimeout", "clearTimeout"] });
    await pornesteMicrofonul();
    await taci();

    await waitFor(() => expect(api.transcribeAudio).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(caseta.disabled).toBe(false));
    // pe codul de dinainte de 176 aici se vede ce pleca singur și ce rămânea în casetă
    expect({ trimiteri: api.submitPracticeTurn.mock.calls, caseta: caseta.value }).toEqual({
      trimiteri: [],
      caseta: `Am o întrebare. ${VORBIT}`,
    });
    await waitFor(() => expect(document.activeElement).toBe(caseta));
    expect(caseta.selectionStart).toBe(caseta.value.length);
    expect(caseta.selectionEnd).toBe(caseta.value.length);
  });

  it("2 · oprit de om (al doilea clic): același rezultat", async () => {
    const caseta = await porneste();
    fireEvent.change(caseta, { target: { value: "Am o întrebare." } });

    await pornesteMicrofonul();
    await act(async () => {
      fireEvent.click(screen.getByTitle("Oprește înregistrarea"));
    });

    await waitFor(() => expect(caseta.value).toBe(`Am o întrebare. ${VORBIT}`));
    expect(api.submitPracticeTurn).not.toHaveBeenCalled();
    await waitFor(() => expect(document.activeElement).toBe(caseta));
    expect(caseta.selectionStart).toBe(caseta.value.length);
  });

  it("3 · omul corectează și apasă Trimite: pleacă o dată, textul corectat; Enter după nu mai trimite nimic", async () => {
    const caseta = await porneste();
    vi.useFakeTimers({ shouldAdvanceTime: true, toFake: ["setTimeout", "clearTimeout"] });
    await pornesteMicrofonul();
    await taci();
    await waitFor(() => expect(caseta.value).toBe(VORBIT));

    const corectat = "Bună ziua, aș vrea să discutăm despre termen.";
    const amanat = raspunsAmanat();
    api.submitPracticeTurn.mockReturnValue(amanat.promisiune);
    fireEvent.change(caseta, { target: { value: corectat } });
    fireEvent.click(screen.getByRole("button", { name: "Trimite" }));

    expect(await screen.findByText(corectat)).toBeTruthy();
    expect(caseta.value).toBe("");
    await act(async () => amanat.rezolva(raspunsCu(corectat)));
    expect(await screen.findByText("Replica lui Cody.")).toBeTruthy();
    expect(screen.getAllByText(corectat)).toHaveLength(1);

    fireEvent.keyDown(caseta, { key: "Enter" });
    expect(api.submitPracticeTurn).toHaveBeenCalledTimes(1);
    expect(api.submitPracticeTurn).toHaveBeenCalledWith("sesiune-1", corectat);
  });

  it("4 · transcriere goală: caseta neschimbată, mesajul „nimic auzit”, nimic trimis (170 + 174)", async () => {
    api.transcribeAudio.mockResolvedValue({ text: "", estimated_usd: 0 });
    const caseta = await porneste();
    fireEvent.change(caseta, { target: { value: "Am o întrebare." } });

    vi.useFakeTimers({ shouldAdvanceTime: true, toFake: ["setTimeout", "clearTimeout"] });
    await pornesteMicrofonul();
    await taci();

    expect(await screen.findByText(TEXTE_MICROFON.nimicAuzit)).toBeTruthy();
    expect(caseta.value).toBe("Am o întrebare.");
    expect(api.submitPracticeTurn).not.toHaveBeenCalled();
  });

  it("5 · textul vine cât încă se așteaptă o replică: apare o singură dată în casetă, nu pleacă", async () => {
    const caseta = await porneste(SALUT);
    vi.useFakeTimers({ shouldAdvanceTime: true, toFake: ["setTimeout", "clearTimeout"] });
    await pornesteMicrofonul();

    // cât ascultă microfonul, omul apasă „Da, hai” — replica stă în așteptare
    const amanat = raspunsAmanat();
    api.submitPracticeTurn.mockReturnValue(amanat.promisiune);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Da, hai" }));
    });
    await taci();
    await waitFor(() => expect(api.transcribeAudio).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(caseta.value).not.toBe(""));

    expect({ trimiteri: api.submitPracticeTurn.mock.calls.map((c) => c[1]), caseta: caseta.value }).toEqual({
      trimiteri: ["Da, hai."],
      caseta: VORBIT,
    });
    await act(async () => amanat.rezolva(raspunsCu("Da, hai.")));
    expect(caseta.value).toBe(VORBIT);
  });
});
