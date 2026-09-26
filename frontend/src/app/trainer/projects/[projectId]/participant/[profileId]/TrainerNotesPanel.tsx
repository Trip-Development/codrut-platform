"use client";

import { useState } from "react";

import { addTrainerNote, type TrainerNote } from "@/api/practice";
import { Card } from "@/components/ui/card";

/** Notele trainerului — portat din `TrainerNotes.tsx` (149 rd.). Andrei scrie, se salvează. */
export function TrainerNotesPanel({
  projectId,
  profileId,
  initialNotes,
  canWrite,
}: {
  projectId: string;
  profileId: string;
  initialNotes: TrainerNote[];
  canWrite: boolean;
}) {
  const [notes, setNotes] = useState<TrainerNote[]>(initialNotes);
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    const t = text.trim();
    if (!t) return;
    setSaving(true);
    setError(null);
    try {
      const nota = await addTrainerNote(projectId, profileId, t);
      setNotes((prev) => [nota, ...prev]);
      setText("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nu am putut salva nota.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="p-5">
      <h3 className="text-base font-semibold text-foreground">Notele trainerului</h3>
      <p className="mt-1 text-xs text-muted-foreground">
        Ce observi tu despre om, în afara cifrelor. Le vezi doar tu.
      </p>

      {canWrite ? (
        <div className="mt-4">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={3}
            placeholder="Scrie o notă…"
            className="w-full rounded-md border bg-surface px-3 py-2 text-sm"
          />
          <div className="mt-2 flex items-center gap-3">
            <button
              type="button"
              onClick={save}
              disabled={saving || !text.trim()}
              className="rounded-md bg-burgundy px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {saving ? "Salvez…" : "Salvează nota"}
            </button>
            {error ? <span className="text-sm text-danger">{error}</span> : null}
          </div>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">
          Participantul nu are încă un cont, deci nu i se pot atașa note.
        </p>
      )}

      {notes.length === 0 ? (
        <p className="mt-5 text-sm text-muted-foreground">Nicio notă încă.</p>
      ) : (
        <ul className="mt-5 flex flex-col gap-3">
          {notes.map((n) => (
            <li key={n.id} className="border-t pt-3 first:border-t-0 first:pt-0">
              <p className="whitespace-pre-wrap text-sm text-foreground">{n.note}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {n.createdAt ? new Date(n.createdAt).toLocaleString("ro-RO") : ""}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
