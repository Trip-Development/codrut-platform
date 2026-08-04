"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CalendarDaysIcon,
  CheckCircle2Icon,
  ChevronDownIcon,
  LinkIcon,
  Loader2Icon,
  MailIcon,
  RefreshCwIcon,
  SendIcon,
} from "lucide-react";

import {
  getAssessmentCycles,
  getCompanyAssignments,
  getCompanyInvitationStatuses,
  hasPermanentParticipantAccount,
  resendParticipantInvitation,
  sendParticipantInvitations,
  type AssessmentCycle,
  type CompanyAssignment,
  type CompanyParticipant,
  type CompanyProject,
  type CompanyTeam,
  type ParticipantInvitationMode,
  type ParticipantInvitationStatus,
  type RosterInviteResult,
} from "@/api/companies";
import {
  getEmailSendCapacity,
  type EmailSendCapacity,
} from "@/api/email";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SelectControl } from "@/components/ui/select-control";
import { useUrlState } from "@/hooks/use-url-state";
import { cn } from "@/utils/cn";
import { formatRomanianDateTime } from "@/utils/date-format";

export type InvitationDeliveryWorkspaceProps = {
  companyId: string;
  companyName: string;
  projects: CompanyProject[];
  selectedProjectId: string | null;
  participants: CompanyParticipant[];
  assignments: CompanyAssignment[];
  invitationStatuses: ParticipantInvitationStatus[];
  teams: CompanyTeam[];
  initialAssessmentCycles?: AssessmentCycle[];
  initialSelectedCycleId?: string | null;
  showProjectSelector?: boolean;
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
  deliveryState: "none" | "ready" | "pending" | "success" | "danger";
  deliveryError: string | null;
  secureLinkUrl: string | null;
  secureLinkExpiresAt: string | null;
  nextAction: string;
};

type InvitationFilter = "all" | "ready" | "errors" | "no_assignments" | "not_signed_up";
type InvitationPendingAction =
  | "selected-email"
  | "unsent-email"
  | "all-email"
  | "selected-links"
  | "all-links"
  | "resend";

const completedStatuses = new Set(["submitted", "validated", "scored"]);
const activeInviteStatuses = new Set(["invited", "started", "submitted", "validated", "scored"]);
const persistedEmailStates: Record<
  string,
  Pick<ParticipantInviteRow, "deliveryLabel" | "deliveryTone" | "deliveryState">
> = {
  queued: {
    deliveryLabel: "Email în coadă",
    deliveryTone: "warning",
    deliveryState: "pending",
  },
  dispatching: {
    deliveryLabel: "Trimitere în curs",
    deliveryTone: "warning",
    deliveryState: "pending",
  },
  accepted: {
    deliveryLabel: "Acceptat de furnizor",
    deliveryTone: "success",
    deliveryState: "success",
  },
  delivered: {
    deliveryLabel: "Email livrat",
    deliveryTone: "success",
    deliveryState: "success",
  },
  opened: {
    deliveryLabel: "Email deschis",
    deliveryTone: "success",
    deliveryState: "success",
  },
  clicked: {
    deliveryLabel: "Link accesat",
    deliveryTone: "success",
    deliveryState: "success",
  },
  indeterminate: {
    deliveryLabel: "Livrare neconfirmată",
    deliveryTone: "danger",
    deliveryState: "danger",
  },
  cancelled: {
    deliveryLabel: "Trimitere anulată",
    deliveryTone: "danger",
    deliveryState: "danger",
  },
  failed: {
    deliveryLabel: "Trimitere eșuată",
    deliveryTone: "danger",
    deliveryState: "danger",
  },
  bounced: {
    deliveryLabel: "Email respins",
    deliveryTone: "danger",
    deliveryState: "danger",
  },
};
const questionnaireLabels: Record<string, string> = {
  lencioni: "Lencioni - evaluare echipă",
  lencioni_en: "Lencioni - evaluare echipă",
  distress_drivers: "Driveri de stres TA",
  distress_drivers_en: "Driveri de stres TA",
  boss_360: "iCARE 360 pentru manager",
  icare: "Feedback 360 iCARE",
  pcm_base: "Baza și faza PCM",
};

function normalizeInvitationFilter(value: string | null): InvitationFilter {
  if (
    value === "ready" ||
    value === "errors" ||
    value === "no_assignments" ||
    value === "not_signed_up"
  ) {
    return value;
  }
  return "all";
}

