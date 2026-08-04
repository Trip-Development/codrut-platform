"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FolderIcon, MailIcon, NetworkIcon, UsersIcon } from "lucide-react";

import { cn } from "@/utils/cn";

const companySections = [
  { key: "projects", label: "Proiecte", suffix: "", icon: FolderIcon },
  { key: "participants", label: "Participanți", suffix: "/participants", icon: UsersIcon },
  { key: "teams", label: "Echipe", suffix: "/teams", icon: NetworkIcon },
  { key: "invitations", label: "Invitații", suffix: "/invitations", icon: MailIcon },
] as const;

export function CompanySectionTabs({ basePath }: { basePath: string }) {
  const pathname = normalizePathname(usePathname());
  const normalizedBasePath = normalizePathname(basePath);

  return (
    <nav className="mb-5 border-b border-border" aria-label="Vizualizare companie">
      <div className="flex items-center gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
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
              "inline-flex h-11 shrink-0 items-center gap-2 border-b-2 px-3 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/45 sm:px-4",
              active
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon aria-hidden="true" className="size-3.5" strokeWidth={1.8} />
            {section.label}
          </Link>
        );
      })}
      </div>
    </nav>
  );
}

function normalizePathname(pathname: string): string {
  if (pathname === "/") return pathname;
  return pathname.replace(/\/+$/, "");
}
