"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FolderIcon, UsersIcon } from "lucide-react";

import { cn } from "@/utils/cn";

const companySections = [
  { key: "projects", label: "Proiecte", suffix: "", icon: FolderIcon },
  { key: "participants", label: "Participanți", suffix: "/participants", icon: UsersIcon },
] as const;

export function CompanySectionTabs({ basePath }: { basePath: string }) {
  const pathname = normalizePathname(usePathname());
  const normalizedBasePath = normalizePathname(basePath);

  return (
    <nav className="mb-5 flex w-fit items-center gap-1 rounded-md bg-muted p-1" aria-label="Vizualizare companie">
      {companySections.map((section) => {
        const href = `${normalizedBasePath}${section.suffix}`;
        const active = section.suffix === ""
          ? pathname === normalizedBasePath
          : pathname === href || pathname.startsWith(`${href}/`);
        const Icon = section.icon;

        return (
          <Link
            key={section.key}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "inline-flex h-9 items-center gap-2 rounded-sm px-3 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45",
              active
                ? "bg-surface text-primary shadow-sm"
                : "text-muted-foreground hover:bg-background/70 hover:text-foreground",
            )}
          >
            <Icon aria-hidden="true" className="size-3.5" strokeWidth={1.8} />
            {section.label}
          </Link>
        );
      })}
    </nav>
  );
}

function normalizePathname(pathname: string): string {
  if (pathname === "/") return pathname;
  return pathname.replace(/\/+$/, "");
}
