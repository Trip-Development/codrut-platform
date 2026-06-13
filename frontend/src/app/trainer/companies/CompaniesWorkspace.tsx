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
        setMessage("Lista de companii nu a putut fi reîmprospătată.");
      });
  }, []);

  const sortedCompanies = useMemo(
    () => [...companies].sort((a, b) => a.name.localeCompare(b.name, "ro")),
    [companies],
  );
  const totalParticipants = companies.reduce((total, company) => total + company.participantCount, 0);
  const totalProjects = companies.reduce((total, company) => total + company.projectCount, 0);
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
      setMessage("Compania a fost creată și salvată.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Compania nu a putut fi creată.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="bento-card overflow-hidden relative">
        <div className="absolute top-0 right-0 p-32 bg-burgundy/5 blur-3xl rounded-full -mr-16 -mt-16 pointer-events-none"></div>
        <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_26rem] relative z-10">
          <div className="p-6 md:p-8">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80">Spațiu clienți</p>
            <h2 className="mt-2 text-2xl md:text-3xl font-display font-bold text-foreground tracking-tight">Companiile pornesc tot fluxul</h2>
            <p className="mt-3 max-w-xl text-sm md:text-base leading-relaxed text-foreground/60">
              Intră în companie pentru lista de participanți, organigramă, echipe, invitații și rapoarte. Lista de aici rămâne scurtă, scanabilă și legată de datele salvate.
            </p>
            <div className="mt-8 grid gap-4 sm:grid-cols-3">
              <CompanySummary label="Companii" value={activeCompanies} />
              <CompanySummary label="Proiecte" value={totalProjects} />
              <CompanySummary label="Participanți" value={totalParticipants} />
            </div>
          </div>
          <div className="bg-surface-muted/30 border-t border-[var(--border)] lg:border-l lg:border-t-0 p-6 md:p-8 flex flex-col justify-center">
            <form onSubmit={handleCreateCompany} className="flex flex-col gap-4">
              <label className="text-xs font-bold uppercase tracking-wider text-foreground/60">
                Nume companie
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Ex. Michelin România"
                  className="mt-2 min-h-[3rem] w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-semibold text-foreground outline-none transition-all placeholder:text-foreground/30 focus:border-burgundy/45 focus:ring-2 focus:ring-burgundy/10 shadow-sm"
                />
              </label>
              <button
                type="submit"
                disabled={isSubmitting || !name.trim()}
                className="btn-premium w-full mt-2"
              >
                {isSubmitting ? "Se salvează..." : "Adaugă companie"}
              </button>
            </form>
            {message && (
              <p aria-live="polite" className="mt-4 rounded-xl border border-border bg-surface px-4 py-3 text-sm font-semibold text-foreground/70 text-center animate-fade-in-up">
                {message}
              </p>
            )}
          </div>
        </div>
      </section>

      {sortedCompanies.length === 0 ? (
        <section className="bento-card bg-surface-muted/20 p-12 text-center flex flex-col items-center justify-center min-h-[30vh]">
          <p className="text-xl font-bold text-foreground">Nu există companii încă.</p>
          <p className="mt-3 text-sm leading-relaxed text-foreground/60">Adaugă prima companie ca să activezi spațiul de lucru.</p>
        </section>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
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
    <Link href={`/trainer/companies/${company.id}`} className="group relative flex min-h-64 flex-col rounded-xl border border-[var(--border)] bg-surface p-6 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:shadow-[0_8px_30px_-12px_rgba(137,5,5,0.15)] hover:border-burgundy/30 overflow-hidden cursor-pointer">
      <div className="absolute inset-0 bg-gradient-to-b from-surface to-surface-muted/20 opacity-0 transition-opacity duration-200 group-hover:opacity-100"></div>
      
      <div className="relative z-10 flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-[var(--border)] bg-surface-muted/50 text-xl font-bold text-burgundy shadow-sm transition-transform duration-300 group-hover:scale-105 group-hover:shadow-md group-hover:border-burgundy/20">
            {company.name.trim().charAt(0).toLocaleUpperCase("ro")}
          </div>
          <div className="min-w-0">
            <h2 className="truncate text-lg font-bold text-foreground transition-colors group-hover:text-burgundy">{company.name}</h2>
            <p className="mt-1 text-[11px] font-bold uppercase tracking-wider text-foreground/50">
              {company.dataUnavailable ? "Date indisponibile" : stageLabel(company.stage)}
            </p>
          </div>
        </div>
      </div>

      <div className="relative z-10 mt-6 mb-4 flex-1">
        {company.dataUnavailable ? (
          <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs font-semibold leading-relaxed text-amber-800">
            Datele operaționale nu au putut fi citite momentan. Deschide compania pentru verificare.
          </p>
        ) : (
          <dl className="grid grid-cols-3 divide-x divide-[var(--border)] rounded-xl border border-[var(--border)] bg-surface-muted/30 py-4 text-center">
            <CompanyStat label="Proiecte" value={company.projectCount} />
            <CompanyStat label="Participanți" value={company.participantCount} />
            <CompanyStat label="Finalizate" value={company.completedCount} />
          </dl>
        )}
      </div>

      <div className="relative z-10 mt-auto pt-5 border-t border-[var(--border)]">
        <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-foreground/60 mb-3">
          <span>Progres general</span>
          <span className="text-foreground">{company.dataUnavailable ? "N/A" : `${completion}%`}</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-surface-muted/80 shadow-inner">
          <div
            className={["h-full rounded-full transition-all duration-1000", company.dataUnavailable ? "bg-amber-400" : "bg-gradient-to-r from-burgundy to-[#d13a3a]"].join(" ")}
            style={{ width: `${company.dataUnavailable ? 100 : completion}%` }}
          />
        </div>
      </div>
    </Link>
  );
}

function CompanySummary({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-surface-muted/20 px-4 py-3 transition-colors hover:bg-surface-muted/40">
      <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/50 mb-1">{label}</p>
      <p className="font-display text-2xl font-bold text-foreground tracking-tight">{value}</p>
    </div>
  );
}

function CompanyStat({ label, value }: { label: string | number; value: string | number }) {
  return (
    <div className="px-3">
      <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/50 mb-1.5">{label}</p>
      <p className="text-base font-bold text-foreground">{value}</p>
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
    projectCount: 0,
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
