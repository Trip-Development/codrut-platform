import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

const deliveryRows = [
  {
    name: "Ana Pop",
    team: "Leadership",
    tasks: "3/4",
    email: "Invitat",
    reminder: "Maine",
    status: "In progres",
  },
  {
    name: "Mihai Ionescu",
    team: "Sales",
    tasks: "0/2",
    email: "Trimis",
    reminder: "Azi",
    status: "Neinceput",
  },
  {
    name: "Elena Dima",
    team: "Leadership",
    tasks: "4/4",
    email: "Livrat",
    reminder: "Oprit",
    status: "Complet",
  },
];

export default function TrainerEmailPage() {
  return (
    <AppShell
      audience="trainer"
      eyebrow="Email"
      title="Invitatii, remindere si campanii"
      description="Suprafata owner-friendly pentru email transactional de assessment si, mai tarziu, outreach cu video links."
      navItems={trainerNavItems}
      activeHref="/trainer/email"
    >
      <div className="space-y-5">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {[
            { label: "Invitatii trimise", value: "42", detail: "Cont + bundle de sarcini" },
            { label: "In progres", value: "18", detail: "Au intrat in app" },
            { label: "Completate", value: "11", detail: "Toate sarcinile finalizate" },
            { label: "Reminder azi", value: "7", detail: "Necompletare dupa regula" },
          ].map((metric) => (
            <article key={metric.label} className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-burgundy/75">{metric.label}</p>
              <p className="mt-3 text-3xl font-bold text-foreground">{metric.value}</p>
              <p className="mt-2 text-sm leading-6 text-foreground/60">{metric.detail}</p>
            </article>
          ))}
        </div>

        <section className="rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
          <div className="border-b border-[var(--border)] p-5">
            <h2 className="text-lg font-bold text-foreground">Livrare si completare</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/65">
              Suprafata de lucru pentru owner/trainer: cine a primit emailul, cine a intrat in app,
              cine a completat si cine intra in reminder. Statusurile raman separate de raspunsurile
              confidentiale si pot fi folosite pentru follow-up operational.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] border-collapse text-left text-sm">
              <thead className="bg-surface-muted text-xs uppercase tracking-[0.12em] text-foreground/55">
                <tr>
                  {["Participant", "Echipa", "Sarcini", "Email", "Reminder", "Status"].map((header) => (
                    <th key={header} className="px-5 py-3 font-bold">{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {deliveryRows.map((row) => (
                  <tr key={row.name} className="border-t border-[var(--border)]">
                    <td className="px-5 py-4 font-semibold text-foreground">{row.name}</td>
                    <td className="px-5 py-4 text-foreground/65">{row.team}</td>
                    <td className="px-5 py-4 text-foreground/65">{row.tasks}</td>
                    <td className="px-5 py-4 text-foreground/65">{row.email}</td>
                    <td className="px-5 py-4 text-foreground/65">{row.reminder}</td>
                    <td className="px-5 py-4">
                      <span className="rounded-full border border-burgundy/20 bg-burgundy-50 px-3 py-1 text-xs font-bold text-burgundy">
                        {row.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <div className="grid gap-4 lg:grid-cols-3">
          <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
            <h2 className="text-lg font-bold text-foreground">Invitatii assessment</h2>
            <p className="mt-2 text-sm leading-6 text-foreground/65">Emailuri pentru cont si chestionarele asignate.</p>
          </section>
          <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
            <h2 className="text-lg font-bold text-foreground">Remindere</h2>
            <p className="mt-2 text-sm leading-6 text-foreground/65">Reguli configurabile pentru necompletare inainte de deadline.</p>
          </section>
          <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
            <h2 className="text-lg font-bold text-foreground">Campaign readiness</h2>
            <p className="mt-2 text-sm leading-6 text-foreground/65">Separat de participant data: clienti trecuti, potentiali clienti, video links.</p>
          </section>
        </div>
      </div>
    </AppShell>
  );
}
