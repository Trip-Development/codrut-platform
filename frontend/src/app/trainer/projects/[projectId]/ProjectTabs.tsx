"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

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
  const normalizedBasePath = normalizePathname(basePath);

  return (
    <nav className="mb-6 rounded-lg bg-surface p-2 shadow-sm ring-1 ring-border" aria-label="Navigare proiect">
      <div className="flex items-center gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {projectTabs.map((tab) => {
          const href = `${normalizedBasePath}${tab.key}`;
          const isActive = tab.key === ""
            ? activePath === normalizedBasePath
            : activePath === href || activePath.startsWith(`${href}/`);
          const disabled = locked && !["", "/participants", "/settings"].includes(tab.key);

          if (disabled) {
            return (
              <span
                key={tab.key}
                title="Importă rosterul proiectului înainte de a folosi acest instrument."
                className="inline-flex h-9 shrink-0 cursor-not-allowed items-center justify-center rounded-lg px-3 text-sm font-semibold text-muted-foreground/55 sm:px-4"
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
                "inline-flex h-9 shrink-0 items-center justify-center rounded-lg px-3 text-sm font-semibold transition-colors sm:px-4",
                isActive
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              ].join(" ")}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>
      {locked ? (
        <p className="mt-2 rounded-lg bg-muted px-3 py-2 text-xs font-semibold leading-5 text-muted-foreground">
          După ce adaugi participanți, asignările, invitațiile, organigrama și rezultatele devin disponibile.
        </p>
      ) : null}
    </nav>
  );
}

function normalizePathname(pathname: string): string {
  if (pathname === "/") return pathname;
  return pathname.replace(/\/+$/, "");
}
