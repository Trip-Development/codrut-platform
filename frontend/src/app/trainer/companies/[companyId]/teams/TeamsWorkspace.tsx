"use client";

import { useMemo, useState, type FormEvent } from "react";

import {
  addCompanyTeamMembership,
  createCompanyTeam,
  type CompanyParticipant,
  type CompanyTeam,
  type CompanyTeamMembership,
} from "@/api/companies";

type TeamsWorkspaceProps = {
  companyId: string;
  initialTeams: CompanyTeam[];
  participants: CompanyParticipant[];
  initialMembershipsByTeam: Record<string, CompanyTeamMembership[]>;
};

type TeamMemberEntry = {
  membership: Pick<CompanyTeamMembership, "id" | "role">;
  participant: CompanyParticipant;
};

type DerivedTeam = {
  id: string;
  name: string;
  type: CompanyTeam["type"];
  source: "leadership" | "reports_to";
  members: TeamMemberEntry[];
};

const rootManagerNames = new Set(["", "-", "—", "---", "root", "radacina", "rădăcină", "fara manager", "fără manager"]);

function normalizedName(value: string | null | undefined) {
  return (value ?? "").trim().toLocaleLowerCase("ro-RO");
}

function isRootManagerName(value: string | null | undefined) {
  return rootManagerNames.has(normalizedName(value));
}

export function deriveOrganizationTeams(
  participants: CompanyParticipant[],
  teams: CompanyTeam[],
): DerivedTeam[] {
  const derivedTeams: DerivedTeam[] = [];
  const hasPersistedLeadership = teams.some((team) => team.type === "leadership");
  const participantByName = new Map(
    participants.map((participant) => [normalizedName(participant.full_name), participant]),
  );

  if (!hasPersistedLeadership) {
    const leadershipMembers = participants.filter((participant) => participant.role_group === "leadership");
    if (leadershipMembers.length > 0) {
      derivedTeams.push({
        id: "derived-leadership",
        name: "Leadership",
        type: "leadership",
        source: "leadership",
        members: leadershipMembers.map((participant) => ({
          membership: {
            id: `derived-leadership-${participant.id}`,
            role: "leader",
          },
          participant,
        })),
      });
    }
  }

  const directReportsByManager = new Map<string, CompanyParticipant[]>();
  for (const participant of participants) {
    if (isRootManagerName(participant.reports_to_name)) continue;

    const managerKey = normalizedName(participant.reports_to_name);
    if (!managerKey) continue;

    directReportsByManager.set(managerKey, [
      ...(directReportsByManager.get(managerKey) ?? []),
      participant,
    ]);
  }

  for (const [managerKey, directReports] of directReportsByManager) {
    const manager = participantByName.get(managerKey);
    const managerName = manager?.full_name ?? directReports[0]?.reports_to_name ?? "Manager";
    const members: TeamMemberEntry[] = [
      ...(manager
        ? [
            {
              membership: { id: `derived-manager-${manager.id}`, role: "leader" as const },
              participant: manager,
            },
          ]
        : []),
      ...directReports.map((participant) => ({
        membership: {
          id: `derived-report-${participant.id}`,
          role: "member" as const,
        },
        participant,
      })),
    ];

    derivedTeams.push({
      id: `derived-manager-${managerKey}`,
      name: `Echipa ${managerName}`,
      type: "functional",
      source: "reports_to",
      members,
    });
  }

  return derivedTeams;
}

