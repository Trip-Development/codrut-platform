"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FolderIcon, MailIcon, NetworkIcon, UsersIcon } from "lucide-react";

import { SectionNavigationList, sectionNavigationItemVariants } from "@/components/ui/section-navigation";
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
    <nav className="mb-5" aria-label="Vizualizare companie">
      <SectionNavigationList>
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
              className={sectionNavigationItemVariants({ active })}
            >
              <Icon aria-hidden="true" className={cn("size-3.5", active && "text-brand-text")} strokeWidth={1.8} />
              {section.label}
            </Link>
          );
        })}
      </SectionNavigationList>
    </nav>
  );
}

function normalizePathname(pathname: string): string {
  if (pathname === "/") return pathname;
  return pathname.replace(/\/+$/, "");
}
