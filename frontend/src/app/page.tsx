import Link from "next/link";

import {
  accessRoutes,
  campaignClientTypes,
  campaignMetrics,
  campaignOutcomeFlags,
  campaignWorkflowSteps,
  participantWorkflowRoutes,
  trainerWorkflowRoutes,
} from "../api/routes";
import { BrandMark } from "../components/brand/brand-mark";
import { ThemeToggle } from "../components/theme/theme-toggle";

const deliveryStats = [
  { label: "Invitatii livrate", value: "84%", detail: "status email si acces" },
  { label: "Sarcini inchise", value: "62%", detail: "pe proiect si echipa" },
  { label: "Rapoarte pregatite", value: "12", detail: "trainer raw / anonimizat" },
];

const landingSections = [
  {
    title: "Intake clar pentru companii",
    description:
      "Trainerul incarca structura organizatiei, seteaza echipele si trimite invitatii fara sa piarda controlul asupra deadline-ului.",
  },
  {
    title: "Chestionare in acelasi flux",
    description:
      "PCM, Lencioni, 360 si driverii de distres folosesc aceeasi experienta de completare si acelasi progres operational.",
  },
  {
    title: "Emailuri care duc oamenii la actiune",
    description:
      "Participantii primesc linkul potrivit, iar ownerul vede livrare, completare, remindere si campanii video dintr-un singur loc.",
  },
];

const brandColors = [
  { label: "Rosu", value: "#890505" },
  { label: "Verde", value: "#a3d376" },
  { label: "Gri", value: "#5e5e5e" },
];

