"use client";

import { useEffect, useMemo, useState } from "react";

import {
  createCompanyAssignment,
  getCompanyDefaultAssignmentPlan,
  resendParticipantInvitation,
  saveCompanyDefaultAssignmentPlan,
  sendParticipantInvitations,
  type CompanyAssignment,
  type CompanyAssignmentPlan,
  type CompanyAssignmentPlanItem,
  type CompanyParticipant,
  type CompanyTeam,
  type CreateCompanyAssignmentPayload,
  type ParticipantInvitationStatus,
  type ParticipantInvitationMode,
  type RosterInviteResult,
} from "@/api/companies";
import {
  listQuestionnaireDefinitionStubs,
  type QuestionnaireDefinitionStub,
} from "@/api/questionnaires";

type InvitationsWorkspaceProps = {
  companyId: string;
  companyName: string;
  participants: CompanyParticipant[];
  assignments: CompanyAssignment[];
  invitationStatuses: ParticipantInvitationStatus[];
  teams: CompanyTeam[];
};

type AssignmentTargetType = CompanyAssignment["target_type"];

type AssignmentFormState = {
  respondentProfileId: string;
  questionnaireKey: string;
  targetType: AssignmentTargetType;
  targetPersonId: string;
  targetTeamId: string;
};

type ParticipantInviteRow = {
  participant: CompanyParticipant;
  assignments: CompanyAssignment[];
  totalTasks: number;
  completedTasks: number;
  completionLabel: string;
  signedUp: boolean;
  deliveryLabel: string;
  deliveryTone: "default" | "success" | "warning" | "danger";
  secureLinkUrl: string | null;
  nextAction: string;
};

const completedStatuses = new Set(["submitted", "validated", "scored"]);
const activeInviteStatuses = new Set(["invited", "started", "submitted", "validated", "scored"]);

export function buildInvitationRows(
  participants: CompanyParticipant[],
  assignments: CompanyAssignment[],
  invitationStatuses: ParticipantInvitationStatus[],
  resultsByParticipant: Map<string, RosterInviteResult>,
): ParticipantInviteRow[] {
  const assignmentsByParticipant = new Map<string, CompanyAssignment[]>();
  const statusByParticipant = new Map(
    invitationStatuses.map((status) => [status.participant_id, status]),
  );

  for (const assignment of assignments) {
    assignmentsByParticipant.set(assignment.respondent_profile_id, [
      ...(assignmentsByParticipant.get(assignment.respondent_profile_id) ?? []),
      assignment,
    ]);
  }

  return participants.map((participant) => {
    const participantAssignments = assignmentsByParticipant.get(participant.id) ?? [];
    const persistedStatus = statusByParticipant.get(participant.id);
    const result = resultsByParticipant.get(participant.id);
    const completedTasks = participantAssignments.filter((assignment) => completedStatuses.has(assignment.status)).length;
    const totalTasks = participantAssignments.length;
    const signedUp = Boolean(participant.user_id);

    let deliveryLabel = "Fără asignări";
    let deliveryTone: ParticipantInviteRow["deliveryTone"] = "default";
    const secureLinkUrl = result?.invite_url ?? persistedStatus?.active_secure_link_url ?? null;

    if (result?.error) {
      deliveryLabel = "Eroare trimitere";
      deliveryTone = "danger";
    } else if (result?.email_sent) {
      deliveryLabel = "Email trimis";
      deliveryTone = "success";
    } else if (result?.delivery_mode === "secure_links") {
      deliveryLabel = "Link securizat generat";
      deliveryTone = "success";
    } else if (persistedStatus?.latest_email_status === "failed" || persistedStatus?.latest_email_status === "bounced") {
      deliveryLabel = "Eroare trimitere";
      deliveryTone = "danger";
    } else if (persistedStatus?.latest_email_status === "queued") {
      deliveryLabel = "Email în coadă";
      deliveryTone = "warning";
    } else if (persistedStatus?.latest_email_status) {
      deliveryLabel = "Email trimis";
      deliveryTone = "success";
    } else if (persistedStatus?.has_active_secure_link) {
      deliveryLabel = "Link securizat activ";
      deliveryTone = "success";
    } else if (participantAssignments.some((assignment) => activeInviteStatuses.has(assignment.status))) {
      deliveryLabel = "Invitație activă";
      deliveryTone = "success";
    } else if (totalTasks > 0) {
      deliveryLabel = "Pregătit, netrimis";
      deliveryTone = "warning";
    }

    const completionLabel = totalTasks > 0 ? `${completedTasks}/${totalTasks}` : "0/0";
    const nextAction =
      totalTasks === 0
        ? "Configurează asignări"
        : completedTasks === totalTasks
          ? "Verifică raportul"
          : deliveryTone === "success"
            ? "Urmărește progresul"
            : "Trimite invitația";

    return {
      participant,
      assignments: participantAssignments,
      totalTasks,
      completedTasks,
      completionLabel,
      signedUp,
      deliveryLabel,
      deliveryTone,
      secureLinkUrl,
      nextAction,
    };
  });
}

