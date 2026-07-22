import { cn } from "@/utils/cn";

type OperationFeedbackProps = {
  title: string;
  detail?: string;
  meta?: string;
  tone?: "default" | "danger";
  className?: string;
};

export function OperationFeedback({
  title,
  detail,
  meta = "în lucru",
  tone = "default",
  className,
}: OperationFeedbackProps) {
  const isDanger = tone === "danger";

  return (
    <div
      className={cn(
        "rounded-lg border bg-surface px-4 py-3 text-sm shadow-sm",
        isDanger
          ? "border-destructive/25 text-destructive"
          : "border-primary/15 text-foreground",
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center justify-between gap-3">
        <span className="flex min-w-0 items-center gap-2 font-semibold">
          <span
            aria-hidden="true"
            className={cn(
              "size-2 shrink-0 rounded-full",
              isDanger ? "bg-destructive" : "bg-primary",
            )}
          />
          <span className="truncate">{title}</span>
        </span>
        <span
          className={cn(
            "shrink-0 rounded-full px-2 py-0.5 text-[0.68rem] font-semibold tabular-nums",
            isDanger
              ? "bg-destructive/10 text-destructive"
              : "bg-primary/8 text-primary",
          )}
        >
          {meta}
        </span>
      </div>
      <div className="mt-3 h-1 overflow-hidden rounded-full bg-muted" aria-hidden="true">
        <div
          className={cn(
            "loading-bar-sweep h-full w-1/3 rounded-full",
            isDanger ? "bg-destructive" : "bg-primary",
          )}
        />
      </div>
      {detail ? (
        <p className={cn("mt-3 text-xs font-medium leading-5", isDanger ? "text-destructive/80" : "text-muted-foreground")}>
          {detail}
        </p>
      ) : null}
    </div>
  );
}
