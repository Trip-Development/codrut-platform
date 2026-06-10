"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { deleteCompany } from "@/api/companies";

type CompanySettingsWorkspaceProps = {
  company: {
    id: string;
    name: string;
    stats: {
      totalParticipants: number;
      totalAssignments: number;
      completedAssignments: number;
      completionRate: number;
    };
  };
};

export function CompanySettingsWorkspace({ company }: CompanySettingsWorkspaceProps) {
  const router = useRouter();
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const canDelete = confirmation.trim() === company.name;

  async function handleDelete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canDelete) return;

    setIsDeleting(true);
    setMessage(null);
    try {
      await deleteCompany(company.id);
      router.push("/trainer/companies");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Compania nu a putut fi ștearsă.");
      setIsDeleting(false);
    }
  }

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm md:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-[var(--border)] bg-background text-xl font-semibold text-burgundy shadow-sm">
              {company.name.trim().charAt(0).toLocaleUpperCase("ro")}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-burgundy/75">Identitate companie</p>
              <h2 className="mt-1 text-2xl font-semibold text-foreground">{company.name}</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
                Setările țin identitatea, sumarul operațional și acțiunile administrative ale companiei într-un singur loc.
              </p>
            </div>
          </div>
          <div className="rounded-xl bg-surface-muted px-3 py-2 text-sm font-semibold text-foreground/62">
            {company.stats.totalParticipants} în roster
          </div>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <SettingStat label="Roster" value={company.stats.totalParticipants} />
          <SettingStat label="Asignări" value={company.stats.totalAssignments} />
          <SettingStat label="Completate" value={company.stats.completedAssignments} />
          <SettingStat label="Rată completare" value={`${company.stats.completionRate}%`} />
        </div>
      </section>

      <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm md:p-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm font-semibold text-foreground/52">Administrare</p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">Acțiuni asupra companiei</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
              Acțiunile sensibile sunt separate de fluxul zilnic de roster, organigramă și rapoarte.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setIsDeleteOpen((current) => !current)}
            className="tap-soft inline-flex min-h-10 items-center justify-center rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm font-semibold text-red-800 hover:bg-red-100"
          >
            {isDeleteOpen ? "Închide ștergerea" : "Configurează ștergerea"}
          </button>
        </div>

        {isDeleteOpen ? (
          <div className="mt-5 rounded-xl border border-red-200 bg-red-50/70 p-4">
            <p className="text-sm font-semibold text-red-950">Șterge compania</p>
            <p className="mt-2 text-sm leading-6 text-red-900/72">
              Ștergerea elimină compania împreună cu rosterul, organigrama, echipele, invitațiile și asignările legate de ea.
            </p>

            <form onSubmit={handleDelete} className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_14rem] md:items-end">
              <label className="block text-sm font-semibold text-red-950">
                Scrie numele companiei pentru confirmare
                <input
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                  placeholder={company.name}
                  className="mt-2 min-h-11 w-full rounded-xl border border-red-200 bg-white px-4 py-2.5 text-sm font-semibold text-red-950 outline-none transition-colors placeholder:text-red-900/35 focus:border-red-400 focus:ring-2 focus:ring-red-200/70"
                />
              </label>
              <button
                type="submit"
                disabled={!canDelete || isDeleting}
                className={[
                  "tap-soft inline-flex min-h-11 items-center justify-center rounded-xl px-5 py-2.5 text-sm font-bold shadow-sm disabled:cursor-not-allowed",
                  canDelete
                    ? "bg-red-700 text-white hover:bg-red-800"
                    : "border border-red-200 bg-white text-red-900/35",
                ].join(" ")}
              >
                {isDeleting ? "Se șterge..." : "Șterge compania"}
              </button>
            </form>
          </div>
        ) : null}

        {message ? (
          <p aria-live="polite" className="mt-3 rounded-xl border border-red-200 bg-white px-3 py-2 text-sm font-semibold text-red-800">
            {message}
          </p>
        ) : null}
      </section>
    </div>
  );
}

function SettingStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-background/80 px-3 py-3">
      <p className="text-xs font-semibold text-foreground/48">{label}</p>
      <p className="mt-1 text-lg font-semibold text-foreground">{value}</p>
    </div>
  );
}