export function TeamsWorkspace({
  companyId,
  initialTeams,
  participants,
  initialMembershipsByTeam,
}: TeamsWorkspaceProps) {
  const [teams, setTeams] = useState<CompanyTeam[]>(initialTeams);
  const [membershipsByTeam, setMembershipsByTeam] = useState(initialMembershipsByTeam);
  const [teamName, setTeamName] = useState("");
  const [teamType, setTeamType] = useState<CompanyTeam["type"]>("functional");
  const [message, setMessage] = useState<string | null>(null);
  const [isCreatingTeam, setIsCreatingTeam] = useState(false);

  const participantById = useMemo(
    () => new Map(participants.map((participant) => [participant.id, participant])),
    [participants],
  );
  const assignedMemberCount = useMemo(
    () => Object.values(membershipsByTeam).reduce((total, memberships) => total + memberships.length, 0),
    [membershipsByTeam],
  );
  const derivedTeams = useMemo(
    () => deriveOrganizationTeams(participants, teams),
    [participants, teams],
  );

  async function handleCreateTeam(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = teamName.trim();
    if (!name) return;

    setIsCreatingTeam(true);
    setMessage(null);
    try {
      const team = await createCompanyTeam(companyId, { name, type: teamType });
      setTeams((current) => [...current, team].sort((a, b) => a.name.localeCompare(b.name, "ro")));
      setMembershipsByTeam((current) => ({ ...current, [team.id]: [] }));
      setTeamName("");
      setTeamType("functional");
      setMessage(`Echipa "${team.name}" a fost creată.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Echipa nu a putut fi creată.");
    } finally {
      setIsCreatingTeam(false);
    }
  }

  async function handleAddMember(
    teamId: string,
    participantProfileId: string,
    role: CompanyTeamMembership["role"],
  ) {
    if (!participantProfileId) return;

    setMessage(null);
    try {
      const membership = await addCompanyTeamMembership(companyId, teamId, {
        participantProfileId,
        role,
      });
      setMembershipsByTeam((current) => ({
        ...current,
        [teamId]: [...(current[teamId] ?? []), membership],
      }));
      setMessage("Membrul a fost adăugat în echipă.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Membrul nu a putut fi adăugat.");
    }
  }

  return (
    <div className="space-y-5">
      <section className="surface-panel overflow-hidden">
        <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_24rem]">
          <div className="p-5 md:p-6">
            <p className="text-sm font-semibold text-burgundy/75">Structură echipe</p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">Grupează participanții în echipe clare</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
              Creează echipe de leadership sau funcționale, iar structura din manager direct este recunoscută automat din lista de participanți.
            </p>
            <div className="mt-4 grid gap-2 sm:grid-cols-3">
              <TeamSummary label="Echipe" value={teams.length + derivedTeams.length} />
              <TeamSummary label="Membri în echipe" value={assignedMemberCount} />
              <TeamSummary label="Automate" value={derivedTeams.length} />
            </div>
          </div>
          <form onSubmit={handleCreateTeam} className="space-y-3 border-t border-[var(--border)] bg-surface-muted p-5 md:p-6 lg:border-l lg:border-t-0">
            <label className="block text-sm font-semibold text-foreground">
              Nume echipă
              <input
                value={teamName}
                onChange={(event) => setTeamName(event.target.value)}
                placeholder="Ex. Leadership septembrie"
                className="control-input mt-2 min-h-11 w-full py-2.5"
              />
            </label>
            <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
              <select
                value={teamType}
                onChange={(event) => setTeamType(event.target.value as CompanyTeam["type"])}
                aria-label="Tip echipă"
                className="control-input min-h-11 px-3 py-2.5"
              >
                <option value="functional">Funcțională</option>
                <option value="leadership">Leadership</option>
              </select>
              <button
                type="submit"
                disabled={isCreatingTeam || !teamName.trim()}
                className="tap-soft rounded-full bg-burgundy px-4 py-2.5 text-sm font-bold text-white shadow-sm shadow-burgundy/10 hover:bg-burgundy-700 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-45"
              >
                {isCreatingTeam ? "Se salvează..." : "Adaugă"}
              </button>
            </div>
          </form>
        </div>
        {message ? (
          <p aria-live="polite" className="border-t border-[var(--border)] bg-surface-muted px-5 py-3 text-sm font-semibold text-foreground/62">
            {message}
          </p>
        ) : null}
      </section>

      {participants.length === 0 ? (
        <section className="surface-panel border-dashed p-8 text-center">
          <p className="text-base font-semibold text-foreground">Lista de participanți este goală.</p>
          <p className="mt-2 text-sm text-foreground/58">Importă participanții înainte de a construi echipe.</p>
        </section>
      ) : teams.length === 0 && derivedTeams.length === 0 ? (
        <section className="surface-panel border-dashed p-8 text-center">
          <p className="text-base font-semibold text-foreground">Nu există echipe încă.</p>
          <p className="mt-2 text-sm text-foreground/58">Creează prima echipă, apoi adaugă membrii din lista de participanți.</p>
        </section>
      ) : (
        <div className="space-y-5">
          {teams.length > 0 ? (
            <section className="space-y-3">
              <div>
                <h3 className="text-sm font-bold uppercase tracking-[0.12em] text-foreground/48">Echipe salvate</h3>
                <p className="mt-1 text-sm text-foreground/58">Echipe create explicit și folosite pentru asignări.</p>
              </div>
              <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                {teams.map((team) => (
                  <TeamCard
                    key={team.id}
                    team={team}
                    participants={participants}
                    members={(membershipsByTeam[team.id] ?? [])
                      .map((membership) => ({
                        membership,
                        participant: participantById.get(membership.participant_profile_id),
                      }))
                      .filter(
                        (entry): entry is { membership: CompanyTeamMembership; participant: CompanyParticipant } =>
                          Boolean(entry.participant),
                      )}
                    onAddMember={handleAddMember}
                  />
                ))}
              </div>
            </section>
          ) : null}

          {derivedTeams.length > 0 ? (
            <section className="space-y-3">
              <div>
                <h3 className="text-sm font-bold uppercase tracking-[0.12em] text-foreground/48">Structură recunoscută din participanți</h3>
                <p className="mt-1 text-sm text-foreground/58">
                  Carduri generate din leadership și din câmpul Manager direct. Nu modifică echipele salvate.
                </p>
              </div>
              <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                {derivedTeams.map((team) => (
                  <DerivedTeamCard key={team.id} team={team} />
                ))}
              </div>
            </section>
          ) : null}
        </div>
      )}
    </div>
  );
}

function TeamSummary({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-surface px-3 py-2.5">
      <p className="text-xs font-semibold text-foreground/48">{label}</p>
      <p className="mt-1 text-lg font-semibold text-foreground">{value}</p>
    </div>
  );
}

function DerivedTeamCard({ team }: { team: DerivedTeam }) {
  return (
    <article className="flex min-h-[20rem] flex-col rounded-xl border border-dashed border-burgundy/24 bg-surface p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3 border-b border-[var(--border)] pb-3">
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold text-foreground">{team.name}</h2>
          <p className="mt-1 text-xs font-semibold text-foreground/50">
            {team.members.length} membri recunoscuți automat
          </p>
        </div>
        <span className="rounded-full border border-burgundy/20 bg-burgundy/10 px-2.5 py-1 text-xs font-semibold text-burgundy">
          {team.source === "leadership" ? "Leadership" : "Manager direct"}
        </span>
      </div>

      <div className="mt-4 flex-1">
        <div className="max-h-64 divide-y divide-[var(--border)] overflow-y-auto pr-1">
          {team.members.map(({ membership, participant }) => (
            <div key={membership.id} className="flex items-center justify-between gap-3 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-foreground">{participant.full_name}</p>
                <p className="truncate text-xs text-foreground/50">{participant.position ?? "Membru"}</p>
              </div>
              <span className="shrink-0 rounded-full bg-surface-muted px-2 py-0.5 text-[11px] font-semibold text-foreground/50">
                {membership.role === "leader" ? "Lider" : "Membru"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </article>
  );
}

function TeamCard({
  team,
  participants,
  members,
  onAddMember,
}: {
  team: CompanyTeam;
  participants: CompanyParticipant[];
  members: Array<{ membership: CompanyTeamMembership; participant: CompanyParticipant }>;
  onAddMember: (
    teamId: string,
    participantProfileId: string,
    role: CompanyTeamMembership["role"],
  ) => Promise<void>;
}) {
  const availableParticipants = useMemo(() => {
    const memberIds = new Set(members.map((entry) => entry.participant.id));
    return participants.filter((participant) => !memberIds.has(participant.id));
  }, [members, participants]);
  const [selectedParticipantId, setSelectedParticipantId] = useState(availableParticipants[0]?.id ?? "");
  const [selectedRole, setSelectedRole] = useState<CompanyTeamMembership["role"]>("member");
  const [isAdding, setIsAdding] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedParticipantId) return;
    setIsAdding(true);
    try {
      await onAddMember(team.id, selectedParticipantId, selectedRole);
      const nextParticipant = availableParticipants.find(
        (participant) => participant.id !== selectedParticipantId,
      );
      setSelectedParticipantId(nextParticipant?.id ?? "");
      setSelectedRole("member");
    } finally {
      setIsAdding(false);
    }
  }

  return (
    <article className="flex min-h-[28rem] flex-col rounded-xl border border-[var(--border)] bg-surface p-5 shadow-sm transition-colors hover:border-burgundy/25">
      <div className="flex items-start justify-between gap-3 border-b border-[var(--border)] pb-3">
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold text-foreground">{team.name}</h2>
          <p className="mt-1 text-xs font-semibold text-foreground/50">
            {members.length} membri
          </p>
        </div>
        <span className="rounded-full border border-burgundy/20 bg-burgundy/10 px-2.5 py-1 text-xs font-semibold text-burgundy">
          {team.type === "leadership" ? "Leadership" : "Funcțională"}
        </span>
      </div>

      <div className="mt-4 flex-1">
        {members.length === 0 ? (
          <p className="rounded-xl border border-dashed border-[var(--border)] bg-surface-muted px-3 py-4 text-sm leading-6 text-foreground/55">
            Niciun membru adăugat încă.
          </p>
        ) : (
          <div className="max-h-64 divide-y divide-[var(--border)] overflow-y-auto pr-1">
            {members.map(({ membership, participant }) => (
              <div key={membership.id} className="flex items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-foreground">{participant.full_name}</p>
                  <p className="truncate text-xs text-foreground/50">{participant.position ?? "Membru"}</p>
                </div>
                <span className="shrink-0 rounded-full bg-surface-muted px-2 py-0.5 text-[11px] font-semibold text-foreground/50">
                  {membership.role === "leader" ? "Lider" : "Membru"}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="mt-4 space-y-2 border-t border-[var(--border)] pt-4">
        <p className="text-xs font-semibold text-foreground/48">Adaugă membru</p>
        <select
          value={selectedParticipantId}
          onChange={(event) => setSelectedParticipantId(event.target.value)}
          aria-label={`Participant pentru ${team.name}`}
          className="control-input min-h-10 w-full px-3 py-2"
        >
          <option value="">Selectează participant</option>
          {availableParticipants.map((participant) => (
            <option key={participant.id} value={participant.id}>
              {participant.full_name}
            </option>
          ))}
        </select>
        <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
          <select
            value={selectedRole}
            onChange={(event) => setSelectedRole(event.target.value as CompanyTeamMembership["role"])}
            aria-label={`Rol în ${team.name}`}
            className="control-input min-h-10 px-3 py-2"
          >
            <option value="member">Membru</option>
            <option value="leader">Lider</option>
          </select>
          <button
            type="submit"
            disabled={isAdding || !selectedParticipantId}
            className="tap-soft rounded-full border border-[var(--border)] bg-surface px-4 py-2 text-sm font-bold text-foreground hover:border-burgundy/45 hover:bg-surface-muted hover:text-burgundy disabled:cursor-not-allowed disabled:opacity-45"
          >
            {isAdding ? "..." : "Adaugă"}
          </button>
        </div>
      </form>
    </article>
  );
}