export function buildInvitationRows(
  participants: CompanyParticipant[],
  assignments: CompanyAssignment[],
  invitationStatuses: ParticipantInvitationStatus[],
  resultsByParticipant: Map<string, RosterInviteResult>,
  assessmentCycleId?: string | null,
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
    const immediateResult = resultsByParticipant.get(invitationIdentity(assessmentCycleId, participant.id))
      ?? resultsByParticipant.get(participant.id);
    const persistedEmailState = persistedStatus?.latest_email_status
      ? persistedEmailStates[persistedStatus.latest_email_status]
      : undefined;
    const result = immediateResult?.email_queued && persistedEmailState
      && persistedStatus?.latest_email_status !== "queued"
      && persistedStatus?.latest_email_status !== "dispatching"
      ? undefined
      : immediateResult;
    const completedTasks = participantAssignments.filter((assignment) =>
      completedStatuses.has(assignment.status),
    ).length;
    const totalTasks = participantAssignments.length;
    const signedUp = hasPermanentParticipantAccount(participant);
    const secureLinkUrl = result?.invite_url ?? persistedStatus?.active_secure_link_url ?? null;
    const secureLinkExpiresAt = persistedStatus?.active_secure_link_expires_at ?? null;
    let deliveryError = result
      ? result.error
      : persistedStatus?.latest_email_error ?? null;
    let deliveryLabel = "Fără asignări";
    let deliveryTone: ParticipantInviteRow["deliveryTone"] = "default";
    let deliveryState: ParticipantInviteRow["deliveryState"] = "none";

    if (result?.error) {
      deliveryLabel = "Trimitere eșuată";
      deliveryTone = "danger";
      deliveryState = "danger";
    } else if (result?.email_queued) {
      deliveryLabel = "Email în coadă";
      deliveryTone = "warning";
      deliveryState = "pending";
    } else if (result?.email_sent) {
      deliveryLabel = "Acceptat de furnizor";
      deliveryTone = "success";
      deliveryState = "success";
    } else if (result?.delivery_mode === "secure_links") {
      deliveryLabel = "Link securizat generat";
      deliveryTone = "success";
      deliveryState = "success";
    } else if (result) {
      deliveryLabel = "Livrare neconfirmată";
      deliveryTone = "danger";
      deliveryState = "danger";
      deliveryError = "Verifică starea livrării înainte de retrimitere.";
    } else if (persistedStatus?.latest_email_status) {
      if (persistedEmailState) {
        ({ deliveryLabel, deliveryTone, deliveryState } = persistedEmailState);
        if (deliveryState !== "danger") {
          deliveryError = null;
        }
        if (persistedStatus.latest_email_status === "indeterminate" && !deliveryError) {
          deliveryError = "Verifică starea livrării înainte de retrimitere.";
        }
      } else {
        deliveryLabel = "Stare de livrare necunoscută";
        deliveryTone = "danger";
        deliveryState = "danger";
        deliveryError ??= "Reîncarcă pagina sau verifică livrarea înainte de retrimitere.";
      }
    } else if (persistedStatus?.has_active_secure_link) {
      deliveryLabel = "Link securizat activ";
      deliveryTone = "success";
      deliveryState = "success";
    } else if (participantAssignments.some((assignment) => activeInviteStatuses.has(assignment.status))) {
      deliveryLabel = "Invitație activă";
      deliveryTone = "success";
      deliveryState = "success";
    } else if (totalTasks > 0) {
      deliveryLabel = "Pregătit, netrimis";
      deliveryTone = "warning";
      deliveryState = "ready";
    }

    const nextAction =
      totalTasks === 0
        ? "Adaugă asignări"
        : completedTasks === totalTasks
          ? "Raport disponibil"
          : deliveryState === "pending"
            ? "În curs de trimitere"
            : deliveryState === "success"
              ? "În progres"
              : deliveryState === "danger"
                ? "Verifică livrarea"
                : "Trimite invitația";

    return {
      participant,
      assignments: participantAssignments,
      totalTasks,
      completedTasks,
      completionLabel: totalTasks > 0 ? `${completedTasks}/${totalTasks}` : "0/0",
      signedUp,
      deliveryLabel,
      deliveryTone,
      deliveryState,
      deliveryError,
      secureLinkUrl,
      secureLinkExpiresAt,
      nextAction,
    };
  });
}

function invitationIdentity(assessmentCycleId: string | null | undefined, participantId: string): string {
  return `${assessmentCycleId ?? "legacy"}:${participantId}`;
}

