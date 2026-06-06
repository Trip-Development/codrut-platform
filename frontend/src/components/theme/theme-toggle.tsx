"use client";

import { useEffect, useState } from "react";

type ThemeMode = "light" | "dark";

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

  useEffect(() => {
    const initialTheme = getInitialTheme();
    setTheme(initialTheme);
    document.documentElement.dataset.theme = initialTheme;
  }, []);

  function toggleTheme() {
    const nextTheme = theme === "light" ? "dark" : "light";
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    window.localStorage.setItem(STORAGE_KEY, nextTheme);
  }

  const isDark = theme === "dark";

  return (
    <button
      type="button"
      aria-label={isDark ? "Activeaza tema luminoasa" : "Activeaza tema intunecata"}
      aria-pressed={isDark}
      onClick={toggleTheme}
      className="tap-soft inline-grid h-10 grid-cols-2 items-center rounded-full border border-[var(--border)] bg-surface-muted/82 p-1 text-foreground/42 shadow-sm backdrop-blur hover:text-foreground/68"
    >
      <span
        aria-hidden
        className={[
          "flex h-8 w-8 items-center justify-center rounded-full transition-colors",
          isDark ? "text-foreground/36" : "bg-surface text-burgundy shadow-sm",
        ].join(" ")}
      >
        <SunIcon />
      </span>
      <span
        aria-hidden
        className={[
          "flex h-8 w-8 items-center justify-center rounded-full transition-colors",
          isDark ? "bg-surface text-success-ink shadow-sm" : "text-foreground/36",
        ].join(" ")}
      >
        <MoonIcon />
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
