export function ReportSection({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  const headingId = `report-section-${id}`;
  return (
    <section className="grid gap-6 border-b border-border pb-10" aria-labelledby={headingId}>
      <div>
        <h2 id={headingId} className="text-2xl font-semibold tracking-tight text-foreground">{title}</h2>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
      <div className="grid gap-5">{children}</div>
    </section>
  );
}
