import * as React from "react";
import { ChevronDownIcon, type LucideIcon } from "lucide-react";

import { cn } from "@/utils/cn";

type SelectControlProps = React.SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  icon?: LucideIcon;
  wrapperClassName?: string;
};

function SelectControl({
  className,
  wrapperClassName,
  label,
  icon: Icon,
  children,
  ...props
}: SelectControlProps) {
  return (
    <label data-slot="select-control" className={cn("relative block min-w-0", wrapperClassName)}>
      <span className="sr-only">{label}</span>
      {Icon ? (
        <Icon
          aria-hidden="true"
          className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          strokeWidth={1.8}
        />
      ) : null}
      <select
        data-slot="select"
        className={cn(
          "h-11 w-full min-w-0 cursor-pointer appearance-none rounded-lg border border-border bg-surface-elevated px-3.5 py-2 pr-9 text-sm font-semibold text-foreground shadow-none outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/25 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60",
          Icon && "pl-10",
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <ChevronDownIcon
        aria-hidden="true"
        className="pointer-events-none absolute right-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
        strokeWidth={1.8}
      />
    </label>
  );
}

export { SelectControl };
