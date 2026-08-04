"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CalendarDaysIcon,
  CheckCircle2Icon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ClipboardListIcon,
  Loader2Icon,
  PlusIcon,
  RefreshCwIcon,
  Trash2Icon,
  XIcon,
} from "lucide-react";

import {
  closeAssessmentCycle,
  CompanyMutationError,
  createAssessmentCycle,
  createCompanyAssignment,
  deleteAssessmentCycle,
  getAssessmentCycles,
  getCompanyAssignments,
  getCompanyDefaultAssignmentPlan,
  saveCompanyDefaultAssignmentPlan,
  type AssessmentCycle,
  type CompanyAssignment,
  type CompanyAssignmentPlan,
  type CompanyAssignmentPlanItem,
  type CompanyParticipant,
  type CompanyProject,
  type CompanyTeam,
  type CreateCompanyAssignmentPayload,
} from "@/api/companies";
import {
  listQuestionnaireDefinitionStubs,
  type QuestionnaireDefinitionStub,
} from "@/api/questionnaires";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ModalLayer } from "@/components/ui/modal-layer";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SelectControl } from "@/components/ui/select-control";
import { Sheet, SheetBody, SheetFooter, SheetHeader } from "@/components/ui/sheet";
import { useUrlState } from "@/hooks/use-url-state";
import { cn } from "@/utils/cn";

type AssignmentTargetType = CompanyAssignment["target_type"];

type AssignmentFormState = {
  respondentProfileId: string;
  questionnaireKey: string;
  targetType: AssignmentTargetType;
  targetPersonId: string;
  targetTeamId: string;
};

type CycleCreateForm = {
  name: string;
  dueDate: string;
  sourceCycleId: string;
};

