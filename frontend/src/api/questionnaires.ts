import { getApiBaseUrl } from "./runtime";

export type QuestionnaireDefinitionStub = {
  id: string;
  name: string;
  description: string;
  status: "planned" | "draft" | "active";
  version?: number;
  source?: string;
  audience: "leadership" | "team" | "participant";
  estimatedItems?: number;
};

export type QuestionnaireScaleOption = {
  value: number;
  label: string;
};

export type QuestionnaireStatement = {
  id: string;
  code: string;
  label: string;
  scoring?: Record<string, string>;
};

export type QuestionnaireQuestion = {
  id: string;
  code: string;
  type: "likert" | "statement_score_set";
  label: string;
  required: boolean;
  instructions?: string;
  scale: QuestionnaireScaleOption[];
  statements?: QuestionnaireStatement[];
};

export type QuestionnaireSection = {
  id: string;
  title: string;
  questions: QuestionnaireQuestion[];
};

export type QuestionnaireDefinition = {
  key: string;
  version: number;
  title: string;
  description: string;
  schema: {
    schema_version: string;
    source?: {
      path?: string;
      status?: string;
      type?: string;
    };
    instructions?: string;
    sections: QuestionnaireSection[];
    scoring?: Record<string, unknown>;
  };
};

export type QuestionnaireResponseRecord = {
  id: string;
  assignment_id: string;
  questionnaire_key: string;
  questionnaire_version: number;
  status: "draft" | "submitted";
  answers: Record<string, number>;
};

const seededAssignmentQuestionnaires: Record<string, string> = {
  "11111111-1111-4111-8111-111111111111": "lencioni",
  "22222222-2222-4222-8222-222222222222": "boss_360",
  "33333333-3333-4333-8333-333333333333": "lencioni",
};

function stubFromDefinition(definition: QuestionnaireDefinition): QuestionnaireDefinitionStub {
  const questions = definition.schema.sections.flatMap((section) => section.questions);
  const estimatedItems = questions.reduce((count, question) => {
    return count + (question.statements?.length ?? 1);
  }, 0);

  return {
    id: definition.key,
    name: definition.title,
    description: definition.description,
    status: "active",
    version: definition.version,
    source: definition.schema.source?.path,
    audience: definition.key === "distress_drivers" ? "leadership" : "team",
    estimatedItems,
  };
}

const fallbackDefinitions: QuestionnaireDefinitionStub[] = [
  {
    id: "lencioni",
    name: "Lencioni team assessment",
    description: "15 item team assessment with five dysfunction scoring groups.",
    status: "active",
    version: 1,
    source: "docs/questionnaires/lencioni.pdf",
    audience: "team",
    estimatedItems: 15,
  },
  {
    id: "distress_drivers",
    name: "Distress drivers",
    description: "10 scored statement sets for TA driver self-assessment.",
    status: "active",
    version: 1,
    source: "docs/questionnaires/distress_drivers.pdf",
    audience: "leadership",
    estimatedItems: 50,
  },
  {
    id: "pcm_baseline",
    name: "PCM baseline",
    description: "Source pending. Will use the same versioned definition format.",
    status: "planned",
    audience: "leadership",
  },
  {
    id: "phase",
    name: "Phase",
    description: "Source pending. Will use the same reusable questionnaire renderer.",
    status: "planned",
    audience: "leadership",
  },
  {
    id: "boss_360",
    name: "Boss / manager 360",
    description: "Prototype 360 feedback form for a direct manager.",
    status: "active",
    version: 1,
    audience: "participant",
    estimatedItems: 5,
  },
];

