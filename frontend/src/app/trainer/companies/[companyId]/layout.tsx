import Link from "next/link";
import { notFound } from "next/navigation";
import { SettingsIcon } from "lucide-react";

import { getTrainerSession } from "@/api/auth-server";
import { getCompanyDetail } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { IdentityMark } from "@/components/presentation/identity-mark";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { serverLinkButtonClassName } from "@/components/ui/server-link-button";
import { CompanySectionTabs } from "./CompanySectionTabs";

export default async function CompanyDetailLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ companyId: string }>;
}) {
  const [{ companyId }, requestOptions, trainer] = await Promise.all([
    params,
    getServerApiRequestOptions(),
    getTrainerSession(),
  ]);
  const basePath = `/trainer/companies/${companyId}`;
  const company = await getCompanyDetail(companyId, requestOptions);

  if (!company) {
    notFound();
  }

  return (
    <AppShell
      audience="trainer"
      eyebrow=""
      title="Companie"
      description=""
      navItems={trainerNavItems}
      activeHref="/trainer/companies"
      userLabel={trainer.user.name}
      session={trainer}
      showHeader={false}
    >
      <section className="mb-5 rounded-lg border bg-surface px-5 py-5 md:px-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-start gap-4">
            <IdentityMark
              kind="company"
              label={company.name}
              seed={`company:${company.id}`}
              size="xl"
            />
            <div className="min-w-0">
              <p className="text-xs font-semibold text-muted-foreground">Companie</p>
              <h1 className="mt-1 break-words text-2xl font-semibold leading-tight text-foreground md:text-3xl">
                {company.name}
              </h1>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-5">
            <dl className="flex flex-wrap items-center gap-5 text-sm">
              <div>
                <dt className="text-muted-foreground">Participanți</dt>
                <dd className="mt-0.5 text-xl font-semibold tabular-nums text-foreground">
                  {company.stats.totalParticipants}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Proiecte</dt>
                <dd className="mt-0.5 text-xl font-semibold tabular-nums text-foreground">
                  {company.projects.length}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Completare</dt>
                <dd className="mt-0.5 text-xl font-semibold tabular-nums text-foreground">
                  {company.stats.completionRate}%
                </dd>
              </div>
            </dl>

            <Link
              href={`${basePath}/settings`}
              aria-label="Setări companie"
              title="Setări companie"
              className={serverLinkButtonClassName({
                variant: "ghost",
                size: "icon-sm",
              })}
            >
              <SettingsIcon aria-hidden="true" />
            </Link>
          </div>
        </div>
      </section>
      <CompanySectionTabs basePath={basePath} />
      {children}
    </AppShell>
  );
}