export type AssignmentWorkspaceProps = {
  companyId: string;
  companyName: string;
  projects: CompanyProject[];
  selectedProjectId: string | null;
  participants: CompanyParticipant[];
  assignments: CompanyAssignment[];
  teams: CompanyTeam[];
  initialAssessmentCycles?: AssessmentCycle[];
  initialSelectedCycleId?: string | null;
  showProjectSelector?: boolean;
  onAssignmentsChange?: (assignments: CompanyAssignment[]) => void;
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

export function AssignmentWorkspace({
  companyId,
  projects,
  selectedProjectId,
  participants,
  assignments,
  teams,
  initialAssessmentCycles = [],
  initialSelectedCycleId = null,
  onAssignmentsChange,
}: AssignmentWorkspaceProps) {
  const { get, isPending: urlStatePending, searchKey, setParams } = useUrlState();
  const assignmentSavingRef = useRef(false);
  const planLoadingRef = useRef(false);
  const planSavingRef = useRef(false);
  const cycleMutationRef = useRef(false);
  const assignmentErrorRef = useRef<HTMLDivElement | null>(null);
  const cycleErrorRef = useRef<HTMLDivElement | null>(null);
  const initialCycleId = initialSelectedCycleId ?? assignments[0]?.assessment_cycle_id ?? null;
  const [assignmentState, setAssignmentState] = useState(assignments);
  const [assessmentCycles, setAssessmentCycles] = useState<AssessmentCycle[]>(initialAssessmentCycles);
  const [loadedCyclesProjectId, setLoadedCyclesProjectId] = useState<string | null>(
    selectedProjectId && initialAssessmentCycles.every((cycle) => cycle.project_id === selectedProjectId)
      ? selectedProjectId
      : null,
  );
  const [selectedCycleId, setSelectedCycleId] = useState<string | null>(
    initialCycleId ?? get("cycle"),
  );
  const [loadedCycleScope, setLoadedCycleScope] = useState<string | null>(
    selectedProjectId && initialCycleId && initialAssessmentCycles.some((cycle) => cycle.id === initialCycleId)
      ? `${selectedProjectId}:${initialCycleId}`
      : null,
  );
  const [cyclesLoading, setCyclesLoading] = useState(false);
  const [cycleAssignmentsLoading, setCycleAssignmentsLoading] = useState(false);
  const [cycleMessage, setCycleMessage] = useState<string | null>(null);
  const [cycleSheetOpen, setCycleSheetOpen] = useState(false);
  const [cycleStep, setCycleStep] = useState(1);
  const [cycleCreating, setCycleCreating] = useState(false);
  const [cyclePreviewLoading, setCyclePreviewLoading] = useState(false);
  const [cyclePreviewPlan, setCyclePreviewPlan] = useState<CompanyAssignmentPlan | null>(null);
  const [cycleForm, setCycleForm] = useState<CycleCreateForm>({
    name: "",
    dueDate: "",
    sourceCycleId: "",
  });
  const [questionnaires, setQuestionnaires] = useState<QuestionnaireDefinitionStub[]>([]);
  const [questionnaireMessage, setQuestionnaireMessage] = useState<string | null>(null);
  const [assignmentSaving, setAssignmentSaving] = useState(false);
  const [plan, setPlan] = useState<CompanyAssignmentPlan | null>(null);
  const [selectedPlanKeys, setSelectedPlanKeys] = useState<Set<string>>(new Set());
  const [planLoading, setPlanLoading] = useState(false);
  const [planSaving, setPlanSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [assignmentModalMessage, setAssignmentModalMessage] = useState<string | null>(null);
  const [showAdvancedAssignmentModal, setShowAdvancedAssignmentModal] = useState(
    get("modal") === "advanced-assignment",
  );
  const [assignmentForm, setAssignmentForm] = useState<AssignmentFormState>({
    respondentProfileId: participants[0]?.id ?? "",
    questionnaireKey: "",
    targetType: "self",
    targetPersonId: "",
    targetTeamId: "",
  });

  const hasProjects = projects.length > 0;
  const canUseProjectActions = !hasProjects || selectedProjectId !== null;
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
  const selectedPlanItems = useMemo(
    () => plan?.assignments.filter((assignment) => selectedPlanKeys.has(assignment.key)) ?? [],
    [plan, selectedPlanKeys],
  );
  const selectablePlanItems = useMemo(
    () => plan?.assignments.filter((assignment) => !assignment.existing_assignment_id) ?? [],
    [plan],
  );
  const allPlanItemsSelected =
    selectablePlanItems.length > 0 &&
    selectablePlanItems.every((assignment) => selectedPlanKeys.has(assignment.key));
  const selectedCycle = useMemo(
    () => assessmentCycles.find((cycle) => cycle.id === selectedCycleId) ?? null,
    [assessmentCycles, selectedCycleId],
  );
  const cycleIsEditable = !selectedProjectId || selectedCycle?.status !== "closed";
  const sourceCycle = useMemo(
    () => assessmentCycles.find((cycle) => cycle.id === cycleForm.sourceCycleId) ?? null,
    [assessmentCycles, cycleForm.sourceCycleId],
  );
  const previewPlan = cyclePreviewPlan ?? emptyAssignmentPlan(selectedProjectId);
  const previewQuestionnaireKeys = useMemo(() => {
    const pinnedKeys = sourceCycle?.questionnaires.map((item) => item.questionnaire_key) ?? [];
    return pinnedKeys.length > 0
      ? Array.from(new Set(pinnedKeys))
      : Array.from(new Set(previewPlan.assignments.map((assignment) => assignment.questionnaire_key)));
  }, [previewPlan.assignments, sourceCycle]);
  const openCycle = useMemo(
    () => assessmentCycles.find((cycle) => cycle.status === "draft" || cycle.status === "active") ?? null,
    [assessmentCycles],
  );
  const cycleScopeKey = `${selectedProjectId ?? "company"}:${selectedCycleId ?? "legacy"}`;
  const cycleScopeReady = !selectedProjectId || Boolean(
    selectedCycleId &&
    loadedCycleScope === cycleScopeKey &&
    !cyclesLoading &&
    !cycleAssignmentsLoading,
  );
  const publishAssignments = useCallback((next: CompanyAssignment[]) => {
    setAssignmentState(next);
    onAssignmentsChange?.(next);
  }, [onAssignmentsChange]);

  useEffect(() => {
    setAssignmentState(assignments);
  }, [assignments]);

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
          setParams({ cycle: preferred.id }, "replace");
        }
        setCycleMessage(null);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setAssessmentCycles([]);
        setSelectedCycleId(null);
        setLoadedCycleScope(null);
        setCycleMessage(
          error instanceof Error ? error.message : "Evaluările nu au putut fi încărcate.",
        );
      })
      .finally(() => {
        if (!cancelled) setCyclesLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [companyId, get, loadedCyclesProjectId, selectedProjectId, setParams]);

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

    setLoadedCycleScope(null);
    publishAssignments([]);
    setCycleAssignmentsLoading(true);
    getCompanyAssignments(companyId, {}, {
      projectId: selectedProjectId,
      assessmentCycleId: selectedCycleId,
    })
      .then((nextAssignments) => {
        if (cancelled) return;
        publishAssignments(nextAssignments);
        setLoadedCycleScope(requestedScope);
        setCycleMessage(null);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setCycleMessage(
            error instanceof Error ? error.message : "Asignările evaluării nu au putut fi încărcate.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setCycleAssignmentsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [companyId, loadedCycleScope, publishAssignments, selectedProjectId, selectedCycleId]);

  useEffect(() => {
    setShowAdvancedAssignmentModal(get("modal") === "advanced-assignment");
  }, [get, searchKey]);

  useEffect(() => {
    setPlan(null);
    setSelectedPlanKeys(new Set());
    setMessage(null);
  }, [cycleScopeKey]);

  useEffect(() => {
    let cancelled = false;

    async function loadQuestionnaires() {
      try {
        const definitions = await listQuestionnaireDefinitionStubs();
        if (cancelled) return;
        setQuestionnaires(definitions.filter((definition) => definition.status === "active"));
        setQuestionnaireMessage(null);
      } catch {
        if (!cancelled) setQuestionnaireMessage("Chestionarele nu au putut fi încărcate.");
      }
    }

    void loadQuestionnaires();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const respondentProfileId = participants.some(
      (participant) => participant.id === assignmentForm.respondentProfileId,
    )
      ? assignmentForm.respondentProfileId
      : (participants[0]?.id ?? "");

    setAssignmentForm((current) => ({
      ...current,
      respondentProfileId,
      targetPersonId:
        current.targetPersonId !== respondentProfileId &&
        participants.some((participant) => participant.id === current.targetPersonId)
          ? current.targetPersonId
          : (participants.find((participant) => participant.id !== respondentProfileId)?.id ?? ""),
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

  useEffect(() => {
    if (assignmentModalMessage && showAdvancedAssignmentModal) {
      assignmentErrorRef.current?.focus({ preventScroll: true });
    }
  }, [assignmentModalMessage, showAdvancedAssignmentModal]);

  useEffect(() => {
    if (cycleMessage && cycleSheetOpen) {
      cycleErrorRef.current?.focus({ preventScroll: true });
    }
  }, [cycleMessage, cycleSheetOpen]);

  useEffect(() => {
    let cancelled = false;
    if (!cycleSheetOpen || cycleStep !== 2 || !selectedProjectId || !cycleForm.sourceCycleId) {
      return;
    }

    setCyclePreviewLoading(true);
    setCyclePreviewPlan(null);
    getCompanyDefaultAssignmentPlan(companyId, {}, {
      projectId: selectedProjectId,
      sourceCycleId: cycleForm.sourceCycleId,
    })
      .then((nextPlan) => {
        if (!cancelled) {
          setCyclePreviewPlan(nextPlan);
          setCycleMessage(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setCycleMessage(
            error instanceof Error ? error.message : "Previzualizarea nu a putut fi încărcată.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setCyclePreviewLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [
    companyId,
    cycleForm.sourceCycleId,
    cycleSheetOpen,
    cycleStep,
    selectedProjectId,
  ]);

  const canCreateAssignment =
    cycleIsEditable &&
    cycleScopeReady &&
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
  const canSavePlan = cycleIsEditable && cycleScopeReady && canUseProjectActions && selectedPlanItems.length > 0 && !planSaving;
  const canCreateCycle = Boolean(
    cycleScopeReady &&
    selectedProjectId &&
    cycleForm.name.trim() &&
    cycleForm.sourceCycleId &&
    previewQuestionnaireKeys.length > 0 &&
    previewPlan.assignments.length > 0,
  );
  const currentOperation = cyclesLoading || cycleAssignmentsLoading
    ? { title: "Încărcăm evaluarea", detail: "Sincronizăm asignările selectate." }
    : planLoading
    ? { title: "Generăm planul", detail: "Pregătim propunerile pentru proiect." }
    : planSaving
      ? { title: "Salvăm asignările", detail: `${selectedPlanItems.length} selectate.` }
      : assignmentSaving
        ? { title: "Creăm asignarea", detail: "Salvăm excepția în proiect." }
        : null;

  function selectAssessmentCycle(assessmentCycleId: string) {
    if (assessmentCycleId === selectedCycleId) return;
    setCycleMessage(null);
    setLoadedCycleScope(null);
    publishAssignments([]);
    setSelectedCycleId(assessmentCycleId);
    setParams({ cycle: assessmentCycleId }, "push");
  }

  function openCycleCreation() {
    const source = selectedCycle ?? assessmentCycles.at(-1) ?? null;
    const nextSequence = Math.max(1, ...assessmentCycles.map((cycle) => cycle.sequence + 1));
    setCycleForm({
      name: `Reevaluare ${Math.max(1, nextSequence - 1)}`,
      dueDate: "",
      sourceCycleId: source?.id ?? "",
    });
    setCyclePreviewPlan(null);
    setCycleStep(1);
    setCycleMessage(null);
    setCycleSheetOpen(true);
  }

  async function handleCreateCycle() {
    if (!selectedProjectId || !canCreateCycle || cycleMutationRef.current) return;
    cycleMutationRef.current = true;
    setCycleCreating(true);
    setCycleMessage(null);
    try {
      const created = await createAssessmentCycle(companyId, selectedProjectId, {
        name: cycleForm.name.trim(),
        sourceCycleId: cycleForm.sourceCycleId,
        dueAt: cycleForm.dueDate ? new Date(`${cycleForm.dueDate}T23:59:59`).toISOString() : null,
      });
      setAssessmentCycles((current) => [...current, created].sort((left, right) => left.sequence - right.sequence));
      publishAssignments([]);
      setLoadedCycleScope(`${selectedProjectId}:${created.id}`);
      setSelectedCycleId(created.id);
      setParams({ cycle: created.id }, "replace");
      setCycleSheetOpen(false);
      setCycleMessage(`${created.name} a fost creată ca draft.`);
    } catch (error) {
      setCycleMessage(error instanceof Error ? error.message : "Reevaluarea nu a putut fi creată.");
    } finally {
      cycleMutationRef.current = false;
      setCycleCreating(false);
    }
  }

  async function handleCloseCycle() {
    if (!cycleScopeReady || !selectedProjectId || !selectedCycle || selectedCycle.status !== "active" || cycleMutationRef.current) return;
    cycleMutationRef.current = true;
    setCycleMessage(null);
    try {
      const closed = await closeAssessmentCycle(companyId, selectedProjectId, selectedCycle.id);
      setAssessmentCycles((current) => current.map((cycle) => cycle.id === closed.id ? closed : cycle));
      setCycleMessage(`${closed.name} a fost închisă.`);
    } catch (error) {
      if (
        error instanceof CompanyMutationError &&
        error.code === "assessment_cycle_has_unfinished_assignments" &&
        window.confirm(
          "Evaluarea are asignări nefinalizate. Le anulezi și închizi evaluarea?",
        )
      ) {
        try {
          const closed = await closeAssessmentCycle(
            companyId,
            selectedProjectId,
            selectedCycle.id,
            true,
          );
          setAssessmentCycles((current) =>
            current.map((cycle) => cycle.id === closed.id ? closed : cycle),
          );
          setCycleMessage(`${closed.name} a fost închisă.`);
          return;
        } catch (retryError) {
          setCycleMessage(
            retryError instanceof Error ? retryError.message : "Evaluarea nu a putut fi închisă.",
          );
          return;
        }
      }
      setCycleMessage(error instanceof Error ? error.message : "Evaluarea nu a putut fi închisă.");
    } finally {
      cycleMutationRef.current = false;
    }
  }

  async function handleDeleteDraft() {
    if (!cycleScopeReady || !selectedProjectId || !selectedCycle || selectedCycle.status !== "draft" || cycleMutationRef.current) return;
    if (!window.confirm(`Ștergi draftul „${selectedCycle.name}”?`)) return;
    cycleMutationRef.current = true;
    setCycleMessage(null);
    try {
      await deleteAssessmentCycle(companyId, selectedProjectId, selectedCycle.id);
      const remaining = assessmentCycles.filter((cycle) => cycle.id !== selectedCycle.id);
      const fallback = remaining.at(-1) ?? null;
      setAssessmentCycles(remaining);
      setSelectedCycleId(fallback?.id ?? null);
      setParams({ cycle: fallback?.id ?? null }, "replace");
      setCycleMessage("Draftul a fost șters.");
    } catch (error) {
      setCycleMessage(error instanceof Error ? error.message : "Draftul nu a putut fi șters.");
    } finally {
      cycleMutationRef.current = false;
    }
  }

  function updateAssignmentForm(patch: Partial<AssignmentFormState>) {
    setAssignmentForm((current) => {
      const next = { ...current, ...patch };
      if (
        !next.targetPersonId ||
        next.targetPersonId === next.respondentProfileId ||
        !participants.some((participant) => participant.id === next.targetPersonId)
      ) {
        next.targetPersonId =
          participants.find((participant) => participant.id !== next.respondentProfileId)?.id ?? "";
      }
      return next;
    });
  }

  function setAdvancedAssignmentModalOpen(open: boolean) {
    if (open) setAssignmentModalMessage(null);
    setShowAdvancedAssignmentModal(open);
    setParams({ modal: open ? "advanced-assignment" : null }, open ? "push" : "replace");
  }

  async function handleCreateAssignment() {
    if (!canCreateAssignment || assignmentSavingRef.current) return;
    assignmentSavingRef.current = true;
    setAssignmentSaving(true);
    setMessage(null);
    setAssignmentModalMessage(null);

    const payload: CreateCompanyAssignmentPayload = {
      projectId: selectedProjectId,
      ...(selectedProjectId && selectedCycleId ? { assessmentCycleId: selectedCycleId } : {}),
      respondentProfileId: assignmentForm.respondentProfileId,
      questionnaireKey: assignmentForm.questionnaireKey,
      targetType: assignmentForm.targetType,
      targetPersonId:
        assignmentForm.targetType === "person" ? assignmentForm.targetPersonId : null,
      targetTeamId: assignmentForm.targetType === "team" ? assignmentForm.targetTeamId : null,
    };

    try {
      const created = await createCompanyAssignment(companyId, payload);
      publishAssignments([...assignmentState, created]);
      const respondentName =
        participantsById.get(created.respondent_profile_id)?.full_name ?? "participant";
      setMessage(`Asignare creată pentru ${respondentName}.`);
      setAdvancedAssignmentModalOpen(false);
    } catch (error) {
      setAssignmentModalMessage(
        error instanceof Error ? error.message : "Asignarea nu a putut fi creată.",
      );
    } finally {
      assignmentSavingRef.current = false;
      setAssignmentSaving(false);
    }
  }

  async function handleGeneratePlan() {
    if (planLoadingRef.current || planSavingRef.current) return;
    if (!canUseProjectActions || !cycleScopeReady || !selectedCycleId) {
      setMessage("Evaluarea selectată nu este încă disponibilă.");
      return;
    }
    if (!cycleIsEditable) {
      setMessage("Evaluările închise sunt disponibile doar pentru consultare.");
      return;
    }

    planLoadingRef.current = true;
    setPlanLoading(true);
    setMessage(null);
    try {
      const generated = await getCompanyDefaultAssignmentPlan(
        companyId,
        {},
        {
          projectId: selectedProjectId,
          assessmentCycleId: selectedCycleId,
        },
      );
      setPlan(generated);
      setSelectedPlanKeys(
        new Set(
          generated.assignments
            .filter((assignment) => assignment.selected && !assignment.existing_assignment_id)
            .map((assignment) => assignment.key),
        ),
      );
      setMessage(
        generated.assignments.length > 0
          ? `${generated.suggested_count} propuse, ${generated.existing_count} deja salvate.`
          : "Planul nu conține asignări pentru structura curentă.",
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Planul nu a putut fi generat.");
    } finally {
      planLoadingRef.current = false;
      setPlanLoading(false);
    }
  }

  async function handleSavePlan() {
    if (!canSavePlan || planSavingRef.current || planLoadingRef.current) return;
    planSavingRef.current = true;
    setPlanSaving(true);
    setMessage(null);
    try {
      if (!selectedCycleId || !cycleScopeReady) {
        setMessage("Evaluarea selectată nu este încă disponibilă.");
        return;
      }
      const result = await saveCompanyDefaultAssignmentPlan(
        companyId,
        selectedPlanItems,
        selectedProjectId,
        selectedCycleId,
      );
      const savedIdsByPlanKey = new Map(
        selectedPlanItems.map((assignment, index) => [
          assignment.key,
          result.assignments[index]?.id ?? null,
        ]),
      );
      publishAssignments(mergeAssignments(assignmentState, result.assignments));
      setPlan((current) =>
        current
          ? {
              ...current,
              assignments: current.assignments.map((assignment) =>
                selectedPlanKeys.has(assignment.key)
                  ? {
                      ...assignment,
                      selected: false,
                      existing_assignment_id:
                        assignment.existing_assignment_id ??
                        savedIdsByPlanKey.get(assignment.key) ??
                        null,
                    }
                  : assignment,
              ),
            }
          : current,
      );
      setSelectedPlanKeys(new Set());
      setMessage(`${result.created_count} create, ${result.existing_count} deja existente.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Asignările nu au putut fi salvate.");
    } finally {
      planSavingRef.current = false;
      setPlanSaving(false);
    }
  }

  function togglePlanItem(key: string) {
    setSelectedPlanKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function toggleAllPlanItems(checked: boolean) {
    setSelectedPlanKeys(
      checked ? new Set(selectablePlanItems.map((assignment) => assignment.key)) : new Set(),
    );
  }

  return (
    <div className="flex flex-col gap-4" aria-busy={Boolean(currentOperation)}>
      {currentOperation ? (
        <OperationFeedback title={currentOperation.title} detail={currentOperation.detail} />
      ) : null}
      {message ? <InlineFeedback>{message}</InlineFeedback> : null}
      {cycleMessage && !cycleSheetOpen ? <InlineFeedback>{cycleMessage}</InlineFeedback> : null}

      {assessmentCycles.length > 0 ? (
        <AssessmentCycleToolbar
          cycles={assessmentCycles}
          selectedCycleId={selectedCycleId}
          loading={cyclesLoading || cycleAssignmentsLoading}
          onSelect={selectAssessmentCycle}
          action={
            selectedCycle?.status === "active" ? (
              <Button type="button" variant="outline" size="sm" onClick={() => void handleCloseCycle()} disabled={!cycleScopeReady}>
                Închide evaluarea
              </Button>
            ) : selectedCycle?.status === "draft" ? (
              <Button type="button" variant="ghost" size="sm" onClick={() => void handleDeleteDraft()} disabled={!cycleScopeReady}>
                <Trash2Icon data-icon="inline-start" aria-hidden="true" />
                Șterge draftul
              </Button>
            ) : !openCycle ? (
              <Button type="button" size="sm" onClick={openCycleCreation} disabled={!cycleScopeReady}>
                <PlusIcon data-icon="inline-start" aria-hidden="true" />
                Reevaluare nouă
              </Button>
            ) : null
          }
        />
      ) : null}

      <section className="overflow-hidden rounded-lg border border-border bg-surface">
        <header className="flex flex-col gap-3 border-b border-border px-4 py-4 md:flex-row md:items-center md:justify-between md:px-5">
          <div className="flex min-w-0 items-baseline gap-3">
            <h2 className="text-xl font-semibold text-foreground">Plan de asignări</h2>
            <span className="text-sm text-muted-foreground">
              {assignmentState.length} salvate
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setAdvancedAssignmentModalOpen(true)}
              disabled={!cycleIsEditable || !cycleScopeReady || participants.length === 0}
            >
              <PlusIcon data-icon="inline-start" aria-hidden="true" />
              Asignare individuală
            </Button>
            {!plan && assignmentState.length === 0 ? (
              <Button
                type="button"
                size="sm"
                onClick={() => void handleGeneratePlan()}
                disabled={!cycleIsEditable || !cycleScopeReady || !canUseProjectActions || planLoading || participants.length === 0}
              >
                {planLoading ? (
                  <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" />
                ) : (
                  <ClipboardListIcon data-icon="inline-start" aria-hidden="true" />
                )}
                {planLoading ? "Generăm planul" : "Generează plan"}
              </Button>
            ) : (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void handleGeneratePlan()}
                disabled={!cycleIsEditable || !cycleScopeReady || !canUseProjectActions || planLoading || participants.length === 0}
                title={participants.length === 0 ? "Adaugă participanți înainte de regenerare." : undefined}
              >
                {planLoading ? (
                  <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" />
                ) : (
                  <RefreshCwIcon data-icon="inline-start" aria-hidden="true" />
                )}
                {planLoading ? "Regenerăm planul" : "Regenerează planul"}
              </Button>
            )}
            {plan && selectedPlanItems.length > 0 ? (
              <Button
                type="button"
                size="sm"
                onClick={() => void handleSavePlan()}
                disabled={!canSavePlan}
              >
                {planSaving ? (
                  <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" />
                ) : (
                  <CheckCircle2Icon data-icon="inline-start" aria-hidden="true" />
                )}
                {planSaving ? "Salvăm asignările" : `Salvează ${selectedPlanItems.length} ${selectedPlanItems.length === 1 ? "asignare" : "asignări"}`}
              </Button>
            ) : null}
          </div>
        </header>

        {questionnaireMessage ? (
          <InlineFeedback tone="danger" className="m-4 md:m-5">
            {questionnaireMessage}
          </InlineFeedback>
        ) : null}

        <AssignmentTable
          assignments={assignmentState}
          plan={plan}
          participantsById={participantsById}
          teamsById={teamsById}
          selectedKeys={selectedPlanKeys}
          allSelected={allPlanItemsSelected}
          onToggleAll={toggleAllPlanItems}
          onToggleItem={togglePlanItem}
          readOnly={!cycleIsEditable}
        />
      </section>

      {showAdvancedAssignmentModal ? (
        <ModalLayer
          labelledBy="advanced-assignment-title"
          onClose={() => {
            if (!urlStatePending) setAdvancedAssignmentModalOpen(false);
          }}
          panelClassName="max-w-2xl"
          closeOnBackdrop={!urlStatePending}
          closeOnEscape={!urlStatePending}
        >
          <div className="flex items-center justify-between gap-4">
            <h2 id="advanced-assignment-title" className="text-xl font-semibold text-foreground">
              Asignare individuală
            </h2>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setAdvancedAssignmentModalOpen(false)}
              disabled={urlStatePending}
            >
              Închide
            </Button>
          </div>

          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <LabeledSelect
              label="Respondent"
              value={assignmentForm.respondentProfileId}
              onChange={(value) => updateAssignmentForm({ respondentProfileId: value })}
              disabled={assignmentSaving || participants.length === 0}
            >
              {participants.map((participant) => (
                <option key={participant.id} value={participant.id}>
                  {participant.full_name}
                </option>
              ))}
            </LabeledSelect>
            <LabeledSelect
              label="Chestionar"
              value={assignmentForm.questionnaireKey}
              onChange={(value) => updateAssignmentForm({ questionnaireKey: value })}
              disabled={assignmentSaving || questionnaires.length === 0}
            >
              {questionnaires.map((definition) => (
                <option key={definition.id} value={definition.id}>
                  {definition.name}
                </option>
              ))}
            </LabeledSelect>
          </div>

          <fieldset className="mt-5">
            <legend className="text-xs font-semibold text-muted-foreground">Țintă</legend>
            <div className="mt-2 grid grid-cols-3 gap-2">
              {(["self", "person", "team"] as const).map((targetType) => (
                <Button
                  key={targetType}
                  type="button"
                  variant={assignmentForm.targetType === targetType ? "default" : "outline"}
                  size="sm"
                  aria-pressed={assignmentForm.targetType === targetType}
                  onClick={() => updateAssignmentForm({ targetType })}
                >
                  {formatTargetType(targetType)}
                </Button>
              ))}
            </div>
          </fieldset>

          {assignmentForm.targetType === "person" ? (
            <div className="mt-4">
              <LabeledSelect
                label="Persoana evaluată"
                value={assignmentForm.targetPersonId}
                onChange={(value) => updateAssignmentForm({ targetPersonId: value })}
                disabled={assignmentSaving || targetPersonOptions.length === 0}
              >
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
                {teams.map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name}
                  </option>
                ))}
              </LabeledSelect>
            </div>
          ) : null}

          {assignmentModalMessage ? (
            <div ref={assignmentErrorRef} tabIndex={-1} className="mt-4 outline-none">
              <InlineFeedback tone="danger">{assignmentModalMessage}</InlineFeedback>
            </div>
          ) : null}

          <div className="mt-6 flex justify-end border-t border-border pt-5">
            <Button
              type="button"
              size="sm"
              onClick={() => void handleCreateAssignment()}
              disabled={!canCreateAssignment || assignmentSaving}
            >
              {assignmentSaving ? (
                <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" />
              ) : (
                <CheckCircle2Icon data-icon="inline-start" aria-hidden="true" />
              )}
              {assignmentSaving ? "Salvăm asignarea" : "Creează asignarea"}
            </Button>
          </div>
        </ModalLayer>
      ) : null}

      <Sheet
        open={cycleSheetOpen}
        onOpenChange={setCycleSheetOpen}
        labelledBy="assessment-cycle-sheet-title"
        closeOnBackdrop={!cycleCreating}
        closeOnEscape={!cycleCreating}
        panelClassName="!flex !flex-col"
      >
        <SheetHeader className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold text-muted-foreground">Pasul {cycleStep} din 3</p>
            <h2 id="assessment-cycle-sheet-title" className="mt-1 text-xl font-semibold text-foreground">
              Reevaluare nouă
            </h2>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="Închide"
            onClick={() => setCycleSheetOpen(false)}
            disabled={cycleCreating}
          >
            <XIcon aria-hidden="true" />
          </Button>
        </SheetHeader>

        <SheetBody className="flex flex-col gap-5">
          {cycleMessage ? (
            <div ref={cycleErrorRef} tabIndex={-1} className="outline-none">
              <InlineFeedback tone="danger">{cycleMessage}</InlineFeedback>
            </div>
          ) : null}
          <CycleStepIndicator step={cycleStep} />
          {cycleStep === 1 ? (
            <div className="grid gap-4">
              <Field>
                <FieldLabel htmlFor="cycle-name">Nume</FieldLabel>
                <Input
                  id="cycle-name"
                  value={cycleForm.name}
                  onChange={(event) => setCycleForm((current) => ({ ...current, name: event.target.value }))}
                  maxLength={120}
                  autoFocus
                />
              </Field>
              <Field>
                <FieldLabel>Sursă</FieldLabel>
                <Select
                  value={cycleForm.sourceCycleId}
                  onValueChange={(sourceCycleId) => setCycleForm((current) => ({ ...current, sourceCycleId }))}
                >
                  <SelectTrigger aria-label="Evaluare sursă">
                    <SelectValue placeholder="Alege evaluarea sursă" />
                  </SelectTrigger>
                  <SelectContent>
                    {assessmentCycles.filter((cycle) => cycle.status !== "draft").map((cycle) => (
                      <SelectItem key={cycle.id} value={cycle.id}>{cycle.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field>
                <FieldLabel htmlFor="cycle-due-date">Termen</FieldLabel>
                <Input
                  id="cycle-due-date"
                  type="date"
                  value={cycleForm.dueDate}
                  onChange={(event) => setCycleForm((current) => ({ ...current, dueDate: event.target.value }))}
                />
              </Field>
            </div>
          ) : cycleStep === 2 ? (
            <div className="grid gap-5">
              <section aria-labelledby="cycle-questionnaires-title">
                <h3 id="cycle-questionnaires-title" className="text-sm font-semibold text-foreground">
                  Chestionare repetate
                </h3>
                <div className="mt-3 flex flex-wrap gap-2">
                  {previewQuestionnaireKeys.map((key) => (
                    <span key={key} className="inline-flex items-center gap-2 rounded-md bg-muted px-3 py-2 text-sm font-medium text-foreground">
                      <CheckCircle2Icon className="size-4 text-success-ink" aria-hidden="true" />
                      {formatQuestionnaireLabel(key)}
                    </span>
                  ))}
                </div>
              </section>
              <section aria-labelledby="cycle-preview-title" className="overflow-hidden rounded-lg border border-border">
                <header className="border-b border-border px-4 py-3">
                  <h3 id="cycle-preview-title" className="text-sm font-semibold text-foreground">
                    Previzualizare grupată
                  </h3>
                </header>
                {cyclePreviewLoading ? (
                  <div className="flex items-center gap-2 px-4 py-8 text-sm text-muted-foreground">
                    <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
                    Încărcăm structura
                  </div>
                ) : (
                  <AssignmentPlanGroups
                    plan={previewPlan}
                    selectedKeys={new Set(previewPlan.assignments.map((item) => item.key))}
                    allSelected
                    onToggleAll={() => undefined}
                    onToggleItem={() => undefined}
                    readOnly
                  />
                )}
              </section>
            </div>
          ) : (
            <div className="grid gap-5">
              <div>
                <p className="text-sm text-muted-foreground">Evaluare</p>
                <p className="mt-1 text-lg font-semibold text-foreground">{cycleForm.name}</p>
              </div>
              <dl className="grid gap-4 border-y border-border py-4 sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-semibold text-muted-foreground">Sursă</dt>
                  <dd className="mt-1 font-medium text-foreground">{sourceCycle?.name ?? "Evaluare anterioară"}</dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold text-muted-foreground">Termen</dt>
                  <dd className="mt-1 font-medium text-foreground">{cycleForm.dueDate || "Fără termen"}</dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold text-muted-foreground">Chestionare</dt>
                  <dd className="mt-1 font-medium text-foreground">{previewQuestionnaireKeys.length}</dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold text-muted-foreground">Asignări propuse</dt>
                  <dd className="mt-1 font-medium text-foreground">{previewPlan.assignments.length}</dd>
                </div>
              </dl>
              <InlineFeedback>Draftul nu trimite invitații până când salvezi planul și pornești livrarea.</InlineFeedback>
            </div>
          )}
        </SheetBody>

        <SheetFooter className="flex items-center justify-between gap-3">
          <Button
            type="button"
            variant="ghost"
            onClick={() => cycleStep === 1 ? setCycleSheetOpen(false) : setCycleStep((step) => step - 1)}
            disabled={cycleCreating}
          >
            <ChevronLeftIcon data-icon="inline-start" aria-hidden="true" />
            {cycleStep === 1 ? "Anulează" : "Înapoi"}
          </Button>
          {cycleStep < 3 ? (
            <Button
              type="button"
              onClick={() => setCycleStep((step) => step + 1)}
              disabled={
                (cycleStep === 1 && (!cycleForm.name.trim() || !cycleForm.sourceCycleId))
                || (cycleStep === 2 && (cyclePreviewLoading || previewPlan.assignments.length === 0))
              }
            >
              Continuă
              <ChevronRightIcon data-icon="inline-end" aria-hidden="true" />
            </Button>
          ) : (
            <Button type="button" onClick={() => void handleCreateCycle()} disabled={!canCreateCycle || cycleCreating}>
              {cycleCreating ? <Loader2Icon className="animate-spin" data-icon="inline-start" aria-hidden="true" /> : null}
              {cycleCreating ? "Creăm draftul" : "Creează draftul"}
            </Button>
          )}
        </SheetFooter>
      </Sheet>
    </div>
  );
}

export function AssessmentCycleToolbar({
  cycles,
  selectedCycleId,
  loading,
  onSelect,
  action,
}: {
  cycles: AssessmentCycle[];
  selectedCycleId: string | null;
  loading: boolean;
  onSelect: (assessmentCycleId: string) => void;
  action?: React.ReactNode;
}) {
  const selected = cycles.find((cycle) => cycle.id === selectedCycleId) ?? null;

  return (
    <section className="flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-center" aria-label="Evaluare selectată">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <CalendarDaysIcon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <Select value={selectedCycleId ?? undefined} onValueChange={onSelect} disabled={loading}>
          <SelectTrigger className="h-9 w-full max-w-72 bg-surface" aria-label="Evaluare">
            <SelectValue placeholder={loading ? "Încărcăm evaluările" : "Alege evaluarea"} />
          </SelectTrigger>
          <SelectContent>
            {cycles.map((cycle) => (
              <SelectItem key={cycle.id} value={cycle.id}>
                {cycle.name} · {formatCycleStatus(cycle.status)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {selected ? (
          <span className="hidden text-xs font-semibold text-muted-foreground md:inline">
            {formatCycleStatus(selected.status)}
          </span>
        ) : null}
      </div>
      {action ? <div className="flex shrink-0 items-center gap-2">{action}</div> : null}
    </section>
  );
}

function CycleStepIndicator({ step }: { step: number }) {
  return (
    <ol className="grid grid-cols-3 gap-2" aria-label="Pașii reevaluării">
      {["Detalii", "Plan", "Confirmare"].map((label, index) => {
        const value = index + 1;
        const active = value === step;
        const complete = value < step;
        return (
          <li key={label} className="min-w-0">
            <span
              className={cn(
                "block h-1 rounded-full",
                active || complete ? "bg-burgundy" : "bg-muted",
              )}
              aria-hidden="true"
            />
            <span className={cn("mt-2 block truncate text-xs font-semibold", active ? "text-foreground" : "text-muted-foreground")}>
              {label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function formatCycleStatus(status: AssessmentCycle["status"]): string {
  if (status === "draft") return "Draft";
  if (status === "active") return "Activă";
  return "Închisă";
}

function AssignmentTable({
  assignments,
  plan,
  participantsById,
  teamsById,
  selectedKeys,
  allSelected,
  onToggleAll,
  onToggleItem,
  readOnly = false,
}: {
  assignments: CompanyAssignment[];
  plan: CompanyAssignmentPlan | null;
  participantsById: Map<string, CompanyParticipant>;
  teamsById: Map<string, CompanyTeam>;
  selectedKeys: Set<string>;
  allSelected: boolean;
  onToggleAll: (checked: boolean) => void;
  onToggleItem: (key: string) => void;
  readOnly?: boolean;
}) {
  if (plan) {
    return (
      <AssignmentPlanGroups
        plan={plan}
        selectedKeys={selectedKeys}
        allSelected={allSelected}
        onToggleAll={onToggleAll}
        onToggleItem={onToggleItem}
        readOnly={readOnly}
      />
    );
  }

  const hasRows = assignments.length > 0;

  return (
    <div className="min-w-0 max-w-full md:overflow-x-auto">
      <table className="block w-full text-left text-sm md:table md:min-w-[760px] xl:min-w-0 xl:table-fixed">
        <thead className="hidden bg-muted text-[11px] font-bold uppercase tracking-[0.08em] text-muted-foreground md:table-header-group">
          <tr>
            <th className="w-12 px-4 py-3" />
            <th className="px-4 py-3">Respondent</th>
            <th className="px-4 py-3">Chestionar</th>
            <th className="px-4 py-3">Țintă</th>
            <th className="px-4 py-3">Grup</th>
            <th className="px-4 py-3">Stare</th>
          </tr>
        </thead>
        <tbody className="block divide-y divide-border md:table-row-group">
          {!hasRows ? (
            <tr className="block md:table-row">
              <td colSpan={6} className="block px-4 py-10 text-center md:table-cell">
                <p className="font-semibold text-foreground">Nicio asignare</p>
              </td>
            </tr>
          ) : (
            assignments.map((assignment) => (
              <tr key={assignment.id} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-3 px-4 py-4 hover:bg-muted/60 md:table-row md:px-0 md:py-0">
                <td className="hidden md:table-cell md:px-4 md:py-3" />
                <td className="col-start-1 row-start-1 min-w-0 font-semibold text-foreground md:table-cell md:px-4 md:py-3">
                  {participantsById.get(assignment.respondent_profile_id)?.full_name ?? "Participant"}
                </td>
                <td className="col-start-1 row-start-2 md:table-cell md:px-4 md:py-3">
                  <span className="mr-2 text-[10px] font-bold uppercase tracking-[0.08em] text-muted-foreground md:hidden">Chestionar</span>
                  {formatQuestionnaireLabel(assignment.questionnaire_key)}
                </td>
                <td className="col-start-1 row-start-3 min-w-0 md:table-cell md:px-4 md:py-3">
                  <p className="mb-1 text-[10px] font-bold uppercase tracking-[0.08em] text-muted-foreground md:hidden">Țintă</p>
                  <p className="font-medium text-foreground">
                    {formatSavedTarget(assignment, participantsById, teamsById)}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {formatTargetType(assignment.target_type)}
                  </p>
                </td>
                <td className="hidden text-muted-foreground md:table-cell md:px-4 md:py-3">Proiect</td>
                <td className="col-start-2 row-start-1 md:table-cell md:px-4 md:py-3">
                  <AssignmentState saved selected={false} />
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function AssignmentPlanGroups({
  plan,
  selectedKeys,
  allSelected,
  onToggleAll,
  onToggleItem,
  readOnly = false,
}: {
  plan: CompanyAssignmentPlan;
  selectedKeys: Set<string>;
  allSelected: boolean;
  onToggleAll: (checked: boolean) => void;
  onToggleItem: (key: string) => void;
  readOnly?: boolean;
}) {
  const groups = buildAssignmentPlanGroups(plan);
  const selectableCount = plan.assignments.filter((assignment) => !assignment.existing_assignment_id).length;

  if (plan.assignments.length === 0) {
    return (
      <div className="px-4 py-10 text-center">
        <p className="font-semibold text-foreground">Nicio asignare</p>
        <p className="mt-1 text-sm text-muted-foreground">Structura proiectului nu a produs propuneri.</p>
      </div>
    );
  }

  return (
    <div className="min-w-0">
      {!readOnly ? (
        <div className="flex flex-wrap items-center gap-3 border-b border-border px-4 py-3 md:px-5">
          <Checkbox
            aria-label="Selectează toate asignările propuse"
            checked={allSelected}
            disabled={selectableCount === 0}
            onCheckedChange={(checked) => onToggleAll(checked === true)}
          />
          <span className="text-sm font-semibold text-foreground">Selectează toate propunerile</span>
          <span className="ml-auto text-xs tabular-nums text-muted-foreground">
            {selectedKeys.size} selectate din {selectableCount}
          </span>
        </div>
      ) : null}

      <div className="divide-y divide-border">
        {groups.map(({ scope, assignments: scopeAssignments }) => (
          <section key={scope.id} aria-label={scope.name}>
            <header className="flex items-center justify-between gap-4 bg-muted/45 px-4 py-3 md:px-5">
              <div className="min-w-0">
                <h3 className="truncate text-sm font-semibold text-foreground">{scope.name}</h3>
                <p className="mt-0.5 text-xs text-muted-foreground">{formatScopeType(scope.type)}</p>
              </div>
              <span className="shrink-0 text-xs font-semibold tabular-nums text-muted-foreground">
                {scopeAssignments.length} {scopeAssignments.length === 1 ? "asignare" : "asignări"}
              </span>
            </header>

            <div className="space-y-3 p-3 md:p-4">
              {buildAssignmentTargetGroups(scopeAssignments).map((targetGroup) => (
                <section
                  key={targetGroup.id}
                  aria-label={`Țintă ${formatTargetType(targetGroup.type)}: ${targetGroup.name}`}
                  className="overflow-hidden rounded-md border border-border bg-background"
                >
                  <header className="flex items-start justify-between gap-4 border-b border-border bg-muted/35 px-4 py-3">
                    <div className="min-w-0">
                      <p className="text-[11px] font-semibold uppercase text-muted-foreground">
                        {formatTargetType(targetGroup.type)}
                      </p>
                      <h4 className="mt-0.5 break-words text-sm font-semibold text-foreground">
                        {targetGroup.name}
                      </h4>
                    </div>
                    <span className="shrink-0 text-xs font-semibold tabular-nums text-muted-foreground">
                      {targetGroup.assignments.length}{" "}
                      {targetGroup.assignments.length === 1 ? "asignare" : "asignări"}
                    </span>
                  </header>

                  <div
                    className="hidden grid-cols-[3rem_minmax(9rem,1fr)_minmax(12rem,1.2fr)_minmax(9rem,1fr)_minmax(8rem,.8fr)_7rem] bg-muted/15 px-2 text-[11px] font-semibold uppercase text-muted-foreground lg:grid"
                    aria-hidden="true"
                  >
                    <span className="px-2 py-2" />
                    <span className="px-2 py-2">Respondent</span>
                    <span className="px-2 py-2">Chestionar</span>
                    <span className="px-2 py-2">Țintă</span>
                    <span className="px-2 py-2">Grup</span>
                    <span className="px-2 py-2">Stare</span>
                  </div>

                  <div role="list" className="divide-y divide-border/80">
                    {targetGroup.assignments.map((assignment) => {
                      const saved = Boolean(assignment.existing_assignment_id);
                      const selected = selectedKeys.has(assignment.key);
                      return (
                        <div
                          key={assignment.key}
                          role="listitem"
                          className="grid min-w-0 grid-cols-[2rem_minmax(0,1fr)] gap-x-3 gap-y-3 px-4 py-4 transition-colors hover:bg-muted/35 lg:grid-cols-[3rem_minmax(9rem,1fr)_minmax(12rem,1.2fr)_minmax(9rem,1fr)_minmax(8rem,.8fr)_7rem] lg:items-center lg:gap-0 lg:px-2 lg:py-3"
                        >
                          <div className="pt-0.5 lg:px-2 lg:pt-0">
                            <Checkbox
                              aria-label={`Selectează asignarea pentru ${assignment.respondent_name}`}
                              checked={saved || selected}
                              disabled={saved || readOnly}
                              onCheckedChange={() => onToggleItem(assignment.key)}
                            />
                          </div>
                          <PlanRowValue label="Respondent" strong>{assignment.respondent_name}</PlanRowValue>
                          <PlanRowValue label="Chestionar">
                            {formatQuestionnaireLabel(assignment.questionnaire_key)}
                          </PlanRowValue>
                          <PlanRowValue label="Țintă">{formatPlanTarget(assignment)}</PlanRowValue>
                          <PlanRowValue label="Grup">{scope.name}</PlanRowValue>
                          <div className="col-start-2 lg:col-start-auto lg:px-2">
                            <span className="mb-1 block text-[11px] font-semibold text-muted-foreground lg:hidden">
                              Stare
                            </span>
                            <AssignmentState saved={saved} selected={selected} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </section>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

function PlanRowValue({
  label,
  strong = false,
  children,
}: {
  label: string;
  strong?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="col-start-2 min-w-0 lg:col-start-auto lg:px-2">
      <span className="mb-1 block text-[11px] font-semibold text-muted-foreground lg:hidden">{label}</span>
      <span className={cn("break-words", strong && "font-semibold text-foreground")}>{children}</span>
    </div>
  );
}

function buildAssignmentTargetGroups(assignments: CompanyAssignmentPlanItem[]) {
  const groups = new Map<
    string,
    {
      id: string;
      name: string;
      type: AssignmentTargetType;
      assignments: CompanyAssignmentPlanItem[];
    }
  >();

  for (const assignment of assignments) {
    const targetId =
      assignment.target_type === "person"
        ? (assignment.target_person_id ?? assignment.target_person_name)
        : assignment.target_type === "team"
          ? (assignment.target_team_id ?? assignment.target_team_name)
          : assignment.respondent_profile_id;
    const id = `${assignment.target_type}:${targetId ?? assignment.key}`;
    const current = groups.get(id);
    if (current) {
      current.assignments.push(assignment);
      continue;
    }

    groups.set(id, {
      id,
      name: formatPlanTarget(assignment),
      type: assignment.target_type,
      assignments: [assignment],
    });
  }

  return Array.from(groups.values());
}

function buildAssignmentPlanGroups(plan: CompanyAssignmentPlan) {
  const assignmentsByScope = new Map<string, CompanyAssignmentPlanItem[]>();
  for (const assignment of plan.assignments) {
    const current = assignmentsByScope.get(assignment.scope_id) ?? [];
    current.push(assignment);
    assignmentsByScope.set(assignment.scope_id, current);
  }

  const knownScopeIds = new Set(plan.scopes.map((scope) => scope.id));
  const groups = plan.scopes
    .map((scope) => ({ scope, assignments: assignmentsByScope.get(scope.id) ?? [] }))
    .filter((group) => group.assignments.length > 0);

  for (const assignment of plan.assignments) {
    if (knownScopeIds.has(assignment.scope_id)) continue;
    knownScopeIds.add(assignment.scope_id);
    groups.push({
      scope: {
        id: assignment.scope_id,
        name: assignment.scope_name,
        type: assignment.scope_type,
        participant_ids: [],
      },
      assignments: assignmentsByScope.get(assignment.scope_id) ?? [],
    });
  }

  return groups;
}

function emptyAssignmentPlan(projectId: string | null): CompanyAssignmentPlan {
  return {
    project_id: projectId,
    assessment_cycle_id: null,
    source_cycle_id: null,
    scopes: [],
    assignments: [],
    suggested_count: 0,
    existing_count: 0,
  };
}

export function buildCyclePreviewPlan(
  assignments: CompanyAssignment[],
  participantsById: Map<string, CompanyParticipant>,
  teamsById: Map<string, CompanyTeam>,
): CompanyAssignmentPlan {
  const scopes = new Map<string, CompanyAssignmentPlan["scopes"][number]>();
  const items = assignments.map((assignment) => {
    const respondent = participantsById.get(assignment.respondent_profile_id);
    const targetPerson = assignment.target_person_id
      ? participantsById.get(assignment.target_person_id)
      : null;
    const targetTeam = assignment.target_team_id ? teamsById.get(assignment.target_team_id) : null;
    const scopeId = assignment.target_type === "person"
      ? `manager:${assignment.target_person_id ?? assignment.id}`
      : assignment.target_type === "team"
        ? `team:${assignment.target_team_id ?? assignment.id}`
        : `self:${assignment.respondent_profile_id}`;
    const scopeName = targetPerson?.full_name
      ?? targetTeam?.name
      ?? respondent?.full_name
      ?? "Grup de evaluare";
    const scopeType = assignment.target_type === "person"
      ? "manager"
      : assignment.target_type === "team"
        ? (targetTeam?.type === "leadership" ? "leadership_team" : "manager_team")
        : "member";

    if (!scopes.has(scopeId)) {
      scopes.set(scopeId, {
        id: scopeId,
        name: scopeName,
        type: scopeType,
        participant_ids: [],
      });
    }
    const scope = scopes.get(scopeId)!;
    if (!scope.participant_ids.includes(assignment.respondent_profile_id)) {
      scope.participant_ids.push(assignment.respondent_profile_id);
    }

    return {
      key: `preview:${assignment.id}`,
      scope_id: scopeId,
      scope_name: scopeName,
      scope_type: scopeType,
      respondent_profile_id: assignment.respondent_profile_id,
      respondent_name: respondent?.full_name ?? "Participant",
      questionnaire_key: assignment.questionnaire_key,
      target_type: assignment.target_type,
      target_person_id: assignment.target_person_id,
      target_person_name: targetPerson?.full_name ?? null,
      target_team_id: assignment.target_team_id,
      target_team_name: targetTeam?.name ?? null,
      target_team_type: targetTeam?.type ?? null,
      target_team_member_ids: [],
      target_team_leader_id: null,
      visibility_policy: assignment.visibility_policy ?? "trainer_raw_review",
      selected: true,
      existing_assignment_id: null,
    } satisfies CompanyAssignmentPlanItem;
  });

  return {
    project_id: assignments[0]?.project_id ?? null,
    assessment_cycle_id: assignments[0]?.assessment_cycle_id ?? null,
    scopes: Array.from(scopes.values()),
    assignments: items,
    suggested_count: items.length,
    existing_count: 0,
  };
}

function formatScopeType(type: string): string {
  if (type === "leadership_team") return "Echipă de leadership";
  if (type === "manager_team") return "Echipă funcțională";
  if (type === "manager") return "Autoevaluare și feedback 360";
  if (type === "member") return "Participant";
  return "Grup de asignări";
}

function AssignmentState({ saved, selected }: { saved: boolean; selected: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold",
        saved
          ? "status-success-soft"
          : selected
            ? "bg-burgundy/10 text-burgundy"
            : "bg-muted text-muted-foreground",
      )}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          saved ? "bg-success-ink" : selected ? "bg-burgundy" : "bg-muted-foreground",
        )}
        aria-hidden="true"
      />
      {saved ? "Salvată" : selected ? "Selectată" : "Propusă"}
    </span>
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
    <div className="block">
      <span className="text-xs font-semibold text-muted-foreground">{label}</span>
      <SelectControl
        label={label}
        wrapperClassName="mt-1.5"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
      >
        {children}
      </SelectControl>
    </div>
  );
}

function mergeAssignments(
  current: CompanyAssignment[],
  incoming: CompanyAssignment[],
): CompanyAssignment[] {
  const merged = new Map(current.map((assignment) => [assignment.id, assignment]));
  for (const assignment of incoming) merged.set(assignment.id, assignment);
  return Array.from(merged.values());
}

function formatQuestionnaireLabel(key: string): string {
  return questionnaireLabels[key] ?? key.replaceAll("_", " ");
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

function formatSavedTarget(
  assignment: CompanyAssignment,
  participantsById: Map<string, CompanyParticipant>,
  teamsById: Map<string, CompanyTeam>,
): string {
  if (assignment.target_type === "person") {
    return assignment.target_person_id
      ? (participantsById.get(assignment.target_person_id)?.full_name ?? "Persoană")
      : "Persoană";
  }
  if (assignment.target_type === "team") {
    return assignment.target_team_id
      ? (teamsById.get(assignment.target_team_id)?.name ?? "Echipă")
      : "Echipă";
  }
  return participantsById.get(assignment.respondent_profile_id)?.full_name ?? "Participant";
}
