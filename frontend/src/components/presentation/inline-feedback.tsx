import type { ReactNode } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { cn } from "@/utils/cn";

type InlineFeedbackProps = {
  children: ReactNode;
  tone?: "neutral" | "danger";
  className?: string;
  descriptionClassName?: string;
  id?: string;
};

export function InlineFeedback({
  children,
  tone = "neutral",
  className,
  descriptionClassName,
  id,
}: InlineFeedbackProps) {
  const isDanger = tone === "danger";

  return (
    <Alert
      id={id}
      role={isDanger ? "alert" : "status"}
      aria-live={isDanger ? "assertive" : "polite"}
      variant={isDanger ? "destructive" : "default"}
      className={cn(
        "px-4 py-3",
        isDanger
          ? "border-destructive/25 bg-destructive/8 text-destructive"
          : "border-border bg-muted text-foreground",
        className,
      )}
    >
      <AlertDescription
        className={cn(
          "text-sm font-semibold leading-6",
          isDanger ? "text-destructive" : "text-muted-foreground",
          descriptionClassName,
        )}
      >
        {children}
      </AlertDescription>
    </Alert>
  );
}
