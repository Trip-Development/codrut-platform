"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2Icon,
  ClipboardListIcon,
  Loader2Icon,
  PlusIcon,
  RefreshCwIcon,
} from "lucide-react";

import {
  createCompanyAssignment,
  getCompanyDefaultAssignmentPlan,
  saveCompanyDefaultAssignmentPlan,
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
import { ModalLayer } from "@/components/ui/modal-layer";
import { SelectControl } from "@/components/ui/select-control";
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

export type AssignmentWorkspaceProps = {
  companyId: string;
  companyName: string;
  projects: CompanyProject[];
  selectedProjectId: string | null;
  participants: CompanyParticipant[];
  assignments: CompanyAssignment[];
  teams: CompanyTeam[];
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
  onAssignmentsChange,
}: AssignmentWorkspaceProps) {
  const { get, searchKey, setParams } = useUrlState();
  const assignmentSavingRef = useRef(false);
  const planLoadingRef = useRef(false);
  const planSavingRef = useRef(false);
  const [assignmentState, setAssignmentState] = useState(assignments);
  const [questionnaires, setQuestionnaires] = useState<QuestionnaireDefinitionStub[]>([]);
  const [questionnaireMessage, setQuestionnaireMessage] = useState<string | null>(null);
  const [assignmentSaving, setAssignmentSaving] = useState(false);
  const [plan, setPlan] = useState<CompanyAssignmentPlan | null>(null);
  const [selectedPlanKeys, setSelectedPlanKeys] = useState<Set<string>>(new Set());
  const [planLoading, setPlanLoading] = useState(false);
  const [planSaving, setPlanSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
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

  useEffect(() => {
    setAssignmentState(assignments);
  }, [assignments]);

  useEffect(() => {
    setShowAdvancedAssignmentModal(get("modal") === "advanced-assignment");
  }, [get, searchKey]);

  useEffect(() => {
    setPlan(null);
    setSelectedPlanKeys(new Set());
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
  const currentOperation = planLoading
    ? { title: "Generăm planul", detail: "Pregătim propunerile pentru proiect." }
    : planSaving
      ? { title: "Salvăm asignările", detail: `${selectedPlanItems.length} selectate.` }
      : assignmentSaving
        ? { title: "Creăm asignarea", detail: "Salvăm excepția în proiect." }
        : null;

  function publishAssignments(next: CompanyAssignment[]) {
    setAssignmentState(next);
    onAssignmentsChange?.(next);
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
    setShowAdvancedAssignmentModal(open);
    setParams({ modal: open ? "advanced-assignment" : null }, open ? "push" : "replace");
  }

  async function handleCreateAssignment() {
    if (!canCreateAssignment || assignmentSavingRef.current) return;
    assignmentSavingRef.current = true;
    setAssignmentSaving(true);
    setMessage(null);

    const payload: CreateCompanyAssignmentPayload = {
      projectId: selectedProjectId,
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
      setMessage(error instanceof Error ? error.message : "Asignarea nu a putut fi creată.");
    } finally {
      assignmentSavingRef.current = false;
      setAssignmentSaving(false);
    }
  }

  async function handleGeneratePlan() {
    if (planLoadingRef.current || planSavingRef.current) return;
    if (!canUseProjectActions) {
      setMessage("Alege un proiect înainte de a genera planul.");
      return;
    }

    planLoadingRef.current = true;
    setPlanLoading(true);
    setMessage(null);
    try {
      const generated = await getCompanyDefaultAssignmentPlan(
        companyId,
        {},
        { projectId: selectedProjectId },
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
      const result = await saveCompanyDefaultAssignmentPlan(
        companyId,
        selectedPlanItems,
        selectedProjectId,
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
              disabled={participants.length === 0}
            >
              <PlusIcon data-icon="inline-start" aria-hidden="true" />
              Asignare individuală
            </Button>
            {!plan && assignmentState.length === 0 ? (
              <Button
                type="button"
                size="sm"
                onClick={() => void handleGeneratePlan()}
                disabled={!canUseProjectActions || planLoading || participants.length === 0}
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
                disabled={!canUseProjectActions || planLoading || participants.length === 0}
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
        />
      </section>

      {showAdvancedAssignmentModal ? (
        <ModalLayer
          labelledBy="advanced-assignment-title"
          onClose={() => setAdvancedAssignmentModalOpen(false)}
          panelClassName="max-w-2xl"
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
    </div>
  );
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
}: {
  assignments: CompanyAssignment[];
  plan: CompanyAssignmentPlan | null;
  participantsById: Map<string, CompanyParticipant>;
  teamsById: Map<string, CompanyTeam>;
  selectedKeys: Set<string>;
  allSelected: boolean;
  onToggleAll: (checked: boolean) => void;
  onToggleItem: (key: string) => void;
}) {
  const hasRows = plan ? plan.assignments.length > 0 : assignments.length > 0;

  return (
    <div className="overflow-x-auto">
      <table className="min-w-[760px] w-full text-left text-sm">
        <thead className="bg-muted text-[11px] font-bold uppercase tracking-[0.08em] text-muted-foreground">
          <tr>
            <th className="w-12 px-4 py-3">
              {plan ? (
                <Checkbox
                  aria-label="Selectează toate asignările propuse"
                  checked={allSelected}
                  disabled={plan.assignments.every((assignment) => Boolean(assignment.existing_assignment_id))}
                  onCheckedChange={(checked) => onToggleAll(checked === true)}
                />
              ) : null}
            </th>
            <th className="px-4 py-3">Respondent</th>
            <th className="px-4 py-3">Chestionar</th>
            <th className="px-4 py-3">Țintă</th>
            <th className="px-4 py-3">Grup</th>
            <th className="px-4 py-3">Stare</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {!hasRows ? (
            <tr>
              <td colSpan={6} className="px-4 py-10 text-center">
                <p className="font-semibold text-foreground">Nicio asignare</p>
                {plan ? (
                  <p className="mt-1 text-sm text-muted-foreground">
                    Structura proiectului nu a produs propuneri.
                  </p>
                ) : null}
              </td>
            </tr>
          ) : plan ? (
            plan.assignments.map((assignment) => {
              const saved = Boolean(assignment.existing_assignment_id);
              return (
                <tr key={assignment.key} className="hover:bg-muted/60">
                  <td className="px-4 py-3">
                    <Checkbox
                      aria-label={`Selectează asignarea pentru ${assignment.respondent_name}`}
                      checked={saved || selectedKeys.has(assignment.key)}
                      disabled={saved}
                      onCheckedChange={() => onToggleItem(assignment.key)}
                    />
                  </td>
                  <td className="px-4 py-3 font-semibold text-foreground">
                    {assignment.respondent_name}
                  </td>
                  <td className="px-4 py-3">{formatQuestionnaireLabel(assignment.questionnaire_key)}</td>
                  <td className="px-4 py-3">
                    <p className="font-medium text-foreground">{formatPlanTarget(assignment)}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {formatTargetType(assignment.target_type)}
                    </p>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{assignment.scope_name}</td>
                  <td className="px-4 py-3">
                    <AssignmentState saved={saved} selected={selectedKeys.has(assignment.key)} />
                  </td>
                </tr>
              );
            })
          ) : (
            assignments.map((assignment) => (
              <tr key={assignment.id} className="hover:bg-muted/60">
                <td className="px-4 py-3" />
                <td className="px-4 py-3 font-semibold text-foreground">
                  {participantsById.get(assignment.respondent_profile_id)?.full_name ?? "Participant"}
                </td>
                <td className="px-4 py-3">{formatQuestionnaireLabel(assignment.questionnaire_key)}</td>
                <td className="px-4 py-3">
                  <p className="font-medium text-foreground">
                    {formatSavedTarget(assignment, participantsById, teamsById)}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {formatTargetType(assignment.target_type)}
                  </p>
                </td>
                <td className="px-4 py-3 text-muted-foreground">Proiect</td>
                <td className="px-4 py-3">
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
