"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const companyTabs = [
  { key: "", label: "Sumar" },
  { key: "/participants", label: "Roster" },
  { key: "/invitations", label: "Invitații" },
  { key: "/org-chart", label: "Organigramă" },
  { key: "/teams", label: "Echipe" },
  { key: "/reports", label: "Rapoarte" },
  { key: "/settings", label: "Setări" },
];

export function CompanyTabs({ basePath }: { basePath: string }) {
  const pathname = usePathname();

  return (
    <nav className="mb-6 rounded-xl border border-[var(--border)] bg-surface px-2 py-2 shadow-sm" aria-label="Navigare companie">
      <div className="flex flex-wrap gap-1">
        {companyTabs.map((tab) => {
          const href = `${basePath}${tab.key}`;
          const isActive = tab.key === "" ? pathname === basePath : pathname.startsWith(href);

          return (
            <Link
              key={tab.key}
              href={href}
              aria-current={isActive ? "page" : undefined}
              className={[
                "tap-soft rounded-lg px-3.5 py-2 text-sm font-semibold transition-all",
                isActive
                  ? "bg-burgundy text-white shadow-sm shadow-burgundy/10"
                  : "text-foreground/58 hover:bg-surface-muted hover:text-foreground",
              ].join(" ")}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
