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
  type CompanyProject,
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
  projects: CompanyProject[];
  selectedProjectId: string | null;
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
  secureLinkExpiresAt: string | null;
  nextAction: string;
};

type InvitationFilter = "all" | "ready" | "errors" | "no_assignments" | "not_signed_up";

const completedStatuses = new Set(["submitted", "validated", "scored"]);
const activeInviteStatuses = new Set(["invited", "started", "submitted", "validated", "scored"]);
const questionnaireLabels: Record<string, string> = {
  lencioni: "Lencioni - evaluare echipă",
  lencioni_en: "Lencioni Team Assessment",
  distress_drivers: "Driveri de stres TA",
  distress_drivers_en: "TA Distress Drivers",
  boss_360: "iCARE 360 pentru manager",
  icare: "Feedback 360 iCARE",
  pcm_base: "Baza și faza PCM",
};

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
    const secureLinkExpiresAt = persistedStatus?.active_secure_link_expires_at ?? null;

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
      secureLinkExpiresAt,
      nextAction,
    };
  });
}

export function InvitationsWorkspace({
  companyId,
  companyName,
  projects,
  selectedProjectId,
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
  const [selectedParticipantIds, setSelectedParticipantIds] = useState<Set<string>>(new Set());
  const [invitationFilter, setInvitationFilter] = useState<InvitationFilter>("all");
  const [showAdvancedAssignments, setShowAdvancedAssignments] = useState(false);
  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );
  const hasProjects = projects.length > 0;
  const canUseProjectActions = !hasProjects || selectedProjectId !== null;

  useEffect(() => {
    setAssignmentState(assignments);
  }, [assignments]);

  useEffect(() => {
    setPlan(null);
    setSelectedPlanKeys(new Set());
    setSelectedParticipantIds(new Set());
    setResultsByParticipant(new Map());
    setCopiedParticipantId(null);
    setMessage(null);
  }, [selectedProjectId]);

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
  const filteredRows = useMemo(
    () => rows.filter((row) => matchesInvitationFilter(row, invitationFilter)),
    [invitationFilter, rows],
  );
  const selectableRows = useMemo(
    () => filteredRows.filter((row) => row.totalTasks > 0),
    [filteredRows],
  );
  const selectedRows = useMemo(
    () => rows.filter((row) => selectedParticipantIds.has(row.participant.id)),
    [rows, selectedParticipantIds],
  );
  const selectedReadyCount = selectedRows.filter((row) => row.totalTasks > 0).length;
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
  const visibleSelectedCount = filteredRows.filter((row) => selectedParticipantIds.has(row.participant.id)).length;
  const allVisibleSelected = selectableRows.length > 0 && selectableRows.every((row) => selectedParticipantIds.has(row.participant.id));
  const canCreateAssignment =
    canUseProjectActions &&
    participants.length > 0 &&
    questionnaires.length > 0 &&
    Boolean(assignmentForm.respondentProfileId) &&
    Boolean(assignmentForm.questionnaireKey) &&
    (assignmentForm.targetType === "self" ||
      (assignmentForm.targetType === "person" &&
        Boolean(assignmentForm.targetPersonId) &&
        assignmentForm.targetPersonId !== assignmentForm.respondentProfileId) ||
      (assignmentForm.targetType === "team" && Boolean(assignmentForm.targetTeamId)));
  const canSavePlan = canUseProjectActions && selectedPlanItems.length > 0 && !planSaving;

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
      projectId: selectedProjectId,
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
    if (!canUseProjectActions) {
      setMessage("Alege un proiect înainte de a genera planul de asignări.");
      return;
    }
    setPlanLoading(true);
    setMessage(null);
    setCopiedParticipantId(null);
    try {
      const generated = await getCompanyDefaultAssignmentPlan(
        companyId,
        {},
        { projectId: selectedProjectId },
      );
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
      const result = await saveCompanyDefaultAssignmentPlan(
        companyId,
        selectedPlanItems,
        selectedProjectId,
      );
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

  function toggleParticipantSelection(participantId: string) {
    setSelectedParticipantIds((current) => {
      const next = new Set(current);
      if (next.has(participantId)) {
        next.delete(participantId);
      } else {
        next.add(participantId);
      }
      return next;
    });
  }

  function setVisibleParticipantSelection(checked: boolean) {
    setSelectedParticipantIds((current) => {
      const next = new Set(current);
      for (const row of selectableRows) {
        if (checked) {
          next.add(row.participant.id);
        } else {
          next.delete(row.participant.id);
        }
      }
      return next;
    });
  }

  function selectReadyUnsentParticipants() {
    setInvitationFilter("ready");
    setSelectedParticipantIds(
      new Set(rows.filter((row) => matchesInvitationFilter(row, "ready")).map((row) => row.participant.id)),
    );
  }

  async function dispatchInvitations(mode: ParticipantInvitationMode, participantIds: string[], emptyMessage: string) {
    if (participantIds.length === 0) {
      setMessage(emptyMessage);
      return;
    }
    if (!canUseProjectActions) {
      setMessage("Alege un proiect înainte de trimitere.");
      return;
    }
    setSendingMode(mode);
    setMessage(null);
    setCopiedParticipantId(null);
    try {
      const result = await sendParticipantInvitations(companyId, {
        mode,
        participantIds,
        projectId: selectedProjectId,
      });
      setResultsByParticipant((current) => {
        const next = new Map(current);
        for (const item of result.results) {
          next.set(item.participant_id, item);
        }
        return next;
      });
      setSelectedParticipantIds(new Set());
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

  async function handleSend(mode: ParticipantInvitationMode) {
    if (selectedReadyCount === 0) {
      setMessage("Selectează cel puțin o persoană cu sarcini salvate înainte de trimitere.");
      return;
    }
    const participantIds = selectedRows
      .filter((row) => row.totalTasks > 0)
      .map((row) => row.participant.id);
    await dispatchInvitations(mode, participantIds, "Selectează cel puțin o persoană cu sarcini salvate înainte de trimitere.");
  }

  async function handleSendAll(mode: ParticipantInvitationMode) {
    const participantIds = rows.filter((row) => row.totalTasks > 0).map((row) => row.participant.id);
    await dispatchInvitations(mode, participantIds, "Nu există persoane cu sarcini salvate pentru trimitere.");
  }

  async function handleResend(participantId: string) {
    setSendingMode("resend");
    setMessage(null);
    setCopiedParticipantId(null);
    try {
      if (!canUseProjectActions) {
        setMessage("Alege un proiect înainte de retrimitere.");
        return;
      }
      const result = await resendParticipantInvitation(companyId, participantId, selectedProjectId);
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
        <ProjectScopeSelector
          companyId={companyId}
          projects={projects}
          selectedProjectId={selectedProjectId}
        />
        <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_26rem]">
          <div className="p-5 md:p-6">
            <p className="text-sm font-semibold text-burgundy/75">
              {selectedProject ? "Invitații proiect" : "Invitații companie"}
            </p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">Status invitații pentru {companyName}</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/62">
              {selectedProject
                ? `Lucrezi pe proiectul ${selectedProject.name}. Vezi cine are invitația activă, cine și-a creat contul și câte sarcini are în proiect.`
                : "Vezi cine are invitația activă, cine și-a creat contul, câte sarcini are și ce trebuie urmărit."}
            </p>
            <div className="mt-4 grid gap-2 sm:grid-cols-4">
              <InviteSummary label="Invitații active" value={activeInvites} />
              <InviteSummary label="Conturi create" value={signedUpCount} />
              <InviteSummary label="Completate" value={completedCount} />
              <InviteSummary label="Blocaje" value={blockedCount} />
            </div>
          </div>
          <div className="space-y-3 border-t border-[var(--border)] bg-surface-muted/45 p-5 md:p-6 lg:border-l lg:border-t-0">
            <div className="rounded-xl border border-[var(--border)] bg-background/70 px-3 py-2.5">
              <p className="text-xs font-semibold text-foreground/48">Selecție pentru trimitere</p>
              <p className="mt-1 text-lg font-semibold text-foreground">
                {selectedReadyCount} persoane cu sarcini
              </p>
            </div>
            <button
              type="button"
              onClick={() => void handleSend("secure_links")}
              disabled={!canUseProjectActions || sendingMode !== null || selectedReadyCount === 0}
              className="tap-soft w-full rounded-xl bg-burgundy px-4 py-3 text-sm font-bold text-white shadow-sm shadow-burgundy/10 hover:bg-burgundy-700 disabled:cursor-not-allowed disabled:opacity-45"
            >
              {sendingMode === "secure_links" ? "Se generează linkurile..." : "Generează linkuri securizate"}
            </button>
            <button
              type="button"
              onClick={() => void handleSend("email")}
              disabled={!canUseProjectActions || sendingMode !== null || selectedReadyCount === 0}
              className="tap-soft w-full rounded-xl border border-[var(--border)] bg-background px-4 py-3 text-sm font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy disabled:cursor-not-allowed disabled:opacity-45"
            >
              {sendingMode === "email" ? "Se trimit emailurile..." : "Trimite email invitații"}
            </button>
            <p className="text-xs leading-5 text-foreground/52">
              Trimiterea folosește doar persoanele bifate în tabel și sarcinile din proiectul selectat. Persoanele fără sarcini salvate nu pot fi selectate.
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
        <div className="flex flex-col gap-3 border-b border-[var(--border)] bg-surface-muted/35 px-5 py-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm font-semibold text-burgundy/75">Pregătire sarcini</p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">Asignări înainte de trimitere</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-foreground/58">
              Generează și salvează planul implicit doar când trebuie să ajustezi sarcinile. Pentru trimitere rapidă folosește tabul Persoane invitate.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowAdvancedAssignments((current) => !current)}
            className="tap-soft rounded-xl border border-[var(--border)] bg-background px-4 py-2.5 text-sm font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy"
          >
            {showAdvancedAssignments ? "Ascunde avansat" : "Configurează asignări avansat"}
          </button>
        </div>
        {showAdvancedAssignments ? (
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
                disabled={!canUseProjectActions || planLoading || participants.length === 0}
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
              <>
                <AssignmentPlanList
                  groups={planGroups}
                  selectedKeys={selectedPlanKeys}
                  onToggleItem={togglePlanItem}
                  onToggleScope={togglePlanScope}
                />
                <AssignmentMatrix assignments={plan.assignments} selectedKeys={selectedPlanKeys} />
              </>
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
        ) : null}
      </section>

      <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
        <div className="border-b border-[var(--border)] px-5 py-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-semibold text-burgundy/75">Urmărire</p>
              <h2 className="mt-1 text-xl font-semibold text-foreground">Persoane invitate</h2>
              <p className="mt-2 text-sm text-foreground/58">
                Bifează destinatarii înainte de a genera linkuri sau emailuri.
              </p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <button
                type="button"
                onClick={() => void handleSendAll("email")}
                disabled={!canUseProjectActions || sendingMode !== null || rows.every((row) => row.totalTasks === 0)}
                className="tap-soft rounded-xl bg-burgundy px-3 py-2 text-xs font-bold text-white hover:bg-burgundy-700 disabled:cursor-not-allowed disabled:opacity-45"
              >
                {sendingMode === "email" ? "Se trimit..." : "Trimite email tuturor"}
              </button>
              <button
                type="button"
                onClick={() => void handleSendAll("secure_links")}
                disabled={!canUseProjectActions || sendingMode !== null || rows.every((row) => row.totalTasks === 0)}
                className="tap-soft rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy disabled:cursor-not-allowed disabled:opacity-45"
              >
                {sendingMode === "secure_links" ? "Se generează..." : "Generează linkuri tuturor"}
              </button>
              <button
                type="button"
                onClick={selectReadyUnsentParticipants}
                className="tap-soft rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy"
              >
                Selectează netrimiși
              </button>
              <button
                type="button"
                onClick={() => setSelectedParticipantIds(new Set())}
                disabled={selectedParticipantIds.size === 0}
                className="tap-soft rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy disabled:cursor-not-allowed disabled:opacity-45"
              >
                Curăță selecția
              </button>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <FilterButton active={invitationFilter === "all"} onClick={() => setInvitationFilter("all")}>
              Toți ({rows.length})
            </FilterButton>
            <FilterButton active={invitationFilter === "ready"} onClick={() => setInvitationFilter("ready")}>
              Netrimiși ({rows.filter((row) => matchesInvitationFilter(row, "ready")).length})
            </FilterButton>
            <FilterButton active={invitationFilter === "errors"} onClick={() => setInvitationFilter("errors")}>
              Erori ({rows.filter((row) => matchesInvitationFilter(row, "errors")).length})
            </FilterButton>
            <FilterButton active={invitationFilter === "no_assignments"} onClick={() => setInvitationFilter("no_assignments")}>
              Fără sarcini ({participantsWithoutAssignments})
            </FilterButton>
            <FilterButton active={invitationFilter === "not_signed_up"} onClick={() => setInvitationFilter("not_signed_up")}>
              Fără cont ({rows.filter((row) => matchesInvitationFilter(row, "not_signed_up")).length})
            </FilterButton>
          </div>
          <p className="mt-3 text-xs font-semibold text-foreground/50">
            {visibleSelectedCount} selectate în filtrul curent · {selectedReadyCount} pregătite pentru trimitere
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-surface-muted text-xs font-semibold uppercase tracking-[0.1em] text-foreground/50">
              <tr>
                <th className="w-12 px-5 py-3">
                  <input
                    aria-label="Selectează persoanele vizibile"
                    type="checkbox"
                    checked={allVisibleSelected}
                    disabled={selectableRows.length === 0}
                    onChange={(event) => setVisibleParticipantSelection(event.target.checked)}
                    className="h-4 w-4 rounded border-[var(--border)] accent-[#890505]"
                  />
                </th>
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
                  <td colSpan={7} className="px-5 py-6 text-center text-foreground/62">
                    Nu există persoane în lista de participanți.
                  </td>
                </tr>
              ) : filteredRows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-5 py-6 text-center text-foreground/62">
                    Nu există persoane pentru filtrul ales.
                  </td>
                </tr>
              ) : (
                filteredRows.map((row) => (
                  <tr key={row.participant.id} className="align-top transition-colors hover:bg-surface-muted/40">
                    <td className="px-5 py-4">
                      <input
                        aria-label={`Selectează ${row.participant.full_name}`}
                        type="checkbox"
                        checked={selectedParticipantIds.has(row.participant.id)}
                        disabled={row.totalTasks === 0 || sendingMode !== null}
                        onChange={() => toggleParticipantSelection(row.participant.id)}
                        className="h-4 w-4 rounded border-[var(--border)] accent-[#890505] disabled:cursor-not-allowed disabled:opacity-35"
                      />
                    </td>
                    <td className="px-5 py-4">
                      <p className="font-semibold text-foreground">{formatParticipantIdentity(row.participant)}</p>
                      <p className="mt-1 text-xs text-foreground/50">{row.participant.email}</p>
                    </td>
                    <td className="px-5 py-4">
                      <div className="space-y-1">
                        <StatusPill tone={row.deliveryTone} active={row.deliveryTone === "success"}>{row.deliveryLabel}</StatusPill>
                        {row.secureLinkExpiresAt ? (
                          <p className="text-xs font-semibold text-foreground/45">
                            Expiră: {formatDateTime(row.secureLinkExpiresAt)}
                          </p>
                        ) : null}
                      </div>
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

function AssignmentMatrix({
  assignments,
  selectedKeys,
}: {
  assignments: CompanyAssignmentPlanItem[];
  selectedKeys: Set<string>;
}) {
  return (
    <details className="mt-4 overflow-hidden rounded-2xl border border-[var(--border)] bg-background/70">
      <summary className="cursor-pointer px-4 py-3 text-sm font-bold text-foreground hover:bg-surface-muted/45">
        Vezi matricea completă de asignări
      </summary>
      <div className="max-h-80 overflow-auto border-t border-[var(--border)]">
        <table className="min-w-full text-left text-xs">
          <thead className="sticky top-0 bg-surface-muted text-foreground/55">
            <tr>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Respondent</th>
              <th className="px-4 py-2">Chestionar</th>
              <th className="px-4 py-2">Țintă</th>
              <th className="px-4 py-2">Grup</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {assignments.map((assignment) => (
              <tr key={assignment.key} className="hover:bg-surface-muted/35">
                <td className="px-4 py-2 font-semibold">
                  {assignment.existing_assignment_id ? "Salvat" : selectedKeys.has(assignment.key) ? "Bifat" : "Nebifat"}
                </td>
                <td className="px-4 py-2">{assignment.respondent_name}</td>
                <td className="px-4 py-2">{formatQuestionnaireLabel(assignment.questionnaire_key)}</td>
                <td className="px-4 py-2">{formatPlanTarget(assignment)}</td>
                <td className="px-4 py-2">{assignment.scope_name}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function matchesInvitationFilter(row: ParticipantInviteRow, filter: InvitationFilter): boolean {
  if (filter === "ready") return row.totalTasks > 0 && row.deliveryTone !== "success";
  if (filter === "errors") return row.deliveryTone === "danger";
  if (filter === "no_assignments") return row.totalTasks === 0;
  if (filter === "not_signed_up") return !row.signedUp;
  return true;
}

function ProjectScopeSelector({
  companyId,
  projects,
  selectedProjectId,
}: {
  companyId: string;
  projects: CompanyProject[];
  selectedProjectId: string | null;
}) {
  function handleChange(value: string) {
    const suffix = value ? `?projectId=${encodeURIComponent(value)}` : "";
    window.location.href = `/trainer/companies/${companyId}/invitations${suffix}`;
  }

  return (
    <div className="border-b border-[var(--border)] bg-surface-muted/35 px-5 py-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-semibold text-burgundy/75">Proiect curent</p>
          <p className="mt-1 text-sm font-semibold text-foreground">
            {selectedProjectId
              ? projects.find((project) => project.id === selectedProjectId)?.name
              : projects.length > 0
                ? "Alege un proiect pentru planificare și trimitere"
                : "Fără proiecte create încă"}
          </p>
        </div>
        <select
          value={selectedProjectId ?? ""}
          onChange={(event) => handleChange(event.target.value)}
          className="min-h-10 rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-sm font-semibold text-foreground outline-none hover:border-burgundy/45 focus:border-burgundy/45"
        >
          <option value="">Toată compania</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

function formatResendMessage(result: RosterInviteResult): string {
  if (result.email_sent) return `Email retrimis către ${result.email}.`;
  if (result.error) return `Emailul nu a fost retrimis către ${result.email}: ${result.error}`;
  if (result.invite_url) return `Link pregătit pentru ${result.email}.`;
  return `Invitația nu a fost retrimisă către ${result.email}.`;
}

function formatParticipantIdentity(participant: CompanyParticipant): string {
  const anonymousName = participant.anonymous_name ?? "Anonim";
  return `${anonymousName} (${participant.full_name})`;
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "dată indisponibilă";
  return new Intl.DateTimeFormat("ro-RO", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
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
        aria-label={`Selectează asignarea pentru ${assignment.respondent_name}`}
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
        <p className="font-semibold text-foreground">{formatQuestionnaireLabel(assignment.questionnaire_key)}</p>
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

function formatQuestionnaireLabel(key: string): string {
  return questionnaireLabels[key] ?? key.replaceAll("_", " ");
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

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "tap-soft rounded-full border px-3 py-1.5 text-xs font-bold transition-colors",
        active
          ? "border-burgundy bg-burgundy text-white"
          : "border-[var(--border)] bg-background text-foreground/68 hover:border-burgundy/45 hover:text-burgundy",
      ].join(" ")}
    >
      {children}
    </button>
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
    return `${formatQuestionnaireLabel(assignment.questionnaire_key)} · despre ${targetName ?? "persoană"}`;
  }
  if (assignment.target_type === "team") {
    const teamName = assignment.target_team_id ? teamsById.get(assignment.target_team_id)?.name : null;
    return `${formatQuestionnaireLabel(assignment.questionnaire_key)} · echipa ${teamName ?? "selectată"}`;
  }
  return `${formatQuestionnaireLabel(assignment.questionnaire_key)} · autoevaluare`;
}

function StatusPill({
  tone,
  active = false,
  children,
}: {
  tone: ParticipantInviteRow["deliveryTone"];
  active?: boolean;
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

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold ${className}`}>
      {active ? <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.85)]" aria-hidden="true" /> : null}
      {children}
    </span>
  );
}
