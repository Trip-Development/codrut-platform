"use client";

import { ArchiveIcon, Loader2Icon, RotateCcwIcon, SearchIcon } from "lucide-react";

import type { CampaignRecipientRow } from "@/api/email";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { campaignRecipientName, campaignRecipientStatusLabel } from "./campaign-domain";

type ArchiveAction = {
  recipientId: string;
  kind: "restore";
} | null;

export function ArchivedContactsWorkspaceView({
  message,
  contacts,
  search,
  action,
  setSearch,
  restoreContact,
}: {
  message: string | null;
  contacts: CampaignRecipientRow[];
  search: string;
  action: ArchiveAction;
  setSearch: (value: string) => void;
  restoreContact: (recipient: CampaignRecipientRow) => void;
}) {
  return (
    <div className="p-5">
      {message ? (
        <InlineFeedback className="mb-4" descriptionClassName="text-xs leading-5">
          {message}
        </InlineFeedback>
      ) : null}

      <div className="mb-4 grid gap-3 border-b border-[var(--border)] pb-4 md:grid-cols-[minmax(18rem,32rem)_1fr] md:items-center">
        <label className="relative">
          <SearchIcon
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            strokeWidth={1.8}
          />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Caută în arhivă"
            className="h-11 rounded-md bg-background pl-9 text-sm"
            aria-label="Caută contacte arhivate"
          />
        </label>
        <p className="text-xs leading-5 text-muted-foreground md:text-right">
          Contactele rămân în siguranță în Arhivă și nu pot fi folosite în campanii.{" "}
          Ștergerea definitivă va deveni disponibilă după următoarea actualizare de confidențialitate.
        </p>
      </div>

      <div className="overflow-x-auto rounded-lg border border-[var(--border)] bg-surface">
        <table className="min-w-[42rem] text-left text-xs">
          <thead className="border-b border-[var(--border)] bg-surface-muted text-[10px] font-semibold uppercase tracking-[0.12em] text-foreground/50">
            <tr>
              <th className="min-w-[22rem] px-4 py-3">Contact</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Acțiuni</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {contacts.length > 0 ? contacts.map((recipient) => {
              const name = campaignRecipientName(recipient);
              const restoring = action?.recipientId === recipient.id && action.kind === "restore";
              const disabled = action !== null;
              return (
                <tr key={recipient.id} className="transition-colors hover:bg-surface-muted/70">
                  <td className="px-4 py-3">
                    <div className="flex min-w-0 items-start gap-3">
                      <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-zinc-400 text-xs font-semibold uppercase text-white">
                        {(name || recipient.company || recipient.email).slice(0, 2)}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-foreground">{recipient.company}</p>
                        <p className="mt-1 truncate text-xs font-medium text-foreground/60">{name || "Contact fără nume"}</p>
                        <p className="mt-1 truncate font-mono text-[11px] text-foreground/40">{recipient.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-2 font-semibold text-foreground">
                      <ArchiveIcon aria-hidden="true" className="size-4 text-muted-foreground" strokeWidth={1.8} />
                      {campaignRecipientStatusLabel("archived")}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={disabled}
                        onClick={() => restoreContact(recipient)}
                      >
                        {restoring
                          ? <Loader2Icon data-icon="inline-start" aria-hidden="true" className="animate-spin" strokeWidth={1.8} />
                          : <RotateCcwIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />}
                        {restoring ? "Restaurăm" : "Restaurează"}
                      </Button>
                    </div>
                  </td>
                </tr>
              );
            }) : (
              <tr>
                <td colSpan={3} className="px-6 py-12 text-center text-sm font-medium text-foreground/50">
                  <ArchiveIcon aria-hidden="true" className="mx-auto mb-3 size-6" strokeWidth={1.6} />
                  {search.trim() ? "Niciun contact arhivat nu corespunde căutării." : "Arhiva este goală."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
