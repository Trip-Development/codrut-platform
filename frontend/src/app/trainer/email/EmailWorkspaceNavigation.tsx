"use client";

import { ArchiveIcon, FileTextIcon, MailIcon, UsersIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SectionNavigationList, sectionNavigationItemVariants } from "@/components/ui/section-navigation";
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
    <nav aria-label="Navigare Comunicare" className="min-w-0">
      <SectionNavigationList>
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
                sectionNavigationItemVariants({ active: isActive }),
                "h-10 border-0 px-3 font-medium shadow-none sm:px-3",
              )}
            >
              <Icon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
              {label}
            </Button>
          );
        })}
      </SectionNavigationList>
    </nav>
  );
}
