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
      <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_28rem] lg:items-end">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Flux principal</p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">Adaugă și gestionează companii</h2>
            <p className="mt-2 text-sm leading-6 text-foreground/62">
              Creează clientul aici, apoi intră în companie pentru roster, organigramă, echipe, invitații și rapoarte.
            </p>
          </div>
          <form onSubmit={handleCreateCompany} className="flex flex-col gap-2 sm:flex-row">
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Nume companie"
              className="min-h-11 flex-1 rounded-xl border border-[var(--border)] bg-background px-4 py-2.5 text-sm font-semibold text-foreground outline-none focus:border-burgundy/45"
            />
            <button
              type="submit"
              disabled={isSubmitting || !name.trim()}
              className="tap-soft rounded-xl bg-burgundy px-5 py-2.5 text-sm font-bold text-white hover:bg-burgundy-700 disabled:cursor-not-allowed disabled:opacity-45"
            >
              {isSubmitting ? "Se salvează..." : "Adaugă companie"}
            </button>
          </form>
        </div>
        {message ? <p className="mt-3 text-sm font-semibold text-foreground/58">{message}</p> : null}
      </section>

      {sortedCompanies.length === 0 ? (
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-8 text-center shadow-sm">
          <p className="text-sm text-foreground/62">Nicio companie configurată încă.</p>
        </section>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {sortedCompanies.map((company) => (
            <CompanyCard key={company.id} company={company} />
          ))}
        </div>
      )}
    </div>
  );
}

function CompanyCard({ company }: { company: CompanyListItem }) {
  const completion =
    !company.dataUnavailable && company.assignmentCount > 0
      ? Math.round((company.completedCount / company.assignmentCount) * 100)
      : 0;

  return (
    <article className="flex flex-col rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-semibold text-foreground">{company.name}</h2>
        <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-foreground/55">
          {company.dataUnavailable ? "date indisponibile" : company.stage}
        </span>
      </div>

      {company.dataUnavailable ? (
        <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold leading-5 text-amber-800">
          Datele operaționale nu au putut fi citite momentan. Deschide compania pentru verificare.
        </p>
      ) : (
        <p className="mt-3 text-sm text-foreground/62">
          {company.participantCount} participanți · {company.completedCount}/{company.assignmentCount} completate
        </p>
      )}

      <div className="mt-4">
        <div className="flex items-center justify-between text-sm font-semibold text-foreground/62">
          <span>
            {company.dataUnavailable ? "N/A" : `${company.completedCount}/${company.assignmentCount}`}
          </span>
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
        className="tap-soft mt-4 inline-flex w-full justify-center rounded-xl bg-foreground px-4 py-2.5 text-sm font-semibold text-background hover:bg-burgundy hover:text-white"
      >
        Deschide compania
      </Link>
    </article>
  );
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
