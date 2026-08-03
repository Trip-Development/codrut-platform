import Link from "next/link";
import { HomeIcon, LogInIcon } from "lucide-react";

import { BrandMark } from "@/components/brand/brand-mark";
import { SmartBackButton } from "@/components/navigation/SmartBackButton";
import { serverLinkButtonClassName } from "@/components/ui/server-link-button";

export default function NotFound() {
  return (
    <main className="min-h-[100dvh] bg-background px-4 py-8 text-foreground md:px-8">
      <div className="mx-auto flex min-h-[calc(100dvh-4rem)] w-full max-w-6xl flex-col">
        <header className="flex items-center justify-between gap-4">
          <Link href="/" className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45">
            <BrandMark subtitle="Platformă de training și coaching" />
          </Link>
          <Link href="/login" className={serverLinkButtonClassName({ variant: "outline", size: "sm" })}>
            <LogInIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
            Intră în cont
          </Link>
        </header>

        <section className="grid flex-1 items-center gap-10 py-16 lg:grid-cols-[minmax(0,0.86fr)_minmax(18rem,0.42fr)]">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-primary">404</p>
            <h1 className="mt-5 max-w-3xl text-5xl font-semibold leading-[0.98] tracking-normal text-foreground md:text-7xl">
              Pagina nu există.
            </h1>
            <p className="mt-6 max-w-xl text-base leading-7 text-muted-foreground">
              Linkul poate fi vechi sau ai ajuns într-un spațiu care nu mai este public.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <SmartBackButton />
              <Link href="/" className={serverLinkButtonClassName({ variant: "outline", size: "lg" })}>
                <HomeIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
                Pagina principală
              </Link>
            </div>
          </div>

          <aside className="rounded-lg border bg-surface p-5 shadow-sm">
            <div className="rounded-lg bg-primary p-4 text-primary-foreground">
              <p className="text-sm font-semibold">Cody</p>
              <p className="mt-3 text-3xl font-semibold leading-tight">Revenim la traseul corect.</p>
            </div>
            <div className="mt-4 grid gap-3">
              <div className="rounded-lg bg-muted p-4">
                <p className="text-xs font-semibold text-muted-foreground">Pentru traineri</p>
                <p className="mt-1 text-sm font-semibold text-foreground">Companii, proiecte, invitații și rapoarte.</p>
              </div>
              <div className="rounded-lg bg-muted p-4">
                <p className="text-xs font-semibold text-muted-foreground">Pentru participanți</p>
                <p className="mt-1 text-sm font-semibold text-foreground">Chestionare, rezultate și contul tău.</p>
              </div>
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}
