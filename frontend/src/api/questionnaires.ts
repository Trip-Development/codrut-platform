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
    description: "Source pending. Assignment targets remain many-to-many capable.",
    status: "planned",
    audience: "participant",
  },
];

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
    if (!response.ok) return null;

    return (await response.json()) as QuestionnaireDefinition;
  } catch {
    return null;
  }
}
