"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const companyTabs = [
  { key: "", label: "Prezentare" },
  { key: "/participants", label: "Participanți" },
  { key: "/org-chart", label: "Organigramă" },
  { key: "/reports", label: "Rapoarte" },
  { key: "/teams", label: "Echipe" },
];

export function CompanyTabs({ basePath }: { basePath: string }) {
  const pathname = usePathname();

  return (
    <nav className="mb-6 overflow-x-auto rounded-2xl border border-[var(--border)] bg-surface/95 p-1.5 shadow-sm">
      <div className="flex min-w-max gap-1">
        {companyTabs.map((tab) => {
          const href = `${basePath}${tab.key}`;
          const isActive = tab.key === "" ? pathname === basePath : pathname.startsWith(href);

          return (
            <Link
              key={tab.key}
              href={href}
              aria-current={isActive ? "page" : undefined}
              className={[
                "tap-soft rounded-xl px-4 py-2.5 text-sm font-semibold transition-all",
                isActive
                  ? "bg-burgundy text-white shadow-sm shadow-burgundy/10"
                  : "text-foreground/62 hover:bg-surface-muted/70 hover:text-burgundy",
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
