"use client";

import { useEffect, useRef, useState } from "react";

type CountUpProps = {
  value: number;
  duration?: number;
  delay?: number;
  format?: (value: number) => string;
  className?: string;
};

const defaultFormat = (value: number) => Math.round(value).toLocaleString("ro-RO");

export function CountUp({
  value,
  duration = 900,
  delay = 0,
  format = defaultFormat,
  className,
}: CountUpProps) {
  const [displayValue, setDisplayValue] = useState(0);
  const startTimeRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const mediaQuery = typeof window !== "undefined" && window.matchMedia
      ? window.matchMedia("(prefers-reduced-motion: reduce)")
      : null;

    if (mediaQuery?.matches) {
      setDisplayValue(value);
      return;
    }

    const safeValue = Number.isFinite(value) ? value : 0;
    if (safeValue === 0) {
      setDisplayValue(0);
      return;
    }

    const timeoutId = window.setTimeout(() => {
      startTimeRef.current = null;

      const tick = (timestamp: number) => {
        if (startTimeRef.current === null) {
          startTimeRef.current = timestamp;
        }

        const elapsed = timestamp - startTimeRef.current;
        const progress = Math.min(1, elapsed / duration);
        const eased = 1 - Math.pow(1 - progress, 3);
        setDisplayValue(safeValue * eased);

        if (progress < 1) {
          rafRef.current = window.requestAnimationFrame(tick);
          return;
        }

        setDisplayValue(safeValue);
      };

      rafRef.current = window.requestAnimationFrame(tick);
    }, delay);

    return () => {
      window.clearTimeout(timeoutId);
      if (rafRef.current !== null) {
        window.cancelAnimationFrame(rafRef.current);
      }
    };
  }, [delay, duration, value]);

  return <span className={className}>{format(displayValue)}</span>;
}
