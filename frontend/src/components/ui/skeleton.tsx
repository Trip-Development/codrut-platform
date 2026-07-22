import * as React from "react";

import { cn } from "@/utils/cn";

function Skeleton({
  className,
  tone = "default",
  ...props
}: React.ComponentProps<"div"> & { tone?: "default" | "inverted" | "wash" }) {
  return (
    <div
      data-slot="skeleton"
      data-tone={tone}
      aria-hidden="true"
      className={cn("skeleton-shimmer rounded-lg", className)}
      {...props}
    />
  );
}

export { Skeleton };
