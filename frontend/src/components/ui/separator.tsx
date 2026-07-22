import * as React from "react";

import { cn } from "@/utils/cn";

type SeparatorProps = React.ComponentProps<"div"> & {
  decorative?: boolean;
  orientation?: "horizontal" | "vertical";
};

function Separator({
  "aria-hidden": ariaHidden,
  "aria-orientation": ariaOrientation,
  className,
  orientation = "horizontal",
  role,
  decorative = true,
  ...props
}: SeparatorProps) {
  return (
    <div
      data-slot="separator"
      data-orientation={orientation}
      role={decorative ? "none" : role ?? "separator"}
      aria-hidden={decorative ? true : ariaHidden}
      aria-orientation={decorative ? undefined : ariaOrientation ?? orientation}
      className={cn(
        "shrink-0 bg-border data-[orientation=horizontal]:h-px data-[orientation=horizontal]:w-full data-[orientation=vertical]:w-px data-[orientation=vertical]:self-stretch",
        className,
      )}
      {...props}
    />
  );
}

export { Separator };