export default function HomePage() {
  return (
    <main className="bg-vines-pattern app-min-height overflow-hidden bg-background text-foreground">
      <header className="safe-top sticky top-0 z-40 border-b border-[var(--border)] bg-background/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 md:px-6">
          <Link href="/" className="min-w-0">
            <BrandMark />
          </Link>

          <nav aria-label="Acces rapid" className="hidden items-center gap-2 md:flex">
            <Link href="#cum-functioneaza" className="rounded-full px-4 py-2 text-sm font-bold text-foreground/65 hover:text-burgundy">
              Cum functioneaza
            </Link>
            <Link href="#acces" className="rounded-full px-4 py-2 text-sm font-bold text-foreground/65 hover:text-burgundy">
              Acces
            </Link>
            <Link href="/trainer/login" className="rounded-full px-4 py-2 text-sm font-bold text-foreground/65 hover:text-burgundy">
              Trainer login
            </Link>
          </nav>

          <ThemeToggle />
        </div>
      </header>

      <section className="relative mx-auto grid min-h-[calc(100dvh-5rem)] max-w-7xl items-center gap-10 px-4 py-12 md:grid-cols-[1.02fr_0.98fr] md:px-6 md:py-16">
        <div className="relative z-10 max-w-3xl">
          <div className="mb-8 inline-flex items-center gap-3 rounded-full border border-[var(--border)] bg-surface/80 px-3 py-2 shadow-sm backdrop-blur">
            <span className="h-2.5 w-2.5 rounded-full bg-burgundy" />
            <span className="text-sm font-bold text-foreground/70">Platforma pentru training, feedback si rollout</span>
          </div>

          <h1 className="font-display text-5xl font-semibold leading-[1.02] text-foreground md:text-7xl">
            Codrut transforma trainingul in actiune masurabila.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-foreground/68 md:text-xl md:leading-9">
            O experienta calda si structurata pentru companii: invitatii clare, chestionare ghidate,
            progres vizibil si rapoarte pregatite pentru trainer fara munca manuala inutila.
          </p>

          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/invite/demo-token"
              className="tap-soft rounded-2xl bg-burgundy px-6 py-4 text-center text-base font-bold text-white shadow-brand hover:bg-burgundy-700"
            >
              Am primit invitatie
            </Link>
            <Link
              href="/participant"
              className="tap-soft rounded-2xl border border-burgundy bg-surface px-6 py-4 text-center text-base font-bold text-burgundy hover:bg-burgundy-50"
            >
              Intru in cont
            </Link>
          </div>

          <dl className="mt-10 grid gap-3 sm:grid-cols-3">
            {deliveryStats.map((stat) => (
              <div key={stat.label} className="rounded-2xl border border-[var(--border)] bg-surface/82 p-4 shadow-sm backdrop-blur">
                <dt className="text-xs font-bold text-foreground/55">{stat.label}</dt>
                <dd className="mt-2 font-display text-3xl font-semibold text-burgundy">{stat.value}</dd>
                <p className="mt-1 text-sm font-semibold text-foreground/58">{stat.detail}</p>
              </div>
            ))}
          </dl>
        </div>

        <div className="relative z-10">
          <div className="landing-orbit absolute -left-8 top-10 h-28 w-28 rounded-full border border-burgundy/15" />
          <div className="relative rounded-[2rem] border border-[var(--border)] bg-surface/90 p-4 shadow-2xl shadow-burgundy/10 backdrop-blur md:p-5">
            <div className="rounded-[1.5rem] border border-[var(--border)] bg-surface-muted p-5">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-bold text-burgundy">Livrare proiect</p>
                  <h2 className="mt-1 text-2xl font-bold text-foreground">Intake Iunie</h2>
                </div>
                <span className="rounded-full bg-success/30 px-3 py-1 text-sm font-bold text-success-ink">Activ</span>
              </div>

              <div className="mt-6 grid gap-3">
                {[
                  ["Leadership suite", "PCM, Phase, Lencioni, 360", "74%"],
                  ["Membri echipa", "Link securizat fara cont", "58%"],
                  ["Rapoarte", "Raw trainer / anonimizat", "12"],
                ].map(([title, detail, value]) => (
                  <div key={title} className="rounded-2xl border border-[var(--border)] bg-surface p-4">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <p className="font-bold text-foreground">{title}</p>
                        <p className="mt-1 text-sm font-semibold text-foreground/55">{detail}</p>
                      </div>
                      <span className="font-display text-3xl font-semibold text-burgundy">{value}</span>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-5 rounded-2xl bg-burgundy p-4 text-white">
                <p className="text-sm font-bold text-white/70">Urmatorul pas</p>
                <p className="mt-1 text-lg font-bold">Trimite remindere catre 18 participanti inainte de deadline.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="cum-functioneaza" className="mx-auto max-w-7xl px-4 py-12 md:px-6 md:py-16">
        <div className="max-w-3xl">
          <h2 className="font-display text-4xl font-semibold text-foreground md:text-5xl">O platforma gandita pentru ritmul real al companiilor.</h2>
          <p className="mt-4 text-lg leading-8 text-foreground/65">
            Codrut tine impreuna comunicarea, chestionarele si urmarirea completarii, astfel incat trainerul poate livra programul fara foi separate si fara status cerut manual.
          </p>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {landingSections.map((section, index) => (
            <article key={section.title} className="rounded-3xl border border-[var(--border)] bg-surface p-6 shadow-sm">
              <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-burgundy-50 text-sm font-black text-burgundy">
                {index + 1}
              </span>
              <h3 className="mt-5 text-xl font-bold text-foreground">{section.title}</h3>
              <p className="mt-3 text-base leading-7 text-foreground/62">{section.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="acces" className="mx-auto max-w-7xl px-4 pb-16 md:px-6 md:pb-24">
        <div className="grid gap-6 lg:grid-cols-[0.86fr_1.14fr]">
          <div>
            <h2 className="font-display text-4xl font-semibold text-foreground">Alege intrarea potrivita.</h2>
            <p className="mt-4 text-lg leading-8 text-foreground/65">
              Participantii invitati nu trebuie sa caute conturi. Managerii au progres persistent. Trainerul are o intrare separata pentru operatiuni.
            </p>
          </div>

          <div className="grid gap-3">
            {accessRoutes.map((route) => (
              <Link
                key={route.href}
                href={route.href}
                className="tap-soft group rounded-3xl border border-[var(--border)] bg-surface p-5 shadow-sm hover:border-burgundy/45"
              >
                <span className="flex items-center justify-between gap-4">
                  <span>
                    <span className="block text-lg font-bold text-foreground group-hover:text-burgundy">{route.label}</span>
                    <span className="mt-1 block text-sm leading-6 text-foreground/58">{route.description}</span>
                  </span>
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-surface-muted text-lg font-black text-burgundy">
                    {">"}
                  </span>
                </span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-16 md:px-6 md:pb-24">
        <div className="rounded-[2rem] border border-[var(--border)] bg-surface/92 p-6 shadow-sm md:p-8">
          <div className="grid gap-8 lg:grid-cols-[0.82fr_1.18fr]">
            <div>
              <h2 className="font-display text-4xl font-semibold text-foreground">
                Campanii video pentru clienti si prospecti.
              </h2>
              <p className="mt-4 text-base leading-7 text-foreground/65">
                Ownerul segmenteaza baza de date, verifica emailul, trimite thumbnail-ul catre pagina Codrut de video si urmareste deschideri, clickuri, vizionari si rezultate comerciale.
              </p>
              <div className="mt-6 flex flex-wrap gap-2">
                {brandColors.map((color) => (
                  <span key={color.value} className="rounded-full border border-[var(--border)] bg-surface-muted px-3 py-2 text-xs font-bold text-foreground/65">
                    <span className="mr-2 inline-block h-3 w-3 rounded-full align-[-2px]" style={{ backgroundColor: color.value }} />
                    {color.label} {color.value}
                  </span>
                ))}
              </div>
            </div>

            <div className="grid gap-4">
              <div className="grid gap-3 sm:grid-cols-2">
                {campaignClientTypes.map((type) => (
                  <article key={type.id} className="rounded-2xl border border-[var(--border)] bg-surface-muted p-4">
                    <p className="text-sm font-black text-burgundy">{type.label}</p>
                    <p className="mt-2 text-sm leading-6 text-foreground/62">{type.description}</p>
                  </article>
                ))}
              </div>

              <div className="rounded-2xl border border-[var(--border)] bg-surface-muted p-4">
                <h3 className="font-bold text-foreground">Workflow campanie</h3>
                <ol className="mt-3 grid gap-2">
                  {campaignWorkflowSteps.map((step, index) => (
                    <li key={step.id} className="flex gap-3 text-sm font-semibold text-foreground/68">
                      <span className="text-burgundy">{index + 1}.</span>
                      <span>{step.label}</span>
                    </li>
                  ))}
                </ol>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl bg-burgundy p-4 text-white">
                  <p className="text-sm font-bold text-white/70">Metrici</p>
                  <p className="mt-2 text-lg font-bold">{campaignMetrics.join(" / ")}</p>
                </div>
                <div className="rounded-2xl border border-[var(--border)] bg-surface p-4">
                  <p className="text-sm font-bold text-foreground/55">Rezultat obtinut</p>
                  <p className="mt-2 text-lg font-bold text-foreground">{campaignOutcomeFlags.join(" / ")}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-4 pb-16 md:grid-cols-2 md:px-6 md:pb-24">
        <WorkflowPanel title="Pentru trainer" routes={trainerWorkflowRoutes} />
        <WorkflowPanel title="Pentru participanti" routes={participantWorkflowRoutes} />
      </section>
    </main>
  );
}

function WorkflowPanel({ title, routes }: { title: string; routes: typeof trainerWorkflowRoutes }) {
  return (
    <section className="rounded-3xl border border-[var(--border)] bg-surface/92 p-6 shadow-sm">
      <h2 className="text-2xl font-bold text-foreground">{title}</h2>
      <div className="mt-5 grid gap-3">
        {routes.map((route) => (
          <Link
            key={route.href}
            href={route.href}
            className="tap-soft rounded-2xl border border-[var(--border)] bg-surface-muted p-4 hover:border-burgundy/45"
          >
            <span className="block font-bold text-foreground">{route.label}</span>
            <span className="mt-1 block text-sm leading-6 text-foreground/58">{route.description}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
