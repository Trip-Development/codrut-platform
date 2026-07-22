"use client";

import { SearchIcon, XIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/cn";

export { SearchableCombobox as SearchableProjectFilter } from "@/components/ui/searchable-combobox";
export { normalizeComboboxSearch as normalizeWorkspaceSearch } from "@/components/ui/searchable-combobox";

export function WorkspaceSearchInput({
  id,
  label,
  placeholder,
  value,
  onValueChange,
  className,
}: {
  id: string;
  label: string;
  placeholder: string;
  value: string;
  onValueChange: (value: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("relative min-w-0", className)}>
      <label htmlFor={id} className="sr-only">{label}</label>
      <SearchIcon
        aria-hidden="true"
        className="pointer-events-none absolute left-3.5 top-1/2 z-10 size-4 -translate-y-1/2 text-muted-foreground"
        strokeWidth={1.8}
      />
      <Input
        id={id}
        type="text"
        inputMode="search"
        autoComplete="off"
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        placeholder={placeholder}
        className="h-11 bg-background pl-10 pr-10"
      />
      {value ? (
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label="Șterge căutarea"
          onClick={() => onValueChange("")}
          className="absolute right-2.5 top-1/2 size-7 -translate-y-1/2 text-muted-foreground hover:text-foreground active:-translate-y-1/2"
        >
          <XIcon aria-hidden="true" strokeWidth={1.8} />
        </Button>
      ) : null}
    </div>
  );
}
