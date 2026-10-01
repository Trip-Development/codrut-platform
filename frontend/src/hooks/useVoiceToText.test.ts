/**
 * Plicul 170 — microfonul, partea de ecran.
 *
 * Doua lucruri, amandoua vazute de om:
 *  A. transcrierea goala (tacere, zgomot, ton) nu intra in caseta si NU se trimite singura;
 *  B. microfonul blocat de browser nu mai scrie „Eroare voce: Permission denied".
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TEXTE_MICROFON, mesajDeMicrofon, useVoiceToText } from "@/hooks/useVoiceToText";

const transcribeAudio = vi.hoisted(() => vi.fn());
vi.mock("@/api/practice", () => ({ transcribeAudio }));

/** O eroare cu `name`, exact ce arunca `getUserMedia`. */
function eroareDom(nume: string, mesaj: string): Error {
  const e = new Error(mesaj);
  e.name = nume;
  return e;
}

/**
 * Un `MediaRecorder` de minciuna: la `stop()` da un bloc audio destul de mare ca sa treaca
 * poarta `size < 100` si cheama `onstop`, ca in browser.
 */
function pregatesteBrowserul(): { porneste: () => void } {
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
      return {
        fftSize: 512,
        frequencyBinCount: 256,
        // 128 = linie dreapta = tacere, deci porneste timerul de oprire automata
        getByteTimeDomainData: (a: Uint8Array) => a.fill(128),
        connect: () => {},
      };
    }
    createMediaStreamSource() {
      return { connect: () => {} };
    }
    createOscillator() {
      return {
        type: "", frequency: { setValueAtTime: () => {} },
        connect: () => {}, start: () => {}, stop: () => {},
      };
    }
    createGain() {
      return {
        gain: { setValueAtTime: () => {}, exponentialRampToValueAtTime: () => {} },
        connect: () => {},
      };
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
  return { porneste: () => {} };
}

describe("useVoiceToText — fara vorbire nu se inventeaza o replica (plicul 170)", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    transcribeAudio.mockReset();
    pregatesteBrowserul();
  });

  it("transcrierea goala nu intra in caseta si NU se trimite singura", async () => {
    // Pe proba, 2 s de ton ieseau „Bună ziua." si se trimiteau singure. Cu promptul reparat
    // modelul intoarce gol — iar ecranul trebuie sa nu faca nimic cu golul.
    transcribeAudio.mockResolvedValue({ text: "", estimated_usd: 0 });
    const onTranscript = vi.fn();
    const onAutoSubmit = vi.fn();
    const onError = vi.fn();
    const { result } = renderHook(() => useVoiceToText({ onTranscript, onAutoSubmit, onError }));

    await act(async () => {
      await result.current.startListening();
    });
    await act(async () => {
      result.current.stopListening();
    });

    await waitFor(() => expect(transcribeAudio).toHaveBeenCalledTimes(1));
    expect(onTranscript).not.toHaveBeenCalled();
    expect(onAutoSubmit).not.toHaveBeenCalled();
    expect(result.current.transcript).toBe("");
    expect(result.current.error).toBe(TEXTE_MICROFON.nimicAuzit);
    expect(onError).toHaveBeenCalledWith(TEXTE_MICROFON.nimicAuzit, true);
  });

  it("textul numai din spatii se trateaza ca gol", async () => {
    transcribeAudio.mockResolvedValue({ text: "   \n ", estimated_usd: 0 });
    const onAutoSubmit = vi.fn();
    const { result } = renderHook(() => useVoiceToText({ onAutoSubmit }));

    await act(async () => {
      await result.current.startListening();
    });
    await act(async () => {
      result.current.stopListening();
    });

    await waitFor(() => expect(result.current.error).toBe(TEXTE_MICROFON.nimicAuzit));
    expect(onAutoSubmit).not.toHaveBeenCalled();
  });

  it("vorbirea adevarata trece in caseta, ca pana acum", async () => {
    transcribeAudio.mockResolvedValue({
      text: "  Bună ziua, aș vrea să discutăm despre termenul de predare.  ",
      estimated_usd: 0,
    });
    const onTranscript = vi.fn();
    const { result } = renderHook(() => useVoiceToText({ onTranscript }));

    await act(async () => {
      await result.current.startListening();
    });
    await act(async () => {
      result.current.stopListening();
    });

    await waitFor(() =>
      expect(onTranscript).toHaveBeenCalledWith(
        "Bună ziua, aș vrea să discutăm despre termenul de predare.",
      ),
    );
    expect(result.current.error).toBeNull();
  });
});

describe("mesajDeMicrofon — microfonul blocat, pe limba omului (plicul 170)", () => {
  it("permisiunea refuzata spune ce sa apese, nu „Permission denied”", () => {
    const { text, pentruOm } = mesajDeMicrofon(eroareDom("NotAllowedError", "Permission denied"));
    expect(pentruOm).toBe(true);
    expect(text).toBe(TEXTE_MICROFON.faraPermisiune);
    expect(text).toContain("Permite microfonul pentru acest site");
    expect(text).not.toContain("Permission denied");
  });

  it("SecurityError primeste acelasi text", () => {
    expect(mesajDeMicrofon(eroareDom("SecurityError", "blocked")).text).toBe(
      TEXTE_MICROFON.faraPermisiune,
    );
  });

  it("niciun microfon la dispozitiv", () => {
    const { text, pentruOm } = mesajDeMicrofon(
      eroareDom("NotFoundError", "Requested device not found"),
    );
    expect(pentruOm).toBe(true);
    expect(text).toBe(TEXTE_MICROFON.faraMicrofon);
  });

  it("o eroare neprevazuta ramane tehnica, cu prefix", () => {
    const { text, pentruOm } = mesajDeMicrofon(eroareDom("AbortError", "ceva neasteptat"));
    expect(pentruOm).toBe(false);
    expect(text).toBe("ceva neasteptat");
  });

  it("ce nu e eroare deloc nu darama ecranul", () => {
    expect(mesajDeMicrofon("sir gol")).toEqual({
      text: "Nu am putut accesa microfonul",
      pentruOm: false,
    });
  });
});
