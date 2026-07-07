type SessionUnavailableNoticeProps = {
  audience: "trainer" | "participant";
};

export function SessionUnavailableNotice({ audience }: SessionUnavailableNoticeProps) {
  const homeHref = audience === "trainer" ? "/trainer" : "/participant";

  return (
    <main className="min-h-screen bg-background px-6 py-10 text-foreground">
      <section className="mx-auto flex min-h-[60vh] max-w-2xl flex-col justify-center">
        <div className="rounded-2xl border border-[var(--border)] bg-surface p-6 shadow-sm">
          <p className="text-xs font-bold uppercase tracking-wider text-burgundy/75">
            Verificare sesiune
          </p>
          <h1 className="mt-3 text-2xl font-bold tracking-tight">
            Nu am putut verifica sesiunea momentan.
          </h1>
          <p className="mt-3 text-sm leading-6 text-foreground/68">
            Contul nu a fost deconectat. Reîncarcă pagina după ce conexiunea cu serverul revine.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <a href={homeHref} className="btn-primary px-5 py-3">
              Reîncearcă
            </a>
            <a href="/login" className="btn-secondary px-5 py-3">
              Intră în alt cont
            </a>
          </div>
        </div>
      </section>
    </main>
  );
}