const fallbackDefinitionDetails: Record<string, QuestionnaireDefinition> = {
  boss_360: {
    key: "boss_360",
    version: 1,
    title: "Feedback 360 pentru manager",
    description: "Formular scurt de feedback confidential pentru persoana catre care raportezi.",
    schema: {
      schema_version: "questionnaire.v1",
      source: {
        type: "prototype",
        path: "seeded/boss_360",
        status: "provisional",
      },
      instructions:
        "Raspunde concret si echilibrat. Persoana evaluata nu primeste raspunsurile individuale.",
      sections: [
        {
          id: "manager_feedback",
          title: "Feedback manager",
          questions: [
            {
              id: "boss_360_q01",
              code: "Q1",
              type: "likert",
              label: "Managerul meu clarifica asteptarile si prioritatile.",
              required: true,
              scale: [
                { value: 1, label: "Rar" },
                { value: 2, label: "Uneori" },
                { value: 3, label: "De obicei" },
              ],
            },
            {
              id: "boss_360_q02",
              code: "Q2",
              type: "likert",
              label: "Managerul meu ofera feedback util si la timp.",
              required: true,
              scale: [
                { value: 1, label: "Rar" },
                { value: 2, label: "Uneori" },
                { value: 3, label: "De obicei" },
              ],
            },
            {
              id: "boss_360_q03",
              code: "Q3",
              type: "likert",
              label: "Managerul meu creeaza spatiu pentru intrebari si opinii diferite.",
              required: true,
              scale: [
                { value: 1, label: "Rar" },
                { value: 2, label: "Uneori" },
                { value: 3, label: "De obicei" },
              ],
            },
            {
              id: "boss_360_q04",
              code: "Q4",
              type: "likert",
              label: "Managerul meu sustine colaborarea in echipa.",
              required: true,
              scale: [
                { value: 1, label: "Rar" },
                { value: 2, label: "Uneori" },
                { value: 3, label: "De obicei" },
              ],
            },
            {
              id: "boss_360_q05",
              code: "Q5",
              type: "likert",
              label: "Managerul meu gestioneaza tensiunile intr-un mod constructiv.",
              required: true,
              scale: [
                { value: 1, label: "Rar" },
                { value: 2, label: "Uneori" },
                { value: 3, label: "De obicei" },
              ],
            },
          ],
        },
      ],
    },
  },
};

export async function listQuestionnaireDefinitionStubs(): Promise<QuestionnaireDefinitionStub[]> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/forms/definitions`, {
      cache: "no-store",
    });
    if (!response.ok) return fallbackDefinitions;

    const definitions = (await response.json()) as QuestionnaireDefinition[];
    const activeDefinitions = definitions.map(stubFromDefinition);
    const plannedDefinitions = fallbackDefinitions.filter((definition) => definition.status !== "active");
    return [...activeDefinitions, ...plannedDefinitions];
  } catch {
    return fallbackDefinitions;
  }
}

export async function getQuestionnaireDefinition(
  key: string,
): Promise<QuestionnaireDefinition | null> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/forms/definitions/${key}`, {
      cache: "no-store",
    });
    if (!response.ok) return fallbackDefinitionDetails[key] ?? null;

    return (await response.json()) as QuestionnaireDefinition;
  } catch {
    return fallbackDefinitionDetails[key] ?? null;
  }
}

export async function saveQuestionnaireResponse(
  assignmentId: string,
  answers: Record<string, number>,
): Promise<QuestionnaireResponseRecord> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/forms/assignments/${assignmentId}/response`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    });

    if (!response.ok) {
      return seededQuestionnaireResponse(assignmentId, answers, "draft");
    }

    return (await response.json()) as QuestionnaireResponseRecord;
  } catch {
    return seededQuestionnaireResponse(assignmentId, answers, "draft");
  }
}

export async function submitQuestionnaireResponse(
  assignmentId: string,
  answers: Record<string, number>,
): Promise<QuestionnaireResponseRecord> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/forms/assignments/${assignmentId}/response/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    });

    if (!response.ok) {
      return seededQuestionnaireResponse(assignmentId, answers, "submitted");
    }

    return (await response.json()) as QuestionnaireResponseRecord;
  } catch {
    return seededQuestionnaireResponse(assignmentId, answers, "submitted");
  }
}

function seededQuestionnaireResponse(
  assignmentId: string,
  answers: Record<string, number>,
  status: "draft" | "submitted",
): QuestionnaireResponseRecord {
  const questionnaireKey = seededAssignmentQuestionnaires[assignmentId];

  if (!questionnaireKey) {
    throw new Error(status === "draft" ? "Nu am putut salva draftul." : "Nu am putut trimite raspunsurile.");
  }

  return {
    id: `seeded-${assignmentId}-${status}`,
    assignment_id: assignmentId,
    questionnaire_key: questionnaireKey,
    questionnaire_version: 1,
    status,
    answers,
  };
}
