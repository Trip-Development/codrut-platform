import Link from "next/link";
import Image from "next/image";
import {
  ArrowRightIcon,
  BarChart3Icon,
  CheckCircle2Icon,
  LockKeyholeIcon,
  ShieldCheckIcon,
  UsersIcon,
} from "lucide-react";

import { AccountAccessLink } from "@/components/auth/account-access-link";
import { PublicSiteHeader } from "@/components/landing/public-site-header";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { serverLinkButtonClassName } from "@/components/ui/server-link-button";

const audienceRows = [
  {
    title: "Traineri",
    body: "Configurează companii, proiecte, invitații și chestionare fără administrație pierdută.",
  },
  {
    title: "HR și L&D",
    body: "Urmărește progresul programelor, blocajele și completările dintr-un spațiu comun.",
  },
  {
    title: "Participanți",
    body: "Intră din link securizat, completează sarcinile și revino la ce mai este deschis.",
  },
] as const;

const processRows = [
  {
    title: "Pornești proiectul",
    body: "Trainerul adaugă compania, definește participanții și alege setul de evaluări potrivit.",
  },
  {
    title: "Trimiți invitațiile",
    body: "Linkurile securizate duc participantul direct în contextul proiectului, cu acordul salvat corect.",
  },
  {
    title: "Vezi ce se mișcă",
    body: "Stările, completările și sarcinile rămase sunt vizibile înainte să devină problemă.",
  },
  {
    title: "Închizi cu raport",
    body: "Rezultatele sunt grupate pentru discuții executive și decizii de follow-up.",
  },
] as const;

const reportItems = [
  "Completări pe proiect",
  "Participanți blocați",
  "Chestionare active",
  "Istoric invitații",
] as const;

const securityItems = [
  {
    title: "Roluri separate",
    body: "Trainerii văd administrarea proiectului, participanții intră doar în sarcinile lor.",
  },
  {
    title: "Acord explicit",
    body: "Confidențialitatea este confirmată înainte ca un chestionar să fie completat.",
  },
  {
    title: "Linkuri securizate",
    body: "Invitațiile și revenirile păstrează contextul corect al proiectului.",
  },
] as const;

