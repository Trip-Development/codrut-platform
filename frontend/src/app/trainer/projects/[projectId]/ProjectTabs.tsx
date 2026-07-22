"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

const projectTabs = [
  { key: "", label: "Sumar" },
  { key: "/participants", label: "Participanți" },
  { key: "/assignments", label: "Asignări" },
  { key: "/invitations", label: "Invitații" },
  { key: "/org-chart", label: "Organigramă" },
  { key: "/teams", label: "Echipe" },
  { key: "/reports", label: "Rezultate" },
  { key: "/settings", label: "Setări" },
];

export function ProjectTabs({
  basePath,
  locked,
}: {
  basePath: string;
  locked?: boolean;
}) {
  const activePath = normalizePathname(usePathname());
  const searchParams = useSearchParams();
  const normalizedBasePath = normalizePathname(basePath);
  const cycleId = searchParams.get("cycle");
  const baselineId = searchParams.get("baseline");
  const compareId = searchParams.get("compare");

  return (
    <nav className="mb-6 border-b border-border" aria-label="Navigare proiect">
      <div className="flex items-center gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {projectTabs.map((tab) => {
          const baseHref = `${normalizedBasePath}${tab.key}`;
          const targetParams = new URLSearchParams();
          if (cycleId) targetParams.set("cycle", cycleId);
          if (tab.key === "/reports") {
            if (baselineId) targetParams.set("baseline", baselineId);
            if (compareId) targetParams.set("compare", compareId);
          }
          const query = targetParams.toString();
          const href = query ? `${baseHref}?${query}` : baseHref;
          const isActive = tab.key === ""
            ? activePath === normalizedBasePath
            : activePath === baseHref || activePath.startsWith(`${baseHref}/`);
          const disabled = locked && !["", "/participants", "/settings"].includes(tab.key);

          if (disabled) {
            return (
              <span
                key={tab.key}
                title="Importă rosterul proiectului înainte de a folosi acest instrument."
                className="inline-flex h-11 shrink-0 cursor-not-allowed items-center justify-center border-b-2 border-transparent px-3 text-sm font-semibold text-muted-foreground/55 sm:px-4"
              >
                {tab.label}
              </span>
            );
          }

          return (
            <Link
              key={tab.key}
              href={href}
              aria-current={isActive ? "page" : undefined}
              className={[
                "inline-flex h-11 shrink-0 items-center justify-center border-b-2 px-3 text-sm font-semibold transition-colors sm:px-4",
                isActive
                  ? "border-burgundy text-burgundy"
                  : "border-transparent text-muted-foreground hover:text-foreground",
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

function normalizePathname(pathname: string): string {
  if (pathname === "/") return pathname;
  return pathname.replace(/\/+$/, "");
}
