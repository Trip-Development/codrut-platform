"use client";

import { useState } from "react";

import {
  reopenParticipantAssignment,
  type CompanyParticipant,
  type ParticipantReopenableAssignment,
} from "@/api/companies";
import { Button } from "@/components/ui/button";
import { ModalCloseButton, ModalLayer } from "@/components/ui/modal-layer";

/** De la a cata redeschidere aratam avertismentul. Butonul ramane apasabil. */
export const REOPEN_WARNING_THRESHOLD = 3;

const QUESTIONNAIRE_NAMES: Record<string, string> = {
  lencioni: "Lencioni",
  lencioni_en: "Lencioni (engleză)",
  distress_drivers: "Driveri de stres",
  distress_drivers_en: "Driveri de stres (engleză)",
  boss_360: "Feedback 360",
  boss_360_en: "Feedback 360 (engleză)",
  icare: "iCARE 360",
  pcm_base: "PCM – profil de bază",
  phase: "PCM – faza",
};

export function questionnaireName(key: string): string {
  return QUESTIONNAIRE_NAMES[key] ?? key;
}

export function formatReopenDate(value: string | null | undefined): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleDateString("ro-RO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

/** Textul de sub numele omului: de câte ori a fost redeschis și când ultima dată. */
export function reopenSummaryText(participant: CompanyParticipant): string | null {
  const count = participant.reopen_count ?? 0;
  if (count <= 0) return null;
  const date = formatReopenDate(participant.last_reopened_at);
  const times = count === 1 ? "o dată" : `de ${count} ori`;
  return date ? `Redeschis ${times} · ultima pe ${date}` : `Redeschis ${times}`;
}

export type ReopenQuestionnaireDialogProps = {
  companyId: string;
  participant: CompanyParticipant;
  onClose: () => void;
  onDone: () => void;
};

export function ReopenQuestionnaireDialog({
  companyId,
  participant,
  onClose,
  onDone,
}: ReopenQuestionnaireDialogProps) {
  const options = participant.reopenable_assignments ?? [];
  const [selectedId, setSelectedId] = useState<string>(options[0]?.assignment_id ?? "");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selected: ParticipantReopenableAssignment | undefined = options.find(
    (option) => option.assignment_id === selectedId,
  );
  const timesBefore = selected?.reopen_count ?? 0;
  const showWarning = timesBefore + 1 >= REOPEN_WARNING_THRESHOLD;

  async function confirm() {
    if (!selected) return;
    setWorking(true);
    setError(null);
    try {
      await reopenParticipantAssignment(companyId, selected.assignment_id);
      onDone();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Redeschiderea nu a reușit.");
      setWorking(false);
    }
  }

  return (
    <ModalLayer labelledBy="reopen-title" onClose={onClose} panelClassName="max-w-xl">
      <div className="flex items-start justify-between gap-4">
        <h2 id="reopen-title" className="text-xl font-semibold text-foreground">
          Redeschide un chestionar
        </h2>
        <ModalCloseButton onClick={onClose} />
      </div>

      <div className="mt-5 space-y-4 text-sm">
        <p className="text-foreground">
          Pentru <strong>{participant.full_name}</strong>.
        </p>

        {options.length > 1 ? (
          <fieldset className="space-y-2">
            <legend className="mb-1 font-medium text-foreground">Care chestionar?</legend>
            {options.map((option) => (
              <label
                key={option.assignment_id}
                className="flex items-center gap-3 rounded-md border border-border px-3 py-2"
              >
                <input
                  type="radio"
                  name="reopen-assignment"
                  value={option.assignment_id}
                  checked={option.assignment_id === selectedId}
                  onChange={() => setSelectedId(option.assignment_id)}
                />
                <span className="text-foreground">{questionnaireName(option.questionnaire_key)}</span>
                {option.reopen_count > 0 ? (
                  <span className="ml-auto text-xs text-muted-foreground">
                    redeschis {option.reopen_count === 1 ? "o dată" : `de ${option.reopen_count} ori`}
                  </span>
                ) : null}
              </label>
            ))}
          </fieldset>
        ) : selected ? (
          <p className="text-foreground">
            Chestionarul: <strong>{questionnaireName(selected.questionnaire_key)}</strong>
          </p>
        ) : null}

        <div className="rounded-md bg-muted/60 px-4 py-3 text-foreground/80">
          <p className="font-medium text-foreground">Ce se întâmplă</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>Răspunsurile date până acum se păstrează într-o arhivă.</li>
            <li>Omul pornește de la zero, cu chestionarul gol.</li>
            <li>Rezultatul lui dispare acum și reapare după ce îl trimite din nou.</li>
            <li>Nu i se trimite niciun email. Îl găsește singur în lista lui.</li>
          </ul>
        </div>

        {showWarning ? (
          <div
            role="alert"
            className="rounded-md border border-amber-500/50 bg-amber-50 px-4 py-3 text-amber-900"
          >
            <p className="font-medium">
              Atenție: ar fi a {timesBefore + 1}-a oară când i se redeschide acest chestionar.
            </p>
            <p className="mt-1">
              Poți continua, dar merită întâi o vorbă cu el — de obicei atâtea reluări înseamnă
              că altceva nu e în regulă.
            </p>
          </div>
        ) : null}

        {error ? (
          <p role="alert" className="rounded-md bg-destructive/10 px-4 py-3 text-destructive">
            {error}
          </p>
        ) : null}
      </div>

      <div className="mt-6 flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onClose} disabled={working}>
          Renunță
        </Button>
        <Button type="button" onClick={confirm} disabled={working || !selected}>
          {working ? "Se redeschide..." : "Da, redeschide"}
        </Button>
      </div>
    </ModalLayer>
  );
}
