import { getCompanyAssignments, getCompanyParticipants } from "@/api/companies";
import { getScoringResult } from "@/api/trainer";
import { getServerApiRequestOptions } from "@/api/server-request";
import Link from "next/link";

const lencioniLabels: Record<string, string> = {
  absence_of_trust: "Absența încrederii (Trust)",
  fear_of_conflict: "Teama de conflict (Conflict)",
  lack_of_commitment: "Lipsa angajamentului (Commitment)",
  avoidance_of_accountability: "Evitarea responsabilității (Accountability)",
  inattention_to_results: "Neatenția la rezultate (Results)",
};

const driverLabels: Record<string, string> = {
  be_strong: "Fii Puternic (Be Strong)",
  be_perfect: "Fii Perfect (Be Perfect)",
  try_hard: "Străduiește-te (Try Hard)",
  hurry_up: "Grăbește-te (Hurry Up)",
  please_people: "Mulțumește-i pe alții (Please People)",
};

export default async function CompanyReportsPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  const requestOptions = await getServerApiRequestOptions();
  const [assignments, participants] = await Promise.all([
    getCompanyAssignments(companyId, requestOptions),
    getCompanyParticipants(companyId, requestOptions),
  ]);

  const participantMap = new Map(participants.map((p) => [p.id, p]));

  const reportableAssignments = assignments
    .filter((a) => a.status === "submitted" || a.status === "validated" || a.status === "scored")
    .sort((a, b) => (b.submitted_at ?? "").localeCompare(a.submitted_at ?? ""));

  // Fetch scoring results for all reportable assignments in parallel
  const resultsList = await Promise.all(
    reportableAssignments.map(async (a) => {
      try {
        const res = await getScoringResult(a.id, requestOptions);
        return { assignmentId: a.id, result: res };
      } catch {
        return { assignmentId: a.id, result: null };
      }
    })
  );

  const resultMap = new Map(resultsList.map((item) => [item.assignmentId, item.result]));

  // 1. Calculate Lencioni Aggregates
  const lencioniSums = {
    absence_of_trust: 0,
    fear_of_conflict: 0,
    lack_of_commitment: 0,
    avoidance_of_accountability: 0,
    inattention_to_results: 0,
  };
  let lencioniCount = 0;

  // 2. Calculate Distress Drivers Aggregates
  const driverSums = {
    be_strong: 0,
    be_perfect: 0,
    try_hard: 0,
    hurry_up: 0,
    please_people: 0,
  };
  let driverCount = 0;

  reportableAssignments.forEach((a) => {
    const res = resultMap.get(a.id);
    if (!res || !res.scores) return;

    if (a.questionnaire_key === "lencioni") {
      lencioniCount++;
      Object.keys(lencioniSums).forEach((key) => {
        const valObj = res.scores[key];
        const val = typeof valObj === "object" && valObj !== null ? (valObj as { score?: unknown }).score : valObj;
        lencioniSums[key as keyof typeof lencioniSums] += Number(val || 0);
      });
    } else if (a.questionnaire_key === "distress_drivers") {
      driverCount++;
      Object.keys(driverSums).forEach((key) => {
        const val = res.scores[key];
        driverSums[key as keyof typeof driverSums] += Number(val || 0);
      });
    }
  });

  const lencioniAverages = Object.entries(lencioniSums).map(([key, sum]) => {
    const avg = lencioniCount > 0 ? sum / lencioniCount : 0;
    return {
      id: key,
      label: lencioniLabels[key] || key,
      avg: Number(avg.toFixed(1)),
    };
  });

  const driverAverages = Object.entries(driverSums).map(([key, sum]) => {
    const avg = driverCount > 0 ? sum / driverCount : 0;
    return {
      id: key,
      label: driverLabels[key] || key,
      avg: Number(avg.toFixed(1)),
    };
  });

  const totalAssigned = assignments.length;
  const totalCompleted = reportableAssignments.length;
  const completionRate = totalAssigned > 0 ? Math.round((totalCompleted / totalAssigned) * 100) : 0;

  return (
    <div className="space-y-6">
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
      <div className="grid gap-5 lg:grid-cols-2">
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
                Niciun răspuns Lencioni completat pentru această companie.
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
                Niciun răspuns Distress Drivers completat pentru această companie.
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
                <th className="px-5 py-3">Chestionar</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Rezultat Principal</th>
                <th className="px-5 py-3">Dată Finalizare</th>
                <th className="px-5 py-3 text-right">Acțiuni</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {reportableAssignments.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-center text-foreground/62">
                    Niciun raport individual disponibil momentan pentru această companie.
                  </td>
                </tr>
              ) : (
                reportableAssignments.map((a) => {
                  const participant = participantMap.get(a.respondent_profile_id);
                  const res = resultMap.get(a.id);
                  const formattedResult = res?.primary_result ? res.primary_result.replaceAll("_", " ") : "În așteptare";

                  return (
                    <tr key={a.id} className="align-middle hover:bg-surface-muted/20 transition-colors">
                      <td className="px-5 py-4">
                        <p className="font-bold text-foreground">{participant?.full_name ?? "Necunoscut"}</p>
                        <p className="text-xs text-foreground/50">{participant?.email ?? ""}</p>
                      </td>
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
