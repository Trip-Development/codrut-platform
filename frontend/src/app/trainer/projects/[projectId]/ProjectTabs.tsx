"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { SectionNavigationList, sectionNavigationItemVariants } from "@/components/ui/section-navigation";

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
  const activePath = normalizePathname(usePathname());
  const searchParams = useSearchParams();
  const normalizedBasePath = normalizePathname(basePath);
  const cycleId = searchParams.get("cycle");
  const baselineId = searchParams.get("baseline");
  const compareId = searchParams.get("compare");

  return (
    <nav className="mb-6" aria-label="Navigare proiect">
      <SectionNavigationList>
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
                className={sectionNavigationItemVariants({ disabled: true })}
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
              className={sectionNavigationItemVariants({ active: isActive })}
            >
              {tab.label}
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
