"use client";

import {
  ArchiveIcon,
  Loader2Icon,
  RotateCcwIcon,
  Trash2Icon,
} from "lucide-react";

import type { CampaignRecipientRow } from "@/api/email";
import { IdentityMark } from "@/components/presentation/identity-mark";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { Button } from "@/components/ui/button";
import { SearchField } from "@/components/ui/search-field";
import {
  campaignRecipientIdentityLabel,
  campaignRecipientName,
  campaignRecipientStatusLabel,
} from "./campaign-domain";

type ArchiveAction = {
  recipientId: string;
  kind: "restore" | "delete";
} | null;

export function ArchivedContactsWorkspaceView({
  message,
  contacts,
  search,
  action,
  setSearch,
  restoreContact,
  deleteContact,
}: {
  message: string | null;
  contacts: CampaignRecipientRow[];
  search: string;
  action: ArchiveAction;
  setSearch: (value: string) => void;
  restoreContact: (recipient: CampaignRecipientRow) => void;
  deleteContact: (recipient: CampaignRecipientRow) => void;
}) {
  return (
    <div className="p-5">
      {message ? (
        <InlineFeedback className="mb-4" descriptionClassName="text-xs leading-5">
          {message}
        </InlineFeedback>
      ) : null}

      <div className="mb-4 grid gap-3 border-b border-[var(--border)] pb-4 md:grid-cols-[minmax(18rem,32rem)_1fr] md:items-center">
        <SearchField
          id="archived-contacts-search"
          label="Caută contacte arhivate"
          value={search}
          onValueChange={setSearch}
          placeholder="Caută în arhivă"
        />
        <p className="text-xs leading-5 text-muted-foreground md:text-right">
          Contactele arhivate nu mai pot fi folosite în campanii. Le poți restaura înainte
          de curățarea automată sau le poți șterge definitiv acum. Păstrăm doar protecția
          necesară ca o adresă respinsă ori dezabonată să nu primească alte mesaje.
        </p>
      </div>

      <div className="overflow-x-auto rounded-lg border border-[var(--border)] bg-surface">
        <table className="min-w-[42rem] text-left text-xs">
          <thead className="border-b border-[var(--border)] bg-surface-muted text-[10px] font-semibold uppercase tracking-[0.12em] text-foreground/50">
            <tr>
              <th className="min-w-[22rem] px-4 py-3">Contact</th>
              <th className="px-4 py-3">Status și curățare</th>
              <th className="px-4 py-3 text-right">Acțiuni</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {contacts.length > 0 ? contacts.map((recipient) => {
              const name = campaignRecipientName(recipient);
              const restoring = action?.recipientId === recipient.id && action.kind === "restore";
              const deleting = action?.recipientId === recipient.id && action.kind === "delete";
              const disabled = action !== null;
              return (
                <tr key={recipient.id} className="transition-colors hover:bg-surface-muted/70">
                  <td className="px-4 py-3">
                    <div className="flex min-w-0 items-start gap-3">
                      <IdentityMark
                        kind="contact"
                        label={campaignRecipientIdentityLabel(recipient)}
                        seed={`contact:${recipient.id}`}
                        size="sm"
                      />
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
                    <p className="mt-1.5 text-[11px] leading-4 text-muted-foreground">
                      Înainte: {archivedProtectionLabel(recipient.statusBeforeArchive)}
                    </p>
                    <p className="mt-1 text-[11px] leading-4 text-muted-foreground">
                      {recipient.purgeAfter
                        ? `Curățare automată: ${formatArchiveDate(recipient.purgeAfter)}`
                        : "Data curățării nu este disponibilă"}
                    </p>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
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
                      <Button
                        type="button"
                        variant="destructive"
                        size="sm"
                        disabled={disabled}
                        onClick={() => deleteContact(recipient)}
                      >
                        {deleting
                          ? <Loader2Icon data-icon="inline-start" aria-hidden="true" className="animate-spin" strokeWidth={1.8} />
                          : <Trash2Icon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />}
                        {deleting ? "Ștergem" : "Șterge definitiv"}
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

function archivedProtectionLabel(
  status: CampaignRecipientRow["statusBeforeArchive"],
): string {
  if (status === "suppressed") return "Adresă respinsă";
  if (status === "unsubscribed") return "Dezabonat";
  if (status === "active") return "Activ";
  return "Status indisponibil";
}

function formatArchiveDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "dată indisponibilă";
  return new Intl.DateTimeFormat("ro-RO", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Europe/Bucharest",
  }).format(date);
}
