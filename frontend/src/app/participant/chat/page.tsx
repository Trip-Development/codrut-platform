import Link from "next/link";
import { ArrowRightIcon } from "lucide-react";

import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";

export default async function ParticipantChatPage() {
  const requestOptions = await getServerApiRequestOptions();
  const summary = await getParticipantWorkspaceSummary(requestOptions);
  const identity = summary.participantFullName.trim() || summary.anonymousName?.trim() || "Participant";
  const openTasks = summary.tasks.filter((task) => task.status !== "completed").length;

  return (
    <AppShell
      audience="participant"
      eyebrow=""
      title="Suport"
      description=""
      navItems={participantNavItems}
      activeHref="/participant/chat"
      userLabel={identity.split(/\s+/)[0]}
    >
      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_17rem] lg:gap-12">
        <section>
          <div className="border-b border-border pb-6">
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">Ai nevoie de ajutor?</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
              Răspunde mesajului primit de la trainer pentru întrebări despre proiect sau acces.
            </p>
          </div>
          <nav className="divide-y divide-border" aria-label="Acțiuni de suport">
            <SupportLink href="/participant/questionnaires" label="Chestionare" detail={openTasks > 0 ? `${openTasks} sarcini deschise` : "Nicio sarcină deschisă"} />
            <SupportLink href="/participant/results" label="Rezultate" detail="Scoruri și interpretări disponibile" />
          </nav>
        </section>

        <aside className="border-t border-border pt-6 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
          <p className="text-sm font-semibold text-foreground">{identity}</p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{summary.projectName}</p>
          <p className="mt-6 border-t border-border pt-5 text-sm leading-6 text-muted-foreground">
            Răspunsurile individuale nu sunt afișate celorlalți participanți.
          </p>
        </aside>
      </div>
    </AppShell>
  );
}

function SupportLink({
  href,
  label,
  detail,
}: {
  href: string;
  label: string;
  detail: string;
}) {
  return (
    <Link href={href} className="group flex items-center justify-between gap-4 py-5">
      <span>
        <span className="block text-base font-semibold text-foreground group-hover:text-burgundy">{label}</span>
        <span className="mt-1 block text-sm text-muted-foreground">{detail}</span>
      </span>
      <ArrowRightIcon aria-hidden="true" className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-burgundy" />
    </Link>
  );
}
