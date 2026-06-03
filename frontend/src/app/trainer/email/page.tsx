import { getEmailOpsSummary, type AssessmentDeliveryRow } from "@/api/email";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

export default async function TrainerEmailPage() {
  const summary = await getEmailOpsSummary();

  return (
    <AppShell
      audience="trainer"
      eyebrow="Email"
      title="Invitatii si remindere"
      description="Suprafata owner-friendly pentru livrare assessment: cine a primit emailul, cine a intrat in app si cine trebuie urmarit."
      navItems={trainerNavItems}
      activeHref="/trainer/email"
    >
      <div className="space-y-5">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {summary.metrics.map((metric) => (
            <article key={metric.label} className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">{metric.label}</p>
              <p className="mt-3 text-3xl font-semibold text-foreground">{metric.value}</p>
              <p className="mt-2 text-sm leading-6 text-foreground/60">{metric.detail}</p>
            </article>
          ))}
        </div>

        <section className="rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
          <div className="border-b border-[var(--border)] px-5 py-4">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Delivery queue</p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">Invitatii assessment</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/62">
              Liderii primesc cont, membrii primesc link securizat. Follow-up-ul se bazeaza pe livrare, acces si completare,
              nu pe continutul raspunsurilor.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-surface-muted text-xs font-semibold uppercase tracking-[0.1em] text-foreground/50">
                <tr>
                  <th className="px-5 py-3">Recipient</th>
                  <th className="px-5 py-3">Acces</th>
                  <th className="px-5 py-3">Sarcini</th>
                  <th className="px-5 py-3">Livrare</th>
                  <th className="px-5 py-3">Reminder</th>
                  <th className="px-5 py-3">Urmatorul pas</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {summary.assessmentRows.map((row) => (
                  <DeliveryRow key={row.id} row={row} />
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Actiuni rapide</p>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              {["Trimite invitatii lipsa", "Trimite reminder azi", "Corecteaza emailuri blocate"].map((action) => (
                <button
                  key={action}
                  type="button"
                  className="tap-soft rounded-xl border border-[var(--border)] bg-background px-4 py-3 text-sm font-semibold text-foreground hover:border-burgundy/45 hover:text-burgundy"
                >
                  {action}
                </button>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Reguli</p>
            <div className="mt-4 space-y-2">
              {summary.rules.map((rule) => (
                <p key={rule} className="rounded-xl bg-surface-muted px-3 py-2 text-xs leading-5 text-foreground/62">
                  {rule}
                </p>
              ))}
            </div>
          </section>
        </div>
      </div>
    </AppShell>
  );
}

function DeliveryRow({ row }: { row: AssessmentDeliveryRow }) {
  return (
    <tr className="align-top">
      <td className="px-5 py-4">
        <p className="font-semibold text-foreground">{row.participant}</p>
        <p className="mt-1 text-xs text-foreground/50">{row.email}</p>
        <p className="mt-1 text-xs font-semibold text-burgundy">{row.project}</p>
      </td>
      <td className="px-5 py-4">
        <StatusPill value={row.audience === "leadership_account" ? "cont lider" : "link securizat"} />
      </td>
      <td className="px-5 py-4 text-foreground/62">{row.tasks}</td>
      <td className="px-5 py-4">
        <StatusPill value={row.delivery} />
      </td>
      <td className="px-5 py-4">
        <StatusPill value={row.reminder} />
      </td>
      <td className="px-5 py-4 text-foreground/62">{row.nextAction}</td>
    </tr>
  );
}

function StatusPill({ value }: { value: string }) {
  return (
    <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-foreground/60">
      {value}
    </span>
  );
}
