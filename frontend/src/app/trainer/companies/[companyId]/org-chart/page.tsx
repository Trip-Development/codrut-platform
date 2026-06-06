import { getCompanyParticipants, type CompanyParticipant } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";

export default async function CompanyOrgChartPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  const participants = await getCompanyParticipants(companyId, await getServerApiRequestOptions());
  const rootMembers = participants.filter((p) => !p.reports_to_name);

  return (
    <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Org chart</p>

      {participants.length === 0 ? (
        <p className="mt-4 text-sm text-foreground/62">Niciun participant importat inca.</p>
      ) : (
        <div className="mt-5 space-y-4">
          {rootMembers.map((member) => (
            <OrgNode key={member.id} member={member} members={participants} depth={0} />
          ))}
        </div>
      )}
    </section>
  );
}

function OrgNode({
  member,
  members,
  depth,
}: {
  member: CompanyParticipant;
  members: CompanyParticipant[];
  depth: number;
}) {
  const reports = members.filter((c) => c.reports_to_name === member.full_name);

  return (
    <div className={depth > 0 ? "ml-5 border-l border-[var(--border)] pl-4" : ""}>
      <article className="rounded-xl border border-[var(--border)] bg-background px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-foreground">{member.full_name}</h2>
            <p className="mt-1 text-xs font-semibold text-burgundy">{member.position ?? "—"}</p>
          </div>
          {member.role_group ? (
            <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-foreground/55">
              {member.role_group}
            </span>
          ) : null}
        </div>
        <p className="mt-2 text-xs leading-5 text-foreground/55">
          {member.location ?? "—"} · {member.email}
          {member.pcm_profile ? ` · PCM ${member.pcm_profile}` : ""}
        </p>
      </article>
      {reports.length > 0 ? (
        <div className="mt-3 space-y-3">
          {reports.map((report) => (
            <OrgNode key={report.id} member={report} members={members} depth={depth + 1} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
