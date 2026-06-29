export default function ProjectLoading() {
  return (
    <>
      <nav className="surface-panel mb-6 overflow-hidden" aria-label="Se încarcă navigarea proiectului">
        <div className="flex gap-2 overflow-hidden px-3 py-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="h-9 w-24 shrink-0 rounded-full bg-surface-muted" />
          ))}
        </div>
      </nav>
      <section className="surface-panel p-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="h-3 w-28 rounded-full bg-surface-muted" />
            <div className="mt-3 h-6 w-56 rounded-full bg-surface-muted" />
          </div>
          <div className="h-10 w-32 rounded-full bg-surface-muted" />
        </div>
        <div className="mt-6 grid gap-3 md:grid-cols-3">
          <div className="h-24 rounded-xl bg-surface-muted" />
          <div className="h-24 rounded-xl bg-surface-muted" />
          <div className="h-24 rounded-xl bg-surface-muted" />
        </div>
      </section>
    </>
  );
}
