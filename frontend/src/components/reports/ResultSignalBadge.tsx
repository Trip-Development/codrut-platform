import { cn } from "@/utils/cn";

export function ResultSignalBadge({
  status,
  className,
}: {
  status: "watch" | "ok";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "whitespace-nowrap rounded-full px-2 py-0.5 text-[0.68rem] font-semibold",
        status === "watch"
          ? "bg-destructive/10 text-destructive"
          : "bg-emerald-500/10 text-emerald-500",
        className,
      )}
    >
      {status === "watch" ? "De urmărit" : "În regulă"}
    </span>
  );
}
