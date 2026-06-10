"use client";

import { useMemo, useState } from "react";

import type { CompanyParticipant } from "@/api/companies";

export type OrgExplorerCompany = {
  id: string;
  name: string;
  participants: CompanyParticipant[];
};

type OrgExplorerProps = {
  companies: OrgExplorerCompany[];
};

export function OrgExplorer({ companies }: OrgExplorerProps) {
  const [companyId, setCompanyId] = useState(companies[0]?.id ?? "");
  const [query, setQuery] = useState("");
  const [zoom, setZoom] = useState(1);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const company = companies.find((item) => item.id === companyId);
  const participants = useMemo(() => company?.participants ?? [], [company?.participants]);
  const roots = useMemo(() => participants.filter((participant) => !participant.reports_to_name), [participants]);

  function toggle(id: string) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[20rem_minmax(0,1fr)]">
      <aside className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
        <div>
          <p className="text-sm font-semibold text-burgundy/75">Explorare rapidă</p>
          <h2 className="mt-1 text-lg font-semibold text-foreground">Organigramă pe companie</h2>
          <p className="mt-2 text-sm leading-6 text-foreground/58">
            Alege clientul, caută persoana și ajustează nivelul de detaliu.
          </p>
        </div>

        <label className="block">
          <span className="mt-5 block text-sm font-semibold text-foreground">Companie</span>
          <select
            value={companyId}
            onChange={(event) => {
              setCompanyId(event.target.value);
              setCollapsed(new Set());
            }}
            className="mt-2 min-h-11 w-full rounded-xl border border-[var(--border)] bg-background px-3 py-2.5 text-sm font-semibold text-foreground outline-none transition-colors focus:border-burgundy/45 focus:ring-2 focus:ring-burgundy/10"
          >
            {companies.length === 0 ? <option value="">Nicio companie</option> : null}
            {companies.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>

        <label className="mt-4 block">
          <span className="text-sm font-semibold text-foreground">Caută</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="nume, email, poziție"
            className="mt-2 min-h-11 w-full rounded-xl border border-[var(--border)] bg-background px-3 py-2.5 text-sm font-semibold text-foreground outline-none transition-colors placeholder:text-foreground/34 focus:border-burgundy/45 focus:ring-2 focus:ring-burgundy/10"
          />
        </label>

        <div className="mt-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-foreground">Zoom</p>
            <p className="text-xs font-semibold text-foreground/50">{Math.round(zoom * 100)}%</p>
          </div>
          <input
            type="range"
            min="0.75"
            max="1.25"
            step="0.05"
            value={zoom}
            onChange={(event) => setZoom(Number(event.target.value))}
            className="mt-3 w-full accent-[var(--burgundy)]"
          />
        </div>

        <div className="mt-5 grid grid-cols-2 gap-2">
          <OrgStat label="Persoane" value={participants.length} />
          <OrgStat label="Rădăcini" value={roots.length} />
        </div>
      </aside>

      <section className="min-h-[32rem] overflow-auto rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
        {participants.length === 0 ? (
          <div className="flex min-h-64 items-center justify-center rounded-xl border border-dashed border-[var(--border)] bg-background/70 p-6 text-center">
            <div>
              <p className="text-base font-semibold text-foreground">Nu există roster importat.</p>
              <p className="mt-2 text-sm text-foreground/58">Importă participanții ca să vezi organigrama.</p>
            </div>
          </div>
        ) : (
          <div className="min-w-[44rem] origin-top-left transition-transform" style={{ transform: `scale(${zoom})` }}>
            <div className="space-y-4">
              {roots.map((member) => (
                <OrgNode
                  key={member.id}
                  member={member}
                  members={participants}
                  query={query}
                  collapsed={collapsed}
                  onToggle={toggle}
                  depth={0}
                />
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function OrgStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-background/80 px-3 py-2.5">
      <p className="text-xs font-semibold text-foreground/48">{label}</p>
      <p className="mt-1 text-base font-semibold text-foreground">{value}</p>
    </div>
  );
}

function OrgNode({
  member,
  members,
  query,
  collapsed,
  onToggle,
  depth,
}: {
  member: CompanyParticipant;
  members: CompanyParticipant[];
  query: string;
  collapsed: Set<string>;
  onToggle: (id: string) => void;
  depth: number;
}) {
  const reports = members.filter((candidate) => candidate.reports_to_name === member.full_name);
  const isCollapsed = collapsed.has(member.id);
  const matches = queryMatches(member, query);
  const childMatches = reports.some((report) => branchMatches(report, members, query));
  const hiddenBySearch = query.trim() && !matches && !childMatches;

  if (hiddenBySearch) return null;

  return (
    <div className={depth > 0 ? "ml-7 border-l border-[var(--border)] pl-5" : ""}>
      <article
        className={[
          "rounded-xl border px-4 py-3 shadow-sm transition-all hover:border-burgundy/20 hover:shadow-md",
          matches && query.trim()
            ? "border-burgundy bg-burgundy-50 dark:bg-burgundy/10"
            : "border-[var(--border)] bg-background",
        ].join(" ")}
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-foreground">{member.full_name}</h2>
            <p className="mt-1 text-xs font-semibold text-burgundy">{member.position ?? "Fără poziție"}</p>
            <p className="mt-2 text-xs leading-5 text-foreground/55">
              {member.location ?? "Fără locație"} · {member.email}
              {member.pcm_profile ? ` · PCM ${member.pcm_profile}` : ""}
            </p>
          </div>
          <button
            type="button"
            disabled={reports.length === 0}
            onClick={() => onToggle(member.id)}
            className="tap-soft rounded-full border border-[var(--border)] bg-surface px-3 py-1.5 text-xs font-bold text-foreground/65 hover:border-burgundy/40 hover:text-burgundy disabled:opacity-45"
          >
            {reports.length === 0 ? "0" : isCollapsed ? `+${reports.length}` : `-${reports.length}`}
          </button>
        </div>
      </article>

      {!isCollapsed && reports.length > 0 ? (
        <div className="mt-3 space-y-3">
          {reports.map((report) => (
            <OrgNode
              key={report.id}
              member={report}
              members={members}
              query={query}
              collapsed={collapsed}
              onToggle={onToggle}
              depth={depth + 1}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function branchMatches(member: CompanyParticipant, members: CompanyParticipant[], query: string): boolean {
  if (queryMatches(member, query)) return true;
  return members
    .filter((candidate) => candidate.reports_to_name === member.full_name)
    .some((child) => branchMatches(child, members, query));
}

function queryMatches(member: CompanyParticipant, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return false;
  return [member.full_name, member.email, member.position, member.location, member.role_group]
    .filter(Boolean)
    .some((value) => value!.toLowerCase().includes(normalized));
}
