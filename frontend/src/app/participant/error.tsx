"use client";

import { ParticipantRouteError } from "@/components/shell/route-error";

export default function ParticipantError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <ParticipantRouteError error={error} reset={reset} />;
}
