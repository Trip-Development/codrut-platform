"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const companyTabs = [
  { key: "", label: "Prezentare" },
  { key: "/participants", label: "Roster" },
  { key: "/org-chart", label: "Organigramă" },
  { key: "/teams", label: "Echipe" },
  { key: "/reports", label: "Rapoarte" },
  { key: "/settings", label: "Setări" },
];

export function CompanyTabs({ basePath }: { basePath: string }) {
  const pathname = usePathname();

  return (
    <nav className="mb-6 border-b border-[var(--border)]" aria-label="Navigare companie">
      <div className="flex flex-wrap gap-x-5 gap-y-2">
        {companyTabs.map((tab) => {
          const href = `${basePath}${tab.key}`;
          const isActive = tab.key === "" ? pathname === basePath : pathname.startsWith(href);

          return (
            <Link
              key={tab.key}
              href={href}
              aria-current={isActive ? "page" : undefined}
              className={[
                "tap-soft border-b-2 pb-3 pt-1 text-sm font-semibold transition-all",
                isActive
                  ? "border-burgundy text-burgundy"
                  : "border-transparent text-foreground/58 hover:text-foreground",
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
