import Link from "next/link";

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
    return (
      <section className="rounded-xl border border-dashed border-[var(--border)] bg-surface/70 p-8 text-center">
        <p className="text-base font-semibold text-foreground">Compania nu a fost găsită.</p>
      </section>
    );
  }

  const basePath = `/trainer/companies/${companyId}`;

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 hero-shape shadow-glass animate-fade-in-up p-8 md:p-12 relative overflow-hidden">
        <div className="absolute inset-0 bg-hero-mesh opacity-100"></div>
        <div className="relative z-10">
          <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-burgundy/80">Context companie</p>
          <h2 className="mt-3 font-display text-4xl font-bold leading-tight text-foreground tracking-tight">Sumar și Setări</h2>
          <p className="mt-4 text-lg leading-relaxed text-foreground/60 max-w-md">Administrează participanții globali și setările organizației într-un spațiu aerisit.</p>
        </div>
        <div className="flex flex-wrap gap-3 relative z-10">
          <Link
            href={`${basePath}/participants`}
            className="btn-secondary"
          >
            Participanți
          </Link>
          <Link
            href={`${basePath}/settings`}
            className="btn-premium"
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
        />
      </div>
    </div>
  );
}


