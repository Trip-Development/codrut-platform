import Link from "next/link";
import { notFound } from "next/navigation";

import {
  getAllCompanyProjects,
  getCompanyAssignments,
  getCompanyInvitationStatuses,
  getProjectParticipants,
} from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { StatCard } from "@/components/presentation/stat-card";

export default async function ProjectOverviewPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const requestOptions = await getServerApiRequestOptions();
  const projects = await getAllCompanyProjects(requestOptions);
  const project = projects.find((item) => item.id === projectId);

  if (!project) {
    notFound();
  }

  const [participants, assignments, invitationStatuses] = await Promise.all([
    getProjectParticipants(project.company_id, project.id, requestOptions),
    getCompanyAssignments(project.company_id, requestOptions, { projectId: project.id }),
    getCompanyInvitationStatuses(project.company_id, requestOptions, { projectId: project.id }),
  ]);
  const completed = assignments.filter((assignment) =>
    ["submitted", "validated", "scored"].includes(assignment.status),
  ).length;
  const completionRate = assignments.length > 0 ? Math.round((completed / assignments.length) * 100) : 0;
  const invited = invitationStatuses.filter(
    (status) => status.latest_delivery_mode || status.has_active_secure_link,
  ).length;
  const basePath = `/trainer/projects/${project.id}`;

  return (
    <div className="space-y-6">
      <section className="bento-card p-6 md:p-8 relative overflow-hidden">
        <div className="absolute top-0 right-0 p-32 bg-burgundy/5 blur-3xl rounded-full -mr-16 -mt-16 pointer-events-none"></div>
        <div className="relative z-10 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-green-100 bg-green-50 px-3 py-1 text-xs font-bold text-green-800 shadow-[0_0_12px_rgba(34,197,94,0.15)]">
              <span className="h-2 w-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]" />
              {statusLabel(project.status)}
            </div>
            <h2 className="mt-4 text-3xl font-bold text-foreground font-display tracking-tight">Comandă proiect</h2>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-foreground/60">
              Gestionează acest proiect separat de restul companiei: roster, plan de asignări, invitații și rezultate.
            </p>
          </div>
          <Link
            href={`/trainer/companies/${project.company_id}`}
            className="btn-secondary"
          >
            Înapoi la companie
          </Link>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Participanți" value={participants.length} detail="Rosterul acestui proiect." />
        <StatCard label="Asignări" value={assignments.length} detail="Sarcini generate în proiect." />
        <StatCard label="Invitați" value={invited} detail="Email sau link securizat pregătit." />
        <StatCard label="Completare" value={completionRate} suffix="%" detail="Asignări finalizate." tone="success" />
      </div>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <WorkflowTile href={`${basePath}/participants`} title="Participanți" detail="Importă rosterul proiectului și verifică datele." />
        <WorkflowTile href={`${basePath}/assignments`} title="Asignări" detail="Generează și salvează planul implicit." locked={participants.length === 0} />
        <WorkflowTile href={`${basePath}/invitations`} title="Invitații" detail="Trimite emailuri, retrimite și vezi linkuri active." locked={participants.length === 0} />
        <WorkflowTile href={`${basePath}/reports`} title="Rapoarte" detail="Urmărește progresul și rezultatele agregate." locked={participants.length === 0} />
      </section>
    </div>
  );
}

function WorkflowTile({
  href,
  title,
  detail,
  locked = false,
}: {
  href: string;
  title: string;
  detail: string;
  locked?: boolean;
}) {
  if (locked) {
    return (
      <div className="rounded-2xl border border-dashed border-[var(--border)] bg-surface-muted/30 p-6 text-foreground/40">
        <h3 className="font-bold text-base">{title}</h3>
        <p className="mt-2 text-sm leading-relaxed">{detail}</p>
        <p className="mt-4 text-[10px] uppercase tracking-wider font-bold">Disponibil după import roster</p>
      </div>
    );
  }

  return (
    <Link
      href={href}
      className="group bento-card p-6 transition-all hover:-translate-y-1 hover:shadow-[0_8px_24px_-12px_rgba(137,5,5,0.15)] hover:border-burgundy/20"
    >
      <h3 className="font-bold text-base text-foreground transition-colors group-hover:text-burgundy">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-foreground/60">{detail}</p>
    </Link>
  );
}

function statusLabel(status: string): string {
  if (status === "active") return "Activ";
  if (status === "completed") return "Finalizat";
  if (status === "archived") return "Arhivat";
  return "În pregătire";
}
