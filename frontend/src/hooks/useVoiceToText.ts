import { useState, useRef, useCallback, useEffect } from "react";
import { transcribeAudio } from "@/api/practice";

export interface UseVoiceToTextOptions {
  onTranscript?: (text: string) => void;
  onError?: (error: string) => void;
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

  const stopListening = useCallback(() => {
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
    setIsTranscribing(true);
    setError(null);
    try {
      const res = await transcribeAudio(audioBlob);
      if (res.text && res.text.trim()) {
        const text = res.text.trim();
        setTranscript(text);
        if (options?.onTranscript) {
          options.onTranscript(text);
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
    }
  }, [options]);

  const startListening = useCallback(async () => {
    setError(null);
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

        if (rms < silenceThreshold) {
          if (!silenceTimerRef.current) {
            silenceTimerRef.current = setTimeout(() => {
              stopListening();
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
      const errMsg = err instanceof Error ? err.message : "Nu am putut accesa microfonul";
      setError(errMsg);
      if (options?.onError) {
        options.onError(errMsg);
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
    stopListening,
    resetTranscript,
  };
}
