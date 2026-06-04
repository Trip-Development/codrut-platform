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
        <svg viewBox="0 0 44 44" className="h-[78%] w-[78%]" role="img">
          <path
            d="M22 34V14"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="3.4"
          />
          <path
            d="M22 14c4.9 2.2 8.4 5.7 9.9 10.6-4.6.2-8.2-1.4-10.9-4.9"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="3.2"
          />
          <path
            d="M22 14c-5 2.2-8.6 5.8-10.2 10.9 4.8.2 8.5-1.6 11.2-5.2"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="3.2"
          />
          <path
            d="M22 10c3.7 1.5 6.4 4.1 8 7.7-3.9.3-6.8-.9-8.8-3.7"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="3.1"
          />
          <path
            d="M22 10c-3.7 1.5-6.4 4.1-8 7.7 3.9.3 6.8-.9 8.8-3.7"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="3.1"
          />
          <path
            d="M15 34h14"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
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
