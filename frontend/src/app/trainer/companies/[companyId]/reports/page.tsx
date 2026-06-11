import {
  getCompanyAssignments,
  getCompanyParticipants,
  getCompanyProjects,
  getCompanyReportAggregate,
} from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import Link from "next/link";
import type { ReactNode } from "react";

export default async function CompanyReportsPage({
  params,
  searchParams,
}: {
  params: Promise<{ companyId: string }>;
  searchParams: Promise<{ projectId?: string }>;
}) {
  const { companyId } = await params;
  const { projectId } = await searchParams;
  const requestOptions = await getServerApiRequestOptions();
  const projects = await getCompanyProjects(companyId, requestOptions);
  const selectedProjectId = projects.some((project) => project.id === projectId)
    ? projectId ?? null
    : null;
  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;
  const scope = { projectId: selectedProjectId };
  const [assignments, participants, aggregate] = await Promise.all([
    getCompanyAssignments(companyId, requestOptions, scope),
    getCompanyParticipants(companyId, requestOptions),
    getCompanyReportAggregate(companyId, requestOptions, scope),
  ]);

  const participantMap = new Map(participants.map((p) => [p.id, p]));
  const projectMap = new Map(projects.map((project) => [project.id, project]));
  const resultMap = new Map(aggregate.results.map((result) => [result.assignment_id, result]));
  const sortedReportableAssignments = assignments
    .filter((assignment) => resultMap.has(assignment.id))
    .sort((first, second) => (second.submitted_at ?? "").localeCompare(first.submitted_at ?? ""));
  const lencioniCount = aggregate.lencioni_count;
  const driverCount = aggregate.driver_count;
  const boss360Count = aggregate.boss_360_count;
  const lencioniAverages = aggregate.lencioni_averages;
  const driverAverages = aggregate.driver_averages;
  const boss360Averages = aggregate.boss_360_averages;
  const totalAssigned = aggregate.total_assigned;
  const totalCompleted = aggregate.total_completed;
  const completionRate = aggregate.completion_rate;

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-semibold text-burgundy/75">Filtru proiect</p>
            <h2 className="mt-1 text-lg font-semibold text-foreground">
              {selectedProject ? selectedProject.name : "Toată compania"}
            </h2>
            <p className="mt-1 text-sm text-foreground/58">
              {selectedProject
                ? "Rapoartele și agregările sunt calculate doar pentru acest proiect."
                : "Rapoartele includ toate proiectele și asignările istorice fără proiect."}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <ProjectFilterLink
              href={`/trainer/companies/${companyId}/reports`}
              active={!selectedProjectId}
            >
              Toată compania
            </ProjectFilterLink>
            {projects.map((project) => (
              <ProjectFilterLink
                key={project.id}
                href={`/trainer/companies/${companyId}/reports?projectId=${project.id}`}
                active={selectedProjectId === project.id}
              >
                {project.name}
              </ProjectFilterLink>
            ))}
          </div>
        </div>
      </section>

      {/* Overview Statistics Banner */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
          <p className="text-xs font-semibold text-foreground/50 uppercase tracking-wider">Rata de Completare</p>
          <p className="mt-2 text-3xl font-bold text-burgundy">{completionRate}%</p>
          <div className="mt-2 h-1.5 w-full rounded-full bg-surface-muted overflow-hidden">
            <div className="h-full bg-burgundy transition-all" style={{ width: `${completionRate}%` }} />
          </div>
        </div>
        <div className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
          <p className="text-xs font-semibold text-foreground/50 uppercase tracking-wider">Chestionare Trimise</p>
          <p className="mt-2 text-3xl font-bold text-foreground">{totalAssigned}</p>
          <p className="mt-1 text-xs text-foreground/50">Total asignări înregistrate</p>
        </div>
        <div className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
          <p className="text-xs font-semibold text-foreground/50 uppercase tracking-wider">Răspunsuri Primite</p>
          <p className="mt-2 text-3xl font-bold text-emerald-600">{totalCompleted}</p>
          <p className="mt-1 text-xs text-foreground/50">Gata de analiză și scorare</p>
        </div>
        <div className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
          <p className="text-xs font-semibold text-foreground/50 uppercase tracking-wider">În curs de completare</p>
          <p className="mt-2 text-3xl font-bold text-amber-500">{totalAssigned - totalCompleted}</p>
          <p className="mt-1 text-xs text-foreground/50">Asignate dar netransmise</p>
        </div>
      </section>

      {/* Aggregated Visualizations Panel */}
      <div className="grid gap-5 xl:grid-cols-3">
        {/* Lencioni Team Health Aggregation */}
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center border-b border-[var(--border)] pb-3">
              <div>
                <h3 className="font-bold text-foreground">Sănătatea Echipei (Lencioni)</h3>
                <p className="text-xs text-foreground/50 mt-0.5">Scorul mediu pe disfuncționalități (maxim 9.0 puncte)</p>
              </div>
              <span className="rounded-full bg-burgundy/10 px-2.5 py-1 text-xs font-bold text-burgundy border border-burgundy/20">
                {lencioniCount} respondent(i)
              </span>
            </div>
            {lencioniCount === 0 ? (
              <div className="py-12 text-center text-foreground/50 text-sm">
                Niciun răspuns Lencioni completat {selectedProject ? "pentru acest proiect." : "pentru această companie."}
              </div>
            ) : lencioniCount < 3 ? (
              <div className="py-12 text-center text-foreground/50 text-sm italic">
                Rezultatele agregate vor fi afișate după ce minim 3 participanți completează chestionarul (în prezent: {lencioniCount}).
              </div>
            ) : (
              <div className="mt-5 space-y-4">
                {lencioniAverages.map((item) => {
                  let barColor = "bg-red-500";
                  let riskLabel = "Problemă critică";
                  if (item.avg >= 8.0) {
                    barColor = "bg-emerald-500";
                    riskLabel = "Zonă sigură";
                  } else if (item.avg >= 6.0) {
                    barColor = "bg-amber-500";
                    riskLabel = "Risc mediu";
                  }
                  return (
                    <div key={item.id} className="space-y-1.5">
                      <div className="flex justify-between text-xs font-semibold">
                        <span className="text-foreground">{item.label}</span>
                        <span className="text-foreground/70">{item.avg} / 9.0 ({riskLabel})</span>
                      </div>
                      <div className="h-2.5 w-full rounded-full bg-surface-muted overflow-hidden">
                        <div className={`h-full ${barColor} transition-all`} style={{ width: `${(item.avg / 9.0) * 100}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          <div className="mt-5 border-t border-[var(--border)] pt-3 text-[11px] text-foreground/50">
            * Scoruri de 8-9: disfuncție redusă. Scoruri sub 6: necesită atenție și intervenție imediată.
          </div>
        </section>

        {/* 360 iCARE Feedback Aggregation */}
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center border-b border-[var(--border)] pb-3">
              <div>
                <h3 className="font-bold text-foreground">Feedback 360 iCARE</h3>
                <p className="text-xs text-foreground/50 mt-0.5">Media pe dimensiuni iCARE (scală 25-100%)</p>
              </div>
              <span className="rounded-full bg-burgundy/10 px-2.5 py-1 text-xs font-bold text-burgundy border border-burgundy/20">
                {boss360Count} respondent(i)
              </span>
            </div>
            {boss360Count === 0 ? (
              <div className="py-12 text-center text-foreground/50 text-sm">
                Niciun răspuns 360 completat {selectedProject ? "pentru acest proiect." : "pentru această companie."}
              </div>
            ) : boss360Count < 3 ? (
              <div className="py-12 text-center text-foreground/50 text-sm italic">
                Rezultatele agregate vor fi afișate după ce minim 3 respondenți completează feedback-ul 360 (în prezent: {boss360Count}).
              </div>
            ) : (
              <div className="mt-5 space-y-4">
                {boss360Averages.map((item) => (
                  <div key={item.id} className="space-y-1.5">
                    <div className="flex justify-between text-xs font-semibold">
                      <span className="text-foreground">{item.label}</span>
                      <span className="text-foreground/70">{item.avg}%</span>
                    </div>
                    <div className="h-2.5 w-full rounded-full bg-surface-muted overflow-hidden">
                      <div className="h-full bg-emerald-600 transition-all" style={{ width: `${item.avg}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="mt-5 border-t border-[var(--border)] pt-3 text-[11px] text-foreground/50">
            * Scala iCARE activă mapează Rar/Uneori/Frecvent/Întotdeauna la 25/50/75/100%.
          </div>
        </section>

        {/* Distress Drivers Profile Aggregation */}
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center border-b border-[var(--border)] pb-3">
              <div>
                <h3 className="font-bold text-foreground">Driveri de Stres (Distress Drivers)</h3>
                <p className="text-xs text-foreground/50 mt-0.5">Intensitatea medie a driverilor TA (procentaj 0-100%)</p>
              </div>
              <span className="rounded-full bg-burgundy/10 px-2.5 py-1 text-xs font-bold text-burgundy border border-burgundy/20">
                {driverCount} respondent(i)
              </span>
            </div>
            {driverCount === 0 ? (
              <div className="py-12 text-center text-foreground/50 text-sm">
                Niciun răspuns Distress Drivers completat {selectedProject ? "pentru acest proiect." : "pentru această companie."}
              </div>
            ) : driverCount < 3 ? (
              <div className="py-12 text-center text-foreground/50 text-sm italic">
                Rezultatele agregate vor fi afișate după ce minim 3 participanți completează chestionarul (în prezent: {driverCount}).
              </div>
            ) : (
              <div className="mt-5 space-y-4">
                {driverAverages.map((item) => (
                  <div key={item.id} className="space-y-1.5">
                    <div className="flex justify-between text-xs font-semibold">
                      <span className="text-foreground">{item.label}</span>
                      <span className="text-foreground/70">{item.avg}%</span>
                    </div>
                    <div className="h-2.5 w-full rounded-full bg-surface-muted overflow-hidden">
                      <div className="h-full bg-burgundy transition-all" style={{ width: `${item.avg}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="mt-5 border-t border-[var(--border)] pt-3 text-[11px] text-foreground/50">
            * Procentajele mari indică driveri dominanți sub stres, utili în adaptarea stilului de comunicare.
          </div>
        </section>
      </div>

      {/* Confidentiality Warning Alert */}
      <section className="rounded-2xl border border-amber-200 bg-amber-50/50 p-4 text-xs font-semibold text-amber-800 flex gap-3 items-start">
        <svg className="w-5 h-5 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m0-6h.01M12 4v16m8-8H4" />
        </svg>
        <div>
          <p className="font-bold uppercase tracking-wider mb-1">Regulă de Confidențialitate (360/Feedback)</p>
          <p className="leading-relaxed text-amber-700">
            Datele detaliate sunt vizibile exclusiv pentru trainer. Participanții nu pot vedea identitățile celor care au trimis evaluări 360 confidențiale;
            asigurați-vă că nu expuneți direct ecranele cu rapoarte nominale în fața grupului evaluat.
          </p>
        </div>
      </section>

      {/* Individual Completed Assignments Table */}
      <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
        <div className="border-b border-[var(--border)] px-5 py-4 bg-surface-muted/30">
          <h2 className="text-lg font-semibold text-foreground">Rapoarte Individuale</h2>
          <p className="text-xs text-foreground/50 mt-1">
            Lista completă a chestionarelor finalizate și accesul la rapoartele detaliate.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-surface-muted text-xs font-semibold uppercase tracking-[0.1em] text-foreground/50 border-b border-[var(--border)]">
              <tr>
                <th className="px-5 py-3">Participant</th>
                {!selectedProject ? <th className="px-5 py-3">Proiect</th> : null}
                <th className="px-5 py-3">Chestionar</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Rezultat Principal</th>
                <th className="px-5 py-3">Dată Finalizare</th>
                <th className="px-5 py-3 text-right">Acțiuni</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {sortedReportableAssignments.length === 0 ? (
                <tr>
                  <td colSpan={selectedProject ? 6 : 7} className="px-5 py-8 text-center text-foreground/62">
                    Niciun raport individual disponibil momentan {selectedProject ? "pentru acest proiect." : "pentru această companie."}
                  </td>
                </tr>
              ) : (
                sortedReportableAssignments.map((a) => {
                  const participant = participantMap.get(a.respondent_profile_id);
                  const res = resultMap.get(a.id);
                  const formattedResult = res?.primary_result ? res.primary_result.replaceAll("_", " ") : "În așteptare";

                  return (
                    <tr key={a.id} className="align-middle hover:bg-surface-muted/20 transition-colors">
                      <td className="px-5 py-4">
                        <p className="font-bold text-foreground">{participant?.full_name ?? "Necunoscut"}</p>
                        <p className="text-xs text-foreground/50">{participant?.email ?? ""}</p>
                      </td>
                      {!selectedProject ? (
                        <td className="px-5 py-4 text-xs font-semibold text-foreground/58">
                          {a.project_id ? projectMap.get(a.project_id)?.name ?? "Proiect necunoscut" : "Fără proiect"}
                        </td>
                      ) : null}
                      <td className="px-5 py-4">
                        <span className="rounded-full bg-burgundy/10 px-2.5 py-1 text-xs font-bold text-burgundy capitalize border border-burgundy/20">
                          {a.questionnaire_key.replaceAll("_", " ")}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-700 border border-emerald-200">
                          {a.status}
                        </span>
                      </td>
                      <td className="px-5 py-4 font-semibold text-foreground/70 capitalize">
                        {formattedResult}
                      </td>
                      <td className="px-5 py-4 text-foreground/62 font-semibold">
                        {a.submitted_at ? new Date(a.submitted_at).toLocaleDateString("ro-RO") : "—"}
                      </td>
                      <td className="px-5 py-4 text-right">
                        <Link
                          href={`/trainer/reports/${a.id}`}
                          className="tap-soft inline-flex rounded-xl bg-burgundy px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-burgundy-700 transition-colors"
                        >
                          Vezi Raport
                        </Link>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function ProjectFilterLink({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={[
        "tap-soft rounded-xl border px-3 py-2 text-xs font-bold transition-colors",
        active
          ? "border-burgundy bg-burgundy text-white"
          : "border-[var(--border)] bg-background text-foreground/65 hover:border-burgundy/45 hover:text-burgundy",
      ].join(" ")}
    >
      {children}
    </Link>
  );
}
