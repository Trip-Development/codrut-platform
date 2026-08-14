"use client";

import { useId, useMemo } from "react";

import type { CompanyParticipant } from "@/api/companies";
import { managerReferenceKey, normalizeReportsToName } from "@/api/roster-format";
import { Field, FieldLabel } from "@/components/ui/field";
import { SelectControl } from "@/components/ui/select-control";

export function ParticipantManagerSelect({
  participantId,
  participants,
  value,
  disabled = false,
  onChange,
}: {
  participantId: string;
  participants: CompanyParticipant[];
  value: string;
  disabled?: boolean;
  onChange: (value: string) => void;
}) {
  const selectId = useId();
  const options = useMemo(
    () => participants
      .filter((participant) => participant.id !== participantId)
      .sort((first, second) => first.full_name.localeCompare(second.full_name, "ro")),
    [participantId, participants],
  );
  const normalizedValue = normalizeReportsToName(value);
  const valueMatchesParticipant = options.some(
    (participant) => managerReferenceKey(participant.full_name) === managerReferenceKey(normalizedValue),
  );

  return (
    <Field data-disabled={disabled ? true : undefined}>
      <FieldLabel htmlFor={selectId}>Manager</FieldLabel>
      <SelectControl
        id={selectId}
        label="Manager"
        aria-label="Manager"
        value={normalizedValue}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="h-10"
      >
        <option value="">Fără manager</option>
        {normalizedValue && !valueMatchesParticipant ? (
          <option value={normalizedValue}>{normalizedValue} (referință existentă)</option>
        ) : null}
        {options.map((participant) => (
          <option key={participant.id} value={participant.full_name}>
            {participant.full_name}
          </option>
        ))}
      </SelectControl>
    </Field>
  );
}
