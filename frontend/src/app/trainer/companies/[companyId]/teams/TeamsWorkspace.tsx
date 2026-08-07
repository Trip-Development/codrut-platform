"use client";

import { useId, useMemo, useRef, useState, type FormEvent } from "react";
import { Loader2Icon, PlusIcon, Trash2Icon } from "lucide-react";

import {
  addCompanyTeamMembership,
  createCompanyTeam,
  removeCompanyTeamMembership,
  type CompanyParticipant,
  type CompanyTeam,
  type CompanyTeamMembership,
} from "@/api/companies";
import { managerReferenceKey, normalizeReportsToName } from "@/api/roster-format";
import { IdentityMark } from "@/components/presentation/identity-mark";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { SelectControl } from "@/components/ui/select-control";

export type TeamsWorkspaceProps = {
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

export function deriveOrganizationTeams(
  participants: CompanyParticipant[],
  teams: CompanyTeam[],
): DerivedTeam[] {
  const derivedTeams: DerivedTeam[] = [];
  const hasPersistedLeadership = teams.some((team) => team.type === "leadership");
  const participantByName = new Map(
    participants.map((participant) => [managerReferenceKey(participant.full_name), participant]),
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
    const managerName = normalizeReportsToName(participant.reports_to_name);
    const managerKey = managerReferenceKey(managerName);
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
  const [messageTone, setMessageTone] = useState<"neutral" | "danger">("neutral");
  const [isCreatingTeam, setIsCreatingTeam] = useState(false);
  const creatingTeamRef = useRef(false);
  const teamNameInputId = useId();
  const teamTypeSelectId = useId();

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
  const derivedMemberCount = useMemo(
    () => derivedTeams.reduce((total, team) => total + team.members.length, 0),
    [derivedTeams],
  );

  async function handleCreateTeam(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (creatingTeamRef.current) return;

    const name = teamName.trim();
    if (!name) return;

    creatingTeamRef.current = true;
    setIsCreatingTeam(true);
    setMessage(null);
    try {
      const team = await createCompanyTeam(companyId, { name, type: teamType });
      setTeams((current) => [...current, team].sort((a, b) => a.name.localeCompare(b.name, "ro")));
      setMembershipsByTeam((current) => ({ ...current, [team.id]: [] }));
      setTeamName("");
      setTeamType("functional");
      setMessage(`Echipa "${team.name}" a fost creată.`);
      setMessageTone("neutral");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Echipa nu a putut fi creată.");
      setMessageTone("danger");
    } finally {
      creatingTeamRef.current = false;
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
      setMessageTone("neutral");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Membrul nu a putut fi adăugat.");
      setMessageTone("danger");
    }
  }

  async function handleRemoveMember(
    teamId: string,
    membershipId: string,
  ) {
    setMessage(null);
    try {
      await removeCompanyTeamMembership(companyId, teamId, membershipId);
      setMembershipsByTeam((current) => ({
        ...current,
        [teamId]: (current[teamId] ?? []).filter(
          (membership) => membership.id !== membershipId,
        ),
      }));
      setMessage("Membrul a fost eliminat din echipă.");
      setMessageTone("neutral");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Membrul nu a putut fi eliminat.");
      setMessageTone("danger");
    }
  }

  return (
    <div className="flex flex-col gap-7">
      <section className="grid gap-6 border-b border-border pb-6 lg:grid-cols-[minmax(0,1fr)_34rem] lg:items-end">
        <div className="min-w-0">
          <h2 className="text-2xl font-semibold text-foreground">Echipe</h2>
          <dl className="mt-5 flex flex-wrap gap-x-8 gap-y-3">
            <TeamSummary label="Salvate" value={teams.length} />
            <TeamSummary label="Membri salvați" value={assignedMemberCount} />
            <TeamSummary label="Automate" value={derivedTeams.length} detail={`${derivedMemberCount} membri`} />
          </dl>
        </div>

        <form onSubmit={handleCreateTeam} aria-busy={isCreatingTeam}>
          <h3 className="text-sm font-semibold text-foreground">Echipă nouă</h3>
          <FieldGroup className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,1fr)_10rem_auto] sm:items-end">
            <Field data-disabled={isCreatingTeam ? true : undefined}>
              <FieldLabel htmlFor={teamNameInputId}>Nume echipă</FieldLabel>
              <Input
                id={teamNameInputId}
                value={teamName}
                onChange={(event) => setTeamName(event.target.value)}
                placeholder="Ex. Leadership septembrie"
                disabled={isCreatingTeam}
              />
            </Field>
            <Field data-disabled={isCreatingTeam ? true : undefined}>
              <FieldLabel htmlFor={teamTypeSelectId}>Tip echipă</FieldLabel>
              <SelectControl
                id={teamTypeSelectId}
                label="Tip echipă"
                value={teamType}
                onChange={(event) => setTeamType(event.target.value as CompanyTeam["type"])}
                disabled={isCreatingTeam}
              >
                <option value="functional">Funcțională</option>
                <option value="leadership">Leadership</option>
              </SelectControl>
            </Field>
            <Button
              type="submit"
              disabled={isCreatingTeam || !teamName.trim()}
              className="h-11 gap-2"
            >
              {isCreatingTeam ? (
                <Loader2Icon data-icon="inline-start" aria-hidden="true" className="animate-spin" />
              ) : (
                <PlusIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
              )}
              {isCreatingTeam ? "Creăm echipa" : "Adaugă"}
            </Button>
          </FieldGroup>
          <div className="mt-3">
            {isCreatingTeam ? (
              <OperationFeedback
                title="Creăm echipa"
                detail="Salvăm echipa."
              />
            ) : null}
          </div>
        </form>
      </section>

      {message ? (
        <InlineFeedback tone={messageTone}>{message}</InlineFeedback>
      ) : null}

      {participants.length === 0 ? (
        <EmptyState
          title="Lista de participanți este goală."
          description="Importă participanții înainte de a construi echipe."
        />
      ) : teams.length === 0 && derivedTeams.length === 0 ? (
        <EmptyState
          title="Nu există echipe încă."
          description="Creează prima echipă, apoi adaugă membrii din lista de participanți."
        />
      ) : (
        <div className="flex flex-col gap-7">
          {teams.length > 0 ? (
            <section className="flex flex-col gap-4">
              <SectionHeading
                title="Echipe salvate"
                detail={`${teams.length} ${teams.length === 1 ? "echipă" : "echipe"}`}
              />
              <div className="grid gap-4 xl:grid-cols-2">
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
                    onRemoveMember={handleRemoveMember}
                  />
                ))}
              </div>
            </section>
          ) : null}

          {derivedTeams.length > 0 ? (
            <section className="flex flex-col gap-4">
              <SectionHeading
                title="Structură din roster"
                detail={`${derivedTeams.length} ${derivedTeams.length === 1 ? "echipă" : "echipe"}`}
              />
              <div className="grid gap-4 xl:grid-cols-2">
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

function TeamSummary({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail?: string;
}) {
  return (
    <div className="min-w-24">
      <dt className="text-xs font-semibold text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-2xl font-semibold tabular-nums text-foreground">{value}</dd>
      {detail ? (
        <dd className="mt-1 text-xs font-semibold text-muted-foreground">{detail}</dd>
      ) : null}
    </div>
  );
}

function SectionHeading({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border pb-3">
      <h3 className="text-lg font-semibold text-foreground">{title}</h3>
      <p className="text-sm text-muted-foreground">{detail}</p>
    </div>
  );
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <section className="border-y border-border py-10 text-center">
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      <p className="mt-2 text-sm text-muted-foreground">{description}</p>
    </section>
  );
}

function DerivedTeamCard({ team }: { team: DerivedTeam }) {
  return (
    <article className="flex flex-col rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold text-foreground">{team.name}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{team.members.length} membri recunoscuți</p>
        </div>
        <Badge variant="secondary" className="rounded-lg">
          {team.source === "leadership" ? "Leadership" : "Manager direct"}
        </Badge>
      </div>

      <ol className="mt-4 flex max-h-64 flex-col divide-y divide-border overflow-y-auto">
        {team.members.map(({ membership, participant }) => (
          <li key={membership.id} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-1 py-2.5 hover:bg-muted/50">
            <span className="flex min-w-0 items-center gap-2.5">
              <IdentityMark
                kind="person"
                label={participant.full_name}
                seed={`participant:${participant.id}`}
                paletteKey={participant.avatar_palette_key}
                size="xs"
              />
              <span className="min-w-0">
                <span className="block truncate text-sm font-semibold text-foreground">{participant.full_name}</span>
                <span className="block truncate text-xs text-muted-foreground">{participant.position ?? "Membru"}</span>
              </span>
            </span>
            <RoleBadge role={membership.role} />
          </li>
        ))}
      </ol>
    </article>
  );
}

function TeamCard({
  team,
  participants,
  members,
  onAddMember,
  onRemoveMember,
}: {
  team: CompanyTeam;
  participants: CompanyParticipant[];
  members: Array<{ membership: CompanyTeamMembership; participant: CompanyParticipant }>;
  onAddMember: (
    teamId: string,
    participantProfileId: string,
    role: CompanyTeamMembership["role"],
  ) => Promise<void>;
  onRemoveMember: (
    teamId: string,
    membershipId: string,
  ) => Promise<void>;
}) {
  const availableParticipants = useMemo(() => {
    const memberIds = new Set(members.map((entry) => entry.participant.id));
    return participants.filter((participant) => !memberIds.has(participant.id));
  }, [members, participants]);
  const [selectedParticipantId, setSelectedParticipantId] = useState(availableParticipants[0]?.id ?? "");
  const [selectedRole, setSelectedRole] = useState<CompanyTeamMembership["role"]>("member");
  const [isAdding, setIsAdding] = useState(false);
  const [removingMembershipId, setRemovingMembershipId] = useState<string | null>(null);
  const [confirmingMembershipId, setConfirmingMembershipId] = useState<string | null>(null);
  const addingRef = useRef(false);
  const participantSelectId = useId();
  const roleSelectId = useId();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedParticipantId || addingRef.current) return;

    addingRef.current = true;
    setIsAdding(true);
    try {
      await onAddMember(team.id, selectedParticipantId, selectedRole);
      const nextParticipant = availableParticipants.find(
        (participant) => participant.id !== selectedParticipantId,
      );
      setSelectedParticipantId(nextParticipant?.id ?? "");
      setSelectedRole("member");
    } finally {
      addingRef.current = false;
      setIsAdding(false);
    }
  }

  async function handleRemove(membershipId: string) {
    if (removingMembershipId) return;
    setRemovingMembershipId(membershipId);
    try {
      await onRemoveMember(team.id, membershipId);
      setConfirmingMembershipId(null);
    } finally {
      setRemovingMembershipId(null);
    }
  }

  return (
    <article className="flex flex-col rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold text-foreground">{team.name}</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {members.length} {members.length === 1 ? "membru" : "membri"}
          </p>
        </div>
        <Badge variant={team.type === "leadership" ? "default" : "outline"} className="rounded-lg">
          {team.type === "leadership" ? "Leadership" : "Funcțională"}
        </Badge>
      </div>

      <div className="mt-4 min-h-0 flex-1 border-y border-border">
        {members.length === 0 ? (
          <Empty className="min-h-24 px-3 py-4">
            <EmptyHeader>
              <EmptyTitle>Niciun membru adăugat încă.</EmptyTitle>
            </EmptyHeader>
          </Empty>
        ) : (
          <ol className="flex max-h-56 flex-col divide-y divide-border overflow-y-auto">
            {members.map(({ membership, participant }) => (
              <li key={membership.id} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-1 py-2.5">
                <span className="flex min-w-0 items-center gap-2.5">
                  <IdentityMark
                    kind="person"
                    label={participant.full_name}
                    seed={`participant:${participant.id}`}
                    paletteKey={participant.avatar_palette_key}
                    size="xs"
                  />
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-semibold text-foreground">{participant.full_name}</span>
                    <span className="block truncate text-xs text-muted-foreground">{participant.position ?? "Membru"}</span>
                  </span>
                </span>
                {confirmingMembershipId === membership.id ? (
                  <span className="flex items-center gap-1">
                    <Button
                      type="button"
                      size="xs"
                      variant="destructive"
                      disabled={removingMembershipId === membership.id}
                      onClick={() => void handleRemove(membership.id)}
                    >
                      {removingMembershipId === membership.id ? "Eliminăm" : "Confirmă"}
                    </Button>
                    <Button
                      type="button"
                      size="xs"
                      variant="ghost"
                      disabled={removingMembershipId === membership.id}
                      onClick={() => setConfirmingMembershipId(null)}
                    >
                      Anulează
                    </Button>
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <RoleBadge role={membership.role} />
                    <Button
                      type="button"
                      size="icon-xs"
                      variant="ghost"
                      aria-label={`Elimină ${participant.full_name} din ${team.name}`}
                      disabled={Boolean(removingMembershipId)}
                      onClick={() => setConfirmingMembershipId(membership.id)}
                    >
                      <Trash2Icon aria-hidden="true" strokeWidth={1.8} />
                    </Button>
                  </span>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>

      <form onSubmit={handleSubmit} className="mt-4" aria-busy={isAdding}>
        <p className="text-sm font-semibold text-foreground">Adaugă membru</p>
        <FieldGroup className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,1fr)_8rem_auto] sm:items-end">
          <Field data-disabled={isAdding ? true : undefined}>
            <FieldLabel htmlFor={participantSelectId}>Participant</FieldLabel>
            <SelectControl
              id={participantSelectId}
              label={`Participant pentru ${team.name}`}
              value={selectedParticipantId}
              onChange={(event) => setSelectedParticipantId(event.target.value)}
              disabled={isAdding}
            >
              <option value="">Selectează participant</option>
              {availableParticipants.map((participant) => (
                <option key={participant.id} value={participant.id}>
                  {participant.full_name}
                </option>
              ))}
            </SelectControl>
          </Field>
          <Field data-disabled={isAdding ? true : undefined}>
            <FieldLabel htmlFor={roleSelectId}>Rol</FieldLabel>
            <SelectControl
              id={roleSelectId}
              label={`Rol în ${team.name}`}
              value={selectedRole}
              onChange={(event) => setSelectedRole(event.target.value as CompanyTeamMembership["role"])}
              disabled={isAdding}
            >
              <option value="member">Membru</option>
              <option value="leader">Lider</option>
            </SelectControl>
          </Field>
          <Button
            type="submit"
            disabled={isAdding || !selectedParticipantId}
            variant="outline"
            className="h-11"
          >
            {isAdding ? <Loader2Icon data-icon="inline-start" aria-hidden="true" className="animate-spin" /> : null}
            {isAdding ? "Adăugăm membrul" : "Adaugă"}
          </Button>
          {isAdding ? (
            <OperationFeedback
              title="Adăugăm membrul"
              detail="Actualizăm echipa."
              className="sm:col-span-3"
            />
          ) : null}
        </FieldGroup>
      </form>
    </article>
  );
}

function RoleBadge({ role }: { role: CompanyTeamMembership["role"] }) {
  return (
    <Badge variant={role === "leader" ? "secondary" : "outline"} className="shrink-0 rounded-md">
      {role === "leader" ? "Lider" : "Membru"}
    </Badge>
  );
}
