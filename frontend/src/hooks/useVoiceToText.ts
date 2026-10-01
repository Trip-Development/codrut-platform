import { useState, useRef, useCallback, useEffect } from "react";
import { transcribeAudio } from "@/api/practice";
import { decizieClip, nivelDbfs, PRAG_VORBIRE_DBFS } from "./pragulVorbirii";

/**
 * Textele pe care le vede omul cand microfonul nu merge. Toate intr-un singur loc.
 *
 * Pana la plicul 170 ecranul arata textul englezesc al browserului („Permission denied"),
 * cu „Eroare voce:" in fata — un om nu stie ce sa faca cu el.
 */
export const TEXTE_MICROFON = {
  nimicAuzit: "Nu s-a auzit nimic. Mai încearcă o dată, mai aproape de microfon.",
  faraPermisiune:
    "Browserul nu are voie să folosească microfonul. Permite microfonul pentru acest site " +
    "din setările browserului (pe calculator, în Chrome: lacătul de lângă adresă → Microfon " +
    "→ Permite), apoi reîncarcă pagina.",
  faraMicrofon: "Nu găsesc niciun microfon la acest dispozitiv.",
} as const;

/**
 * Traduce refuzul lui `getUserMedia` in ceva ce omul poate urma.
 *
 * `pentruOm: true` = textul e deja scris pentru el, ecranul il arata ca atare.
 * `pentruOm: false` = e o eroare tehnica neprevazuta, ramane cu „Eroare voce:" in fata.
 */
export function mesajDeMicrofon(err: unknown): { text: string; pentruOm: boolean } {
  const nume = err instanceof Error ? err.name : "";
  if (nume === "NotAllowedError" || nume === "SecurityError") {
    return { text: TEXTE_MICROFON.faraPermisiune, pentruOm: true };
  }
  if (nume === "NotFoundError") {
    return { text: TEXTE_MICROFON.faraMicrofon, pentruOm: true };
  }
  const text = err instanceof Error ? err.message : "Nu am putut accesa microfonul";
  return { text, pentruOm: false };
}

export interface UseVoiceToTextOptions {
  onTranscript?: (text: string) => void;
  /**
   * Called when auto-stop fired due to silence (NOT manual stop).
   * Use to trigger auto-send.
   */
  onAutoSubmit?: (text: string) => void;
  /** `pentruOm` = textul e deja scris pentru om, fara prefix tehnic. */
  onError?: (error: string, pentruOm?: boolean) => void;
}

