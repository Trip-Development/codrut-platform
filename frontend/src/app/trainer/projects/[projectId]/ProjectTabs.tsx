"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const projectTabs = [
  { key: "", label: "Sumar" },
  { key: "/participants", label: "Participanți" },
  { key: "/assignments", label: "Asignări" },
  { key: "/invitations", label: "Invitații" },
  { key: "/org-chart", label: "Organigramă" },
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
  const pathname = usePathname();

  return (
    <nav className="surface-panel mb-6 overflow-hidden" aria-label="Navigare proiect">
      <div className="flex items-center gap-1 overflow-x-auto px-2 py-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {projectTabs.map((tab) => {
          const href = `${basePath}${tab.key}`;
          const isActive = tab.key === "" ? pathname === basePath : pathname.startsWith(href);
          const disabled = locked && !["", "/participants", "/settings"].includes(tab.key);

          if (disabled) {
            return (
              <span
                key={tab.key}
                title="Importă rosterul proiectului înainte de a folosi acest instrument."
                className="inline-flex min-h-10 shrink-0 cursor-not-allowed items-center justify-center rounded-full px-3.5 py-2 text-sm font-semibold text-foreground/28 sm:px-4"
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
                "tap-soft inline-flex min-h-10 shrink-0 items-center justify-center rounded-full px-3.5 py-2 text-sm font-semibold transition-all sm:px-4",
                isActive
                  ? "bg-foreground text-background shadow-sm"
                  : "text-foreground/58 hover:bg-surface-muted hover:text-foreground",
              ].join(" ")}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>
      {locked ? (
        <p className="border-t border-[var(--border)] bg-surface-muted px-4 py-3 text-xs font-semibold leading-5 text-foreground/58">
          După ce adaugi participanți, asignările, invitațiile, organigrama și rezultatele devin disponibile.
        </p>
      ) : null}
    </nav>
  );
}
