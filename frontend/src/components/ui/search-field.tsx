"use client";

import * as React from "react";
import { SearchIcon, XIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/cn";

type SearchFieldProps = Omit<
  React.ComponentProps<"input">,
  "className" | "onChange" | "size" | "type" | "value"
> & {
  id: string;
  label: string;
  value: string;
  onValueChange: (value: string) => void;
  className?: string;
  inputClassName?: string;
  clearLabel?: string;
};

const SearchField = React.forwardRef<HTMLInputElement, SearchFieldProps>(
  (
    {
      label,
      value,
      onValueChange,
      className,
      inputClassName,
      clearLabel = "Șterge căutarea",
      onKeyDown,
      ...props
    },
    ref,
  ) => (
    <div data-slot="search-field" className={cn("relative min-w-0", className)}>
      <label htmlFor={props.id} className="sr-only">
        {label}
      </label>
      <SearchIcon
        aria-hidden="true"
        className="pointer-events-none absolute left-3 top-1/2 z-10 size-4 -translate-y-1/2 text-muted-foreground"
        strokeWidth={1.8}
      />
      <Input
        {...props}
        ref={ref}
        type="search"
        inputMode="search"
        autoComplete={props.autoComplete ?? "off"}
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        onKeyDown={(event) => {
          onKeyDown?.(event);
          if (!event.defaultPrevented && event.key === "Escape" && value) {
            event.preventDefault();
            event.stopPropagation();
            onValueChange("");
          }
        }}
        className={cn(
          "appearance-none pl-9 pr-10 font-medium [&::-webkit-search-cancel-button]:appearance-none [&::-webkit-search-decoration]:appearance-none",
          inputClassName,
        )}
      />
      {value ? (
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label={clearLabel}
          onClick={() => onValueChange("")}
          className="absolute right-0.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:bg-transparent hover:text-foreground"
        >
          <XIcon aria-hidden="true" strokeWidth={1.8} />
        </Button>
      ) : null}
    </div>
  ),
);

SearchField.displayName = "SearchField";

export { SearchField };
