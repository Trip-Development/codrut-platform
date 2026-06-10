"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { createCompany, getCompanyList, type CompanyListItem } from "@/api/companies";

type CompaniesWorkspaceProps = {
  initialCompanies: CompanyListItem[];
};

type CompanyIdentity = {
  id: string;
  name: string;
};

export function CompaniesWorkspace({ initialCompanies }: CompaniesWorkspaceProps) {
  const [companies, setCompanies] = useState<CompanyListItem[]>(initialCompanies);
  const [name, setName] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    getCompanyList()
      .then((freshCompanies) => {
        setCompanies((current) => mergeCompanies(current, freshCompanies));
      })
      .catch(() => {
        setMessage("Lista de companii din backend nu a putut fi reîmprospătată.");
      });
  }, []);

  const sortedCompanies = useMemo(
    () => [...companies].sort((a, b) => a.name.localeCompare(b.name, "ro")),
    [companies],
  );
  const totalParticipants = companies.reduce((total, company) => total + company.participantCount, 0);
  const totalAssignments = companies.reduce((total, company) => total + company.assignmentCount, 0);
  const activeCompanies = companies.filter((company) => !company.dataUnavailable).length;

  async function handleCreateCompany(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) return;

    setIsSubmitting(true);
    setMessage(null);
    try {
      const created = await createCompany(trimmedName);
      setCompanies((current) => mergeCompanies(current, [companyToListItem(created)]));
      setName("");
      setMessage("Compania a fost creată în backend.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Compania nu a putut fi creată.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
        <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_24rem]">
          <div className="p-5 md:p-6">
            <p className="text-sm font-semibold text-burgundy/75">Workspace clienți</p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">Companiile pornesc tot fluxul</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
              Intră în companie pentru roster, organigramă, echipe, invitații și rapoarte. Lista de aici rămâne scurtă, scanabilă și legată de datele salvate.
            </p>
            <div className="mt-4 grid gap-2 sm:grid-cols-3">
              <CompanySummary label="Companii" value={activeCompanies} />
              <CompanySummary label="Roster" value={totalParticipants} />
              <CompanySummary label="Asignări" value={totalAssignments} />
            </div>
          </div>
          <form onSubmit={handleCreateCompany} className="flex flex-col justify-end gap-3 border-t border-[var(--border)] bg-surface-muted/45 p-5 md:p-6 lg:border-l lg:border-t-0">
            <label className="text-sm font-semibold text-foreground">
              Nume companie
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Ex. Michelin România"
                className="mt-2 min-h-11 w-full rounded-xl border border-[var(--border)] bg-background px-4 py-2.5 text-sm font-semibold text-foreground outline-none transition-colors placeholder:text-foreground/34 focus:border-burgundy/45 focus:ring-2 focus:ring-burgundy/10"
              />
            </label>
            <button
              type="submit"
              disabled={isSubmitting || !name.trim()}
              className="tap-soft inline-flex min-h-11 items-center justify-center rounded-xl bg-burgundy px-5 py-2.5 text-sm font-bold text-white shadow-sm shadow-burgundy/10 hover:bg-burgundy-700 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-45"
            >
              {isSubmitting ? "Se salvează..." : "Adaugă companie"}
            </button>
          </form>
        </div>
        {message ? (
          <p aria-live="polite" className="border-t border-[var(--border)] bg-background/70 px-5 py-3 text-sm font-semibold text-foreground/62">
            {message}
          </p>
        ) : null}
      </section>

      {sortedCompanies.length === 0 ? (
        <section className="rounded-2xl border border-dashed border-[var(--border)] bg-surface/70 p-8 text-center">
          <p className="text-base font-semibold text-foreground">Nu există companii încă.</p>
          <p className="mt-2 text-sm text-foreground/58">Adaugă prima companie ca să activezi spațiul de lucru.</p>
        </section>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {sortedCompanies.map((company) => (
            <CompanyCard
              key={company.id}
              company={company}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function CompanyCard({
  company,
}: {
  company: CompanyListItem;
}) {
  const completion =
    !company.dataUnavailable && company.assignmentCount > 0
      ? Math.round((company.completedCount / company.assignmentCount) * 100)
      : 0;

  return (
    <article className="group flex min-h-56 flex-col rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:border-burgundy/24 hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[var(--border)] bg-background text-base font-semibold text-burgundy shadow-sm">
            {company.name.trim().charAt(0).toLocaleUpperCase("ro")}
          </div>
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-foreground">{company.name}</h2>
            <p className="mt-1 text-xs font-semibold text-foreground/52">
              {company.dataUnavailable ? "Date indisponibile" : stageLabel(company.stage)}
            </p>
          </div>
        </div>
        <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-foreground/55 transition-colors group-hover:bg-burgundy/10 group-hover:text-burgundy">
          {company.participantCount} pers.
        </span>
      </div>

      {company.dataUnavailable ? (
        <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold leading-5 text-amber-800">
          Datele operaționale nu au putut fi citite momentan. Deschide compania pentru verificare.
        </p>
      ) : (
        <dl className="mt-5 grid grid-cols-3 divide-x divide-[var(--border)] rounded-xl bg-surface-muted/55 py-3 text-center">
          <CompanyStat label="Roster" value={company.participantCount} />
          <CompanyStat label="Asignări" value={company.assignmentCount} />
          <CompanyStat label="Finalizate" value={company.completedCount} />
        </dl>
      )}

      <div className="mt-auto pt-4">
        <div className="flex items-center justify-between text-sm font-semibold text-foreground/62">
          <span>Progres</span>
          <span>{company.dataUnavailable ? "N/A" : `${completion}%`}</span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-muted">
          <div
            className={["h-full rounded-full", company.dataUnavailable ? "bg-amber-400" : "bg-burgundy"].join(" ")}
            style={{ width: `${company.dataUnavailable ? 100 : completion}%` }}
          />
        </div>
      </div>

      <Link
        href={`/trainer/companies/${company.id}`}
        className="tap-soft mt-4 inline-flex min-h-10 items-center justify-center rounded-xl bg-foreground px-4 py-2.5 text-sm font-semibold text-background hover:bg-burgundy hover:text-white hover:shadow-sm"
      >
        Intră în workspace
      </Link>
    </article>
  );
}

function CompanySummary({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-background/80 px-3 py-2.5">
      <p className="text-xs font-semibold text-foreground/48">{label}</p>
      <p className="mt-1 text-lg font-semibold text-foreground">{value}</p>
    </div>
  );
}

function CompanyStat({ label, value }: { label: string | number; value: string | number }) {
  return (
    <div className="px-3">
      <p className="text-xs font-semibold text-foreground/45">{label}</p>
      <p className="mt-1 text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

function stageLabel(stage: CompanyListItem["stage"]): string {
  switch (stage) {
    case "setup":
      return "Configurare";
    case "invites":
      return "Invitații";
    case "completion":
      return "În lucru";
    case "reporting":
      return "Raportare";
    default:
      return stage;
  }
}

function companyToListItem(company: CompanyIdentity): CompanyListItem {
  return {
    id: company.id,
    name: company.name,
    participantCount: 0,
    assignmentCount: 0,
    completedCount: 0,
    stage: "setup",
  };
}

function mergeCompanies(
  current: CompanyListItem[],
  incoming: CompanyListItem[],
): CompanyListItem[] {
  const map = new Map(current.map((company) => [company.id, company]));
  incoming.forEach((company) => map.set(company.id, company));
  return Array.from(map.values());
}
