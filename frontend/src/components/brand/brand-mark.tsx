import Image from "next/image";

import { cn } from "@/utils/cn";

type BrandMarkProps = {
  size?: "sm" | "md" | "lg";
  showText?: boolean;
  subtitle?: string;
  className?: string;
  tone?: "default" | "inverted";
};

const sizeClasses = {
  sm: "size-10 rounded-lg",
  md: "size-11 rounded-lg",
  lg: "size-14 rounded-lg",
};

export function BrandMark({
  size = "md",
  showText = true,
  subtitle = "Platformă de training și coaching",
  className,
  tone = "default",
}: BrandMarkProps) {
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-3", className)}>
      <span
        className={cn(
          "relative flex shrink-0 items-center justify-center overflow-hidden bg-surface shadow-brand border border-[var(--border)]",
          sizeClasses[size],
        )}
        aria-hidden="true"
      >
        <Image
          src="/logo.png"
          alt="Sigla Cody"
          fill
          sizes="(max-width: 768px) 40px, 56px"
          priority
          className="object-cover"
        />
      </span>
      {showText ? (
        <span className="min-w-0 text-left leading-none">
          <span
            className={cn(
              "block truncate text-base font-semibold transition-colors",
              tone === "inverted" ? "text-white" : "text-foreground group-hover:text-burgundy",
            )}
          >
            Cody
          </span>
          {subtitle ? (
            <span
              className={cn(
                "mt-1 block truncate text-xs font-semibold transition-colors",
                tone === "inverted" ? "text-white/68" : "text-foreground/55 group-hover:text-burgundy/68",
              )}
            >
              {subtitle}
            </span>
          ) : null}
        </span>
      ) : null}
    </span>
  );
}
