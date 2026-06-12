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
    <div className="space-y-5">
      <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-green-100 bg-green-50 px-3 py-1 text-xs font-bold text-green-800">
              <span className="h-2 w-2 rounded-full bg-green-500" />
              {statusLabel(project.status)}
            </div>
            <h2 className="mt-3 text-2xl font-semibold text-foreground">Comandă proiect</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
              Gestionează acest proiect separat de restul companiei: roster, plan de asignări, invitații și rezultate.
            </p>
          </div>
          <Link
            href={`/trainer/companies/${project.company_id}`}
            className="tap-soft rounded-xl border border-[var(--border)] bg-background px-4 py-2 text-sm font-bold text-foreground/68 hover:border-burgundy/35 hover:text-burgundy"
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

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
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
      <div className="rounded-2xl border border-dashed border-[var(--border)] bg-surface/60 p-5 text-foreground/38">
        <h3 className="font-semibold">{title}</h3>
        <p className="mt-2 text-sm leading-6">{detail}</p>
        <p className="mt-4 text-xs font-bold">Disponibil după import roster</p>
      </div>
    );
  }

  return (
    <Link
      href={href}
      className="tap-soft rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm hover:-translate-y-0.5 hover:border-burgundy/35 hover:shadow-md"
    >
      <h3 className="font-semibold text-foreground">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-foreground/60">{detail}</p>
    </Link>
  );
}

function statusLabel(status: string): string {
  if (status === "active") return "Activ";
  if (status === "completed") return "Finalizat";
  if (status === "archived") return "Arhivat";
  return "În pregătire";
}
