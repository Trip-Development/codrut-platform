"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";

import type { CompanyParticipant } from "@/api/companies";
import { useUrlState } from "@/hooks/use-url-state";
import {
  normalizeWorkspaceSearch,
  WorkspaceSearchInput,
} from "../../projects/project-workspace-controls";

export function CompanyParticipantsTable({
  participants,
}: {
  participants: CompanyParticipant[];
}) {
  const { get, searchKey, setParam } = useUrlState();
  const [query, setQuery] = useState(() => get("q") ?? "");
  const deferredQuery = useDeferredValue(query);
  const visibleParticipants = useMemo(() => {
    const normalizedQuery = normalizeWorkspaceSearch(deferredQuery);
    if (!normalizedQuery) return participants;

    return participants.filter((participant) =>
      normalizeWorkspaceSearch([
        participant.full_name,
        participant.email,
        participant.position,
        participant.reports_to_name,
        participant.location,
        participant.role_group,
      ].filter(Boolean).join(" ")).includes(normalizedQuery),
    );
  }, [deferredQuery, participants]);

  useEffect(() => {
    setQuery(get("q") ?? "");
  }, [get, searchKey]);

  function updateQuery(nextQuery: string) {
    setQuery(nextQuery);
    setParam("q", nextQuery || null, "replace");
  }

  return (
    <section
      className="overflow-hidden rounded-lg border border-border bg-surface"
      aria-labelledby="company-participants-title"
      aria-busy={query !== deferredQuery}
    >
      <header className="flex min-h-14 items-center justify-between gap-4 border-b border-border px-5 py-3">
        <h2 id="company-participants-title" className="text-base font-semibold text-foreground">Participanți</h2>
        <span className="text-sm font-medium tabular-nums text-muted-foreground">
          {visibleParticipants.length === participants.length
            ? participants.length
            : `${visibleParticipants.length} din ${participants.length}`}
        </span>
      </header>
      {participants.length > 0 ? (
        <>
          <div className="border-b border-border p-4">
            <WorkspaceSearchInput
              id="company-participants-search"
              label="Caută participant"
              value={query}
              onValueChange={updateQuery}
              placeholder="Caută după nume, email, rol sau manager"
              className="max-w-2xl"
            />
          </div>
          <span className="sr-only" role="status" aria-live="polite">
            {query !== deferredQuery ? "Se actualizează lista" : ""}
          </span>
          <div className="overflow-x-auto [scrollbar-width:thin]">
            <table className="w-full min-w-[52rem] text-left text-sm">
              <thead className="bg-muted/60 text-xs font-semibold text-muted-foreground">
                <tr>
                  <th scope="col" className="min-w-52 px-5 py-3">Participant</th>
                  <th scope="col" className="min-w-56 px-4 py-3">Email</th>
                  <th scope="col" className="min-w-40 px-4 py-3">Rol</th>
                  <th scope="col" className="min-w-40 px-4 py-3">Manager</th>
                  <th scope="col" className="min-w-32 px-4 py-3">Cont</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {visibleParticipants.length > 0 ? visibleParticipants.map((participant) => (
                  <tr key={participant.id} className="transition-colors hover:bg-muted/35">
                    <td className="px-5 py-4 font-semibold text-foreground">{participant.full_name}</td>
                    <td className="px-4 py-4 text-muted-foreground">{participant.email ?? "Email lipsă"}</td>
                    <td className="px-4 py-4 text-foreground">
                      {participant.position ?? (participant.role_group === "leadership" ? "Leadership" : "Membru")}
                    </td>
                    <td className="px-4 py-4 text-muted-foreground">{participant.reports_to_name ?? "Fără manager"}</td>
                    <td className="px-4 py-4">
                      <span className="inline-flex items-center gap-2 whitespace-nowrap font-medium text-foreground">
                        <span
                          aria-hidden="true"
                          className={participant.user_id ? "size-2 rounded-full bg-emerald-500" : "size-2 rounded-full bg-zinc-400"}
                        />
                        {participant.user_id ? "Activ" : "Necreat"}
                      </span>
                    </td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan={5} className="px-5 py-10 text-center text-sm text-muted-foreground">
                      Niciun participant pentru căutarea curentă.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p className="px-5 py-10 text-center text-sm text-muted-foreground">Niciun participant adăugat.</p>
      )}
    </section>
  );
}
