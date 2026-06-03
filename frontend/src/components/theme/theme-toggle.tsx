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
      className="tap-soft inline-flex h-11 items-center gap-2 rounded-full border border-[var(--border)] bg-surface px-2 text-sm font-bold text-foreground shadow-sm"
    >
      <span
        aria-hidden="true"
        className={[
          "flex h-7 w-7 items-center justify-center rounded-full text-xs text-white transition-transform",
          isDark ? "translate-x-9 bg-foreground" : "translate-x-0 bg-burgundy",
        ].join(" ")}
      >
        {isDark ? "N" : "L"}
      </span>
      <span className="w-12 text-left text-xs text-foreground/65">{isDark ? "Noapte" : "Lumina"}</span>
    </button>
  );
}