export function InvitationDeliveryWorkspace({
  companyId,
  companyName,
  projects,
  selectedProjectId,
  participants,
  assignments,
  invitationStatuses,
  teams,
  initialAssessmentCycles = [],
  initialSelectedCycleId = null,
  showProjectSelector = true,
}: InvitationDeliveryWorkspaceProps) {
  const { get, searchKey, setParam } = useUrlState();
  const invitationSendingRef = useRef(false);
  const initialCycleId = initialSelectedCycleId ?? assignments[0]?.assessment_cycle_id ?? null;
  const [assessmentCycles, setAssessmentCycles] = useState<AssessmentCycle[]>(initialAssessmentCycles);
  const [loadedCyclesProjectId, setLoadedCyclesProjectId] = useState<string | null>(
    selectedProjectId && initialAssessmentCycles.every((cycle) => cycle.project_id === selectedProjectId)
      ? selectedProjectId
      : null,
  );
  const [selectedCycleId, setSelectedCycleId] = useState<string | null>(
    initialCycleId ?? get("cycle"),
  );
  const [cyclesLoading, setCyclesLoading] = useState(false);
  const [cycleDataLoading, setCycleDataLoading] = useState(false);
  const [loadedCycleScope, setLoadedCycleScope] = useState<string | null>(
    selectedProjectId && initialCycleId && initialAssessmentCycles.some((cycle) => cycle.id === initialCycleId)
      ? `${selectedProjectId}:${initialCycleId}`
      : null,
  );
  const [assignmentState, setAssignmentState] = useState(assignments);
  const [invitationStatusState, setInvitationStatusState] = useState(invitationStatuses);
  const [resultsByParticipant, setResultsByParticipant] = useState(
    new Map<string, RosterInviteResult>(),
  );
  const [message, setMessage] = useState<string | null>(null);
  const [emailCapacity, setEmailCapacity] = useState<EmailSendCapacity | null>(null);
  const [sendingMode, setSendingMode] = useState<ParticipantInvitationMode | "resend" | null>(null);
  const [pendingInviteAction, setPendingInviteAction] = useState<InvitationPendingAction | null>(null);
  const [resendingParticipantId, setResendingParticipantId] = useState<string | null>(null);
  const [copiedParticipantId, setCopiedParticipantId] = useState<string | null>(null);
  const [selectedParticipantIds, setSelectedParticipantIds] = useState<Set<string>>(new Set());
  const [expandedTaskParticipantIds, setExpandedTaskParticipantIds] = useState<Set<string>>(new Set());
  const [invitationFilter, setInvitationFilterState] = useState<InvitationFilter>(
    normalizeInvitationFilter(get("filter")),
  );
  const cycleScopeKey = `${selectedProjectId ?? "company"}:${selectedCycleId ?? "legacy"}`;
  const cycleScopeReady = !selectedProjectId
    || Boolean(selectedCycleId && loadedCycleScope === cycleScopeKey && !cycleDataLoading);
  const selectedCycle = assessmentCycles.find((cycle) => cycle.id === selectedCycleId) ?? null;
  const deliveryEnabled = !selectedProjectId || selectedCycle?.status !== "closed";
  const refreshEmailCapacity = useCallback(async () => {
    try {
      const capacity = await getEmailSendCapacity();
      setEmailCapacity(capacity);
      return capacity;
    } catch {
      setEmailCapacity(null);
      return null;
    }
  }, []);

  useEffect(() => {
    setAssignmentState(assignments);
  }, [assignments]);

  useEffect(() => {
    setInvitationStatusState(invitationStatuses);
  }, [invitationStatuses]);

  useEffect(() => {
    void refreshEmailCapacity();
    const refreshOnFocus = () => void refreshEmailCapacity();
    window.addEventListener("focus", refreshOnFocus);
    return () => window.removeEventListener("focus", refreshOnFocus);
  }, [refreshEmailCapacity]);

  useEffect(() => {
    let cancelled = false;
    if (!selectedProjectId) {
      setAssessmentCycles([]);
      setSelectedCycleId(null);
      setLoadedCyclesProjectId(null);
      setLoadedCycleScope(null);
      return;
    }
    if (loadedCyclesProjectId === selectedProjectId) return;

    setCyclesLoading(true);
    getAssessmentCycles(companyId, selectedProjectId)
      .then((cycles) => {
        if (cancelled) return;
        const sorted = [...cycles].sort((left, right) => left.sequence - right.sequence);
        setAssessmentCycles(sorted);
        setLoadedCyclesProjectId(selectedProjectId);
        const requestedId = get("cycle");
        const requested = sorted.find((cycle) => cycle.id === requestedId);
        const preferred = requested
          ?? [...sorted].reverse().find((cycle) => cycle.status !== "closed")
          ?? sorted.at(-1)
          ?? null;
        setSelectedCycleId(preferred?.id ?? null);
        if (preferred && requestedId !== preferred.id) {
          setParam("cycle", preferred.id, "replace");
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setAssessmentCycles([]);
          setSelectedCycleId(null);
          setLoadedCycleScope(null);
          setMessage(error instanceof Error ? error.message : "Evaluările nu au putut fi încărcate.");
        }
      })
      .finally(() => {
        if (!cancelled) setCyclesLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [companyId, get, loadedCyclesProjectId, selectedProjectId, setParam]);

  useEffect(() => {
    const requestedId = get("cycle");
    if (!requestedId || !assessmentCycles.some((cycle) => cycle.id === requestedId)) return;
    setSelectedCycleId(requestedId);
  }, [assessmentCycles, get, searchKey]);

  useEffect(() => {
    let cancelled = false;
    if (!selectedProjectId || !selectedCycleId) {
      setLoadedCycleScope(null);
      return;
    }

    const requestedScope = `${selectedProjectId}:${selectedCycleId}`;
    if (loadedCycleScope === requestedScope) return;

    setCycleDataLoading(true);
    setLoadedCycleScope(null);
    setAssignmentState([]);
    setInvitationStatusState([]);
    Promise.all([
      getCompanyAssignments(companyId, {}, {
        projectId: selectedProjectId,
        assessmentCycleId: selectedCycleId,
      }),
      getCompanyInvitationStatuses(companyId, {}, {
        projectId: selectedProjectId,
        assessmentCycleId: selectedCycleId,
      }),
    ])
      .then(([nextAssignments, nextStatuses]) => {
        if (cancelled) return;
        setAssignmentState(nextAssignments);
        setInvitationStatusState(nextStatuses);
        setLoadedCycleScope(requestedScope);
        setMessage(null);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setMessage(error instanceof Error ? error.message : "Evaluarea nu a putut fi încărcată.");
        }
      })
      .finally(() => {
        if (!cancelled) setCycleDataLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [companyId, loadedCycleScope, selectedCycleId, selectedProjectId]);

  useEffect(() => {
    setInvitationFilterState(normalizeInvitationFilter(get("filter")));
  }, [get, searchKey]);

  useEffect(() => {
    setSelectedParticipantIds(new Set());
    setResultsByParticipant(new Map());
    setCopiedParticipantId(null);
    setExpandedTaskParticipantIds(new Set());
    setMessage(null);
  }, [cycleScopeKey]);

  const rows = useMemo(
    () => buildInvitationRows(
      participants,
      assignmentState,
      invitationStatusState,
      resultsByParticipant,
      selectedCycleId,
    ),
    [assignmentState, invitationStatusState, participants, resultsByParticipant, selectedCycleId],
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
  const teamsById = useMemo(() => new Map(teams.map((team) => [team.id, team])), [teams]);
  const hasProjects = projects.length > 0;
  const canUseProjectActions = !hasProjects || selectedProjectId !== null;
  const allVisibleSelected =
    selectableRows.length > 0 &&
    selectableRows.every((row) => selectedParticipantIds.has(row.participant.id));
  const readyCount = rows.filter((row) => matchesInvitationFilter(row, "ready")).length;
  const readyEmailCount = rows.filter(
    (row) => matchesInvitationFilter(row, "ready") && Boolean(row.participant.email),
  ).length;
  const allEmailCount = rows.filter(
    (row) => row.totalTasks > 0 && Boolean(row.participant.email),
  ).length;
  const selectedEmailCount = selectedRows.filter(
    (row) => row.totalTasks > 0 && Boolean(row.participant.email),
  ).length;
  const errorCount = rows.filter((row) => matchesInvitationFilter(row, "errors")).length;
  const noAssignmentCount = rows.filter((row) => row.totalTasks === 0).length;
  const currentOperation = getCurrentOperation(
    pendingInviteAction,
    selectedReadyCount,
    resendingParticipantId
      ? participantsById.get(resendingParticipantId)?.full_name ?? null
      : null,
  );

  function selectAssessmentCycle(assessmentCycleId: string) {
    if (assessmentCycleId === selectedCycleId) return;
    setAssignmentState([]);
    setInvitationStatusState([]);
    setLoadedCycleScope(null);
    setSelectedCycleId(assessmentCycleId);
    setParam("cycle", assessmentCycleId, "push");
  }

  async function refreshAssessmentCycles() {
    if (!selectedProjectId) return;
    try {
      const cycles = await getAssessmentCycles(companyId, selectedProjectId);
      setAssessmentCycles([...cycles].sort((left, right) => left.sequence - right.sequence));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Starea evaluării nu a putut fi actualizată.");
    }
  }

  async function refreshInvitationStatuses() {
    if (!selectedProjectId || !selectedCycleId) return;
    try {
      const statuses = await getCompanyInvitationStatuses(companyId, {}, {
        projectId: selectedProjectId,
        assessmentCycleId: selectedCycleId,
      });
      setInvitationStatusState(statuses);
      setMessage("Starea livrării a fost actualizată.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Starea livrării nu a putut fi actualizată.");
    }
  }

  function setInvitationFilter(filter: InvitationFilter) {
    setInvitationFilterState(filter);
    setParam("filter", filter === "all" ? null : filter, "push");
  }

  function toggleTaskDetails(participantId: string) {
    setExpandedTaskParticipantIds((current) => {
      const next = new Set(current);
      if (next.has(participantId)) next.delete(participantId);
      else next.add(participantId);
      return next;
    });
  }

  function toggleParticipantSelection(participantId: string) {
    setSelectedParticipantIds((current) => {
      const next = new Set(current);
      if (next.has(participantId)) next.delete(participantId);
      else next.add(participantId);
      return next;
    });
  }

  function setVisibleParticipantSelection(checked: boolean) {
    setSelectedParticipantIds((current) => {
      const next = new Set(current);
      for (const row of selectableRows) {
        if (checked) next.add(row.participant.id);
        else next.delete(row.participant.id);
      }
      return next;
    });
  }

  function selectReadyUnsentParticipants() {
    setInvitationFilter("ready");
    setSelectedParticipantIds(
      new Set(
        rows
          .filter((row) => matchesInvitationFilter(row, "ready"))
          .map((row) => row.participant.id),
      ),
    );
  }

  function plannedEmailRecipientCount(
    participantIds: string[] | undefined,
    targetMode: "unsent" | "selected" | "all",
  ): number {
    const selectedIds = participantIds ? new Set(participantIds) : null;
    return rows.filter((row) => {
      if (!row.participant.email || row.totalTasks === 0) return false;
      if (targetMode === "unsent") return row.deliveryState === "ready";
      return selectedIds === null || selectedIds.has(row.participant.id);
    }).length;
  }

  async function dispatchInvitations(
    mode: ParticipantInvitationMode,
    participantIds: string[] | undefined,
    emptyMessage: string,
    targetMode: "unsent" | "selected" | "all" = participantIds?.length ? "selected" : "unsent",
    pendingAction: InvitationPendingAction = mode === "email" ? "unsent-email" : "selected-links",
  ) {
    if (invitationSendingRef.current) return;
    if (participantIds?.length === 0) {
      setMessage(emptyMessage);
      return;
    }
    if (!canUseProjectActions) {
      setMessage("Alege un proiect înainte de trimitere.");
      return;
    }
    if (selectedProjectId && (!selectedCycleId || !cycleScopeReady)) {
      setMessage("Așteaptă încărcarea evaluării selectate înainte de trimitere.");
      return;
    }
    if (!deliveryEnabled) {
      setMessage("Evaluările închise sunt disponibile doar pentru consultare.");
      return;
    }

    invitationSendingRef.current = true;
    if (mode === "email") {
      const capacity = await refreshEmailCapacity();
      if (capacity === null) {
        invitationSendingRef.current = false;
        setMessage("Nu am putut verifica limita de trimitere. Reîncearcă înainte să pornești invitațiile.");
        return;
      }
      const plannedCount = plannedEmailRecipientCount(participantIds, targetMode);
      if (plannedCount > capacity.remaining_today) {
        invitationSendingRef.current = false;
        setMessage(
          `Mai sunt disponibile ${capacity.remaining_today} emailuri astăzi, iar această trimitere are ${plannedCount}. Redu selecția și încearcă din nou.`,
        );
        return;
      }
    }
    setSendingMode(mode);
    setPendingInviteAction(pendingAction);
    setMessage(null);
    setCopiedParticipantId(null);
    try {
      const result = await sendParticipantInvitations(companyId, {
        mode,
        participantIds,
        projectId: selectedProjectId,
        ...(selectedProjectId && selectedCycleId ? { assessmentCycleId: selectedCycleId } : {}),
        targetMode,
      });
      setResultsByParticipant((current) => {
        const next = new Map(current);
        for (const item of result.results) {
          next.set(invitationIdentity(selectedCycleId, item.participant_id), item);
        }
        return next;
      });
      setSelectedParticipantIds(new Set());
      setMessage(
        mode === "email"
          ? formatEmailBatchMessage(result)
          : `${result.links_generated}/${result.total} linkuri securizate generate.`,
      );
      await Promise.all([
        refreshAssessmentCycles(),
        mode === "email" ? refreshEmailCapacity() : Promise.resolve(null),
      ]);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Invitațiile nu au putut fi trimise.");
    } finally {
      invitationSendingRef.current = false;
      setSendingMode(null);
      setPendingInviteAction(null);
    }
  }

  async function handleSendSelected(mode: ParticipantInvitationMode) {
    if (selectedReadyCount === 0) {
      setMessage("Selectează cel puțin o persoană cu asignări salvate.");
      return;
    }
    await dispatchInvitations(
      mode,
      selectedRows.filter((row) => row.totalTasks > 0).map((row) => row.participant.id),
      "Selectează cel puțin o persoană cu asignări salvate.",
      "selected",
      mode === "email" ? "selected-email" : "selected-links",
    );
  }

  async function handleSendAll(mode: ParticipantInvitationMode) {
    const participantIds = rows
      .filter((row) => row.totalTasks > 0)
      .map((row) => row.participant.id);
    if (participantIds.length === 0) {
      setMessage("Nu există persoane cu asignări salvate.");
      return;
    }
    await dispatchInvitations(
      mode,
      mode === "email" ? undefined : participantIds,
      "Nu există persoane cu asignări salvate.",
      mode === "email" ? "unsent" : "selected",
      mode === "email" ? "unsent-email" : "all-links",
    );
  }

  async function handleResend(participantId: string) {
    if (invitationSendingRef.current) return;
    if (!canUseProjectActions) {
      setMessage("Alege un proiect înainte de retrimitere.");
      return;
    }
    if (selectedProjectId && (!selectedCycleId || !cycleScopeReady)) {
      setMessage("Așteaptă încărcarea evaluării selectate înainte de retrimitere.");
      return;
    }
    if (!deliveryEnabled) {
      setMessage("Evaluările închise sunt disponibile doar pentru consultare.");
      return;
    }
    invitationSendingRef.current = true;
    const capacity = await refreshEmailCapacity();
    if (capacity === null || capacity.remaining_today < 1) {
      invitationSendingRef.current = false;
      setMessage(
        capacity === null
          ? "Nu am putut verifica limita de trimitere. Reîncearcă înainte de retrimitere."
          : "Capacitatea de trimitere pentru astăzi a fost folosită.",
      );
      return;
    }
    setSendingMode("resend");
    setPendingInviteAction("resend");
    setResendingParticipantId(participantId);
    setMessage(null);
    setCopiedParticipantId(null);
    try {
      const result = selectedProjectId && selectedCycleId
        ? await resendParticipantInvitation(
            companyId,
            participantId,
            selectedProjectId,
            { assessmentCycleId: selectedCycleId },
          )
        : await resendParticipantInvitation(companyId, participantId, selectedProjectId);
      if (result) {
        setResultsByParticipant((current) => new Map(current).set(
          invitationIdentity(selectedCycleId, result.participant_id),
          result,
        ));
        setMessage(formatResendMessage(result));
      }
      await refreshEmailCapacity();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Invitația nu a putut fi retrimisă.");
    } finally {
      invitationSendingRef.current = false;
      setSendingMode(null);
      setPendingInviteAction(null);
      setResendingParticipantId(null);
    }
  }

  async function handleCopyLink(row: ParticipantInviteRow) {
    if (!row.secureLinkUrl || typeof navigator === "undefined") return;
    try {
      await navigator.clipboard.writeText(row.secureLinkUrl);
      setCopiedParticipantId(row.participant.id);
      setMessage(`Link securizat copiat pentru ${row.participant.full_name}.`);
    } catch {
      setMessage("Linkul nu a putut fi copiat automat.");
    }
  }

  return (
    <div className="flex flex-col gap-4" aria-busy={Boolean(currentOperation)}>
      {currentOperation ? (
        <OperationFeedback title={currentOperation.title} detail={currentOperation.detail} />
      ) : null}
      {message ? <InlineFeedback>{message}</InlineFeedback> : null}

      {assessmentCycles.length > 0 ? (
        <InvitationCycleToolbar
          cycles={assessmentCycles}
          selectedCycleId={selectedCycleId}
          loading={cyclesLoading}
          onSelect={selectAssessmentCycle}
        />
      ) : null}

      <section className="overflow-hidden rounded-lg border border-border bg-surface">
        {showProjectSelector ? (
          <ProjectScopeSelector projects={projects} selectedProjectId={selectedProjectId} />
        ) : null}

        <header className="border-b border-border px-4 py-4 md:px-5">
          <p className="mb-3 w-fit rounded-md border border-border bg-muted px-3 py-2 text-xs font-semibold text-foreground/70">
            {emailCapacity
              ? `${emailCapacity.remaining_today} din ${emailCapacity.daily_cap} emailuri disponibile astăzi`
              : "Verificăm capacitatea de trimitere…"}
          </p>
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <div className="flex min-w-0 items-baseline gap-3">
              <h2 className="text-xl font-semibold text-foreground">Livrare invitații</h2>
              <span className="truncate text-sm text-muted-foreground">{companyName}</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                size="sm"
                onClick={() => void handleSendAll("email")}
                disabled={
                  !deliveryEnabled
                  || !canUseProjectActions
                  || !cycleScopeReady
                  || sendingMode !== null
                  || readyCount === 0
                  || (emailCapacity !== null
                    && readyEmailCount > emailCapacity.remaining_today)
                }
              >
                {pendingInviteAction === "unsent-email" ? (
                  <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" />
                ) : (
                  <MailIcon data-icon="inline-start" aria-hidden="true" />
                )}
                {pendingInviteAction === "unsent-email"
                  ? "Trimitem emailurile"
                  : "Trimite email netrimișilor"}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  const participantIds = rows
                    .filter((row) => row.totalTasks > 0)
                    .map((row) => row.participant.id);
                  void dispatchInvitations(
                    "email",
                    participantIds,
                    "Nu există persoane cu asignări salvate.",
                    "all",
                    "all-email",
                  );
                }}
                disabled={
                  !deliveryEnabled
                  || !canUseProjectActions
                  || !cycleScopeReady
                  || sendingMode !== null
                  || rows.every((row) => row.totalTasks === 0)
                  || (emailCapacity !== null
                    && allEmailCount > emailCapacity.remaining_today)
                }
              >
                <SendIcon data-icon="inline-start" aria-hidden="true" />
                {pendingInviteAction === "all-email" ? "Trimitem tuturor" : "Trimite tuturor"}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void handleSendAll("secure_links")}
                disabled={!deliveryEnabled || !canUseProjectActions || !cycleScopeReady || sendingMode !== null || rows.every((row) => row.totalTasks === 0)}
              >
                <LinkIcon data-icon="inline-start" aria-hidden="true" />
                {pendingInviteAction === "all-links" ? "Generăm linkurile" : "Generează linkuri"}
              </Button>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-end gap-2">
            <Button
              type="button"
              variant="ghost"
              size="xs"
              onClick={() => void refreshInvitationStatuses()}
              disabled={!selectedProjectId || !selectedCycleId || !cycleScopeReady || sendingMode !== null}
            >
              <RefreshCwIcon data-icon="inline-start" aria-hidden="true" />
              Actualizează livrarea
            </Button>
            <SelectControl
              label="Filtru invitații"
              wrapperClassName="order-first w-full md:hidden"
              value={invitationFilter}
              onChange={(event) => setInvitationFilter(event.target.value as InvitationFilter)}
            >
              <option value="all">Toți ({rows.length})</option>
              <option value="ready">Netrimiși ({readyCount})</option>
              <option value="errors">Erori ({errorCount})</option>
              <option value="no_assignments">Fără asignări ({noAssignmentCount})</option>
              <option value="not_signed_up">
                Fără cont ({rows.filter((row) => !row.signedUp).length})
              </option>
            </SelectControl>
            <div className="hidden flex-wrap items-center gap-2 md:flex">
              <FilterButton active={invitationFilter === "all"} onClick={() => setInvitationFilter("all")}>
                Toți {rows.length}
              </FilterButton>
              <FilterButton active={invitationFilter === "ready"} onClick={() => setInvitationFilter("ready")}>
                Netrimiși {readyCount}
              </FilterButton>
              <FilterButton active={invitationFilter === "errors"} onClick={() => setInvitationFilter("errors")}>
                Erori {errorCount}
              </FilterButton>
              <FilterButton
                active={invitationFilter === "no_assignments"}
                onClick={() => setInvitationFilter("no_assignments")}
              >
                Fără asignări {noAssignmentCount}
              </FilterButton>
              <FilterButton
                active={invitationFilter === "not_signed_up"}
                onClick={() => setInvitationFilter("not_signed_up")}
              >
                Fără cont {rows.filter((row) => !row.signedUp).length}
              </FilterButton>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="xs"
              onClick={selectReadyUnsentParticipants}
              disabled={!deliveryEnabled || !cycleScopeReady}
            >
              <CheckCircle2Icon data-icon="inline-start" aria-hidden="true" />
              Selectează netrimiși
            </Button>
          </div>

          {selectedParticipantIds.size > 0 ? (
            <div
              className="mt-4 flex flex-wrap items-center gap-2 rounded-lg bg-muted px-3 py-2"
              role="region"
              aria-label="Acțiuni pentru persoanele selectate"
            >
              <span className="mr-auto text-sm font-semibold text-foreground">
                {selectedReadyCount} selectate
              </span>
              <Button
                type="button"
                size="sm"
                onClick={() => void handleSendSelected("email")}
                disabled={
                  !deliveryEnabled
                  || !cycleScopeReady
                  || sendingMode !== null
                  || selectedReadyCount === 0
                  || (emailCapacity !== null
                    && selectedEmailCount > emailCapacity.remaining_today)
                }
              >
                <MailIcon data-icon="inline-start" aria-hidden="true" />
                {pendingInviteAction === "selected-email" ? "Trimitem emailurile" : "Trimite email invitații"}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void handleSendSelected("secure_links")}
                disabled={!deliveryEnabled || !cycleScopeReady || sendingMode !== null || selectedReadyCount === 0}
              >
                <LinkIcon data-icon="inline-start" aria-hidden="true" />
                {pendingInviteAction === "selected-links" ? "Generăm linkurile" : "Generează linkuri securizate"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setSelectedParticipantIds(new Set())}
              >
                Anulează selecția
              </Button>
            </div>
          ) : null}
        </header>

        <div className="md:overflow-x-auto">
          <table className="block w-full text-left text-sm md:table md:min-w-[920px] xl:min-w-0 xl:table-fixed">
            <thead className="hidden bg-muted text-[11px] font-bold uppercase tracking-[0.08em] text-muted-foreground md:table-header-group">
              <tr>
                <th className="w-12 px-4 py-3">
                  <Checkbox
                    aria-label="Selectează persoanele vizibile"
                    checked={allVisibleSelected}
                    disabled={!deliveryEnabled || !cycleScopeReady || selectableRows.length === 0}
                    onCheckedChange={(checked) => setVisibleParticipantSelection(checked === true)}
                  />
                </th>
                <th className="px-4 py-3">Persoană</th>
                <th className="px-4 py-3">Livrare</th>
                <th className="px-4 py-3">Cont</th>
                <th className="px-4 py-3">Sarcini</th>
                <th className="px-4 py-3">Stare</th>
                <th className="px-4 py-3 text-right">Acțiune</th>
              </tr>
            </thead>
            <tbody className="block divide-y divide-border md:table-row-group">
              {rows.length === 0 ? (
                <EmptyTableRow colSpan={7}>Nu există participanți.</EmptyTableRow>
              ) : filteredRows.length === 0 ? (
                <EmptyTableRow colSpan={7}>Niciun rezultat pentru filtrul ales.</EmptyTableRow>
              ) : (
                filteredRows.map((row) => (
                  <tr
                    key={invitationIdentity(selectedCycleId, row.participant.id)}
                    className={cn(
                      "grid grid-cols-[auto_minmax(0,1fr)_auto] gap-x-3 gap-y-4 px-4 py-4 align-top transition-colors hover:bg-muted/60 md:table-row md:px-0 md:py-0",
                      row.deliveryTone === "danger" && "bg-destructive/5",
                    )}
                  >
                    <td className="col-start-1 row-start-1 pt-0.5 md:table-cell md:px-4 md:py-3">
                      <Checkbox
                        aria-label={`Selectează ${row.participant.full_name}`}
                        checked={selectedParticipantIds.has(row.participant.id)}
                        disabled={!deliveryEnabled || !cycleScopeReady || row.totalTasks === 0 || sendingMode !== null}
                        onCheckedChange={() => toggleParticipantSelection(row.participant.id)}
                      />
                    </td>
                    <td className="col-start-2 row-start-1 min-w-0 md:table-cell md:px-4 md:py-3">
                      <p className="font-semibold text-foreground">{row.participant.full_name}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{row.participant.email ?? "Email lipsă"}</p>
                    </td>
                    <td className="col-span-2 col-start-2 row-start-2 min-w-0 md:table-cell md:px-4 md:py-3">
                      <p className="mb-1 text-[10px] font-bold uppercase tracking-[0.08em] text-muted-foreground md:hidden">Livrare</p>
                      <StatusMarker tone={row.deliveryTone}>{row.deliveryLabel}</StatusMarker>
                      {row.deliveryError ? (
                        <p className="mt-2 max-w-56 text-xs font-medium text-destructive">{row.deliveryError}</p>
                      ) : null}
                      {row.secureLinkExpiresAt ? (
                        <p className="mt-2 text-xs text-muted-foreground">
                          Expiră {formatRomanianDateTime(row.secureLinkExpiresAt)}
                        </p>
                      ) : null}
                    </td>
                    <td className="col-start-2 row-start-3 md:table-cell md:px-4 md:py-3">
                      <p className="mb-1 text-[10px] font-bold uppercase tracking-[0.08em] text-muted-foreground md:hidden">Cont</p>
                      <StatusMarker tone={row.signedUp ? "success" : "warning"}>
                        {row.signedUp ? "Activ" : "Neînregistrat"}
                      </StatusMarker>
                    </td>
                    <td className="col-start-3 row-start-3 text-right md:table-cell md:px-4 md:py-3 md:text-left">
                      <p className="mb-1 text-[10px] font-bold uppercase tracking-[0.08em] text-muted-foreground md:hidden">Sarcini</p>
                      <button
                        type="button"
                        aria-expanded={expandedTaskParticipantIds.has(row.participant.id)}
                        aria-controls={`invitation-tasks-${selectedCycleId ?? "legacy"}-${row.participant.id}`}
                        onClick={() => toggleTaskDetails(row.participant.id)}
                        disabled={row.totalTasks === 0}
                        className="inline-flex items-center gap-2 whitespace-nowrap font-semibold text-foreground outline-none hover:text-primary focus-visible:ring-2 focus-visible:ring-ring/45 disabled:cursor-default disabled:text-muted-foreground"
                      >
                        {row.totalTasks > 0 ? `${row.completionLabel} finalizate` : "0 sarcini"}
                        {row.totalTasks > 0 ? (
                          <ChevronDownIcon
                            aria-hidden="true"
                            className={cn("size-3.5 transition-transform", expandedTaskParticipantIds.has(row.participant.id) && "rotate-180")}
                            strokeWidth={1.8}
                          />
                        ) : null}
                      </button>
                      {expandedTaskParticipantIds.has(row.participant.id) ? (
                        <p id={`invitation-tasks-${selectedCycleId ?? "legacy"}-${row.participant.id}`} className="mt-2 max-w-72 text-xs leading-5 text-muted-foreground">
                          {row.assignments
                            .map((assignment) => formatAssignmentLabel(assignment, participantsById, teamsById))
                            .join(", ")}
                        </p>
                      ) : null}
                    </td>
                    <td className="col-span-2 col-start-2 row-start-4 text-muted-foreground md:table-cell md:px-4 md:py-3">
                      <span className="mr-2 text-[10px] font-bold uppercase tracking-[0.08em] text-muted-foreground md:hidden">Următorul pas</span>
                      {row.nextAction}
                    </td>
                    <td className="col-start-3 row-start-1 text-right md:table-cell md:px-4 md:py-3">
                      {row.secureLinkUrl ? (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => void handleCopyLink(row)}
                          disabled={!deliveryEnabled || !cycleScopeReady || sendingMode !== null}
                        >
                          {copiedParticipantId === row.participant.id ? "Copiat" : "Copiază link"}
                        </Button>
                      ) : (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => void handleResend(row.participant.id)}
                          disabled={
                            !deliveryEnabled
                            || !cycleScopeReady
                            || sendingMode !== null
                            || row.totalTasks === 0
                            || (emailCapacity !== null
                              && emailCapacity.remaining_today < 1)
                          }
                        >
                          {pendingInviteAction === "resend" &&
                          resendingParticipantId === row.participant.id ? (
                            <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" />
                          ) : null}
                          {pendingInviteAction === "resend" &&
                          resendingParticipantId === row.participant.id
                            ? "Retrimitem"
                            : "Retrimite"}
                        </Button>
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

function getCurrentOperation(
  action: InvitationPendingAction | null,
  selectedCount: number,
  participantName: string | null,
): { title: string; detail: string } | null {
  if (action === "selected-email") return { title: "Trimitem emailurile selectate", detail: `${selectedCount} persoane.` };
  if (action === "unsent-email") return { title: "Trimitem emailurile netrimise", detail: "Procesăm destinatarii pregătiți." };
  if (action === "all-email") return { title: "Trimitem emailurile tuturor", detail: "Procesăm toți destinatarii eligibili." };
  if (action === "selected-links") return { title: "Generăm linkurile selectate", detail: `${selectedCount} persoane.` };
  if (action === "all-links") return { title: "Generăm linkurile", detail: "Procesăm toți destinatarii eligibili." };
  if (action === "resend") return { title: "Retrimitem invitația", detail: participantName ?? "Participant selectat" };
  return null;
}

function matchesInvitationFilter(row: ParticipantInviteRow, filter: InvitationFilter): boolean {
  if (filter === "ready") return row.totalTasks > 0 && row.deliveryState === "ready";
  if (filter === "errors") return row.deliveryState === "danger";
  if (filter === "no_assignments") return row.totalTasks === 0;
  if (filter === "not_signed_up") return !row.signedUp;
  return true;
}

function ProjectScopeSelector({
  projects,
  selectedProjectId,
}: {
  projects: CompanyProject[];
  selectedProjectId: string | null;
}) {
  const router = useRouter();

  return (
    <div className="border-b border-border bg-muted px-4 py-3 md:px-5">
      <SelectControl
        label="Schimbă proiectul curent"
        wrapperClassName="w-full lg:w-80"
        value={selectedProjectId ?? ""}
        onChange={(event) =>
          router.push(
            event.target.value
              ? `/trainer/projects/${event.target.value}/invitations`
              : "/trainer/projects",
          )
        }
      >
        <option value="">Alege proiect</option>
        {projects.map((project) => (
          <option key={project.id} value={project.id}>
            {project.name}
          </option>
        ))}
      </SelectControl>
    </div>
  );
}

function InvitationCycleToolbar({
  cycles,
  selectedCycleId,
  loading,
  onSelect,
}: {
  cycles: AssessmentCycle[];
  selectedCycleId: string | null;
  loading: boolean;
  onSelect: (assessmentCycleId: string) => void;
}) {
  const selected = cycles.find((cycle) => cycle.id === selectedCycleId) ?? null;
  return (
    <section className="flex items-center gap-3 border-b border-border pb-4" aria-label="Evaluare selectată">
      <CalendarDaysIcon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <Select value={selectedCycleId ?? undefined} onValueChange={onSelect} disabled={loading}>
        <SelectTrigger className="h-9 w-full max-w-72 bg-surface" aria-label="Evaluare">
          <SelectValue placeholder={loading ? "Încărcăm evaluările" : "Alege evaluarea"} />
        </SelectTrigger>
        <SelectContent>
          {cycles.map((cycle) => (
            <SelectItem key={cycle.id} value={cycle.id}>
              {cycle.name} · {cycle.status === "draft" ? "Draft" : cycle.status === "active" ? "Activă" : "Închisă"}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {selected ? (
        <span className="hidden text-xs font-semibold text-muted-foreground md:inline">
          {selected.status === "draft" ? "Draft" : selected.status === "active" ? "Activă" : "Închisă"}
        </span>
      ) : null}
    </section>
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
    <Button type="button" variant={active ? "default" : "outline"} size="xs" onClick={onClick}>
      {children}
    </Button>
  );
}

function EmptyTableRow({ colSpan, children }: { colSpan: number; children: React.ReactNode }) {
  return (
    <tr className="block md:table-row">
      <td colSpan={colSpan} className="block px-4 py-10 text-center text-sm text-muted-foreground md:table-cell">
        {children}
      </td>
    </tr>
  );
}

function StatusMarker({
  tone,
  children,
}: {
  tone: ParticipantInviteRow["deliveryTone"];
  children: React.ReactNode;
}) {
  const className =
    tone === "success"
      ? "status-success"
      : tone === "warning"
        ? "border-ochre/20 bg-ochre-100 text-ochre-700"
        : tone === "danger"
          ? "border-destructive/20 bg-destructive/10 text-destructive"
          : "border-border bg-muted text-muted-foreground";
  const dotClass =
    tone === "success"
      ? "bg-success-ink"
      : tone === "warning"
        ? "bg-ochre"
        : tone === "danger"
          ? "bg-destructive"
          : "bg-muted-foreground";

  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-bold", className)}>
      <span className={cn("size-1.5 rounded-full", dotClass)} aria-hidden="true" />
      {children}
    </span>
  );
}

function formatResendMessage(result: RosterInviteResult): string {
  if (result.email_queued) return `Emailul pentru ${result.email} a fost pus în coadă.`;
  if (result.email_sent) return `Email acceptat de furnizor pentru ${result.email}.`;
  if (result.error) return `Emailul nu a fost retrimis către ${result.email}: ${result.error}`;
  if (result.invite_url) return `Link pregătit pentru ${result.email}.`;
  return `Invitația nu a fost retrimisă către ${result.email}.`;
}

function formatEmailBatchMessage(result: {
  total: number;
  emails_sent: number;
  emails_queued?: number;
  emails_failed: number;
}): string {
  const queued = result.emails_queued
    ?? result.total - result.emails_sent - result.emails_failed;
  return `${result.emails_sent} acceptate de furnizor, ${Math.max(0, queued)} în coadă, ${result.emails_failed} eșuate.`;
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
    return `${formatQuestionnaireLabel(assignment.questionnaire_key)} · ${targetName ?? "persoană"}`;
  }
  if (assignment.target_type === "team") {
    const teamName = assignment.target_team_id
      ? teamsById.get(assignment.target_team_id)?.name
      : null;
    return `${formatQuestionnaireLabel(assignment.questionnaire_key)} · ${teamName ?? "echipă"}`;
  }
  return `${formatQuestionnaireLabel(assignment.questionnaire_key)} · autoevaluare`;
}

function formatQuestionnaireLabel(key: string): string {
  return questionnaireLabels[key] ?? key.replaceAll("_", " ");
}
