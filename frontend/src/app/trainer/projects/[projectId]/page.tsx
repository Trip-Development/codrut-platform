import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowRightIcon,
  BarChart3Icon,
  ClipboardListIcon,
  LockIcon,
  MailIcon,
  UsersIcon,
  type LucideIcon,
} from "lucide-react";

import {
  getCompanyAssignments,
  getCompanyInvitationStatuses,
  getCompanyProjectById,
  getProjectParticipants,
} from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { ProjectStatusBadge, projectTypeLabel } from "@/components/projects/project-display";
import { cn } from "@/utils/cn";
import { formatRomanianDate } from "@/utils/date-format";

export default async function ProjectOverviewPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const [{ projectId }, requestOptions] = await Promise.all([
    params,
    getServerApiRequestOptions(),
  ]);
  const project = await getCompanyProjectById(projectId, requestOptions);

  if (!project) notFound();

  const results = await Promise.allSettled([
    getProjectParticipants(project.company_id, project.id, requestOptions),
    getCompanyAssignments(project.company_id, requestOptions, { projectId: project.id }),
    getCompanyInvitationStatuses(project.company_id, requestOptions, { projectId: project.id }),
  ]);
  const participants = results[0].status === "fulfilled" ? results[0].value : [];
  const assignments = results[1].status === "fulfilled" ? results[1].value : [];
  const invitationStatuses = results[2].status === "fulfilled" ? results[2].value : [];
  const loadErrors = [
    results[0].status === "rejected" ? "Participanții nu au putut fi încărcați." : null,
    results[1].status === "rejected" ? "Asignările nu au putut fi încărcate." : null,
    results[2].status === "rejected" ? "Statusul invitațiilor nu a putut fi încărcat." : null,
  ].filter((error): error is string => Boolean(error));

  const completed = assignments.filter((assignment) =>
    ["submitted", "validated", "scored"].includes(assignment.status),
  ).length;
  const completionRate = assignments.length > 0
    ? Math.round((completed / assignments.length) * 100)
    : 0;
  const pendingAssignments = Math.max(0, assignments.length - completed);
  const invited = invitationStatuses.filter(
    (status) => status.latest_delivery_mode || status.has_active_secure_link,
  ).length;
  const deliveryFailures = invitationStatuses.filter(
    (status) => status.latest_email_error || status.latest_email_status === "failed",
  ).length;
  const pendingInvites = Math.max(0, participants.length - invited);
  const basePath = `/trainer/projects/${project.id}`;
  const workflows: WorkflowStep[] = [
    {
      href: `${basePath}/participants`,
      title: "Participanți",
      metric: `${participants.length} persoane`,
      state: participants.length > 0 ? "Roster pregătit" : "Adaugă rosterul",
      icon: UsersIcon,
      attention: participants.length === 0,
    },
    {
      href: `${basePath}/assignments`,
      title: "Asignări",
      metric: `${assignments.length} sarcini`,
      state: assignments.length === 0
        ? "Generează planul"
        : pendingAssignments > 0
          ? `${pendingAssignments} în lucru`
          : "Finalizate",
      icon: ClipboardListIcon,
      locked: participants.length === 0,
      attention: assignments.length === 0 || pendingAssignments > 0,
    },
    {
      href: `${basePath}/invitations`,
      title: "Invitații",
      metric: `${invited}/${participants.length} trimise`,
      state: deliveryFailures > 0
        ? `${deliveryFailures} erori`
        : pendingInvites > 0
          ? `${pendingInvites} de trimis`
          : "Acoperite",
      icon: MailIcon,
      locked: participants.length === 0,
      attention: deliveryFailures > 0 || pendingInvites > 0,
    },
    {
      href: `${basePath}/reports`,
      title: "Rezultate",
      metric: `${completionRate}% completare`,
      state: completionRate >= 80 ? "Raportabil" : "În colectare",
      icon: BarChart3Icon,
      locked: participants.length === 0,
      attention: completionRate < 80,
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      {loadErrors.map((error) => (
        <InlineFeedback key={error} tone="danger">{error}</InlineFeedback>
      ))}

      <section className="overflow-hidden rounded-lg border bg-surface" aria-labelledby="project-overview-title">
        <div className="border-b px-5 py-5">
          <h2 id="project-overview-title" className="sr-only">Sumar proiect</h2>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
            <ProjectStatusBadge status={project.status} />
            <span className="font-medium text-foreground">{projectTypeLabel(project.project_type)}</span>
            <span className="text-muted-foreground">{formatDateRange(project.starts_at, project.due_at)}</span>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
            <div>
              <div className="flex items-end justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold text-muted-foreground">Completare</p>
                  <p className="mt-1 text-4xl font-semibold tabular-nums text-foreground">{completionRate}%</p>
                </div>
                <p className="pb-1 text-sm font-semibold text-muted-foreground">{completed}/{assignments.length} sarcini</p>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-primary" style={{ width: `${completionRate}%` }} />
              </div>
            </div>
            <dl className="flex flex-wrap gap-x-7 gap-y-3 lg:justify-end">
              <ProjectCount label="Participanți" value={participants.length} />
              <ProjectCount label="De urmărit" value={pendingAssignments + pendingInvites} attention />
              <ProjectCount label="Erori livrare" value={deliveryFailures} attention />
            </dl>
          </div>
        </div>

        <div className="divide-y divide-border">
          {workflows.map((step) => <WorkflowRow key={step.href} step={step} />)}
        </div>
      </section>
    </div>
  );
}

