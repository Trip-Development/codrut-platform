"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type CSSProperties, type FormEvent } from "react";

import { createCompany, type CompanyListItem } from "@/api/companies";
import { ModalLayer } from "@/components/ui/modal-layer";
import { useUrlState } from "@/hooks/use-url-state";

type CompaniesWorkspaceProps = {
  initialCompanies: CompanyListItem[];
};

type CompanyIdentity = {
  id: string;
  name: string;
};

export function CompaniesWorkspace({ initialCompanies }: CompaniesWorkspaceProps) {
  const { get, searchKey, setParam, setParams } = useUrlState();
  const [companies, setCompanies] = useState<CompanyListItem[]>(initialCompanies);
  const [name, setName] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createOpen, setCreateOpen] = useState(get("modal") === "create-company");
  const [searchQuery, setSearchQuery] = useState(get("q") ?? "");

  useEffect(() => {
    setSearchQuery(get("q") ?? "");
    setCreateOpen(get("modal") === "create-company");
  }, [get, searchKey]);

  const sortedCompanies = useMemo(() => {
    const query = normalizeSearchText(searchQuery);
    return companies
      .filter((company) => {
        if (!query) return true;
        return normalizeSearchText(`${company.name} ${company.stage}`).includes(query);
      })
      .sort((a, b) => a.name.localeCompare(b.name, "ro"));
  }, [companies, searchQuery]);
  const totalParticipants = companies.reduce((total, company) => total + company.participantCount, 0);
  const totalProjects = companies.reduce((total, company) => total + company.projectCount, 0);
  const activeCompanies = companies.filter((company) => !company.dataUnavailable).length;

  function closeCreateModal() {
    setCreateOpen(false);
    setParams({ modal: null }, "replace");
  }

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
      closeCreateModal();
      setMessage("Compania a fost creată și salvată.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Compania nu a putut fi creată.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="filter-toolbar">
        <div className="relative w-full md:flex-1">
          <svg className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-foreground/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0z" />
          </svg>
          <input
            value={searchQuery}
            onChange={(event) => {
              setSearchQuery(event.target.value);
              setParam("q", event.target.value, "replace");
            }}
            placeholder="Caută companie..."
            className="control-input control-search w-full py-3 pl-12 pr-4"
          />
        </div>
        <button
          type="button"
          onClick={() => {
            setCreateOpen(true);
            setParam("modal", "create-company");
          }}
          className="btn-primary shrink-0"
        >
          Adaugă companie
        </button>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        <CompanySummary label="Companii" value={activeCompanies} />
        <CompanySummary label="Proiecte" value={totalProjects} />
        <CompanySummary label="Participanți" value={totalParticipants} />
      </section>

      {message && (
        <p aria-live="polite" className="surface-panel px-4 py-3 text-center text-sm font-semibold text-foreground/70">
          {message}
        </p>
      )}

      {createOpen ? (
        <ModalLayer
          labelledBy="create-company-title"
          onClose={() => {
            if (!isSubmitting) closeCreateModal();
          }}
          closeOnBackdrop={!isSubmitting}
        >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80">Companie nouă</p>
                <h3 id="create-company-title" className="mt-1 text-xl font-bold text-foreground">Adaugă companie</h3>
                <p className="mt-2 text-sm leading-6 text-foreground/60">
                  Creează spațiul companiei, apoi configurezi proiectele și rosterul în pagina ei.
                </p>
              </div>
              <button
                type="button"
                onClick={closeCreateModal}
                disabled={isSubmitting}
                className="tap-soft rounded-full border border-[var(--border)] bg-surface-muted px-3 py-2 text-xs font-bold text-foreground/60 hover:text-burgundy disabled:opacity-50"
              >
                Închide
              </button>
            </div>
            <form onSubmit={handleCreateCompany} className="mt-6 flex flex-col gap-4">
              <label className="text-xs font-bold uppercase tracking-wider text-foreground/60">
                Nume companie
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Ex. Michelin România"
                  className="control-input mt-2 min-h-[3rem] w-full py-3"
                  autoFocus
                />
              </label>
              <button
                type="submit"
                disabled={isSubmitting || !name.trim()}
                className="btn-primary mt-2 w-full"
              >
                {isSubmitting ? "Se salvează..." : "Salvează compania"}
              </button>
            </form>
        </ModalLayer>
      ) : null}

      {companies.length === 0 ? (
        <section className="surface-panel-muted flex min-h-[30vh] flex-col items-center justify-center p-12 text-center">
          <p className="text-xl font-bold text-foreground">Nu există companii încă.</p>
          <p className="mt-3 text-sm leading-relaxed text-foreground/60">Adaugă prima companie ca să activezi spațiul de lucru.</p>
        </section>
      ) : sortedCompanies.length === 0 ? (
        <section className="surface-panel flex min-h-[18rem] flex-col items-center justify-center p-10 text-center">
          <p className="font-display text-lg font-bold text-foreground">Nu am găsit companii pentru căutarea curentă.</p>
          <p className="mt-2 max-w-sm text-sm text-foreground/55">Șterge o parte din căutare sau încearcă alt nume.</p>
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
  return (
    <Link href={`/trainer/companies/${company.id}`} className="group flex min-h-64 flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-surface shadow-sm transition-colors hover:border-burgundy/25">
      <div className="visual-band h-24 border-b border-[var(--border)] p-5" style={entityVisualStyle(company.name)}>
        <div className="flex items-center justify-between gap-3">
          <div className="band-mark h-12 w-12 text-xl font-bold">
            {company.name.trim().charAt(0).toLocaleUpperCase("ro")}
          </div>
          <span className="band-chip">
            {company.dataUnavailable ? "Date indisponibile" : stageLabel(company.stage)}
          </span>
        </div>
      </div>
      <div className="flex flex-1 flex-col p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-4">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-bold text-foreground transition-colors group-hover:text-burgundy">{company.name}</h2>
            <p className="mt-1 text-[11px] font-bold uppercase tracking-wider text-foreground/50">
              Spațiu companie
            </p>
          </div>
        </div>
      </div>

      <div className="mt-6 mb-4 flex-1">
        {company.dataUnavailable ? (
          <p className="status-panel-warning px-4 py-3 text-xs leading-relaxed">
            Datele operaționale nu au putut fi citite momentan. Deschide compania pentru verificare.
          </p>
        ) : (
          <dl className="grid grid-cols-3 divide-x divide-[var(--border)] rounded-xl border border-[var(--border)] bg-surface-muted py-4 text-center">
            <CompanyStat label="Proiecte" value={company.projectCount} />
            <CompanyStat label="Participanți" value={company.participantCount} />
            <CompanyStat label="Finalizate" value={company.completedCount} />
          </dl>
        )}
      </div>

      <p className="mt-auto border-t border-[var(--border)] pt-4 text-xs font-semibold leading-5 text-foreground/52">
        Deschide pentru proiecte, roster și echipe.
      </p>
      </div>
    </Link>
  );
}

function CompanySummary({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="surface-panel px-4 py-3">
      <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/50 mb-1">{label}</p>
      <p className="font-display text-2xl font-bold text-foreground tracking-tight">{value}</p>
    </div>
  );
}

function entityVisualStyle(seed: string): CSSProperties {
  const palettes = [
    ["#890505", "#b8860b"],
    ["#650303", "#71717a"],
    ["#8f1d1d", "#a3a3a3"],
    ["#7f1d1d", "#84cc52"],
    ["#9f1239", "#b8860b"],
  ];
  const index = Math.abs(hashString(seed)) % palettes.length;
  const [first, second] = palettes[index];
  return {
    "--band-a": first,
    "--band-b": second,
  } as CSSProperties;
}

function hashString(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) | 0;
  }
  return hash;
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

function normalizeSearchText(value: string): string {
  return value
    .trim()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("ro");
}

function mergeCompanies(
  current: CompanyListItem[],
  incoming: CompanyListItem[],
): CompanyListItem[] {
  const map = new Map(current.map((company) => [company.id, company]));
  incoming.forEach((company) => map.set(company.id, company));
  return Array.from(map.values());
}
