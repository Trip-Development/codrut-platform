import { notFound } from "next/navigation";

import { getAllCompanyProjects, getProjectParticipants } from "@/api/companies";
import { displayReportsToName } from "@/api/roster-format";
import { getServerApiRequestOptions } from "@/api/server-request";
import { RosterImporter } from "@/app/trainer/roster/roster-importer";

export default async function ProjectParticipantsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const requestOptions = await getServerApiRequestOptions();
  const projects = await getAllCompanyProjects(requestOptions);
  const project = projects.find((item) => item.id === projectId);

  if (!project) {
    notFound();
  }

  const participants = await getProjectParticipants(project.company_id, project.id, requestOptions);

  return (
    <div className="space-y-5">
      <RosterImporter
        companies={[{ id: project.company_id, name: project.company_name ?? "Companie" }]}
        defaultCompanyId={project.company_id}
        existingParticipants={participants}
        projects={[project]}
        defaultProjectId={project.id}
        requireProject
        lockCompany
      />

      <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
        <div className="border-b border-[var(--border)] px-5 py-4">
          <p className="text-xs font-semibold text-burgundy/75">Roster proiect</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">Participanți în proiect</h2>
          <p className="mt-2 text-sm leading-6 text-foreground/62">
            Datele de manager, rol și locație sunt specifice acestui proiect.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-surface-muted text-xs font-semibold text-foreground/50">
              <tr>
                <th className="px-5 py-3">Nume</th>
                <th className="px-5 py-3">Manager</th>
                <th className="px-5 py-3">Poziție</th>
                <th className="px-5 py-3">Locație</th>
                <th className="px-5 py-3">Email</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {participants.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-6 text-center text-foreground/62">
                    Niciun participant în acest proiect încă.
                  </td>
                </tr>
              ) : (
                participants.map((member) => (
                  <tr key={member.id} className="align-top transition-colors hover:bg-surface-muted/40">
                    <td className="px-5 py-4 font-semibold text-foreground">{member.full_name}</td>
                    <td className="px-5 py-4 text-foreground/62">{displayReportsToName(member.reports_to_name)}</td>
                    <td className="px-5 py-4 text-foreground/62">{member.position ?? "—"}</td>
                    <td className="px-5 py-4 text-foreground/62">{member.location ?? "—"}</td>
                    <td className="px-5 py-4 text-foreground/62">{member.email}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
