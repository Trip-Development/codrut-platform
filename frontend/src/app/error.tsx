"use client";

import { RootRouteError } from "@/components/shell/route-error";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <RootRouteError error={error} reset={reset} />;
}
