import Image from "next/image";

type BrandMarkProps = {
  size?: "sm" | "md" | "lg";
  showText?: boolean;
  subtitle?: string;
  className?: string;
  tone?: "default" | "inverted";
};

const sizeClasses = {
  sm: "h-10 w-10 rounded-xl",
  md: "h-11 w-11 rounded-2xl",
  lg: "h-14 w-14 rounded-2xl",
};

export function BrandMark({
  size = "md",
  showText = true,
  subtitle = "Training & Coaching Platform",
  className = "",
  tone = "default",
}: BrandMarkProps) {
  return (
    <span className={`inline-flex min-w-0 items-center gap-3 ${className}`}>
      <span
        className={[
          "relative flex shrink-0 items-center justify-center overflow-hidden bg-white shadow-brand border border-[var(--border)]",
          sizeClasses[size],
        ].join(" ")}
        aria-hidden="true"
      >
        <Image
          src="/logo.png"
          alt="Codrut Logo"
          fill
          sizes="(max-width: 768px) 40px, 56px"
          priority
          className="object-cover"
        />
      </span>
      {showText ? (
        <span className="min-w-0 text-left">
          <span className={`block truncate text-sm font-bold font-display ${tone === "inverted" ? "text-white" : "text-foreground"}`}>Codrut</span>
          <span className={`block truncate text-xs font-semibold ${tone === "inverted" ? "text-white/68" : "text-foreground/55"}`}>{subtitle}</span>
        </span>
      ) : null}
    </span>
  );
}
