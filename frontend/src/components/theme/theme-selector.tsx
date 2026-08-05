"use client";

import { useEffect, useState } from "react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export type ThemeMode = "light" | "dark" | "system";
type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "codrut-theme";

export function getStoredThemeMode(): ThemeMode {
  if (typeof window === "undefined") return "system";

  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") return stored;
  } catch {
    // System preference remains available when browser storage is blocked.
  }

  return "system";
}

function getSystemTheme(): ResolvedTheme {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function resolveTheme(mode: ThemeMode): ResolvedTheme {
  return mode === "system" ? getSystemTheme() : mode;
}

function updateDocumentTheme(mode: ThemeMode) {
  document.documentElement.dataset.theme = resolveTheme(mode);
  document.documentElement.dataset.themeMode = mode;
}

export function persistThemeMode(mode: ThemeMode) {
  updateDocumentTheme(mode);
  try {
    window.localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    // Keep the selected theme for this page when storage is unavailable.
  }
}

export function ThemeSelector({ className }: { className?: string }) {
  const [themeMode, setThemeMode] = useState<ThemeMode>("system");

  useEffect(() => {
    const initialMode = getStoredThemeMode();
    setThemeMode(initialMode);
    updateDocumentTheme(initialMode);
  }, []);

  useEffect(() => {
    if (themeMode !== "system" || typeof window.matchMedia !== "function") return undefined;

    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const syncSystemTheme = () => updateDocumentTheme("system");
    query.addEventListener("change", syncSystemTheme);
    return () => query.removeEventListener("change", syncSystemTheme);
  }, [themeMode]);

  function applyTheme(mode: ThemeMode) {
    setThemeMode(mode);
    persistThemeMode(mode);
  }

  return (
    <Select value={themeMode} onValueChange={(value) => applyTheme(value as ThemeMode)}>
      <SelectTrigger aria-label="Temă" className={className ?? "h-9 min-w-32 bg-control px-3 font-medium"}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent align="end">
        <SelectItem value="system">Sistem</SelectItem>
        <SelectItem value="light">Luminoasă</SelectItem>
        <SelectItem value="dark">Întunecată</SelectItem>
      </SelectContent>
    </Select>
  );
}
