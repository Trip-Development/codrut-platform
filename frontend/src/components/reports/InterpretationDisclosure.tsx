import { ChevronDownIcon } from "lucide-react";

import { disclosureTriggerClassName } from "@/components/ui/disclosure";
import { cn } from "@/utils/cn";

export function InterpretationDisclosure({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <details className={cn("group mt-4 text-sm text-muted-foreground", className)}>
      <summary className={cn(disclosureTriggerClassName, "inline-flex min-h-9 items-center gap-2 px-2 py-1.5 text-xs font-semibold text-foreground")}>
        <span className="group-open:hidden">Vezi interpretarea completă</span>
        <span className="hidden group-open:inline">Ascunde interpretarea</span>
        <ChevronDownIcon className="size-3.5 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden="true" />
      </summary>
      <div className="mt-3 max-w-4xl rounded-lg bg-muted/45 px-4 py-3 leading-6 whitespace-pre-line">
        {children}
      </div>
    </details>
  );
}
