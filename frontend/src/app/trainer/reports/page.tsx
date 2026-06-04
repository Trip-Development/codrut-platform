import Link from "next/link";

import { getTrainerSession } from "@/api/auth";
import { getTrainerReports } from "@/api/trainer";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

export default async function TrainerReportsPage() {
  const [trainer, reports] = await Promise.all([
    getTrainerSession(),
    getTrainerReports(),
  ]);

  return (
    <AppShell
      audience="trainer"
      eyebrow="Rapoarte"
      title="Rapoarte de evaluare"
      description="Sumarul complet al raspunsurilor primite. Inspecteaza rezultatele calculate pe disfunctionalitati si profile de distress."
      navItems={trainerNavItems}
      activeHref="/trainer/reports"
      userLabel={trainer.user.name}
      session={trainer}
    >
      <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
        <div className="border-b border-[var(--border)] px-5 py-4 bg-surface-muted/30">
          <h2 className="text-lg font-semibold text-foreground">Sarcini si completari</h2>
          <p className="mt-1 text-xs text-foreground/50">
            Vezi scorurile calculate pentru evaluari PCM, Lencioni, 360 si distress drivers.
          </p>
        </div>

        {reports.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-sm font-semibold text-foreground/60">Nu exista rapoarte disponibile momentan.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="border-b border-[var(--border)] bg-surface-muted/50 text-xs font-bold uppercase tracking-wider text-foreground/60">
                <tr>
                  <th className="px-5 py-4">Participant</th>
                  <th className="px-5 py-4">Chestionar</th>
                  <th className="px-5 py-4">Proiect</th>
                  <th className="px-5 py-4">Status</th>
                  <th className="px-5 py-4">Rezultat principal</th>
                  <th className="px-5 py-4">Finalizat la</th>
                  <th className="px-5 py-4 text-right">Actiuni</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {reports.map((report) => {
                  const dateLabel = report.submittedAt
                    ? new Date(report.submittedAt).toLocaleDateString("ro-RO", {
                        day: "2-digit",
                        month: "2-digit",
                        year: "numeric",
                      })
                    : "-";
                  const isScored = report.status === "scored";

                  return (
                    <tr
                      key={report.assignmentId}
                      className="hover:bg-surface-muted/30 transition-colors"
                    >
                      <td className="px-5 py-4">
                        <span className="block font-bold text-foreground">{report.participantName}</span>
                        <span className="block text-xs font-semibold text-foreground/50">
                          {report.participantEmail}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <span className="rounded-full bg-burgundy-50 px-2.5 py-1 text-xs font-bold text-burgundy capitalize">
                          {report.questionnaireKey.replace("_", " ")}
                        </span>
                      </td>
                      <td className="px-5 py-4 font-semibold text-foreground/70">{report.projectName}</td>
                      <td className="px-5 py-4">
                        <span
                          className={[
                            "rounded-full px-2.5 py-1 text-xs font-bold",
                            isScored || report.primaryResult
                              ? "bg-success/30 text-success-ink"
                              : "bg-warning/30 text-warning-ink",
                          ].join(" ")}
                        >
                          {report.primaryResult ? "calculat" : report.status}
                        </span>
                      </td>
                      <td className="px-5 py-4 font-semibold text-foreground/70">
                        {report.primaryResult ? report.primaryResult.replaceAll("_", " ") : "in asteptare"}
                      </td>
                      <td className="px-5 py-4 font-semibold text-foreground/60">{dateLabel}</td>
                      <td className="px-5 py-4 text-right">
                        <Link
                          href={`/trainer/reports/${report.assignmentId}`}
                          className="tap-soft inline-flex rounded-xl bg-burgundy px-4.5 py-2 text-xs font-bold text-white shadow-sm hover:bg-burgundy-700 transition-colors"
                        >
                          Deschide raport
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </AppShell>
  );
}
