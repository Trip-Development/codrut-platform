import Link from "next/link";
import { notFound } from "next/navigation";

import { getCompanyDetail } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { StatCard } from "@/components/presentation/stat-card";
import { CompanyProjectsPanel } from "./CompanyProjectsPanel";

export default async function CompanyOverviewPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  const company = await getCompanyDetail(companyId, await getServerApiRequestOptions());

  if (!company) {
    notFound();
  }

  const basePath = `/trainer/companies/${companyId}`;

  return (
    <div className="space-y-6">
      <div className="company-arch overflow-hidden p-5 md:p-7">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-burgundy/80">Context companie</p>
            <h2 className="font-display mt-2 text-3xl font-semibold leading-tight text-foreground md:text-4xl">{company.name}</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-foreground/62">
              Administrează proiectele și setările organizației dintr-un singur spațiu.
            </p>
          </div>
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href={`${basePath}/settings`}
            className="btn-primary"
          >
            Setări companie
          </Link>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Participanți"
          value={company.stats.totalParticipants}
          detail="Persoane active în companie."
        />
        <StatCard
          label="Proiecte"
          value={company.projects.length}
          detail="Inițiative salvate pentru companie."
        />
        <StatCard
          label="Asignări"
          value={company.stats.totalAssignments}
          detail="Total asignări finalizate."
        />
        <StatCard
          label="Rata completare"
          value={company.stats.completionRate}
          suffix="%"
          detail="Proporția asignărilor finalizate."
          tone="success"
        />
      </div>

      <div>
        <CompanyProjectsPanel
          companyId={companyId}
          initialProjects={company.projects}
          assignments={company.assignments}
          participantCount={company.stats.totalParticipants}
        />
      </div>
    </div>
  );
}
