import type { ReactNode } from "react";

import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { cn } from "@/utils/cn";

type EmptyStateProps = {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
};

export function EmptyState({ title, description, icon, action, className = "" }: EmptyStateProps) {
  return (
    <Empty className={cn("rounded-lg border border-border bg-surface px-5 py-6 shadow-none", className)}>
      {icon ? (
        <EmptyMedia variant="icon" className="size-12 text-muted-foreground [&_svg:not([class*='size-'])]:size-5">
          {icon}
        </EmptyMedia>
      ) : null}
      <EmptyHeader>
        <EmptyTitle className="text-base font-semibold text-foreground">{title}</EmptyTitle>
        {description ? <EmptyDescription className="max-w-md">{description}</EmptyDescription> : null}
      </EmptyHeader>
      {action ? <EmptyContent className="mt-0">{action}</EmptyContent> : null}
    </Empty>
  );
}
