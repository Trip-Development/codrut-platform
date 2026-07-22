"use client";

import { TrainerRouteError } from "@/components/shell/route-error";

export default function TrainerError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <TrainerRouteError error={error} reset={reset} />;
}
