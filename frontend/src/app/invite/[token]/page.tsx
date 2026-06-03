import Link from "next/link";

import { BrandMark } from "@/components/brand/brand-mark";

type InvitePageProps = {
  params: Promise<{ token: string }>;
};

const demoTasks = [
  { title: "Lencioni pentru echipa ta", status: "Neinceput", detail: "Completare fara cont, asociata emailului tau." },
  { title: "360 pentru manager", status: "In asteptare", detail: "Raspunsurile nu sunt vizibile persoanei evaluate." },
];

export default async function InvitePage({ params }: InvitePageProps) {
  const { token } = await params;

  return (
    <main className="bg-vines-pattern app-min-height flex items-center justify-center bg-background px-4 py-10 text-foreground">
      <section className="w-full max-w-3xl rounded-3xl border border-[var(--border)] bg-surface/92 p-6 shadow-brand backdrop-blur md:p-8">
        <Link href="/" className="mb-8 inline-flex">
          <BrandMark subtitle="Invitatie securizata" />
        </Link>

        <p className="text-sm font-bold uppercase tracking-[0.16em] text-burgundy">Link proiect</p>
        <h1 className="mt-2 font-display text-4xl font-semibold text-foreground md:text-5xl">
          Sarcinile tale pentru acest proiect
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-foreground/65">
          Acest link strange toate chestionarele asociate emailului tau in proiectul curent. Linkul expira la deadline-ul proiectului.
        </p>

        <div className="mt-6 rounded-2xl border border-[var(--border)] bg-surface-muted p-4 text-sm font-semibold text-foreground/62">
          Token demo: <span className="font-mono text-burgundy">{token}</span>
        </div>

        <div className="mt-6 grid gap-3">
          {demoTasks.map((task) => (
            <article key={task.title} className="rounded-2xl border border-[var(--border)] bg-surface p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-lg font-bold text-foreground">{task.title}</h2>
                  <p className="mt-1 text-sm leading-6 text-foreground/58">{task.detail}</p>
                </div>
                <span className="rounded-full bg-burgundy-50 px-3 py-1 text-sm font-bold text-burgundy">{task.status}</span>
              </div>
            </article>
          ))}
        </div>

        <div className="mt-7 flex flex-col gap-3 sm:flex-row">
          <Link href="/participant/questionnaires/lencioni" className="tap-soft rounded-2xl bg-burgundy px-5 py-3 text-center font-bold text-white">
            Incep completarea
          </Link>
          <Link href="/" className="tap-soft rounded-2xl border border-burgundy bg-surface px-5 py-3 text-center font-bold text-burgundy">
            Inapoi la prezentare
          </Link>
        </div>
      </section>
    </main>
  );
}
