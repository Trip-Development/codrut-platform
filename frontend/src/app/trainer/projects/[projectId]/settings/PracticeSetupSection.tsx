"use client";

import { useEffect, useState } from "react";

import {
  configurePracticeSetup,
  getPracticeSetup,
  getPracticeThemes,
  type PracticeSetup,
  type PracticeTheme,
} from "@/api/practice";
import { Card } from "@/components/ui/card";

/**
 * Exersarea pe un proiect de training: tema, și competențele bifate.
 *
 * Decizia lui Andrei, 30 august: *„Automat din temă dar vreau să existe și buton
 * ca eu să mai adaug sau să scot competențe dacă vreau."* Cele ale temei apar
 * bifate; se scot și se pun la loc oricând, nu doar la creare.
 *
 * Până la plicul 29, rândul de configurare se punea de mână, cu un script — nicio
 * rută a aplicației nu îl crea. De aici încolo îl scrie aplicația.
 */
export function PracticeSetupSection({ projectId }: { projectId: string }) {
  const [themes, setThemes] = useState<PracticeTheme[]>([]);
  const [setup, setSetup] = useState<PracticeSetup | null>(null);
  const [themeId, setThemeId] = useState<string>("");
  const [ticked, setTicked] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      const [t, s] = await Promise.all([
        getPracticeThemes(),
        getPracticeSetup(projectId),
      ]);
      if (!alive) return;
      setThemes(t);
      setSetup(s);
      const initialTheme = s?.themeId ?? t.find((x) => x.usable)?.id ?? t[0]?.id ?? "";
      setThemeId(initialTheme);
      if (s && s.competencies.length > 0) {
        setTicked(new Set(s.competencies.map((c) => c.name)));
      } else {
        const theme = t.find((x) => x.id === initialTheme);
        setTicked(new Set((theme?.competencies ?? []).map((c) => c.name)));
      }
    })().catch(() => setError("Nu am putut încărca temele."));
    return () => {
      alive = false;
    };
  }, [projectId]);

  const theme = themes.find((t) => t.id === themeId);

  function pickTheme(id: string) {
    setThemeId(id);
    const t = themes.find((x) => x.id === id);
    // La schimbarea temei, competențele ei vin bifate — asta e „automat din temă".
    setTicked(new Set((t?.competencies ?? []).map((c) => c.name)));
    setMessage(null);
  }

  function toggle(name: string) {
    setTicked((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
    setMessage(null);
  }

  async function save() {
    if (!themeId) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const result = await configurePracticeSetup(projectId, {
        themeId,
        competencies: Array.from(ticked),
      });
      setSetup(result);
      setMessage("Salvat. Participanții pot exersa pe proiectul ăsta.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nu am putut salva.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="p-5">
      <h3 className="text-base font-semibold text-foreground">Exersare cu Cody</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        {setup?.configured
          ? "Exersarea e pornită pe proiectul ăsta."
          : "Alege tema și competențele, ca participanții să poată exersa."}
      </p>

      <label className="mt-4 block text-sm font-medium text-foreground" htmlFor="practice-theme">
        Tema
      </label>
      <select
        id="practice-theme"
        value={themeId}
        onChange={(e) => pickTheme(e.target.value)}
        className="mt-1 w-full rounded-md border bg-surface px-3 py-2 text-sm"
      >
        {themes.map((t) => (
          <option key={t.id} value={t.id} disabled={!t.usable}>
            {t.name}
            {t.usable ? "" : " — fără material, nu poate găzdui o sesiune"}
          </option>
        ))}
      </select>

      <fieldset className="mt-5">
        <legend className="text-sm font-medium text-foreground">
          Competențe evaluate ({ticked.size} din {theme?.competencies.length ?? 0})
        </legend>
        <p className="mt-1 text-xs text-muted-foreground">
          Cele ale temei sunt bifate. Scoate ce nu-ți trebuie, pune la loc dacă te
          răzgândești. Se poate reveni oricând.
        </p>
        <ul className="mt-3 flex flex-col gap-2">
          {(theme?.competencies ?? []).map((c) => (
            <li key={c.name}>
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={ticked.has(c.name)}
                  onChange={() => toggle(c.name)}
                  className="mt-0.5"
                />
                <span>
                  <span className="font-medium text-foreground">{c.name}</span>
                  {c.description ? (
                    <span className="block text-xs text-muted-foreground">{c.description}</span>
                  ) : null}
                </span>
              </label>
            </li>
          ))}
        </ul>
      </fieldset>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={saving || !themeId || !theme?.usable}
          className="rounded-md bg-burgundy px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {saving ? "Salvez…" : "Salvează competențele"}
        </button>
        {message ? <span className="text-sm text-muted-foreground">{message}</span> : null}
        {error ? <span className="text-sm text-danger">{error}</span> : null}
      </div>
    </Card>
  );
}
