"use client";

import Link from "next/link";
import { ArrowLeftIcon, ClockIcon, ShieldCheckIcon, UserIcon } from "lucide-react";

import type { ParticipantViewAudit } from "@/api/companies";
import { EmptyState } from "@/components/presentation/empty-state";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

type ParticipantViewAuditsListProps = {
  companyId: string;
  audits: ParticipantViewAudit[];
};

export function ParticipantViewAuditsList({ companyId, audits }: ParticipantViewAuditsListProps) {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Jurnal de acces: Vizualizări participanți
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Istoricul complet și neschimbabil al accesărilor în modul de previzualizare participant pentru această companie.
          </p>
        </div>
        <Link
          href={`/trainer/companies/${companyId}`}
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground shadow-xs hover:bg-muted"
        >
          <ArrowLeftIcon className="h-3.5 w-3.5" />
          Înapoi la companie
        </Link>
      </div>

      {audits.length === 0 ? (
        <EmptyState
          title="Nu există accesări înregistrate"
          description="Nicio vizualizare ca participant nu a fost efectuată până acum pentru această companie."
        />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/50 text-xs font-semibold text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Data și ora</th>
                  <th className="px-4 py-3">Participant vizualizat</th>
                  <th className="px-4 py-3">Trainer</th>
                  <th className="px-4 py-3">Ecran</th>
                  <th className="px-4 py-3">Stare</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {audits.map((audit) => {
                  const formattedDate = new Date(audit.createdAt).toLocaleString("ro-RO", {
                    dateStyle: "medium",
                    timeStyle: "medium",
                  });
                  return (
                    <tr key={audit.id} className="hover:bg-muted/20">
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-muted-foreground">
                        <div className="flex items-center gap-1.5">
                          <ClockIcon className="h-3.5 w-3.5 text-muted-foreground" />
                          {formattedDate}
                        </div>
                      </td>
                      <td className="px-4 py-3 font-medium text-foreground">
                        <div className="flex items-center gap-1.5">
                          <UserIcon className="h-3.5 w-3.5 text-brand-primary" />
                          {audit.participantName}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        {audit.trainerEmail}
                      </td>
                      <td className="px-4 py-3 text-xs">
                        <Badge variant="secondary" className="font-mono text-xs">
                          {audit.screen}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-xs">
                        <Badge variant="outline" className="gap-1 border-emerald-300 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
                          <ShieldCheckIcon className="h-3 w-3" />
                          Înregistrat (Read-only)
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
