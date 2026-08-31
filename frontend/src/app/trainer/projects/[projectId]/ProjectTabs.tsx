"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { SectionNavigationList, sectionNavigationItemVariants } from "@/components/ui/section-navigation";

// Filele raman exact cele de acum. La proiectele de `training` doar ultima
// se schimba: „Rezultate" (ecranul de coaching) devine „Evolutie competente".
const projectTabs = [
  { key: "", label: "Sumar" },
  { key: "/participants", label: "Participanți" },
  { key: "/assignments", label: "Asignări" },
  { key: "/invitations", label: "Invitații" },
  { key: "/org-chart", label: "Organigramă" },
  { key: "/reports", label: "Rezultate" },
  { key: "/settings", label: "Setări" },
];

// La `training` se intra in CAMERA aplicatiei vechi. Din filele de coaching raman
// doar doua, pentru ca sunt ale platformei, nu ale pedagogiei:
//   Participanti — cine e in proiect (oamenii vin din companie, ca peste tot)
//   Invitatii    — cum intra
// DISPAR: Asignari · Organigrama · Rezultate. N-au ce cauta la training.
// „Sumar" ramane pentru ca ACOLO e camera, iar „Setari" pentru ca acolo se aleg
// tema si competentele — fara ele nu se poate exersa.
const trainingProjectTabs = [
  { key: "", label: "Sumar" },
  { key: "/participants", label: "Participanți" },
  { key: "/invitations", label: "Invitații" },
  { key: "/settings", label: "Setări" },
];

export function ProjectTabs({
  basePath,
  locked,
  isTraining,
}: {
  basePath: string;
  locked?: boolean;
  isTraining?: boolean;
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
        {(isTraining ? trainingProjectTabs : projectTabs).map((tab) => {
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
