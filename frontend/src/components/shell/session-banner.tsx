import type { SessionState } from "@/api/auth";
import { Alert, AlertDescription } from "@/components/ui/alert";

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
    <Alert className="mb-5 border-border bg-muted px-4 py-3" role="status">
      <AlertDescription className="text-sm font-semibold leading-6 text-muted-foreground">
        {message}
      </AlertDescription>
    </Alert>
  );
}