export function useVoiceToText(options?: UseVoiceToTextOptions) {
  const [isListening, setIsListening] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const animFrameRef = useRef<number | null>(null);

  /**
   * Ține minte dacă oprirea a venit din timerul de tăcere (auto) sau manual.
   * Doar dacă a fost auto-stop se declanșează onAutoSubmit.
   */
  const wasAutoStoppedRef = useRef<boolean>(false);

  // Plicul 174: cât din înregistrare a ascultat ecranul și cât a fost peste pragul vorbirii.
  const masuraRef = useRef({ start: 0, stop: 0, msMasurate: 0, msPestePrag: 0, ultimulCadru: 0 });

  // silenceTimeoutMs = 6000    (crescut de la 4000: în quiz omul citește și gândește,
  //                             pauzele naturale trec de 4 secunde; 6 e mai uman)
  const silenceTimeoutMs = 6000;

  // silenceThreshold = 8       (scăzut de la 12: vocea liniștită, la citit, dădea RMS
  //                             sub 12 chiar în vorbire; 8 prinde și șoaptele)
  const silenceThreshold = 8;

  const playBeep = useCallback((freq: number, durationMs: number = 100) => {
    try {
      const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, ctx.currentTime);
      gain.gain.setValueAtTime(0.1, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + durationMs / 1000);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + durationMs / 1000);
      setTimeout(() => {
        ctx.close().catch(() => {});
      }, durationMs + 50);
    } catch {
      // Audio playback might be restricted if no user interaction
    }
  }, []);

  const stopListening = useCallback((wasAuto: boolean = false) => {
    wasAutoStoppedRef.current = wasAuto;
    masuraRef.current.stop = performance.now();
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    setIsListening(false);
    playBeep(440, 80); // stop beep
  }, [playBeep]);

  const handleAudioComplete = useCallback(async (audioBlob: Blob) => {
    if (audioBlob.size < 100) {
      return;
    }
    // Plicul 174: fără vorbire, clipul nu mai pleacă la transcriere și nu se trimite nimic. Ecranul
    // hotărăște numai dacă a ascultat; altfel trimite, ca înainte.
    const masura = masuraRef.current;
    const msInregistrare = Math.max(0, (masura.stop || performance.now()) - masura.start);
    const decizie = decizieClip({
      msInregistrare,
      msMasurate: masura.msMasurate,
      msPestePrag: masura.msPestePrag,
    });
    if (decizie === "nimic") {
      wasAutoStoppedRef.current = false;
      setIsTranscribing(false);
      setError(TEXTE_MICROFON.nimicAuzit);
      if (options?.onError) {
        options.onError(TEXTE_MICROFON.nimicAuzit, true);
      }
      return;
    }
    setIsTranscribing(true);
    setError(null);
    try {
      const res = await transcribeAudio(audioBlob);
      const text = res.text?.trim() ?? "";
      if (text) {
        setTranscript(text);
        if (options?.onTranscript) {
          options.onTranscript(text);
        }
        if (wasAutoStoppedRef.current && options?.onAutoSubmit) {
          options.onAutoSubmit(text);
        }
      } else {
        // Plicul 170: fara vorbire, modelul intoarce text gol. Nu se pune in caseta si nu
        // se trimite singur — altfel oprirea pe tacere scria o replica pe care omul n-a spus-o.
        setError(TEXTE_MICROFON.nimicAuzit);
        if (options?.onError) {
          options.onError(TEXTE_MICROFON.nimicAuzit, true);
        }
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Eroare la transcrierea audio";
      setError(errMsg);
      if (options?.onError) {
        options.onError(errMsg);
      }
    } finally {
      setIsTranscribing(false);
      wasAutoStoppedRef.current = false;
    }
  }, [options]);

  const startListening = useCallback(async () => {
    setError(null);
    wasAutoStoppedRef.current = false;
    masuraRef.current = { start: performance.now(), stop: 0, msMasurate: 0, msPestePrag: 0, ultimulCadru: 0 };
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      const audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      audioContextRef.current = audioCtx;
      const analyser = audioCtx.createAnalyser();
      analyserRef.current = analyser;
      analyser.fftSize = 512;

      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);

      audioChunksRef.current = [];
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/mp4";

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        handleAudioComplete(audioBlob);
      };

      mediaRecorder.start(250);
      setIsListening(true);
      playBeep(880, 100); // start beep

      // Silence detection loop
      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      // Plicul 174: citirea în virgulă mobilă — cea pe octeți are pasul de ~−42 dBFS și n-ar vedea
      // vorbirea încetă.
      const fereastra = new Float32Array(analyser.fftSize);

      const checkSilence = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteTimeDomainData(dataArray);

        // Compute RMS volume
        let sumSquares = 0;
        for (let i = 0; i < bufferLength; i++) {
          const val = (dataArray[i] - 128) / 128;
          sumSquares += val * val;
        }
        const rms = Math.sqrt(sumSquares / bufferLength) * 100;

        // Plicul 174: cât timp a ascultat ecranul și cât a fost peste pragul vorbirii.
        if (typeof analyserRef.current.getFloatTimeDomainData === "function") {
          const acum = performance.now();
          const masura = masuraRef.current;
          if (masura.ultimulCadru > 0) {
            const pas = Math.min(100, Math.max(0, acum - masura.ultimulCadru));
            analyserRef.current.getFloatTimeDomainData(fereastra);
            masura.msMasurate += pas;
            if (nivelDbfs(fereastra) > PRAG_VORBIRE_DBFS) {
              masura.msPestePrag += pas;
            }
          }
          masura.ultimulCadru = acum;
        }

        if (rms < silenceThreshold) {
          if (!silenceTimerRef.current) {
            silenceTimerRef.current = setTimeout(() => {
              stopListening(true); // Auto-stopped due to silence!
            }, silenceTimeoutMs);
          }
        } else {
          if (silenceTimerRef.current) {
            clearTimeout(silenceTimerRef.current);
            silenceTimerRef.current = null;
          }
        }

        animFrameRef.current = requestAnimationFrame(checkSilence);
      };

      checkSilence();
    } catch (err: unknown) {
      const { text: errMsg, pentruOm } = mesajDeMicrofon(err);
      setError(errMsg);
      if (options?.onError) {
        options.onError(errMsg, pentruOm);
      }
      setIsListening(false);
    }
  }, [handleAudioComplete, playBeep, silenceThreshold, silenceTimeoutMs, stopListening, options]);

  const resetTranscript = useCallback(() => {
    setTranscript("");
    setError(null);
  }, []);

  useEffect(() => {
    return () => {
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (audioContextRef.current && audioContextRef.current.state !== "closed") {
        audioContextRef.current.close().catch(() => {});
      }
    };
  }, []);

  return {
    isListening,
    isTranscribing,
    transcript,
    error,
    startListening,
    stopListening: () => stopListening(false),
    resetTranscript,
  };
}