type WorkflowStep = {
  href: string;
  title: string;
  metric: string;
  state: string;
  icon: LucideIcon;
  locked?: boolean;
  attention?: boolean;
};

function WorkflowRow({ step }: { step: WorkflowStep }) {
  const Icon = step.icon;
  const content = (
    <>
      <span
        aria-hidden="true"
        className={cn(
          "inline-flex size-5 shrink-0 items-center justify-center",
          step.locked ? "text-muted-foreground" : step.attention ? "text-warning-ink" : "text-info-ink",
        )}
      >
        {step.locked ? <LockIcon className="size-4" strokeWidth={1.8} /> : <Icon className="size-4" strokeWidth={1.8} />}
      </span>
      <span className="min-w-0 flex-1 font-semibold text-foreground">{step.title}</span>
      <span className="hidden min-w-32 text-sm font-medium text-muted-foreground sm:block">{step.metric}</span>
      <span
        className={cn(
          "min-w-32 text-right text-sm font-semibold",
          step.locked ? "text-muted-foreground" : step.attention ? "text-warning-ink" : "text-success-ink",
        )}
      >
        {step.locked ? "Blocat" : step.state}
      </span>
      <ArrowRightIcon
        aria-hidden="true"
        className={cn("size-4 shrink-0", step.locked ? "text-muted-foreground/40" : "text-muted-foreground")}
        strokeWidth={1.8}
      />
    </>
  );

  if (step.locked) {
    return <div className="flex items-center gap-4 bg-muted/25 px-5 py-4">{content}</div>;
  }

  return (
    <Link
      href={step.href}
      className="flex items-center gap-4 px-5 py-4 transition-colors hover:bg-muted/35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/45"
    >
      {content}
    </Link>
  );
}

function ProjectCount({ label, value, attention = false }: { label: string; value: number; attention?: boolean }) {
  return (
    <div>
      <dt className="text-xs font-semibold text-muted-foreground">{label}</dt>
      <dd className={cn("mt-1 text-xl font-semibold tabular-nums", attention && value > 0 ? "text-warning-ink" : "text-foreground")}>{value}</dd>
    </div>
  );
}

function formatDateRange(start: string | null, end: string | null): string {
  if (!start && !end) return "Perioadă nesetată";
  if (start && end) return `${formatShortDate(start)} - ${formatShortDate(end)}`;
  if (start) return `Din ${formatShortDate(start)}`;
  return `Până la ${formatShortDate(end)}`;
}

function formatShortDate(value: string | null): string {
  if (!value) return "";
  return formatRomanianDate(value, { fallback: value, includeYear: false });
}
