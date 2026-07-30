import {
  inviteTaskHref,
  type InviteTask,
  type InviteTaskStatus,
} from "@/api/invites";

export type ParticipantTaskGroup = {
  id: string;
  kind: "single" | "review360";
  title: string;
  detail: string;
  status: InviteTaskStatus;
  estimatedMinutes: number;
  targetSummary: string;
  completedCount: number;
  totalCount: number;
  pendingCount: number;
  tasks: InviteTask[];
  actionTask?: InviteTask;
  projectId?: string | null;
  projectName?: string | null;
};

export type ParticipantTaskProject = {
  id: string;
  participantProfileId?: string;
  companyName?: string;
  name: string;
  status: "active" | "completed" | "archived";
  historyBucket: "current" | "history";
  deadlineLabel: string;
  completedCount: number;
  totalCount: number;
  groups: ParticipantTaskGroup[];
};

const review360Keys = new Set(["boss_360", "boss_360_en", "icare"]);

export const participantTaskStatusCopy: Record<InviteTaskStatus, { label: string; helper: string }> = {
  not_started: {
    label: "De completat",
    helper: "Alege un moment liniștit pentru completare.",
  },
  in_progress: {
    label: "În lucru",
    helper: "Continuă de unde ai rămas.",
  },
  completed: {
    label: "Finalizat",
    helper: "Răspunsurile au fost salvate.",
  },
};

export function groupParticipantTasks(tasks: InviteTask[]): ParticipantTaskGroup[] {
  const groups: ParticipantTaskGroup[] = [];
  const reviewTasksByProject = new Map<string, InviteTask[]>();

  for (const task of tasks) {
    if (isReview360Task(task)) {
      const projectKey = task.projectId ?? task.projectName ?? "legacy";
      const roundKey = task.assignmentRoundId ?? "legacy";
      const questionnaireKey = task.questionnaireKey || "legacy";
      const definitionKey = task.questionnaireDefinitionId ?? "legacy";
      const groupKey = `${projectKey}:${roundKey}:${questionnaireKey}:${definitionKey}`;
      const projectTasks = reviewTasksByProject.get(groupKey) ?? [];
      projectTasks.push(task);
      reviewTasksByProject.set(groupKey, projectTasks);
      continue;
    }
    groups.push(singleTaskGroup(task));
  }

  for (const reviewTasks of reviewTasksByProject.values()) {
    groups.push(review360TaskGroup(reviewTasks));
  }

  return groups.sort((left, right) => firstTaskIndex(tasks, left) - firstTaskIndex(tasks, right));
}

export function groupParticipantTasksByProject(
  tasks: InviteTask[],
  projectMetadata: Array<{
    id: string;
    participantProfileId?: string;
    companyName?: string;
    name: string;
    status?: "active" | "completed" | "archived";
    historyBucket?: "current" | "history";
    deadlineLabel?: string;
  }> = [],
): ParticipantTaskProject[] {
  const metadataById = new Map(projectMetadata.map((project) => [project.id, project]));
  const tasksByProject = new Map<string, InviteTask[]>();

  for (const task of tasks) {
    const projectId = task.projectId ?? `legacy:${task.projectName ?? "fara-proiect"}`;
    const projectTasks = tasksByProject.get(projectId) ?? [];
    projectTasks.push(task);
    tasksByProject.set(projectId, projectTasks);
  }

  return Array.from(tasksByProject, ([id, projectTasks]) => {
    const metadata = metadataById.get(id);
    const groups = groupParticipantTasks(projectTasks);
    const completedCount = projectTasks.filter(
      (task) => task.status === "completed",
    ).length;
    return {
      id,
      participantProfileId: metadata?.participantProfileId,
      companyName: metadata?.companyName,
      name:
        metadata?.name ??
        projectTasks[0]?.projectName ??
        "Chestionare fără proiect",
      status: metadata?.status ?? "active",
      historyBucket: metadata?.historyBucket ?? "current",
      deadlineLabel:
        metadata?.deadlineLabel ??
        projectTasks.find((task) => task.deadlineLabel)?.deadlineLabel ??
        "Fără termen",
      completedCount,
      totalCount: projectTasks.length,
      groups,
    };
  }).sort(compareTaskProjects);
}

export function participantTaskProjectsFromCatalog(
  projects: Array<{
    id: string;
    participantProfileId?: string;
    companyName?: string;
    name: string;
    status: "active" | "completed" | "archived";
    historyBucket: "current" | "history";
    deadlineLabel: string;
    completedCount: number;
    totalCount: number;
    questionnaires: InviteTask[];
  }>,
): ParticipantTaskProject[] {
  return projects.map((project) => ({
    id: project.id,
    participantProfileId: project.participantProfileId,
    companyName: project.companyName,
    name: project.name,
    status: project.status,
    historyBucket: project.historyBucket,
    deadlineLabel: project.deadlineLabel,
    completedCount: project.completedCount,
    totalCount: project.totalCount,
    groups: groupParticipantTasks(project.questionnaires),
  }));
}

