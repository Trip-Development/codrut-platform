import Link from "next/link";
import { notFound } from "next/navigation";
import { Building2Icon, SettingsIcon } from "lucide-react";

import { getTrainerSession } from "@/api/auth-server";
import { getCompanyDetail } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
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
      <section className="mb-5 rounded-lg bg-primary px-5 py-5 text-primary-foreground shadow-[0_24px_60px_-36px_rgba(137,5,5,0.75)] md:px-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-start gap-4">
            <span className="mt-1 hidden size-10 shrink-0 items-center justify-center rounded-lg bg-primary-foreground/10 text-primary-foreground ring-1 ring-primary-foreground/15 sm:inline-flex">
              <Building2Icon aria-hidden="true" className="size-5" strokeWidth={1.8} />
            </span>
            <div className="min-w-0">
              <h1 className="truncate text-3xl font-semibold leading-tight md:text-4xl">
                {company.name}
              </h1>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-5">
            <dl className="flex flex-wrap items-center gap-5 text-sm">
              <div>
                <dt className="text-primary-foreground/64">Participanți</dt>
                <dd className="mt-0.5 text-xl font-semibold tabular-nums">
                  {company.stats.totalParticipants}
                </dd>
              </div>
              <div>
                <dt className="text-primary-foreground/64">Proiecte</dt>
                <dd className="mt-0.5 text-xl font-semibold tabular-nums">
                  {company.projects.length}
                </dd>
              </div>
              <div>
                <dt className="text-primary-foreground/64">Completare</dt>
                <dd className="mt-0.5 text-xl font-semibold tabular-nums">
                  {company.stats.completionRate}%
                </dd>
              </div>
            </dl>

            <Link
              href={`${basePath}/settings`}
              className={serverLinkButtonClassName({
                className:
                  "bg-primary-foreground text-primary hover:bg-primary-foreground/92 focus-visible:ring-primary-foreground/70",
              })}
            >
              <SettingsIcon aria-hidden="true" className="size-4" />
              Setări
            </Link>
          </div>
        </div>
      </section>
      <CompanySectionTabs basePath={basePath} />
      {children}
    </AppShell>
  );
}
