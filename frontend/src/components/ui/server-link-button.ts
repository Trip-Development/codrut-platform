import { cn } from "@/utils/cn";

type ServerLinkButtonVariant = "primary" | "outline" | "secondary" | "ghost";
type ServerLinkButtonSize = "default" | "sm" | "lg" | "icon-sm";

const baseClassName =
  "inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-lg border text-sm font-semibold outline-none transition-[background-color,border-color,color,box-shadow,transform] duration-150 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/45 focus-visible:ring-offset-2 focus-visible:ring-offset-background active:translate-y-px [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4";

const variantClassNames: Record<ServerLinkButtonVariant, string> = {
  ghost:
    "border-transparent bg-transparent text-foreground hover:bg-muted hover:text-foreground",
  primary: "border-transparent bg-primary text-primary-foreground shadow-sm hover:bg-primary/90",
  outline: "border-border bg-surface text-foreground shadow-sm hover:bg-muted hover:text-foreground",
  secondary:
    "border-transparent bg-secondary text-secondary-foreground hover:bg-muted",
};

const sizeClassNames: Record<ServerLinkButtonSize, string> = {
  default: "h-10 gap-2 px-4 has-data-[icon=inline-end]:pr-3 has-data-[icon=inline-start]:pl-3",
  "icon-sm": "size-9 p-0 [&_svg:not([class*='size-'])]:size-3.5",
  lg: "h-11 gap-2 px-5 has-data-[icon=inline-end]:pr-4 has-data-[icon=inline-start]:pl-4",
  sm: "h-9 gap-1.5 px-3 text-[0.8rem] has-data-[icon=inline-end]:pr-2.5 has-data-[icon=inline-start]:pl-2.5 [&_svg:not([class*='size-'])]:size-3.5",
};

export function serverLinkButtonClassName({
  variant = "primary",
  size = "default",
  className,
}: {
  variant?: ServerLinkButtonVariant;
  size?: ServerLinkButtonSize;
  className?: string;
} = {}) {
  return cn(baseClassName, variantClassNames[variant], sizeClassNames[size], className);
}
