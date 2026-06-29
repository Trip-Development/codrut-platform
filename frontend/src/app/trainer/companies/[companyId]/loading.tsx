export default function CompanyLoading() {
  return (
    <div className="space-y-5">
      <section className="surface-panel p-5 md:p-6">
        <div className="h-3 w-32 rounded-full bg-surface-muted" />
        <div className="mt-3 h-8 w-64 rounded-full bg-surface-muted" />
        <div className="mt-6 grid gap-3 md:grid-cols-4">
          <div className="h-24 rounded-xl bg-surface-muted" />
          <div className="h-24 rounded-xl bg-surface-muted" />
          <div className="h-24 rounded-xl bg-surface-muted" />
          <div className="h-24 rounded-xl bg-surface-muted" />
        </div>
      </section>
      <section className="surface-panel p-5">
        <div className="h-5 w-44 rounded-full bg-surface-muted" />
        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <div className="h-44 rounded-xl bg-surface-muted" />
          <div className="h-44 rounded-xl bg-surface-muted" />
          <div className="h-44 rounded-xl bg-surface-muted" />
        </div>
      </section>
    </div>
  );
}
