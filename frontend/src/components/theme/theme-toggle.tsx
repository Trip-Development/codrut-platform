"use client";

import { useEffect, useRef, useState, type MouseEvent } from "react";

type ThemeMode = "light" | "dark";
type ViewTransitionDocument = Document & {
  startViewTransition?: (callback: () => void) => {
    ready: Promise<void>;
  };
};
type ViewTransitionAnimationOptions = KeyframeAnimationOptions & {
  pseudoElement?: string;
};

const STORAGE_KEY = "codrut-theme";

function getInitialTheme(): ThemeMode {
  if (typeof window === "undefined") {
    return "light";
  }

  try {
    if (!window.localStorage) {
      return "light";
    }
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") {
      return stored;
    }
  } catch {
    // Handle cases where localStorage is disabled or throws
  }

  if (typeof window.matchMedia !== "function") {
    return "light";
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<ThemeMode>("light");
  const revealAnimationRef = useRef<Animation | null>(null);

  useEffect(() => {
    const initialTheme = getInitialTheme();
    setTheme(initialTheme);
    document.documentElement.dataset.theme = initialTheme;
  }, []);

  function applyTheme(nextTheme: ThemeMode) {
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    window.localStorage.setItem(STORAGE_KEY, nextTheme);
  }

  function toggleTheme(event: MouseEvent<HTMLButtonElement>) {
    const nextTheme = theme === "light" ? "dark" : "light";
    const transitionDocument = document as ViewTransitionDocument;

    if (!transitionDocument.startViewTransition || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      applyTheme(nextTheme);
      return;
    }

    const { left, top, width, height } = event.currentTarget.getBoundingClientRect();
    const x = left + width / 2;
    const y = top + height / 2;
    const endRadius = Math.hypot(
      Math.max(x, window.innerWidth - x),
      Math.max(y, window.innerHeight - y),
    );
    const transition = transitionDocument.startViewTransition(() => applyTheme(nextTheme));

    transition.ready.then(() => {
      revealAnimationRef.current?.cancel();
      revealAnimationRef.current = document.documentElement.animate(
        {
          clipPath: [
            `circle(0px at ${x}px ${y}px)`,
            `circle(${endRadius}px at ${x}px ${y}px)`,
          ],
        },
        {
          duration: 860,
          easing: "cubic-bezier(0.16, 1, 0.3, 1)",
          pseudoElement: "::view-transition-new(root)",
        } as ViewTransitionAnimationOptions,
      );
    }).catch(() => undefined);
  }

  const isDark = theme === "dark";

  return (
    <button
      type="button"
      aria-label={isDark ? "Activează tema luminoasă" : "Activează tema întunecată"}
      aria-pressed={isDark}
      onClick={toggleTheme}
      className="radiate-button tap-soft inline-flex h-8 w-8 items-center justify-center rounded-full border border-[var(--border)] bg-surface text-burgundy shadow-sm outline-none hover:border-burgundy/25 hover:bg-surface-muted focus:outline-none focus:ring-0 focus-visible:outline-none focus-visible:ring-0 active:outline-none active:ring-0 dark:text-success-ink"
      style={{ outline: "none", boxShadow: "0 1px 2px rgba(24, 24, 27, 0.04)" }}
    >
      <span
        key={theme}
        aria-hidden
        className="relative z-10 flex h-4 w-4 items-center justify-center animate-fade-up"
      >
        {isDark ? <MoonIcon /> : <SunIcon />}
      </span>
    </button>
  );
}

function SunIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.8" />
      <path
        d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 24 24" fill="none">
      <path
        d="M19 14.6A7.2 7.2 0 0 1 9.4 5a7.5 7.5 0 1 0 9.6 9.6Z"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}