export default function HomePage() {
  return (
    <main id="top" className="min-h-[100dvh] bg-background text-foreground">
      <PublicSiteHeader />

      <section className="mx-auto grid min-h-[calc(100dvh-4.5rem)] max-w-7xl items-center gap-10 px-4 py-14 md:px-6 lg:grid-cols-[0.92fr_1.08fr] lg:py-16">
        <div className="max-w-2xl">
          <span className="mb-5 inline-flex h-5 w-fit shrink-0 items-center justify-center rounded-full bg-secondary px-2 py-0.5 text-xs font-semibold text-secondary-foreground">
            Noul standard în training
          </span>
          <h1 id="hero-title" className="max-w-3xl text-5xl font-semibold leading-[0.98] tracking-normal text-foreground md:text-7xl">
            Training care continuă după workshopuri.
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-muted-foreground">
            Platformă de training pentru susținere, suport și urmărire după sesiune, cu invitații clare, progres vizibil și rapoarte pregătite pentru decizie.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link href="#contact" className={serverLinkButtonClassName({ size: "lg" })}>
              Solicită demo
              <ArrowRightIcon data-icon="inline-end" />
            </Link>
            <AccountAccessLink className={serverLinkButtonClassName({ variant: "outline", size: "lg" })}>
              Intră în cont
            </AccountAccessLink>
          </div>
        </div>

        <div className="rounded-lg border bg-surface p-3">
          <Image
            src="/landing/codrut-workshop-table.png"
            alt="Masă de workshop cu materiale de leadership și instrumente de lucru"
            width={1400}
            height={900}
            priority
            className="h-full min-h-[420px] w-full rounded-lg object-cover"
          />
        </div>
      </section>

      <section className="border-y bg-surface">
        <div className="mx-auto grid max-w-7xl gap-0 px-4 md:grid-cols-3 md:px-6">
          {audienceRows.map((item, index) => (
            <article key={item.title} className="py-8 md:px-8 md:first:pl-0 md:last:pr-0">
              {index > 0 ? <div className="mb-8 h-px w-full bg-border md:hidden" aria-hidden="true" /> : null}
              <h2 className="text-xl font-semibold text-foreground">{item.title}</h2>
              <p className="mt-3 max-w-sm text-sm leading-6 text-muted-foreground">{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="proces" className="scroll-mt-24 px-4 py-20 md:px-6">
        <div className="mx-auto max-w-7xl">
          <div className="max-w-2xl">
            <h2 className="text-4xl font-semibold leading-tight tracking-normal text-foreground md:text-5xl">
              Un proces clar, fără administrare inutilă.
            </h2>
            <p className="mt-4 max-w-xl text-base leading-7 text-muted-foreground">
              Cody leagă pregătirea, trimiterea și raportarea într-un flux pe care trainerul îl poate controla.
            </p>
          </div>

          <div className="mt-10 grid gap-4 lg:grid-cols-[0.78fr_1.22fr]">
            <div className="flex min-h-80 flex-col justify-between rounded-lg bg-primary p-8 text-primary-foreground">
              <ShieldCheckIcon className="size-8" aria-hidden="true" />
              <p className="mt-8 text-3xl font-semibold leading-tight md:text-4xl">
                De la listă de participanți la raport pregătit pentru discuție.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {processRows.map((row, index) => (
                <article key={row.title} className="flex min-h-38 flex-col justify-between rounded-lg border bg-surface p-5">
                  <span className="font-mono text-sm font-semibold tabular-nums text-primary">{String(index + 1).padStart(2, "0")}</span>
                  <div className="mt-8">
                    <h3 className="text-lg font-semibold text-foreground">{row.title}</h3>
                    <p className="mt-3 text-sm leading-6 text-muted-foreground">{row.body}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="px-4 py-20 md:px-6">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <Image
            src="/landing/codrut-team-session.png"
            alt="Sesiune de lucru pentru echipă într-un spațiu de training"
            width={1300}
            height={1000}
            className="h-full min-h-[520px] w-full rounded-lg border object-cover"
          />
          <div className="flex flex-col justify-between rounded-lg border bg-surface p-8">
            <div>
              <UsersIcon className="size-7 text-primary" aria-hidden="true" />
              <h2 className="mt-6 text-4xl font-semibold leading-tight tracking-normal text-foreground">
                Participantul vede doar ce are de făcut.
              </h2>
              <p className="mt-4 text-base leading-7 text-muted-foreground">
                Linkul de invitație păstrează contextul proiectului, acordul și sarcinile active într-o experiență simplă.
              </p>
            </div>
            <div className="mt-10 grid gap-3">
              {["Acces prin link securizat", "Sarcini grupate pe proiect", "Înapoi rapid la chestionarul început"].map((item) => (
                <div key={item} className="flex items-center gap-3 rounded-lg bg-muted px-4 py-3 text-sm font-semibold">
                  <CheckCircle2Icon className="size-4 text-primary" aria-hidden="true" />
                  {item}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section id="raportare" className="scroll-mt-24 px-4 pb-20 md:px-6">
        <div className="mx-auto max-w-7xl rounded-lg border bg-primary p-8 text-primary-foreground md:p-10">
          <div className="grid gap-10 lg:grid-cols-[0.9fr_1.1fr]">
            <div>
              <BarChart3Icon className="size-7" aria-hidden="true" />
              <h2 className="mt-6 text-4xl font-semibold leading-tight tracking-normal">
                Raportare pregătită pentru decizie.
              </h2>
              <p className="mt-4 max-w-xl text-base leading-7 text-primary-foreground/80">
                Datele sunt utile când trainerul poate explica ce se întâmplă și ce trebuie făcut mai departe.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {reportItems.map((item) => (
                <div key={item} className="rounded-lg border border-primary-foreground/18 bg-primary-foreground/10 p-5">
                  <p className="text-lg font-semibold">{item}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="px-4 pb-20 md:px-6">
        <div className="mx-auto max-w-7xl rounded-lg border bg-surface p-6 md:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex max-w-xl gap-4">
              <LockKeyholeIcon className="size-6 shrink-0 text-primary" aria-hidden="true" />
              <div>
                <h2 className="text-2xl font-semibold leading-tight tracking-normal text-foreground">
                  Confidențialitate și acces controlat.
                </h2>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  Cody separă administrarea trainerului de experiența participantului, cu acorduri și linkuri care păstrează contextul corect.
                </p>
              </div>
            </div>
            <div className="grid gap-3 lg:w-[46rem] lg:grid-cols-3">
              {securityItems.map((item) => (
                <article key={item.title} className="rounded-lg bg-muted px-4 py-3">
                  <h3 className="text-sm font-semibold text-foreground">{item.title}</h3>
                  <p className="mt-2 text-xs font-medium leading-5 text-muted-foreground">{item.body}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section id="contact" className="scroll-mt-24 px-4 pb-24 md:px-6">
        <div className="mx-auto grid max-w-7xl gap-8 rounded-lg border bg-surface p-6 md:p-8 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <h2 className="text-4xl font-semibold leading-tight tracking-normal text-foreground">
              Vezi Cody pe un program real.
            </h2>
            <p className="mt-4 max-w-lg text-base leading-7 text-muted-foreground">
              Scrie-ne și revenim cu o discuție aplicată pe programul tău de training.
            </p>
          </div>
          <form
            action="mailto:andrei@andreivacaru.ro"
            method="post"
            encType="text/plain"
            className="flex flex-col justify-end gap-5"
          >
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="landing-email">Email</FieldLabel>
                <Input
                  id="landing-email"
                  name="email"
                  type="email"
                  placeholder="nume@companie.ro"
                  required
                />
              </Field>
            </FieldGroup>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Button type="submit" size="lg">
                Trimite
                <ArrowRightIcon data-icon="inline-end" />
              </Button>
            </div>
          </form>
        </div>
      </section>

      <footer className="border-t bg-surface px-4 py-8 md:px-6">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 text-sm font-semibold text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <span>© {new Date().getFullYear()} Cody. Toate drepturile rezervate.</span>
          <div className="flex flex-wrap gap-4">
            <Link href="/confidentialitate" className="text-foreground transition-colors hover:text-primary">
              Confidențialitate
            </Link>
            <Link href="/termeni" className="text-foreground transition-colors hover:text-primary">
              Termeni
            </Link>
            <Link href="/cookies" className="text-foreground transition-colors hover:text-primary">
              Cookies
            </Link>
            <Link href="/trainer/login" className="text-foreground transition-colors hover:text-primary">
              Autentificare trainer
            </Link>
          </div>
        </div>
      </footer>
    </main>
  );
}
