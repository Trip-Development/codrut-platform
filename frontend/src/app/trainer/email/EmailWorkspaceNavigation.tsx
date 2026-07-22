"use client";

import { FileTextIcon, MailIcon, UsersIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";

export type EmailWorkspaceView = "campaigns" | "contacts" | "templates";

const views: Array<{
  key: EmailWorkspaceView;
  label: string;
  icon: typeof MailIcon;
}> = [
  { key: "campaigns", label: "Campanii", icon: MailIcon },
  { key: "contacts", label: "Contacte", icon: UsersIcon },
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
    <div className="flex justify-end">
      <nav aria-label="Navigare Comunicare" className="flex w-fit items-center gap-1 rounded-md bg-muted p-1">
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
                "h-9 rounded-[6px] px-3 font-medium shadow-none",
                isActive
                  ? "bg-background text-foreground shadow-sm hover:bg-background"
                  : "text-muted-foreground hover:bg-background/70 hover:text-foreground",
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
