import Link from "next/link";

import { getCompanyDetail } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

const companyTabs = [
  { key: "", label: "Prezentare" },
  { key: "/participants", label: "Participanti" },
  { key: "/org-chart", label: "Organigrama" },
  { key: "/reports", label: "Rapoarte" },
  { key: "/teams", label: "Echipe" },
];

export default async function CompanyDetailLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  const company = await getCompanyDetail(companyId, await getServerApiRequestOptions());
  const companyName = company?.name ?? "Companie";
  const basePath = `/trainer/companies/${companyId}`;

  return (
    <AppShell
      audience="trainer"
      eyebrow="Companie"
      title={companyName}
      description={`Detalii, participanti, organigrama si rapoarte pentru ${companyName}.`}
      navItems={trainerNavItems}
      activeHref="/trainer/companies"
    >
      <nav className="mb-6 flex gap-1 overflow-x-auto rounded-2xl border border-[var(--border)] bg-surface p-1.5 shadow-sm">
        {companyTabs.map((tab) => (
          <Link
            key={tab.key}
            href={`${basePath}${tab.key}`}
            className="tap-soft rounded-lg px-4 py-2.5 text-sm font-semibold text-foreground/62 transition-colors hover:bg-surface-muted hover:text-burgundy"
          >
            {tab.label}
          </Link>
        ))}
      </nav>

      {children}
    </AppShell>
  );
}
