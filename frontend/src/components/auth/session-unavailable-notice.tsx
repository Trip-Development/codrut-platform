import { serverLinkButtonClassName } from "@/components/ui/server-link-button";

type SessionUnavailableNoticeProps = {
  audience: "trainer" | "participant";
};

export function SessionUnavailableNotice({ audience }: SessionUnavailableNoticeProps) {
  const homeHref = audience === "trainer" ? "/trainer" : "/participant";

  return (
    <main className="min-h-[100dvh] bg-background px-6 py-10 text-foreground">
      <section className="mx-auto flex min-h-[60vh] max-w-2xl flex-col justify-center">
        <div className="rounded-lg border border-border bg-surface p-6">
          <div className="grid gap-2">
            <p className="text-xs font-bold uppercase tracking-wider text-primary/75">
              Verificare sesiune
            </p>
            <h1 className="font-heading text-2xl font-medium tracking-tight text-foreground">
              Nu am putut verifica sesiunea momentan.
            </h1>
          </div>
          <div className="mt-4">
            <p className="text-sm leading-6 text-muted-foreground">
              Contul nu a fost deconectat. Reîncarcă pagina după ce conexiunea cu serverul revine.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <a href={homeHref} className={serverLinkButtonClassName()}>
                Reîncearcă
              </a>
              <a href="/login" className={serverLinkButtonClassName({ variant: "outline" })}>
                Intră în alt cont
              </a>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
