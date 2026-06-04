import type { SessionState } from "@/api/auth";

type SessionBannerProps = {
  session?: SessionState;
  note?: string;
};

export function SessionBanner({ session, note }: SessionBannerProps) {
  const message = session?.message ?? note;

  if (!message) {
    return null;
  }

  return (
    <div className="mb-5 rounded-2xl border border-[var(--border)] bg-surface-muted px-4 py-3 text-sm font-semibold leading-6 text-foreground/65">
      {message}
    </div>
  );
}
