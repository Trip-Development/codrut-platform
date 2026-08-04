import { ChevronDownIcon, MessageSquareTextIcon } from "lucide-react";

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
      <summary className="inline-flex min-h-9 cursor-pointer list-none items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-xs font-semibold text-foreground outline-none transition-[background-color,border-color,color,box-shadow,transform] hover:border-foreground/20 hover:bg-muted focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/45 focus-visible:ring-offset-2 focus-visible:ring-offset-background active:translate-y-px [&::-webkit-details-marker]:hidden">
        <MessageSquareTextIcon className="size-3.5 text-primary" aria-hidden="true" />
        <span className="group-open:hidden">Vezi interpretarea completă</span>
        <span className="hidden group-open:inline">Ascunde interpretarea</span>
        <ChevronDownIcon className="size-3.5 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden="true" />
      </summary>
      <div className="mt-3 max-w-4xl rounded-lg bg-muted/40 px-4 py-3 leading-6 whitespace-pre-line">
        {children}
      </div>
    </details>
  );
}