export function participantTaskGroupHref(
  group: ParticipantTaskGroup,
  options: { returnTo?: string; inviteToken?: string } = {},
): string | null {
  if (!group.actionTask) return null;
  if (group.kind !== "review360") return inviteTaskHref(group.actionTask, options);

  const safeTargetLabel = safeReviewTargetLabel(group.actionTask.targetLabel);
  return inviteTaskHref({ ...group.actionTask, targetLabel: safeTargetLabel }, options);
}

export function isReview360Task(task: InviteTask): boolean {
  return review360Keys.has(task.questionnaireKey);
}

export function nextPendingReviewTask(
  tasks: InviteTask[],
  currentAssignmentId: string,
): InviteTask | undefined {
  const group = groupParticipantTasks(tasks).find(
    (candidate) =>
      candidate.kind === "review360" &&
      candidate.tasks.some((task) => task.assignmentId === currentAssignmentId),
  );
  if (!group) return undefined;

  const currentIndex = group.tasks.findIndex(
    (task) => task.assignmentId === currentAssignmentId,
  );
  const pending = group.tasks.filter(
    (task) =>
      task.assignmentId !== currentAssignmentId &&
      task.status !== "completed",
  );
  return (
    pending.find(
      (task) =>
        group.tasks.findIndex(
          (candidate) => candidate.assignmentId === task.assignmentId,
        ) > currentIndex,
    ) ?? pending[0]
  );
}

function singleTaskGroup(task: InviteTask): ParticipantTaskGroup {
  return {
    id: task.assignmentId || task.id,
    kind: "single",
    title: task.title,
    detail: task.detail,
    status: task.status,
    estimatedMinutes: task.estimatedMinutes,
    targetSummary: task.targetLabel || "Sarcină individuală",
    completedCount: task.status === "completed" ? 1 : 0,
    totalCount: 1,
    pendingCount: task.status === "completed" ? 0 : 1,
    tasks: [task],
    actionTask: task.status === "completed" ? undefined : task,
    projectId: task.projectId,
    projectName: task.projectName,
  };
}

function review360TaskGroup(tasks: InviteTask[]): ParticipantTaskGroup {
  const completedCount = tasks.filter((task) => task.status === "completed").length;
  const pendingCount = tasks.length - completedCount;
  const status = groupStatus(tasks);
  const targetCount = tasks.length;

  return {
    id: [
      "review-360",
      tasks[0]?.projectId ?? tasks[0]?.projectName ?? "legacy",
      tasks[0]?.assignmentRoundId ?? "legacy",
      tasks[0]?.questionnaireKey ?? "legacy",
      tasks[0]?.questionnaireDefinitionId ?? "legacy",
    ].join(":"),
    kind: "review360",
    title: "Review 360",
    detail:
      pendingCount > 0
        ? `Completează feedbackul pentru ${pendingCount} din ${targetCount} persoane.`
        : `Ai finalizat feedbackul pentru ${targetCount} persoane.`,
    status,
    estimatedMinutes: tasks.reduce((total, task) => total + task.estimatedMinutes, 0),
    targetSummary: `${targetCount} ${targetCount === 1 ? "persoană de evaluat" : "persoane de evaluat"}`,
    completedCount,
    totalCount: tasks.length,
    pendingCount,
    tasks,
    actionTask: tasks.find((task) => task.status !== "completed"),
    projectId: tasks[0]?.projectId,
    projectName: tasks[0]?.projectName,
  };
}

function groupStatus(tasks: InviteTask[]): InviteTaskStatus {
  if (tasks.every((task) => task.status === "completed")) return "completed";
  if (tasks.some((task) => task.status === "in_progress")) return "in_progress";
  return "not_started";
}

export function safeReviewTargetLabel(value: string): string {
  const cleaned = value.trim().replace(/\s+/g, " ");
  if (!cleaned || cleaned.toLocaleLowerCase("ro-RO") === "autoevaluare") return "";
  if (cleaned.includes("@")) return "";
  if (/[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/i.test(cleaned)) {
    return "";
  }
  return cleaned;
}

function firstTaskIndex(allTasks: InviteTask[], group: ParticipantTaskGroup): number {
  const first = group.tasks[0];
  return Math.max(0, allTasks.findIndex((task) => task.assignmentId === first.assignmentId));
}

function compareTaskProjects(
  left: ParticipantTaskProject,
  right: ParticipantTaskProject,
): number {
  const leftComplete = left.completedCount === left.totalCount;
  const rightComplete = right.completedCount === right.totalCount;
  if (leftComplete !== rightComplete) return leftComplete ? 1 : -1;
  if (left.historyBucket !== right.historyBucket) {
    return left.historyBucket === "current" ? -1 : 1;
  }
  return left.name.localeCompare(right.name, "ro");
}
