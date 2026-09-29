"use client";

import { cn } from "@/utils/cn";

/**
 * Alegerea tipului de proiect — plicul 166, A5 (cererea chatului Aplicației, 29 septembrie).
 *
 * Proiectul Cody al lui Andrei a ieșit „de chestionare” fiindcă „Tip proiect” venea gata pus și se
 * rata ușor. Acum nu e nimic ales dinainte, iar sub fiecare tip scrie, pe scurt, ce face.
 * În aplicație numai `training` schimbă ceva (Cody pornit, fără chestionare); celelalte patru se
 * poartă la fel și diferă doar prin nume — explicațiile spun exact asta.
 */
const FARA_CODY = "Chestionare și rezultate pentru participanți. Fără exersare cu Cody.";

export const PROJECT_TYPE_CHOICES: ReadonlyArray<{ value: string; label: string; explicatie: string }> = [
  { value: "training", label: "Training", explicatie: "Exersare cu Cody. Participanții nu primesc chestionare." },
  { value: "team_coaching", label: "Coaching de echipă", explicatie: FARA_CODY },
  { value: "individual_coaching", label: "Coaching individual", explicatie: FARA_CODY },
  { value: "leadership_program", label: "Program de leadership", explicatie: FARA_CODY },
  { value: "custom", label: "Personalizat", explicatie: FARA_CODY },
];

export function ProjectTypeChoice({
  name,
  value,
  onChange,
  disabled = false,
  invalid = false,
}: {
  name: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  invalid?: boolean;
}) {
  // Un tip vechi care nu e în listă (de pildă „cohort_program”) rămâne vizibil și ales.
  const choices = value && !PROJECT_TYPE_CHOICES.some((c) => c.value === value)
    ? [...PROJECT_TYPE_CHOICES, { value, label: value, explicatie: "" }]
    : PROJECT_TYPE_CHOICES;
  return (
    <fieldset
      className={cn("grid gap-2", invalid && "rounded-md ring-1 ring-destructive")}
      aria-invalid={invalid || undefined}
      data-project-type-choice
    >
      <legend className="sr-only">Tip proiect</legend>
      {choices.map((choice) => (
        <label
          key={choice.value}
          className={cn(
            "flex cursor-pointer items-start gap-2.5 rounded-md border border-border bg-surface px-3 py-2",
            value === choice.value && "border-primary bg-primary/5",
            disabled && "cursor-not-allowed opacity-60",
          )}
        >
          <input
            type="radio"
            name={name}
            value={choice.value}
            checked={value === choice.value}
            onChange={() => onChange(choice.value)}
            disabled={disabled}
            className="mt-1"
          />
          <span className="min-w-0">
            <span className="block text-sm font-semibold text-foreground">{choice.label}</span>
            {choice.explicatie ? (
              <span className="block text-xs leading-5 text-muted-foreground">{choice.explicatie}</span>
            ) : null}
          </span>
        </label>
      ))}
    </fieldset>
  );
}
