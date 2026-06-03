"use client";

import { useEffect, useState } from "react";

type ThemeMode = "light" | "dark";

const STORAGE_KEY = "codrut-theme";

function getInitialTheme(): ThemeMode {
  if (typeof window === "undefined") {
    return "light";
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") {
    return stored;
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
      className="tap-soft inline-grid h-10 grid-cols-2 items-center rounded-full border border-[var(--border)] bg-surface-muted/82 p-1 text-xs font-semibold text-foreground/48 shadow-sm backdrop-blur"
    >
      <span
        aria-hidden
        className={[
          "rounded-full px-3 py-1.5 transition-colors",
          isDark ? "text-foreground/42" : "bg-surface text-burgundy shadow-sm",
        ].join(" ")}
      >
        Lumina
      </span>
      <span
        aria-hidden
        className={[
          "rounded-full px-3 py-1.5 transition-colors",
          isDark ? "bg-surface text-burgundy-dark shadow-sm" : "text-foreground/42",
        ].join(" ")}
      >
        Noapte
      </span>
    </button>
  );
}
