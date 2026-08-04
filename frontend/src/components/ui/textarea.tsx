import * as React from "react";

import { cn } from "@/utils/cn";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "min-h-20 w-full min-w-0 rounded-sm border border-control-border bg-control px-3 py-2 text-base font-medium leading-6 text-foreground shadow-none outline-none transition-[background-color,border-color,box-shadow,color] duration-150 placeholder:font-normal placeholder:text-muted-foreground hover:border-foreground/15 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/25 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60 aria-invalid:ring-2 aria-invalid:ring-destructive/20 md:text-sm",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
