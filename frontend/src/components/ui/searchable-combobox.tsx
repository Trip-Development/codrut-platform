"use client";

import { CheckIcon, ChevronDownIcon, SearchIcon, type LucideIcon } from "lucide-react";
import {
  Fragment,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/utils/cn";

export type SearchableComboboxOption = {
  value: string;
  label: string;
  group?: string;
};

export function SearchableCombobox({
  icon: Icon,
  label,
  value,
  allLabel,
  options,
  onValueChange,
  className,
  size = "default",
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  allLabel: string;
  options: SearchableComboboxOption[];
  onValueChange: (value: string) => void;
  className?: string;
  size?: "default" | "sm";
}) {
  const listboxId = useId();
  const searchRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const allOptions = useMemo(
    () => [{ value: "", label: allLabel }, ...options],
    [allLabel, options],
  );
  const selectedOption = allOptions.find((option) => option.value === value) ?? allOptions[0];
  const visibleOptions = useMemo(() => {
    const normalizedQuery = normalizeComboboxSearch(query);
    if (!normalizedQuery) return allOptions;
    return allOptions.filter((option) =>
      normalizeComboboxSearch(option.label).includes(normalizedQuery),
    );
  }, [allOptions, query]);

  useEffect(() => {
    if (!open) return;
    const frame = window.requestAnimationFrame(() => searchRef.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, [open]);

  useEffect(() => {
    setHighlightedIndex(0);
  }, [query]);

  function closeCombobox() {
    setOpen(false);
    setQuery("");
  }

  function selectOption(option: SearchableComboboxOption) {
    onValueChange(option.value);
    closeCombobox();
  }

  function handleSearchKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      closeCombobox();
      return;
    }
    if (visibleOptions.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlightedIndex((current) => Math.min(current + 1, visibleOptions.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightedIndex((current) => Math.max(current - 1, 0));
    } else if (event.key === "Home") {
      event.preventDefault();
      setHighlightedIndex(0);
    } else if (event.key === "End") {
      event.preventDefault();
      setHighlightedIndex(visibleOptions.length - 1);
    } else if (event.key === "Enter") {
      event.preventDefault();
      selectOption(visibleOptions[Math.min(highlightedIndex, visibleOptions.length - 1)]);
    }
  }

  return (
    <Popover
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (!nextOpen) setQuery("");
      }}
    >
      <div className={cn("relative min-w-0", className)}>
        <PopoverTrigger asChild>
          <button
            type="button"
            role="combobox"
            aria-label={label}
            aria-expanded={open}
            aria-controls={listboxId}
            aria-haspopup="listbox"
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setOpen(true);
              }
            }}
            className={cn(
              "flex w-full min-w-0 items-center justify-between gap-3 rounded-md border border-control-border bg-control px-3.5 text-sm font-semibold text-foreground outline-none transition-[background-color,border-color,box-shadow] duration-150 hover:bg-muted hover:border-foreground/15 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/25",
              size === "sm" ? "h-9" : "h-11",
            )}
          >
            <span className="flex min-w-0 items-center gap-3">
              <Icon aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" strokeWidth={1.8} />
              <span className="truncate">{selectedOption.label}</span>
            </span>
            <ChevronDownIcon
              aria-hidden="true"
              className={cn("size-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")}
              strokeWidth={1.8}
            />
          </button>
        </PopoverTrigger>

        <PopoverContent
          align="start"
          className="w-[var(--radix-popover-trigger-width)] min-w-56 p-1.5"
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            window.requestAnimationFrame(() => searchRef.current?.focus());
          }}
        >
          <div className="relative mb-1">
            <SearchIcon
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
              strokeWidth={1.8}
            />
            <Input
              ref={searchRef}
              type="text"
              role="searchbox"
              aria-label={`Caută în ${label.toLocaleLowerCase("ro")}`}
              aria-controls={listboxId}
              aria-activedescendant={visibleOptions.length > 0
                ? `${listboxId}-option-${Math.min(highlightedIndex, visibleOptions.length - 1)}`
                : undefined}
              autoComplete="off"
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={handleSearchKeyDown}
              placeholder="Caută opțiuni"
              className="h-9 rounded-sm bg-control pl-9 pr-3 text-sm"
            />
          </div>
          <div id={listboxId} role="listbox" aria-label={label} className="max-h-64 overflow-y-auto py-0.5">
            {visibleOptions.length === 0 ? (
              <p className="px-3 py-4 text-center text-xs font-medium text-muted-foreground">
                Nicio opțiune găsită
              </p>
            ) : (
              visibleOptions.map((option, index) => {
                const showGroup = Boolean(
                  option.group
                  && option.group !== visibleOptions[index - 1]?.group,
                );
                return (
                  <Fragment key={option.value || "all"}>
                    {showGroup ? (
                      <p
                        role="presentation"
                        className="px-2.5 pb-1 pt-2 text-[0.68rem] font-semibold uppercase tracking-wide text-muted-foreground"
                      >
                        {option.group}
                      </p>
                    ) : null}
                    <button
                      id={`${listboxId}-option-${index}`}
                      type="button"
                      role="option"
                      aria-selected={option.value === value}
                      onMouseEnter={() => setHighlightedIndex(index)}
                      onClick={() => selectOption(option)}
                      className={cn(
                        "flex w-full items-center gap-2 rounded-sm px-2.5 py-2 text-left text-sm font-medium outline-none",
                        index === highlightedIndex && "bg-muted text-foreground",
                      )}
                    >
                      <span className="flex size-4 shrink-0 items-center justify-center">
                        {option.value === value ? <CheckIcon aria-hidden="true" className="size-3.5" strokeWidth={2} /> : null}
                      </span>
                      <span className="truncate">{option.label}</span>
                    </button>
                  </Fragment>
                );
              })
            )}
          </div>
        </PopoverContent>
      </div>
    </Popover>
  );
}

export function normalizeComboboxSearch(value: string): string {
  return value
    .trim()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("ro");
}
