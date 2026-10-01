/**
 * Plicul 174, partea (a) — clipul fără vorbire nu mai pleacă la transcriere.
 *
 * Funcția pură (pragul) + cârligul microfonului cu un analizor fals care dă eșantioane în virgulă
 * mobilă, cadru cu cadru: liniștea nu se mai trimite, vorbirea da, iar ce n-a ascultat ecranul se
 * trimite (hotărăște serverul, ca înainte).
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  decizieClip,
  MIN_MS_VORBIRE,
  nivelDbfs,
  PRAG_VORBIRE_DBFS,
} from "@/hooks/pragulVorbirii";
import { TEXTE_MICROFON, useVoiceToText } from "@/hooks/useVoiceToText";

const transcribeAudio = vi.hoisted(() => vi.fn());
vi.mock("@/api/practice", () => ({ transcribeAudio }));

describe("pragul vorbirii — funcția pură", () => {
  it("nivelul în dBFS", () => {
    expect(nivelDbfs(new Float32Array(512))).toBe(-Infinity);
    expect(nivelDbfs(new Float32Array(512).fill(0.1))).toBeCloseTo(-20, 5);
    expect(nivelDbfs(new Float32Array(512).fill(10 ** (-50 / 20)))).toBeCloseTo(-50, 5);
    expect(PRAG_VORBIRE_DBFS).toBe(-48);
    expect(MIN_MS_VORBIRE).toBe(160);
  });

  it("„nimic” numai dacă a ascultat cel puțin jumătate și vorbirea e sub minim", () => {
    expect(decizieClip({ msInregistrare: 3000, msMasurate: 2900, msPestePrag: 0 })).toBe("nimic");
    expect(decizieClip({ msInregistrare: 3000, msMasurate: 2900, msPestePrag: 159 })).toBe("nimic");
    expect(decizieClip({ msInregistrare: 3000, msMasurate: 2900, msPestePrag: 160 })).toBe("trimite");
    // n-a ascultat deloc sau prea puțin (fila ascunsă) → trimite
    expect(decizieClip({ msInregistrare: 3000, msMasurate: 0, msPestePrag: 0 })).toBe("trimite");
    expect(decizieClip({ msInregistrare: 3000, msMasurate: 1400, msPestePrag: 0 })).toBe("trimite");
  });
});

/** Microfonul fals: nivelul se schimbă din test; cadrele le dă testul, cu ceasul lui. */
const microfon = vi.hoisted(() => ({
  nivel: 0,
  cuMasura: true,
  acum: 0,
  cadru: null as null | FrameRequestCallback,
}));

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
      const analizor: Record<string, unknown> = {
        fftSize: 512,
        frequencyBinCount: 256,
        getByteTimeDomainData: (a: Uint8Array) => a.fill(128 + Math.round(microfon.nivel * 128)),
        connect: () => {},
      };
      if (microfon.cuMasura) {
        analizor.getFloatTimeDomainData = (a: Float32Array) => a.fill(microfon.nivel);
      }
      return analizor;
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
  vi.stubGlobal("requestAnimationFrame", (f: FrameRequestCallback) => {
    microfon.cadru = f;
    return 1;
  });
  vi.stubGlobal("cancelAnimationFrame", () => {
    microfon.cadru = null;
  });
  vi.spyOn(performance, "now").mockImplementation(() => microfon.acum);
}

/** Lasă să curgă cadrele timp de `ms`, câte unul la ~16,7 ms, ca în browser. */
function cadre(ms: number) {
  const capat = microfon.acum + ms;
  while (microfon.acum < capat && microfon.cadru) {
    microfon.acum += 16.7;
    const f = microfon.cadru;
    microfon.cadru = null;
    f(microfon.acum);
  }
  microfon.acum = capat;
}

async function inregistrare(
  rezultat: { current: ReturnType<typeof useVoiceToText> },
  nivel: number,
  ms: number,
) {
  microfon.nivel = nivel;
  await act(async () => {
    await rezultat.current.startListening();
  });
  act(() => cadre(ms));
  await act(async () => {
    rezultat.current.stopListening();
  });
}

describe("useVoiceToText — fără vorbire, nimic nu pleacă (plicul 174, a)", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    transcribeAudio.mockReset();
    microfon.nivel = 0;
    microfon.cuMasura = true;
    microfon.acum = 1000;
    microfon.cadru = null;
    pregatesteBrowserul();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("liniștea (−50 dBFS) nu se transcrie și nu se trimite; apoi vorbirea trece (starea nu rămâne agățată)", async () => {
    transcribeAudio.mockResolvedValue({ text: "Da.", estimated_usd: 0 });
    const onTranscript = vi.fn();
    const onError = vi.fn();
    const { result } = renderHook(() => useVoiceToText({ onTranscript, onError }));

    await inregistrare(result, 10 ** (-50 / 20), 3000);
    expect(transcribeAudio).not.toHaveBeenCalled();
    expect(onTranscript).not.toHaveBeenCalled();
    expect(result.current.error).toBe(TEXTE_MICROFON.nimicAuzit);
    expect(onError).toHaveBeenCalledWith(TEXTE_MICROFON.nimicAuzit, true);
    expect(result.current.isTranscribing).toBe(false);

    // a doua înregistrare, cu vorbire (−20 dBFS)
    await inregistrare(result, 0.1, 2000);
    await waitFor(() => expect(transcribeAudio).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(onTranscript).toHaveBeenCalledWith("Da."));
  });

  it("tăcerea curată nu se trimite", async () => {
    const { result } = renderHook(() => useVoiceToText({}));
    await inregistrare(result, 0, 3000);
    expect(transcribeAudio).not.toHaveBeenCalled();
    expect(result.current.error).toBe(TEXTE_MICROFON.nimicAuzit);
  });

  it("un „Da” scurt (200 ms peste prag) trece", async () => {
    transcribeAudio.mockResolvedValue({ text: "Da.", estimated_usd: 0 });
    const { result } = renderHook(() => useVoiceToText({}));
    microfon.nivel = 0;
    await act(async () => {
      await result.current.startListening();
    });
    act(() => cadre(1000));
    microfon.nivel = 0.1;
    act(() => cadre(200));
    microfon.nivel = 0;
    act(() => cadre(1000));
    await act(async () => {
      result.current.stopListening();
    });
    await waitFor(() => expect(transcribeAudio).toHaveBeenCalledTimes(1));
  });

  it("browser fără măsurare în virgulă mobilă → se trimite (hotărăște serverul)", async () => {
    microfon.cuMasura = false;
    transcribeAudio.mockResolvedValue({ text: "", estimated_usd: 0 });
    const { result } = renderHook(() => useVoiceToText({}));
    await inregistrare(result, 0, 3000);
    await waitFor(() => expect(transcribeAudio).toHaveBeenCalledTimes(1));
  });

  it("ascultat prea puțin (fila ascunsă oprește cadrele) → se trimite", async () => {
    transcribeAudio.mockResolvedValue({ text: "", estimated_usd: 0 });
    const { result } = renderHook(() => useVoiceToText({}));
    microfon.nivel = 0;
    await act(async () => {
      await result.current.startListening();
    });
    act(() => cadre(500));
    microfon.cadru = null; // fila ascunsă: nu mai vin cadre
    microfon.acum += 2500;
    await act(async () => {
      result.current.stopListening();
    });
    await waitFor(() => expect(transcribeAudio).toHaveBeenCalledTimes(1));
  });
});
