import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeftIcon } from "lucide-react";

import { getTrainerSession } from "@/api/auth-server";
import { getCompanyProjectById, getProjectParticipants } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { serverLinkButtonClassName } from "@/components/ui/server-link-button";
import { ProjectTabs } from "./ProjectTabs";

export default async function ProjectLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ projectId: string }>;
}) {
  const [{ projectId }, requestOptions, trainer] = await Promise.all([
    params,
    getServerApiRequestOptions(),
    getTrainerSession(),
  ]);
  const project = await getCompanyProjectById(projectId, requestOptions);

  if (!project) {
    notFound();
  }

  const basePath = `/trainer/projects/${project.id}`;
  const participants = await getProjectParticipants(
    project.company_id,
    project.id,
    requestOptions,
  );

  return (
    <AppShell
      audience="trainer"
      eyebrow=""
      title={project.name}
      description=""
      navItems={trainerNavItems}
      activeHref="/trainer/projects"
      userLabel={trainer.user.name}
      session={trainer}
      headerActions={
        <Link
          href={`/trainer/companies/${project.company_id}`}
          aria-label="Înapoi la companie"
          title="Înapoi la companie"
          className={serverLinkButtonClassName({ variant: "ghost", size: "icon-sm" })}
        >
          <ArrowLeftIcon aria-hidden="true" strokeWidth={1.8} />
        </Link>
      }
    >
      <ProjectTabs basePath={basePath} locked={participants.length === 0} />
      {children}
    </AppShell>
  );
}
