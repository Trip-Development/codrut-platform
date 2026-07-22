import Link from "next/link";
import type { ReactNode } from "react";

import { BrandMark } from "@/components/brand/brand-mark";

export type LegalSection = {
  title: string;
  content: ReactNode;
};

export function LegalPage({ title, updatedAt, introduction, sections }: {
  title: string;
  updatedAt: string;
  introduction: ReactNode;
  sections: LegalSection[];
}) {
  return (
    <main className="min-h-[100dvh] bg-background text-foreground">
      <header className="border-b bg-surface">
        <div className="mx-auto flex h-18 max-w-5xl items-center justify-between px-4 md:px-6">
          <Link href="/" className="-ml-2 rounded-lg px-2 py-1 transition-colors hover:bg-muted">
            <BrandMark subtitle="Platformă de training și coaching" />
          </Link>
          <Link href="/" className="text-sm font-semibold text-primary hover:underline">
            Înapoi
          </Link>
        </div>
      </header>

      <article className="mx-auto max-w-3xl px-4 py-14 md:px-6 md:py-20">
        <p className="text-sm font-semibold text-muted-foreground">Actualizat la {updatedAt}</p>
        <h1 className="mt-3 text-4xl font-semibold leading-tight tracking-normal md:text-5xl">{title}</h1>
        <div className="mt-6 text-base leading-7 text-muted-foreground">{introduction}</div>

        <div className="mt-12">
          {sections.map((section) => (
            <section key={section.title} className="border-t py-8 first:border-t-0 first:pt-0">
              <h2 className="text-xl font-semibold">{section.title}</h2>
              <div className="mt-4 space-y-4 text-sm leading-7 text-muted-foreground">{section.content}</div>
            </section>
          ))}
        </div>
      </article>

      <footer className="border-t bg-surface px-4 py-7 md:px-6">
        <nav className="mx-auto flex max-w-5xl flex-wrap gap-5 text-sm font-semibold" aria-label="Documente legale">
          <Link href="/confidentialitate" className="hover:text-primary">Confidențialitate</Link>
          <Link href="/termeni" className="hover:text-primary">Termeni</Link>
          <Link href="/cookies" className="hover:text-primary">Cookies</Link>
          <a href="mailto:andrei@andreivacaru.ro" className="hover:text-primary">Contact</a>
        </nav>
      </footer>
    </main>
  );
}
