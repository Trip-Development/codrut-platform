import Link from "next/link";

import { inviteStatusLabel, resolveInviteBundle } from "@/api/invites";
import { BrandMark } from "@/components/brand/brand-mark";

type InvitePageProps = {
  params: Promise<{ token: string }>;
};

export default async function InvitePage({ params }: InvitePageProps) {
  const { token } = await params;
  const bundle = await resolveInviteBundle(token);

  return (
    <main className="bg-vines-pattern app-min-height flex items-center justify-center bg-background px-4 py-10 text-foreground">
      <section className="w-full max-w-3xl rounded-3xl border border-[var(--border)] bg-surface/92 p-6 shadow-brand backdrop-blur md:p-8">
        <Link href="/" className="mb-8 inline-flex">
          <BrandMark subtitle="Invitatie securizata" />
        </Link>

        <p className="text-sm font-bold uppercase tracking-[0.16em] text-burgundy">Link proiect</p>
        <h1 className="mt-2 font-display text-4xl font-semibold text-foreground md:text-5xl">
          {bundle.state === "valid" ? "Sarcinile tale pentru acest proiect" : "Invitatia nu este disponibila"}
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-foreground/65">
          {bundle.state === "valid"
            ? `Acest link strange toate chestionarele asociate emailului ${bundle.participantEmail} in proiectul ${bundle.projectName}. Linkul expira la ${bundle.deadlineLabel}.`
            : bundle.message}
        </p>

        <div className="mt-6 rounded-2xl border border-[var(--border)] bg-surface-muted p-4 text-sm font-semibold text-foreground/62">
          Token demo: <span className="font-mono text-burgundy">{token}</span>
        </div>

        {bundle.state === "valid" ? (
          <div className="mt-6 grid gap-3">
            {bundle.tasks.map((task) => (
              <article key={task.id} className="rounded-2xl border border-[var(--border)] bg-surface p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-foreground">{task.title}</h2>
                    <p className="mt-1 text-sm leading-6 text-foreground/58">{task.detail}</p>
                  </div>
                  <span className="rounded-full bg-burgundy-50 px-3 py-1 text-sm font-bold text-burgundy">
                    {inviteStatusLabel(task.status)}
                  </span>
                </div>
              </article>
            ))}
          </div>
        ) : null}

        <div className="mt-7 flex flex-col gap-3 sm:flex-row">
          {bundle.state === "valid" ? (
            <Link
              href={bundle.tasks[0]?.href ?? "/participant/questionnaires"}
              className="tap-soft rounded-2xl bg-burgundy px-5 py-3 text-center font-bold text-white"
            >
              Incep completarea
            </Link>
          ) : null}
          <Link href="/" className="tap-soft rounded-2xl border border-burgundy bg-surface px-5 py-3 text-center font-bold text-burgundy">
            {bundle.state === "valid" ? "Inapoi la prezentare" : "Mergi la Codrut"}
          </Link>
        </div>
      </section>
    </main>
  );
}
