type PlaceholderCardProps = {
  title: string;
  description: string;
  meta?: string;
};

export function PlaceholderCard({ title, description, meta }: PlaceholderCardProps) {
  return (
    <article className="rounded-xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      {meta ? (
        <p className="mb-3 text-xs font-bold uppercase tracking-[0.14em] text-burgundy/80">{meta}</p>
      ) : null}
      <h2 className="text-lg font-bold text-foreground">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-foreground/65">{description}</p>
    </article>
  );
}
