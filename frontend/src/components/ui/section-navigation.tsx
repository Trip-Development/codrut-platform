import type { ComponentProps } from "react";
import { cva } from "class-variance-authority";

import { cn } from "@/utils/cn";

export const sectionNavigationItemVariants = cva(
  "inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-md px-3 text-sm font-semibold outline-none transition-[background-color,color,box-shadow,transform] duration-150 focus-visible:ring-2 focus-visible:ring-ring/45 focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-[0.98] motion-reduce:active:transform-none sm:px-4",
  {
    variants: {
      active: {
        true: "bg-muted text-foreground",
        false: "text-muted-foreground hover:bg-muted/65 hover:text-foreground",
      },
      disabled: {
        true: "cursor-not-allowed text-muted-foreground/50 hover:bg-transparent hover:text-muted-foreground/50",
        false: "",
      },
    },
    defaultVariants: {
      active: false,
      disabled: false,
    },
  },
);

export function SectionNavigationList({
  className,
  children,
  ...props
}: ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "min-w-0 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
      )}
      {...props}
    >
      <div className={cn("flex w-max min-w-full items-center gap-1 pb-1 sm:min-w-0", className)}>
        {children}
      </div>
    </div>
  );
}
