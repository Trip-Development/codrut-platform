"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";

import {
  hasPermanentParticipantAccount,
  type CompanyParticipant,
} from "@/api/companies";
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
              placeholder="Caută participanți"
              className="max-w-2xl"
            />
          </div>
          <span className="sr-only" role="status" aria-live="polite">
            {query !== deferredQuery ? "Se actualizează lista" : ""}
          </span>
          <div className="md:overflow-x-auto md:[scrollbar-width:thin]">
            <table className="block w-full text-left text-sm md:table md:min-w-[52rem] xl:min-w-0 xl:table-fixed">
              <colgroup>
                <col className="w-[22%]" />
                <col className="w-[28%]" />
                <col className="w-[18%]" />
                <col className="w-[20%]" />
                <col className="w-[12%]" />
              </colgroup>
              <thead className="hidden bg-muted/60 text-xs font-semibold text-muted-foreground md:table-header-group">
                <tr>
                  <th scope="col" className="min-w-52 px-5 py-3">Participant</th>
                  <th scope="col" className="min-w-56 px-4 py-3">Email</th>
                  <th scope="col" className="min-w-40 px-4 py-3">Rol</th>
                  <th scope="col" className="min-w-40 px-4 py-3">Manager</th>
                  <th scope="col" className="min-w-32 px-4 py-3">Cont</th>
                </tr>
              </thead>
              <tbody className="block divide-y divide-border md:table-row-group">
                {visibleParticipants.length > 0 ? visibleParticipants.map((participant) => {
                  const hasPermanentAccount = hasPermanentParticipantAccount(participant);
                  return (
                    <tr key={participant.id} className="grid grid-cols-2 gap-x-4 gap-y-3 px-5 py-4 transition-colors hover:bg-muted/35 md:table-row md:px-0 md:py-0">
                      <td className="col-span-2 row-start-1 font-semibold text-foreground md:px-5 md:py-4">{participant.full_name}</td>
                      <td className="col-span-2 row-start-2 break-all text-muted-foreground md:px-4 md:py-4">
                        <span className="mb-1 block text-xs font-medium md:hidden">Email</span>
                        {participant.email ?? "Email lipsă"}
                      </td>
                      <td className="col-start-1 row-start-3 text-foreground md:px-4 md:py-4">
                        <span className="mb-1 block text-xs font-medium text-muted-foreground md:hidden">Rol</span>
                        {participant.position ?? (participant.role_group === "leadership" ? "Leadership" : "Membru")}
                      </td>
                      <td className="col-start-2 row-start-3 text-right text-muted-foreground md:px-4 md:py-4 md:text-left">
                        <span className="mb-1 block text-xs font-medium md:hidden">Manager</span>
                        {participant.reports_to_name ?? "Fără manager"}
                      </td>
                      <td className="col-span-2 row-start-4 border-t pt-3 md:border-0 md:px-4 md:py-4">
                        <span className="mb-1 block text-xs font-medium text-muted-foreground md:hidden">Cont</span>
                        <span className="inline-flex items-center gap-2 whitespace-nowrap font-medium text-foreground">
                          <span
                            aria-hidden="true"
                            className={hasPermanentAccount ? "size-2 rounded-full bg-success-ink" : "size-2 rounded-full bg-muted-foreground"}
                          />
                          {hasPermanentAccount ? "Activ" : "Necreat"}
                        </span>
                      </td>
                    </tr>
                  );
                }) : (
                  <tr className="block md:table-row">
                    <td colSpan={5} className="block px-5 py-10 text-center text-sm text-muted-foreground md:table-cell">
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
