type BrandMarkProps = {
  size?: "sm" | "md" | "lg";
  showText?: boolean;
  subtitle?: string;
  className?: string;
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
}: BrandMarkProps) {
  return (
    <span className={`inline-flex min-w-0 items-center gap-3 ${className}`}>
      <span
        className={[
          "flex shrink-0 items-center justify-center bg-burgundy text-white shadow-brand",
          sizeClasses[size],
        ].join(" ")}
        aria-hidden="true"
      >
        <svg viewBox="0 0 44 44" className="h-[72%] w-[72%]" role="img">
          <path
            d="M22 7.2c-6.4 0-11.8 4.7-12.6 11-.9 7 4.6 13 11.6 13h1.8"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="4.2"
          />
          <path
            d="M25.2 29.8V18.6m0 0 6.8 6.2m-6.8-6.2-6.7 6.2"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="3.4"
          />
          <path
            d="M25.2 18.4c2.1-5 5.1-7.3 9.6-8.2-.4 4.9-2.5 8.3-7.8 10.1"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="3.2"
          />
        </svg>
      </span>
      {showText ? (
        <span className="min-w-0 text-left">
          <span className="block truncate text-sm font-bold text-foreground">Codrut</span>
          <span className="block truncate text-xs font-semibold text-foreground/55">{subtitle}</span>
        </span>
      ) : null}
    </span>
  );
}
