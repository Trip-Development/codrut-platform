"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const companyTabs = [
  { key: "", label: "Sumar", shortLabel: "Sumar" },
  { key: "/participants", label: "Participanți", shortLabel: "Participanți" },
  { key: "/invitations", label: "Invitații", shortLabel: "Invitații" },
  { key: "/org-chart", label: "Organigramă", shortLabel: "Org" },
  { key: "/teams", label: "Echipe", shortLabel: "Echipe" },
  { key: "/reports", label: "Rapoarte", shortLabel: "Rapoarte" },
  { key: "/settings", label: "Setări", shortLabel: "Setări" },
];

export function CompanyTabs({ basePath }: { basePath: string }) {
  const pathname = usePathname();

  return (
    <nav
      className="mb-6 overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm"
      aria-label="Navigare companie"
    >
      <div className="flex items-center gap-1 overflow-x-auto px-2 py-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {companyTabs.map((tab) => {
          const href = `${basePath}${tab.key}`;
          const isActive = tab.key === "" ? pathname === basePath : pathname.startsWith(href);

          return (
            <Link
              key={tab.key}
              href={href}
              aria-current={isActive ? "page" : undefined}
              className={[
                "tap-soft group relative inline-flex min-h-10 shrink-0 items-center justify-center rounded-xl px-3.5 py-2 text-sm font-semibold transition-all sm:px-4",
                isActive
                  ? "bg-foreground text-background shadow-sm"
                  : "text-foreground/58 hover:bg-surface-muted hover:text-foreground",
              ].join(" ")}
            >
              <span className="hidden sm:inline">{tab.label}</span>
              <span className="sm:hidden">{tab.shortLabel}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
