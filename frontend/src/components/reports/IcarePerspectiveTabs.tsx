"use client";

import { useId, useState, type KeyboardEvent, type ReactNode } from "react";

import { cn } from "@/utils/cn";

export type IcarePerspectiveTab = {
  id: string;
  label: string;
  tabLabel?: string;
  responseCount: number;
  content: ReactNode;
};

export function IcarePerspectiveTabs({
  perspectives,
  ariaLabel = "Perspective iCARE",
}: {
  perspectives: IcarePerspectiveTab[];
  ariaLabel?: string;
}) {
  const instanceId = useId();
  const [activeId, setActiveId] = useState(perspectives[0]?.id ?? "");
  const activePerspective = perspectives.find((perspective) => perspective.id === activeId)
    ?? perspectives[0];

  if (!activePerspective) return null;

  function activateTab(index: number, tabs: HTMLButtonElement[]) {
    const nextTab = tabs[index];
    const nextId = perspectives[index]?.id;
    if (!nextTab || !nextId) return;
    setActiveId(nextId);
    nextTab.focus();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const tabs = Array.from(
      event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("[role='tab']") ?? [],
    );
    const currentIndex = tabs.indexOf(event.currentTarget);
    if (currentIndex < 0) return;

    event.preventDefault();
    if (event.key === "Home") {
      activateTab(0, tabs);
      return;
    }
    if (event.key === "End") {
      activateTab(tabs.length - 1, tabs);
      return;
    }
    const offset = event.key === "ArrowRight" ? 1 : -1;
    activateTab((currentIndex + offset + tabs.length) % tabs.length, tabs);
  }

  return (
    <div>
      <div
        aria-label={ariaLabel}
        aria-orientation="horizontal"
        className="grid grid-cols-3 gap-1 rounded-lg border border-border bg-surface-muted p-1"
        role="tablist"
      >
        {perspectives.map((perspective) => {
          const selected = perspective.id === activePerspective.id;
          const tabId = `${instanceId}-${perspective.id}-tab`;
          const panelId = `${instanceId}-${perspective.id}-panel`;
          const responseCopy = `${perspective.responseCount} ${perspective.responseCount === 1 ? "răspuns" : "răspunsuri"}`;
          return (
            <button
              key={perspective.id}
              id={tabId}
              type="button"
              role="tab"
              aria-label={`${perspective.label}: ${responseCopy}`}
              aria-controls={panelId}
              aria-selected={selected}
              tabIndex={selected ? 0 : -1}
              className={cn(
                "min-w-0 rounded-md px-2 py-3 text-left text-xs font-semibold leading-4 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring/40 sm:px-3",
                selected
                  ? "border border-border bg-surface text-foreground shadow-sm"
                  : "border border-transparent text-muted-foreground hover:bg-surface/70 hover:text-foreground",
              )}
              onClick={() => setActiveId(perspective.id)}
              onKeyDown={handleKeyDown}
            >
              <span className="block">{perspective.tabLabel ?? perspective.label}</span>
              <span className="mt-1 block font-normal text-muted-foreground">
                {responseCopy}
              </span>
            </button>
          );
        })}
      </div>

      {perspectives.map((perspective) => {
        const selected = perspective.id === activePerspective.id;
        return (
          <div
            key={perspective.id}
            id={`${instanceId}-${perspective.id}-panel`}
            role="tabpanel"
            aria-labelledby={`${instanceId}-${perspective.id}-tab`}
            className="mt-4 outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
            hidden={!selected}
            tabIndex={selected ? 0 : -1}
          >
            {perspective.content}
          </div>
        );
      })}
    </div>
  );
}
