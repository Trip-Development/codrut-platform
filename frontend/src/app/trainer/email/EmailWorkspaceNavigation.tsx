"use client";

import { ArchiveIcon, FileTextIcon, MailIcon, UsersIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";

export type EmailWorkspaceView = "campaigns" | "contacts" | "archive" | "templates";

const views: Array<{
  key: EmailWorkspaceView;
  label: string;
  icon: typeof MailIcon;
}> = [
  { key: "campaigns", label: "Campanii", icon: MailIcon },
  { key: "contacts", label: "Contacte", icon: UsersIcon },
  { key: "archive", label: "Arhivă", icon: ArchiveIcon },
  { key: "templates", label: "Șabloane", icon: FileTextIcon },
];

export function EmailWorkspaceNavigation({
  activeView,
  onViewChange,
}: {
  activeView: EmailWorkspaceView;
  onViewChange: (view: EmailWorkspaceView) => void;
}) {
  return (
    <div className="min-w-0 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      <nav aria-label="Navigare Comunicare" className="flex w-max min-w-full items-center border-b border-border sm:min-w-0">
        {views.map(({ key, label, icon: Icon }) => {
          const isActive = activeView === key;
          return (
            <Button
              key={key}
              type="button"
              size="sm"
              variant="ghost"
              aria-current={isActive ? "page" : undefined}
              onClick={() => onViewChange(key)}
              className={cn(
                "h-10 shrink-0 rounded-none border-x-0 border-b-2 border-t-0 px-3 font-medium shadow-none",
                isActive
                  ? "border-primary bg-transparent text-primary hover:bg-transparent"
                  : "border-transparent text-muted-foreground hover:bg-muted/50 hover:text-foreground",
              )}
            >
              <Icon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
              {label}
            </Button>
          );
        })}
      </nav>
    </div>
  );
}
