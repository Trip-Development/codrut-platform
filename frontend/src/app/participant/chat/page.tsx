import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";

const scenarios = [
  "Ce înseamnă feedback 360 iCARE?",
  "Cum răspund dacă nu am observat direct comportamentul?",
  "Cum funcționează confidențialitatea răspunsurilor?",
];

export default async function ParticipantChatPage() {
  const requestOptions = await getServerApiRequestOptions();
  const summary = await getParticipantWorkspaceSummary(requestOptions);
  const identity = summary.anonymousName ?? "Profil anonim";

  return (
    <AppShell
      audience="participant"
      eyebrow="Asistent"
      title="Asistent pentru completare"
      description="Spațiu de ghidaj pentru întrebări despre chestionare. Momentan este un preview de scenarii, fără conversație AI activă."
      navItems={participantNavItems}
      activeHref="/participant/chat"
      userLabel={identity}
    >
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <section className="surface-panel p-5 md:p-6">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">Preview scenarii</p>
          <h2 className="mt-2 text-2xl font-semibold text-foreground">Întrebări utile înainte de răspuns</h2>
          <div className="mt-5 space-y-3">
            {scenarios.map((scenario) => (
              <article key={scenario} className="rounded-xl border border-[var(--border)] bg-surface-muted px-4 py-3 transition hover:border-burgundy/25">
                <p className="text-sm font-semibold text-foreground">{scenario}</p>
                <p className="mt-1 text-xs leading-5 text-foreground/55">
                  Va deschide un răspuns ghidat în versiunea completă a asistentului.
                </p>
              </article>
            ))}
          </div>
        </section>
        <aside className="rounded-xl border border-burgundy/16 bg-surface p-5 shadow-sm">
          <p className="text-sm font-bold text-burgundy">Identitate anonimă</p>
          <p className="mt-2 text-2xl font-semibold text-foreground">{identity}</p>
          <p className="mt-3 text-sm leading-6 text-foreground/62">
            Răspunsurile la chestionare rămân legate de această identitate anonimă în experiența ta de participant.
          </p>
        </aside>
      </div>
    </AppShell>
  );
}
