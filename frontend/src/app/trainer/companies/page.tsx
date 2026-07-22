import Link from "next/link";
import { PlusIcon } from "lucide-react";

import { getTrainerSession } from "@/api/auth-server";
import { getCompanyList } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { serverLinkButtonClassName } from "@/components/ui/server-link-button";
import { LazyCompaniesWorkspace } from "./LazyCompaniesWorkspace";

export default async function TrainerCompaniesPage() {
  const requestOptions = await getServerApiRequestOptions();
  const [companies, trainer] = await Promise.all([
    getCompanyList(requestOptions),
    getTrainerSession(),
  ]);

  return (
    <AppShell
      audience="trainer"
      eyebrow=""
      title="Companii"
      description=""
      navItems={trainerNavItems}
      activeHref="/trainer/companies"
      userLabel={trainer.user.name}
      session={trainer}
      headerActions={
        <Link
          href="/trainer/companies?modal=create-company"
          className={serverLinkButtonClassName()}
        >
          <PlusIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
          Companie nouă
        </Link>
      }
    >
      <LazyCompaniesWorkspace initialCompanies={companies} />
    </AppShell>
  );
}