export function InvitationsWorkspace({
  companyId,
  companyName,
  participants,
  assignments,
  invitationStatuses,
  teams,
}: InvitationsWorkspaceProps) {
  const [assignmentState, setAssignmentState] = useState(assignments);
  const [questionnaires, setQuestionnaires] = useState<QuestionnaireDefinitionStub[]>([]);
  const [questionnaireMessage, setQuestionnaireMessage] = useState<string | null>(null);
  const [assignmentSaving, setAssignmentSaving] = useState(false);
  const [plan, setPlan] = useState<CompanyAssignmentPlan | null>(null);
  const [selectedPlanKeys, setSelectedPlanKeys] = useState<Set<string>>(new Set());
  const [planLoading, setPlanLoading] = useState(false);
  const [planSaving, setPlanSaving] = useState(false);
  const [assignmentForm, setAssignmentForm] = useState<AssignmentFormState>({
    respondentProfileId: participants[0]?.id ?? "",
    questionnaireKey: "",
    targetType: "self",
    targetPersonId: "",
    targetTeamId: "",
  });
  const [resultsByParticipant, setResultsByParticipant] = useState(new Map<string, RosterInviteResult>());
  const [message, setMessage] = useState<string | null>(null);
  const [sendingMode, setSendingMode] = useState<ParticipantInvitationMode | "resend" | null>(null);
  const [copiedParticipantId, setCopiedParticipantId] = useState<string | null>(null);

  useEffect(() => {
    setAssignmentState(assignments);
  }, [assignments]);

  useEffect(() => {
    let cancelled = false;

    async function loadQuestionnaires() {
      try {
        const definitions = await listQuestionnaireDefinitionStubs();
        if (cancelled) return;
        setQuestionnaires(definitions.filter((definition) => definition.status === "active"));
        setQuestionnaireMessage(null);
      } catch {
        if (!cancelled) {
          setQuestionnaireMessage("Chestionarele nu au putut fi încărcate.");
        }
      }
    }

    void loadQuestionnaires();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const nextRespondentId = participants.some((participant) => participant.id === assignmentForm.respondentProfileId)
      ? assignmentForm.respondentProfileId
      : (participants[0]?.id ?? "");
    setAssignmentForm((current) => ({
      ...current,
      respondentProfileId: nextRespondentId,
      targetPersonId: participants.some((participant) => participant.id === current.targetPersonId) &&
        current.targetPersonId !== nextRespondentId
        ? current.targetPersonId
        : (participants.find((participant) => participant.id !== nextRespondentId)?.id ?? ""),
      targetTeamId: teams.some((team) => team.id === current.targetTeamId)
        ? current.targetTeamId
        : (teams[0]?.id ?? ""),
    }));
  }, [assignmentForm.respondentProfileId, participants, teams]);

  useEffect(() => {
    if (assignmentForm.questionnaireKey || questionnaires.length === 0) return;
    setAssignmentForm((current) => ({
      ...current,
      questionnaireKey: questionnaires[0]?.id ?? "",
    }));
  }, [assignmentForm.questionnaireKey, questionnaires]);

  const rows = useMemo(
    () => buildInvitationRows(participants, assignmentState, invitationStatuses, resultsByParticipant),
    [assignmentState, invitationStatuses, participants, resultsByParticipant],
  );
  const participantsById = useMemo(
    () => new Map(participants.map((participant) => [participant.id, participant])),
    [participants],
  );
  const teamsById = useMemo(
    () => new Map(teams.map((team) => [team.id, team])),
    [teams],
  );
  const targetPersonOptions = useMemo(
    () => participants.filter((participant) => participant.id !== assignmentForm.respondentProfileId),
    [assignmentForm.respondentProfileId, participants],
  );
  const planGroups = useMemo(() => buildPlanGroups(plan), [plan]);
  const selectedPlanItems = useMemo(
    () => plan?.assignments.filter((assignment) => selectedPlanKeys.has(assignment.key)) ?? [],
    [plan, selectedPlanKeys],
  );

  const signedUpCount = rows.filter((row) => row.signedUp).length;
  const activeInvites = rows.filter((row) => row.deliveryTone === "success").length;
  const completedCount = rows.filter((row) => row.totalTasks > 0 && row.completedTasks === row.totalTasks).length;
  const blockedCount = rows.filter((row) => row.deliveryTone === "danger" || row.totalTasks === 0).length;
  const participantsWithoutAssignments = rows.filter((row) => row.totalTasks === 0).length;
  const canCreateAssignment =
    participants.length > 0 &&
    questionnaires.length > 0 &&
    Boolean(assignmentForm.respondentProfileId) &&
    Boolean(assignmentForm.questionnaireKey) &&
    (assignmentForm.targetType === "self" ||
      (assignmentForm.targetType === "person" &&
        Boolean(assignmentForm.targetPersonId) &&
        assignmentForm.targetPersonId !== assignmentForm.respondentProfileId) ||
      (assignmentForm.targetType === "team" && Boolean(assignmentForm.targetTeamId)));
  const canSavePlan = selectedPlanItems.length > 0 && !planSaving;

  function updateAssignmentForm(patch: Partial<AssignmentFormState>) {
    setAssignmentForm((current) => {
      const next = {
        ...current,
        ...patch,
      };
      const respondentId = next.respondentProfileId;
      const targetPersonStillValid =
        next.targetPersonId &&
        next.targetPersonId !== respondentId &&
        participants.some((participant) => participant.id === next.targetPersonId);

      if (!targetPersonStillValid) {
        next.targetPersonId = participants.find((participant) => participant.id !== respondentId)?.id ?? "";
      }

      return next;
    });
  }

  async function handleCreateAssignment() {
    if (!canCreateAssignment) return;
    setAssignmentSaving(true);
    setMessage(null);
    setCopiedParticipantId(null);

    const payload: CreateCompanyAssignmentPayload = {
      respondentProfileId: assignmentForm.respondentProfileId,
      questionnaireKey: assignmentForm.questionnaireKey,
      targetType: assignmentForm.targetType,
      targetPersonId: assignmentForm.targetType === "person" ? assignmentForm.targetPersonId : null,
      targetTeamId: assignmentForm.targetType === "team" ? assignmentForm.targetTeamId : null,
    };

    try {
      const created = await createCompanyAssignment(companyId, payload);
      setAssignmentState((current) => [...current, created]);
      const respondentName = participantsById.get(created.respondent_profile_id)?.full_name ?? "participant";
      setMessage(`Asignare creată pentru ${respondentName}. Poți trimite invitația când ești pregătit.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Asignarea nu a putut fi creată.");
    } finally {
      setAssignmentSaving(false);
    }
  }

  async function handleGeneratePlan() {
    setPlanLoading(true);
    setMessage(null);
    setCopiedParticipantId(null);
    try {
      const generated = await getCompanyDefaultAssignmentPlan(companyId);
      setPlan(generated);
      setSelectedPlanKeys(
        new Set(generated.assignments.filter((assignment) => assignment.selected).map((assignment) => assignment.key)),
      );
      setMessage(
        generated.assignments.length > 0
          ? `Plan generat: ${generated.suggested_count} sarcini propuse, ${generated.existing_count} deja existente.`
          : "Nu există sarcini propuse pentru structura curentă.",
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Planul de asignări nu a putut fi generat.");
    } finally {
      setPlanLoading(false);
    }
  }

  async function handleSavePlan() {
    if (!canSavePlan) return;
    setPlanSaving(true);
    setMessage(null);
    setCopiedParticipantId(null);
    try {
      const result = await saveCompanyDefaultAssignmentPlan(companyId, selectedPlanItems);
      const savedIdsByPlanKey = new Map(
        selectedPlanItems.map((assignment, index) => [assignment.key, result.assignments[index]?.id ?? null]),
      );
      setAssignmentState((current) => mergeAssignments(current, result.assignments));
      setPlan((current) =>
        current
          ? {
              ...current,
              assignments: current.assignments.map((assignment) =>
                selectedPlanKeys.has(assignment.key)
                  ? {
                      ...assignment,
                      selected: false,
                      existing_assignment_id: assignment.existing_assignment_id ?? savedIdsByPlanKey.get(assignment.key) ?? null,
                    }
                  : assignment,
              ),
              existing_count: current.existing_count + result.created_count,
            }
          : current,
      );
      setSelectedPlanKeys(new Set());
      setMessage(`${result.created_count} asignări create, ${result.existing_count} deja existente.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Asignările selectate nu au putut fi salvate.");
    } finally {
      setPlanSaving(false);
    }
  }

  function togglePlanItem(key: string) {
    setSelectedPlanKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function togglePlanScope(scopeId: string, checked: boolean) {
    const keys = plan?.assignments
      .filter((assignment) => assignment.scope_id === scopeId && !assignment.existing_assignment_id)
      .map((assignment) => assignment.key) ?? [];
    setSelectedPlanKeys((current) => {
      const next = new Set(current);
      for (const key of keys) {
        if (checked) {
          next.add(key);
        } else {
          next.delete(key);
        }
      }
      return next;
    });
  }

  async function handleSend(mode: ParticipantInvitationMode) {
    setSendingMode(mode);
    setMessage(null);
    setCopiedParticipantId(null);
    try {
      const result = await sendParticipantInvitations(companyId, { mode });
      setResultsByParticipant((current) => {
        const next = new Map(current);
        for (const item of result.results) {
          next.set(item.participant_id, item);
        }
        return next;
      });
      setMessage(
        mode === "email"
          ? `${result.emails_sent}/${result.total} emailuri trimise.`
          : `${result.links_generated}/${result.total} linkuri securizate generate.`,
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Invitațiile nu au putut fi trimise.");
    } finally {
      setSendingMode(null);
    }
  }

  async function handleResend(participantId: string) {
    setSendingMode("resend");
    setMessage(null);
    setCopiedParticipantId(null);
    try {
      const result = await resendParticipantInvitation(companyId, participantId);
      if (result) {
        setResultsByParticipant((current) => {
          const next = new Map(current);
          next.set(result.participant_id, result);
          return next;
        });
        setMessage(formatResendMessage(result));
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Invitația nu a putut fi retrimisă.");
    } finally {
      setSendingMode(null);
    }
  }

  async function handleCopyLink(row: ParticipantInviteRow) {
    if (!row.secureLinkUrl || typeof navigator === "undefined") return;
    try {
      await navigator.clipboard.writeText(row.secureLinkUrl);
      setCopiedParticipantId(row.participant.id);
      setMessage(`Link securizat copiat pentru ${row.participant.full_name}.`);
    } catch {
      setMessage("Linkul nu a putut fi copiat automat. Copiază-l manual din browser.");
    }
  }

  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
        <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_26rem]">
          <div className="p-5 md:p-6">
            <p className="text-sm font-semibold text-burgundy/75">Invitații companie</p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">Status invitații pentru {companyName}</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/62">
              Vezi cine are invitația activă, cine și-a creat contul, câte sarcini are și ce trebuie urmărit.
            </p>
            <div className="mt-4 grid gap-2 sm:grid-cols-4">
              <InviteSummary label="Invitații active" value={activeInvites} />
              <InviteSummary label="Conturi create" value={signedUpCount} />
              <InviteSummary label="Completate" value={completedCount} />
              <InviteSummary label="Blocaje" value={blockedCount} />
            </div>
          </div>
          <div className="space-y-3 border-t border-[var(--border)] bg-surface-muted/45 p-5 md:p-6 lg:border-l lg:border-t-0">
            <button
              type="button"
              onClick={() => void handleSend("secure_links")}
              disabled={sendingMode !== null || participants.length === 0}
              className="tap-soft w-full rounded-xl bg-burgundy px-4 py-3 text-sm font-bold text-white shadow-sm shadow-burgundy/10 hover:bg-burgundy-700 disabled:cursor-not-allowed disabled:opacity-45"
            >
              {sendingMode === "secure_links" ? "Se generează linkurile..." : "Generează linkuri securizate"}
            </button>
            <button
              type="button"
              onClick={() => void handleSend("email")}
              disabled={sendingMode !== null || participants.length === 0}
              className="tap-soft w-full rounded-xl border border-[var(--border)] bg-background px-4 py-3 text-sm font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy disabled:cursor-not-allowed disabled:opacity-45"
            >
              {sendingMode === "email" ? "Se trimit emailurile..." : "Trimite email invitații"}
            </button>
            <p className="text-xs leading-5 text-foreground/52">
              Lista de participanți rămâne salvată separat. Trimiterea emailurilor sau generarea linkurilor se face explicit de aici.
            </p>
          </div>
        </div>
        {message ? (
          <p aria-live="polite" className="border-t border-[var(--border)] bg-background/70 px-5 py-3 text-sm font-semibold text-foreground/62">
            {message}
          </p>
        ) : null}
      </section>

      <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
        <div className="grid gap-0 xl:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="p-5 md:p-6">
            <p className="text-sm font-semibold text-burgundy/75">Pregătire sarcini</p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">Configurează asignările înainte de trimitere</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/62">
              Generează planul implicit, verifică rândurile propuse și salvează doar asignările bifate. Invitațiile se trimit separat.
            </p>

            <div className="mt-5 flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                onClick={() => void handleGeneratePlan()}
                disabled={planLoading || participants.length === 0}
                className="tap-soft rounded-xl border border-burgundy bg-surface px-4 py-3 text-sm font-bold text-burgundy hover:bg-burgundy/5 disabled:cursor-not-allowed disabled:opacity-45"
              >
                {planLoading ? "Se generează planul..." : "Generează plan de asignări"}
              </button>
              <button
                type="button"
                onClick={() => void handleSavePlan()}
                disabled={!canSavePlan}
                className="tap-soft rounded-xl bg-burgundy px-4 py-3 text-sm font-bold text-white shadow-sm shadow-burgundy/10 hover:bg-burgundy-700 disabled:cursor-not-allowed disabled:opacity-45"
              >
                {planSaving ? "Se salvează asignările..." : `Salvează asignările bifate (${selectedPlanItems.length})`}
              </button>
            </div>

            {plan ? (
              <AssignmentPlanList
                groups={planGroups}
                selectedKeys={selectedPlanKeys}
                onToggleItem={togglePlanItem}
                onToggleScope={togglePlanScope}
              />
            ) : (
              <div className="mt-5 rounded-2xl border border-dashed border-[var(--border)] bg-background/60 px-4 py-5 text-sm leading-6 text-foreground/58">
                Planul implicit va grupa sarcinile pe leadership, echipe de manager și feedback 360. După generare poți debifa rândurile care nu trebuie salvate.
              </div>
            )}

            <div className="mt-6 border-t border-[var(--border)] pt-5">
              <p className="text-sm font-semibold text-foreground">Asignare punctuală</p>
              <p className="mt-1 text-xs leading-5 text-foreground/52">
                Folosește formularul doar pentru excepții care nu apar în planul implicit.
              </p>
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              <LabeledSelect
                label="Persoană"
                value={assignmentForm.respondentProfileId}
                onChange={(value) => updateAssignmentForm({ respondentProfileId: value })}
                disabled={assignmentSaving || participants.length === 0}
              >
                {participants.length === 0 ? <option value="">Nu există persoane în lista de participanți</option> : null}
                {participants.map((participant) => (
                  <option key={participant.id} value={participant.id}>
                    {participant.full_name} · {participant.email}
                  </option>
                ))}
              </LabeledSelect>

              <LabeledSelect
                label="Chestionar"
                value={assignmentForm.questionnaireKey}
                onChange={(value) => updateAssignmentForm({ questionnaireKey: value })}
                disabled={assignmentSaving || questionnaires.length === 0}
              >
                {questionnaires.length === 0 ? <option value="">Nu există chestionare active</option> : null}
                {questionnaires.map((definition) => (
                  <option key={definition.id} value={definition.id}>
                    {definition.name}
                  </option>
                ))}
              </LabeledSelect>
            </div>

            <div className="mt-4 rounded-2xl border border-[var(--border)] bg-background/70 p-3">
              <p className="px-1 text-xs font-semibold text-foreground/50">Ținta evaluării</p>
              <div className="mt-2 grid gap-2 sm:grid-cols-3">
                <TargetButton
                  active={assignmentForm.targetType === "self"}
                  label="Autoevaluare"
                  detail="Persoana răspunde despre sine."
                  onClick={() => updateAssignmentForm({ targetType: "self" })}
                />
                <TargetButton
                  active={assignmentForm.targetType === "person"}
                  label="Persoană"
                  detail="Feedback despre un manager sau coleg."
                  onClick={() => updateAssignmentForm({ targetType: "person" })}
                />
                <TargetButton
                  active={assignmentForm.targetType === "team"}
                  label="Echipă"
                  detail="Evaluare pentru o echipă definită."
                  onClick={() => updateAssignmentForm({ targetType: "team" })}
                />
              </div>
            </div>

            {assignmentForm.targetType === "person" ? (
              <div className="mt-4">
                <LabeledSelect
                  label="Persoana evaluată"
                  value={assignmentForm.targetPersonId}
                  onChange={(value) => updateAssignmentForm({ targetPersonId: value })}
                  disabled={assignmentSaving || targetPersonOptions.length === 0}
                >
                  {targetPersonOptions.length === 0 ? <option value="">Nu există altă persoană disponibilă</option> : null}
                  {targetPersonOptions.map((participant) => (
                    <option key={participant.id} value={participant.id}>
                      {participant.full_name}
                    </option>
                  ))}
                </LabeledSelect>
              </div>
            ) : null}

            {assignmentForm.targetType === "team" ? (
              <div className="mt-4">
                <LabeledSelect
                  label="Echipa evaluată"
                  value={assignmentForm.targetTeamId}
                  onChange={(value) => updateAssignmentForm({ targetTeamId: value })}
                  disabled={assignmentSaving || teams.length === 0}
                >
                  {teams.length === 0 ? <option value="">Nu există echipe definite</option> : null}
                  {teams.map((team) => (
                    <option key={team.id} value={team.id}>
                      {team.name} · {team.type === "leadership" ? "leadership" : "funcțională"}
                    </option>
                  ))}
                </LabeledSelect>
              </div>
            ) : null}
          </div>

          <div className="flex flex-col justify-between gap-4 border-t border-[var(--border)] bg-surface-muted/45 p-5 md:p-6 xl:border-l xl:border-t-0">
            <div className="space-y-3">
              <AssignmentSummary label="Asignări totale" value={assignmentState.length} />
              <AssignmentSummary label="Bifate în plan" value={selectedPlanItems.length} />
              <AssignmentSummary label="Persoane fără sarcini" value={participantsWithoutAssignments} />
              <AssignmentSummary label="Chestionare active" value={questionnaires.length} />
            </div>
            <div className="space-y-3">
              {questionnaireMessage ? (
                <p className="text-xs font-semibold text-burgundy">{questionnaireMessage}</p>
              ) : null}
              <button
                type="button"
                onClick={() => void handleCreateAssignment()}
                disabled={!canCreateAssignment || assignmentSaving}
                className="tap-soft w-full rounded-xl bg-burgundy px-4 py-3 text-sm font-bold text-white shadow-sm shadow-burgundy/10 hover:bg-burgundy-700 disabled:cursor-not-allowed disabled:opacity-45"
              >
                {assignmentSaving ? "Se salvează asignarea..." : "Creează asignarea"}
              </button>
              <p className="text-xs leading-5 text-foreground/52">
                Invitarea rămâne separată: creezi toate asignările, apoi alegi emailuri sau linkuri securizate.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
        <div className="border-b border-[var(--border)] px-5 py-4">
          <p className="text-xs font-semibold text-burgundy/75">Urmărire</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">Persoane invitate</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-surface-muted text-xs font-semibold uppercase tracking-[0.1em] text-foreground/50">
              <tr>
                <th className="px-5 py-3">Persoană</th>
                <th className="px-5 py-3">Livrare</th>
                <th className="px-5 py-3">Cont</th>
                <th className="px-5 py-3">Sarcini</th>
                <th className="px-5 py-3">Următorul pas</th>
                <th className="px-5 py-3 text-right">Acțiune</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-6 text-center text-foreground/62">
                    Nu există persoane în lista de participanți.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.participant.id} className="align-top transition-colors hover:bg-surface-muted/40">
                    <td className="px-5 py-4">
                      <p className="font-semibold text-foreground">{row.participant.full_name}</p>
                      <p className="mt-1 text-xs text-foreground/50">{row.participant.email}</p>
                    </td>
                    <td className="px-5 py-4">
                      <StatusPill tone={row.deliveryTone}>{row.deliveryLabel}</StatusPill>
                    </td>
                    <td className="px-5 py-4">
                      <StatusPill tone={row.signedUp ? "success" : "warning"}>
                        {row.signedUp ? "Cont activ" : "Neînregistrat"}
                      </StatusPill>
                    </td>
                    <td className="px-5 py-4 text-foreground/62">
                      <p className="font-semibold text-foreground">{row.completionLabel}</p>
                      <p className="mt-1 text-xs text-foreground/50">
                        {row.assignments
                          .map((assignment) => formatAssignmentLabel(assignment, participantsById, teamsById))
                          .join(", ") || "Fără asignări"}
                      </p>
                    </td>
                    <td className="px-5 py-4 text-foreground/62">{row.nextAction}</td>
                    <td className="px-5 py-4 text-right">
                      {row.secureLinkUrl ? (
                        <button
                          type="button"
                          onClick={() => void handleCopyLink(row)}
                          disabled={sendingMode !== null}
                          className="tap-soft rounded-lg border border-[var(--border)] bg-background px-3 py-2 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy disabled:cursor-not-allowed disabled:opacity-45"
                        >
                          {copiedParticipantId === row.participant.id ? "Copiat" : "Copiază link"}
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => void handleResend(row.participant.id)}
                          disabled={sendingMode !== null || row.totalTasks === 0}
                          className="tap-soft rounded-lg border border-[var(--border)] bg-background px-3 py-2 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy disabled:cursor-not-allowed disabled:opacity-45"
                        >
                          Retrimite
                        </button>
                      )}
                    </td>
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

function formatResendMessage(result: RosterInviteResult): string {
  if (result.email_sent) return `Email retrimis către ${result.email}.`;
  if (result.error) return `Emailul nu a fost retrimis către ${result.email}: ${result.error}`;
  if (result.invite_url) return `Link pregătit pentru ${result.email}.`;
  return `Invitația nu a fost retrimisă către ${result.email}.`;
}

type AssignmentPlanGroup = {
  id: string;
  name: string;
  type: string;
  assignments: CompanyAssignmentPlanItem[];
};

function buildPlanGroups(plan: CompanyAssignmentPlan | null): AssignmentPlanGroup[] {
  if (!plan) return [];
  const groups = new Map<string, AssignmentPlanGroup>();

  for (const scope of plan.scopes) {
    groups.set(scope.id, {
      id: scope.id,
      name: scope.name,
      type: scope.type,
      assignments: [],
    });
  }

  for (const assignment of plan.assignments) {
    const group = groups.get(assignment.scope_id) ?? {
      id: assignment.scope_id,
      name: assignment.scope_name,
      type: assignment.scope_type,
      assignments: [],
    };
    group.assignments.push(assignment);
    groups.set(assignment.scope_id, group);
  }

  return Array.from(groups.values()).filter((group) => group.assignments.length > 0);
}

function mergeAssignments(current: CompanyAssignment[], incoming: CompanyAssignment[]): CompanyAssignment[] {
  const merged = new Map(current.map((assignment) => [assignment.id, assignment]));
  for (const assignment of incoming) {
    merged.set(assignment.id, assignment);
  }
  return Array.from(merged.values());
}

function AssignmentPlanList({
  groups,
  selectedKeys,
  onToggleItem,
  onToggleScope,
}: {
  groups: AssignmentPlanGroup[];
  selectedKeys: Set<string>;
  onToggleItem: (key: string) => void;
  onToggleScope: (scopeId: string, checked: boolean) => void;
}) {
  if (groups.length === 0) {
    return (
      <div className="mt-5 rounded-2xl border border-[var(--border)] bg-background/70 px-4 py-5 text-sm text-foreground/58">
        Nu există rânduri de asignare în planul generat.
      </div>
    );
  }

  return (
    <div className="mt-5 space-y-4">
      {groups.map((group) => {
        const selectable = group.assignments.filter((assignment) => !assignment.existing_assignment_id);
        const selectedCount = selectable.filter((assignment) => selectedKeys.has(assignment.key)).length;
        const allSelected = selectable.length > 0 && selectedCount === selectable.length;

        return (
          <div key={group.id} className="overflow-hidden rounded-2xl border border-[var(--border)] bg-background/75">
            <div className="flex flex-col gap-3 border-b border-[var(--border)] bg-surface-muted/55 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-bold text-foreground">{group.name}</p>
                <p className="mt-1 text-xs font-semibold text-foreground/50">
                  {formatScopeType(group.type)} · {group.assignments.length} rânduri
                </p>
              </div>
              <label className="inline-flex items-center gap-2 text-xs font-bold text-foreground/68">
                <input
                  type="checkbox"
                  checked={allSelected}
                  disabled={selectable.length === 0}
                  onChange={(event) => onToggleScope(group.id, event.target.checked)}
                  className="h-4 w-4 rounded border-[var(--border)] accent-[#890505]"
                />
                Selectează grupa
              </label>
            </div>
            <div className="divide-y divide-[var(--border)]">
              {group.assignments.map((assignment) => (
                <PlanAssignmentRow
                  key={assignment.key}
                  assignment={assignment}
                  selected={selectedKeys.has(assignment.key)}
                  onToggle={() => onToggleItem(assignment.key)}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PlanAssignmentRow({
  assignment,
  selected,
  onToggle,
}: {
  assignment: CompanyAssignmentPlanItem;
  selected: boolean;
  onToggle: () => void;
}) {
  const isExisting = Boolean(assignment.existing_assignment_id);

  return (
    <label
      className={[
        "grid gap-3 px-4 py-3 text-sm md:grid-cols-[1.5rem_1.2fr_0.85fr_1fr] md:items-center",
        isExisting ? "bg-surface-muted/35 text-foreground/48" : "cursor-pointer hover:bg-surface-muted/35",
      ].join(" ")}
    >
      <input
        type="checkbox"
        checked={isExisting || selected}
        disabled={isExisting}
        onChange={onToggle}
        className="mt-1 h-4 w-4 rounded border-[var(--border)] accent-[#890505] md:mt-0"
      />
      <div className="min-w-0">
        <p className="font-semibold text-foreground">{assignment.respondent_name}</p>
        <p className="mt-1 text-xs text-foreground/50">Respondent</p>
      </div>
      <div>
        <p className="font-semibold text-foreground">{assignment.questionnaire_key}</p>
        <p className="mt-1 text-xs text-foreground/50">Chestionar</p>
      </div>
      <div className="min-w-0">
        <p className="font-semibold text-foreground">{formatPlanTarget(assignment)}</p>
        <p className="mt-1 text-xs text-foreground/50">
          {formatTargetType(assignment.target_type)}
          {isExisting ? " · deja salvată" : ""}
        </p>
      </div>
    </label>
  );
}

function formatScopeType(type: string): string {
  if (type === "leadership_team") return "Leadership";
  if (type === "manager_team") return "Echipă manager";
  if (type === "manager") return "Manager";
  if (type === "member") return "Membru";
  return type;
}

function formatTargetType(type: AssignmentTargetType): string {
  if (type === "person") return "Persoană";
  if (type === "team") return "Echipă";
  return "Autoevaluare";
}

function formatPlanTarget(assignment: CompanyAssignmentPlanItem): string {
  if (assignment.target_type === "person") return assignment.target_person_name ?? "Persoană";
  if (assignment.target_type === "team") return assignment.target_team_name ?? "Echipă";
  return assignment.respondent_name;
}

function InviteSummary({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-background/80 px-3 py-2.5">
      <p className="text-xs font-semibold text-foreground/48">{label}</p>
      <p className="mt-1 text-lg font-semibold text-foreground">{value}</p>
    </div>
  );
}

function AssignmentSummary({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-background/80 px-3 py-3">
      <p className="text-xs font-semibold text-foreground/48">{label}</p>
      <p className="mt-1 text-xl font-semibold text-foreground">{value}</p>
    </div>
  );
}

function LabeledSelect({
  label,
  value,
  onChange,
  disabled,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-foreground/55">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        className="mt-1.5 w-full rounded-xl border border-[var(--border)] bg-background px-3 py-3 text-sm font-semibold text-foreground outline-none transition-colors hover:border-burgundy/45 focus:border-burgundy disabled:cursor-not-allowed disabled:opacity-45"
      >
        {children}
      </select>
    </label>
  );
}

function TargetButton({
  active,
  label,
  detail,
  onClick,
}: {
  active: boolean;
  label: string;
  detail: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "tap-soft rounded-xl border p-3 text-left transition-colors",
        active
          ? "border-burgundy bg-burgundy text-white shadow-sm shadow-burgundy/10"
          : "border-[var(--border)] bg-surface text-foreground hover:border-burgundy/45 hover:text-burgundy",
      ].join(" ")}
    >
      <span className="block text-sm font-bold">{label}</span>
      <span className={["mt-1 block text-xs leading-5", active ? "text-white/72" : "text-foreground/52"].join(" ")}>
        {detail}
      </span>
    </button>
  );
}

function formatAssignmentLabel(
  assignment: CompanyAssignment,
  participantsById: Map<string, CompanyParticipant>,
  teamsById: Map<string, CompanyTeam>,
) {
  if (assignment.target_type === "person") {
    const targetName = assignment.target_person_id
      ? participantsById.get(assignment.target_person_id)?.full_name
      : null;
    return `${assignment.questionnaire_key} · despre ${targetName ?? "persoană"}`;
  }
  if (assignment.target_type === "team") {
    const teamName = assignment.target_team_id ? teamsById.get(assignment.target_team_id)?.name : null;
    return `${assignment.questionnaire_key} · echipa ${teamName ?? "selectată"}`;
  }
  return `${assignment.questionnaire_key} · autoevaluare`;
}

function StatusPill({
  tone,
  children,
}: {
  tone: ParticipantInviteRow["deliveryTone"];
  children: React.ReactNode;
}) {
  const className =
    tone === "success"
      ? "bg-success/35 text-success-ink"
      : tone === "warning"
        ? "bg-warning/30 text-warning-ink"
        : tone === "danger"
          ? "bg-burgundy-50 text-burgundy dark:bg-burgundy/10"
          : "bg-surface-muted text-foreground/58";

  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${className}`}>{children}</span>;
}
