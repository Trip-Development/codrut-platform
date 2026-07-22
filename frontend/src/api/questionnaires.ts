import { apiFetch } from "./http";
import {
  SYNTHETIC_QUESTIONNAIRE_DEFINITIONS,
  SYNTHETIC_QUESTIONNAIRE_STUBS,
} from "./questionnaire-synthetic-fallback";
import { getApiBaseUrl, isDemoFallbackEnabled, isSeededDemoFallbackEnabled } from "./runtime";

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
  value: number | string;
  label: string;
  description?: string;
};

export type QuestionnaireStatement = {
  id: string;
  code: string;
  label: string;
  scoring?: Record<string, string>;
  scale?: QuestionnaireScaleOption[];
};

export type QuestionnaireQuestion = {
  id: string;
  code: string;
  type: "likert" | "statement_score_set" | "single_choice";
  label: string;
  required: boolean;
  instructions?: string;
  scale: QuestionnaireScaleOption[];
  statements?: QuestionnaireStatement[];
};

export type QuestionnaireAnswerValue = number | string;

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
  active?: boolean;
  schema: {
    schema_version: string;
    source?: {
      path?: string;
      status?: string;
      type?: string;
    };
    audience?: "leadership" | "team" | "participant";
    instructions?: string;
    sections: QuestionnaireSection[];
    scoring?: Record<string, unknown>;
  };
};

export type ParticipantQuestionnaireStatement = Omit<QuestionnaireStatement, "scoring">;
export type ParticipantQuestionnaireQuestion = Omit<QuestionnaireQuestion, "statements"> & {
  statements?: ParticipantQuestionnaireStatement[];
};
export type ParticipantQuestionnaireSection = Omit<QuestionnaireSection, "questions"> & {
  questions: ParticipantQuestionnaireQuestion[];
};
export type ParticipantQuestionnaireDefinition = Omit<QuestionnaireDefinition, "schema"> & {
  schema: {
    schema_version: string;
    audience?: "leadership" | "team" | "participant";
    instructions?: string;
    sections: ParticipantQuestionnaireSection[];
  };
};

export type QuestionnaireResponseRecord = {
  id: string;
  assignment_id: string;
  questionnaire_key: string;
  questionnaire_version: number;
  status: "draft" | "submitted";
  answers: Record<string, QuestionnaireAnswerValue>;
};

export class QuestionnaireRequestError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "QuestionnaireRequestError";
    this.status = status;
    this.code = code;
  }
}

export function isQuestionnaireSessionError(error: unknown): boolean {
  return (
    error instanceof QuestionnaireRequestError &&
    (error.status === 401 || error.status === 403)
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function participantScale(payload: unknown): QuestionnaireScaleOption[] {
  if (!Array.isArray(payload)) throw invalidParticipantDefinition();
  return payload.map((option) => {
    if (!isRecord(option) || !["number", "string"].includes(typeof option.value) || typeof option.label !== "string") {
      throw invalidParticipantDefinition();
    }
    return {
      value: option.value as number | string,
      label: option.label,
      ...(typeof option.description === "string" ? { description: option.description } : {}),
    };
  });
}

function invalidParticipantDefinition(): QuestionnaireRequestError {
  return new QuestionnaireRequestError(
    "Chestionarul primit nu are un format valid. Încearcă din nou.",
    502,
    "invalid_definition_response",
  );
}

export function participantQuestionnaireDefinitionFromPayload(
  payload: unknown,
): ParticipantQuestionnaireDefinition {
  if (
    !isRecord(payload)
    || typeof payload.key !== "string"
    || typeof payload.version !== "number"
    || typeof payload.title !== "string"
    || typeof payload.description !== "string"
    || !isRecord(payload.schema)
    || typeof payload.schema.schema_version !== "string"
    || !Array.isArray(payload.schema.sections)
  ) {
    throw invalidParticipantDefinition();
  }

  const sections = payload.schema.sections.map((section) => {
    if (!isRecord(section) || typeof section.id !== "string" || typeof section.title !== "string" || !Array.isArray(section.questions)) {
      throw invalidParticipantDefinition();
    }
    const questions = section.questions.map((question) => {
      if (
        !isRecord(question)
        || typeof question.id !== "string"
        || typeof question.code !== "string"
        || !["likert", "statement_score_set", "single_choice"].includes(String(question.type))
        || typeof question.label !== "string"
        || typeof question.required !== "boolean"
      ) {
        throw invalidParticipantDefinition();
      }
      const statements = Array.isArray(question.statements)
        ? question.statements.map((statement) => {
          if (!isRecord(statement) || typeof statement.id !== "string" || typeof statement.code !== "string" || typeof statement.label !== "string") {
            throw invalidParticipantDefinition();
          }
          return {
            id: statement.id,
            code: statement.code,
            label: statement.label,
            ...(Array.isArray(statement.scale) ? { scale: participantScale(statement.scale) } : {}),
          };
        })
        : undefined;
      return {
        id: question.id,
        code: question.code,
        type: question.type as ParticipantQuestionnaireQuestion["type"],
        label: question.label,
        required: question.required,
        ...(typeof question.instructions === "string" ? { instructions: question.instructions } : {}),
        scale: participantScale(question.scale),
        ...(statements ? { statements } : {}),
      };
    });
    return { id: section.id, title: section.title, questions };
  });

  const audience = ["leadership", "team", "participant"].includes(String(payload.schema.audience))
    ? payload.schema.audience as ParticipantQuestionnaireDefinition["schema"]["audience"]
    : undefined;
  return {
    key: payload.key,
    version: payload.version,
    title: payload.title,
    description: payload.description,
    ...(typeof payload.active === "boolean" ? { active: payload.active } : {}),
    schema: {
      schema_version: payload.schema.schema_version,
      ...(audience ? { audience } : {}),
      ...(typeof payload.schema.instructions === "string" ? { instructions: payload.schema.instructions } : {}),
      sections,
    },
  };
}

const seededAssignmentQuestionnaires: Record<string, string> = {
  "11111111-1111-4111-8111-111111111111": "lencioni",
  "22222222-2222-4222-8222-222222222222": "boss_360",
  "33333333-3333-4333-8333-333333333333": "lencioni",
  "44444444-4444-4444-8444-444444444444": "distress_drivers",
};

const legacyHiddenQuestionnaireKeys = new Set([
  "icare",
  "phase",
  "boss_360_en",
  "lencioni_en",
  "distress_drivers_en",
]);
const questionnaireDefinitionCacheTtlMs = 60_000;

type CachedPromise<T> = {
  expiresAt: number;
  promise: Promise<T>;
};

const stubsCache = new Map<string, CachedPromise<QuestionnaireDefinitionStub[]>>();
const definitionCache = new Map<string, CachedPromise<QuestionnaireDefinition | null>>();

function cached<T>(cache: Map<string, CachedPromise<T>>, key: string, loader: () => Promise<T>): Promise<T> {
  const existing = cache.get(key);
  const now = Date.now();
  if (existing && existing.expiresAt > now) {
    return existing.promise;
  }

  const promise = loader().catch((error) => {
    cache.delete(key);
    throw error;
  });
  cache.set(key, { expiresAt: now + questionnaireDefinitionCacheTtlMs, promise });
  return promise;
}

export function clearQuestionnaireDefinitionCache(): void {
  stubsCache.clear();
  definitionCache.clear();
}

function stubFromDefinition(definition: QuestionnaireDefinition): QuestionnaireDefinitionStub {
  const questions = definition.schema.sections.flatMap((section) => section.questions);
  const estimatedItems = questions.reduce((count, question) => {
    return count + (question.statements?.length ?? 1);
  }, 0);
  const audience =
    definition.schema.audience ??
    (definition.key === "distress_drivers" ? "leadership" : "team");

  return {
    id: definition.key,
    name: definition.title,
    description: definition.description,
    status: definition.active === false ? "draft" : "active",
    version: definition.version,
    source: definition.schema.source?.path,
    audience,
    estimatedItems,
  };
}

export function latestDefinitionStubs(
  stubs: QuestionnaireDefinitionStub[],
): QuestionnaireDefinitionStub[] {
  const latestByKey = new Map<string, QuestionnaireDefinitionStub>();
  for (const stub of stubs) {
    const current = latestByKey.get(stub.id);
    if ((stub.version ?? 1) > (current?.version ?? 0)) {
      latestByKey.set(stub.id, stub);
    }
  }
  return Array.from(latestByKey.values()).sort((a, b) => a.name.localeCompare(b.name));
}

export function groupQuestionnaireStubsByKey(
  stubs: QuestionnaireDefinitionStub[],
): Map<string, QuestionnaireDefinitionStub[]> {
  const stubsByKey = new Map<string, QuestionnaireDefinitionStub[]>();
  for (const stub of stubs) {
    const existing = stubsByKey.get(stub.id);
    if (existing) {
      existing.push(stub);
    } else {
      stubsByKey.set(stub.id, [stub]);
    }
  }

  for (const group of stubsByKey.values()) {
    group.sort((a, b) => (b.version ?? 1) - (a.version ?? 1));
  }

  return stubsByKey;
}

const fallbackDefinitions = SYNTHETIC_QUESTIONNAIRE_STUBS;
const fallbackDefinitionDetails = SYNTHETIC_QUESTIONNAIRE_DEFINITIONS;

export async function listQuestionnaireDefinitionStubs(
  includeRetired = false,
  options: { latestOnly?: boolean } = {},
): Promise<QuestionnaireDefinitionStub[]> {
  const latestOnly = options.latestOnly ?? true;
  const cacheKey = `stubs:${includeRetired ? "all" : "active"}:${latestOnly ? "latest" : "versions"}`;
  return cached(stubsCache, cacheKey, async () => {
    try {
      const url = includeRetired
        ? `${getApiBaseUrl()}/forms/definitions?include_retired=true`
        : `${getApiBaseUrl()}/forms/definitions`;
      const response = await apiFetch(url, {
        cache: "no-store",
        credentials: "include",
      });
      if (!response.ok) {
        if (isSeededDemoFallbackEnabled()) return fallbackDefinitions;
        throw await responseError(response, "Nu am putut încărca lista de chestionare.");
      }
      const serverDefs = (await response.json()) as QuestionnaireDefinition[];
      const stubs = serverDefs
        .filter((definition) => !legacyHiddenQuestionnaireKeys.has(definition.key))
        .map(stubFromDefinition);
      return latestOnly ? latestDefinitionStubs(stubs) : stubs;
    } catch (error) {
      if (isSeededDemoFallbackEnabled()) {
        return latestOnly ? latestDefinitionStubs(fallbackDefinitions) : fallbackDefinitions;
      }
      throw normalizeResponseError(error, "Nu am putut încărca lista de chestionare.");
    }
  });
}

export async function getQuestionnaireDefinition(
  key: string,
  options: RequestInit = {},
): Promise<QuestionnaireDefinition | null> {
  const [realKey, versionStr] = key.split("@");
  const targetVersion = versionStr ? parseInt(versionStr) : null;
  const cacheKey = targetVersion ? `definition:${realKey}@${targetVersion}` : `definition:${realKey}`;

  return cached(definitionCache, cacheKey, async () => {
    try {
      const url = targetVersion
        ? `${getApiBaseUrl()}/forms/definitions/${realKey}?version=${targetVersion}`
        : `${getApiBaseUrl()}/forms/definitions/${realKey}`;
      const response = await apiFetch(url, {
        cache: "no-store",
        credentials: "include",
        ...options,
      });
      if (response.status === 404 || response.status === 410) return null;
      if (!response.ok) {
        if (isSeededDemoFallbackEnabled()) return fallbackDefinitionDetails[realKey] ?? null;
        throw await responseError(response, "Nu am putut încărca chestionarul.");
      }
      return (await response.json()) as QuestionnaireDefinition;
    } catch (error) {
      if (isSeededDemoFallbackEnabled()) return fallbackDefinitionDetails[realKey] ?? null;
      throw normalizeResponseError(error, "Nu am putut încărca chestionarul.");
    }
  });
}

export async function getSecureQuestionnaireDefinition(
  token: string,
  assignmentId: string,
): Promise<ParticipantQuestionnaireDefinition | null> {
  if (canUseSeededAssignmentFallback(assignmentId)) {
    const key = seededAssignmentQuestionnaires[assignmentId];
    const fallback = fallbackDefinitionDetails[key];
    return fallback ? participantQuestionnaireDefinitionFromPayload(fallback) : null;
  }

  try {
    const response = await apiFetch(
      `${getApiBaseUrl()}/forms/secure-links/${encodeURIComponent(token)}/assignments/${encodeURIComponent(assignmentId)}/definition`,
      {
        cache: "no-store",
      },
    );
    if (response.status === 404 || response.status === 410) return null;
    if (!response.ok) {
      throw await responseError(response, "Nu am putut încărca chestionarul.");
    }
    return participantQuestionnaireDefinitionFromPayload(await response.json());
  } catch (error) {
    throw normalizeResponseError(error, "Nu am putut încărca chestionarul.");
  }
}

export async function getAssignedQuestionnaireDefinition(
  assignmentId: string,
  options: RequestInit = {},
): Promise<ParticipantQuestionnaireDefinition | null> {
  if (canUseSeededAssignmentFallback(assignmentId)) {
    const key = seededAssignmentQuestionnaires[assignmentId];
    const fallback = fallbackDefinitionDetails[key];
    return fallback ? participantQuestionnaireDefinitionFromPayload(fallback) : null;
  }

  try {
    const response = await apiFetch(
      `${getApiBaseUrl()}/forms/assignments/${encodeURIComponent(assignmentId)}/definition`,
      {
        cache: "no-store",
        credentials: "include",
        ...options,
        headers: new Headers(options.headers),
      },
    );
    if (response.status === 404 || response.status === 410) return null;
    if (!response.ok) {
      throw await responseError(response, "Nu am putut încărca chestionarul.");
    }
    return participantQuestionnaireDefinitionFromPayload(await response.json());
  } catch (error) {
    throw normalizeResponseError(error, "Nu am putut încărca chestionarul.");
  }
}

export async function createQuestionnaireDefinitionOnServer(
  definition: Omit<QuestionnaireDefinition, "version"> & { active?: boolean }
): Promise<QuestionnaireDefinition> {
  const response = await apiFetch(`${getApiBaseUrl()}/forms/definitions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      key: definition.key,
      title: definition.title,
      description: definition.description,
      schema: definition.schema,
      active: definition.active ?? true,
    }),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut crea chestionarul pe server.");
  }
  const created = (await response.json()) as QuestionnaireDefinition;
  clearQuestionnaireDefinitionCache();
  return created;
}

export async function updateQuestionnaireDefinitionOnServer(
  key: string,
  fields: { title?: string; description?: string; schema?: QuestionnaireDefinition["schema"]; active?: boolean },
  version?: number
): Promise<QuestionnaireDefinition> {
  const url = version
    ? `${getApiBaseUrl()}/forms/definitions/${key}?version=${version}`
    : `${getApiBaseUrl()}/forms/definitions/${key}`;
  const response = await apiFetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      title: fields.title,
      description: fields.description,
      schema: fields.schema,
      active: fields.active,
    }),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut actualiza chestionarul pe server.");
  }
  const updated = (await response.json()) as QuestionnaireDefinition;
  clearQuestionnaireDefinitionCache();
  return updated;
}

export async function activateQuestionnaireDefinitionOnServer(
  key: string,
  version: number
): Promise<QuestionnaireDefinition> {
  const response = await apiFetch(`${getApiBaseUrl()}/forms/definitions/${key}/versions/${version}/activate`, {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut activa versiunea chestionarului.");
  }
  const activated = (await response.json()) as QuestionnaireDefinition;
  clearQuestionnaireDefinitionCache();
  return activated;
}

export async function deleteQuestionnaireDefinitionOnServer(
  key: string,
  version?: number,
): Promise<QuestionnaireDefinition> {
  const url = version
    ? `${getApiBaseUrl()}/forms/definitions/${key}?version=${version}`
    : `${getApiBaseUrl()}/forms/definitions/${key}`;
  const response = await apiFetch(url, {
    method: "DELETE",
    credentials: "include",
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut pensiona chestionarul.");
  }
  const retired = (await response.json()) as QuestionnaireDefinition;
  clearQuestionnaireDefinitionCache();
  return retired;
}

export async function getQuestionnaireResponse(
  assignmentId: string,
  options: RequestInit = {},
): Promise<QuestionnaireResponseRecord | null> {
  if (canUseSeededAssignmentFallback(assignmentId)) {
    return {
      id: `seeded-${assignmentId}-draft`,
      assignment_id: assignmentId,
      questionnaire_key: seededAssignmentQuestionnaires[assignmentId],
      questionnaire_version: 1,
      status: "draft",
      answers: {},
    };
  }

  try {
    const response = await apiFetch(`${getApiBaseUrl()}/forms/assignments/${assignmentId}/response`, {
      cache: "no-store",
      credentials: "include",
      ...options,
      headers: new Headers(options.headers),
    });
    if (response.status === 404 || response.status === 410) return null;
    if (!response.ok) {
      throw await responseError(response, "Nu am putut încărca răspunsurile salvate.");
    }
    return (await response.json()) as QuestionnaireResponseRecord;
  } catch (error) {
    throw normalizeResponseError(error, "Nu am putut încărca răspunsurile salvate.");
  }
}

export async function getSecureQuestionnaireResponse(
  token: string,
  assignmentId: string,
): Promise<QuestionnaireResponseRecord | null> {
  if (canUseSeededAssignmentFallback(assignmentId)) {
    return {
      id: `seeded-${assignmentId}-draft`,
      assignment_id: assignmentId,
      questionnaire_key: seededAssignmentQuestionnaires[assignmentId],
      questionnaire_version: 1,
      status: "draft",
      answers: {},
    };
  }

  try {
    const response = await apiFetch(
      `${getApiBaseUrl()}/forms/secure-links/${encodeURIComponent(token)}/assignments/${encodeURIComponent(assignmentId)}/response`,
      {
        cache: "no-store",
      },
    );
    if (response.status === 404 || response.status === 410) return null;
    if (!response.ok) {
      throw await responseError(response, "Nu am putut încărca răspunsurile salvate.");
    }
    return (await response.json()) as QuestionnaireResponseRecord;
  } catch (error) {
    throw normalizeResponseError(error, "Nu am putut încărca răspunsurile salvate.");
  }
}

export async function saveQuestionnaireResponse(
  assignmentId: string,
  answers: Record<string, QuestionnaireAnswerValue>,
): Promise<QuestionnaireResponseRecord> {
  if (canUseSeededAssignmentFallback(assignmentId)) {
    return seededQuestionnaireResponse(assignmentId, answers, "draft");
  }

  try {
    const response = await apiFetch(`${getApiBaseUrl()}/forms/assignments/${assignmentId}/response`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ answers }),
    });

    if (!response.ok) {
      throw await responseError(response, "Nu am putut salva draftul.");
    }

    return (await response.json()) as QuestionnaireResponseRecord;
  } catch (error) {
    throw normalizeResponseError(error, "Nu am putut salva draftul.");
  }
}

export async function saveSecureQuestionnaireResponse(
  token: string,
  assignmentId: string,
  answers: Record<string, QuestionnaireAnswerValue>,
): Promise<QuestionnaireResponseRecord> {
  if (canUseSeededAssignmentFallback(assignmentId)) {
    return seededQuestionnaireResponse(assignmentId, answers, "draft");
  }

  try {
    const response = await apiFetch(
      `${getApiBaseUrl()}/forms/secure-links/${encodeURIComponent(token)}/assignments/${encodeURIComponent(assignmentId)}/response`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers }),
      },
    );

    if (!response.ok) {
      throw await responseError(response, "Nu am putut salva draftul.");
    }

    return (await response.json()) as QuestionnaireResponseRecord;
  } catch (error) {
    throw normalizeResponseError(error, "Nu am putut salva draftul.");
  }
}

export async function submitQuestionnaireResponse(
  assignmentId: string,
  answers: Record<string, QuestionnaireAnswerValue>,
): Promise<QuestionnaireResponseRecord> {
  if (canUseSeededAssignmentFallback(assignmentId)) {
    return seededQuestionnaireResponse(assignmentId, answers, "submitted");
  }

  try {
    const response = await apiFetch(`${getApiBaseUrl()}/forms/assignments/${assignmentId}/response/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ answers }),
    });

    if (!response.ok) {
      throw await responseError(response, "Nu am putut trimite răspunsurile.");
    }

    return (await response.json()) as QuestionnaireResponseRecord;
  } catch (error) {
    throw normalizeResponseError(error, "Nu am putut trimite răspunsurile.");
  }
}

export async function submitSecureQuestionnaireResponse(
  token: string,
  assignmentId: string,
  answers: Record<string, QuestionnaireAnswerValue>,
): Promise<QuestionnaireResponseRecord> {
  if (canUseSeededAssignmentFallback(assignmentId)) {
    return seededQuestionnaireResponse(assignmentId, answers, "submitted");
  }

  try {
    const response = await apiFetch(
      `${getApiBaseUrl()}/forms/secure-links/${encodeURIComponent(token)}/assignments/${encodeURIComponent(assignmentId)}/response/submit`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers }),
      },
    );

    if (!response.ok) {
      throw await responseError(response, "Nu am putut trimite răspunsurile.");
    }

    return (await response.json()) as QuestionnaireResponseRecord;
  } catch (error) {
    throw normalizeResponseError(error, "Nu am putut trimite răspunsurile.");
  }
}

function canUseSeededAssignmentFallback(assignmentId: string): boolean {
  return isDemoFallbackEnabled() && Boolean(seededAssignmentQuestionnaires[assignmentId]);
}

async function responseError(response: Response, fallbackMessage: string): Promise<Error> {
  const payload =
    typeof response.json === "function" ? await response.json().catch(() => null) : null;
  const message =
    payload?.error?.message ??
    (typeof payload?.detail === "string" ? payload.detail : fallbackMessage);
  const code = typeof payload?.error?.code === "string" ? payload.error.code : undefined;
  return new QuestionnaireRequestError(message, response.status, code);
}

function normalizeResponseError(error: unknown, fallbackMessage: string): Error {
  if (error instanceof QuestionnaireRequestError) return error;
  return new QuestionnaireRequestError(
    error instanceof Error && error.message ? error.message : fallbackMessage,
    0,
    "network_error",
  );
}

function seededQuestionnaireResponse(
  assignmentId: string,
  answers: Record<string, QuestionnaireAnswerValue>,
  status: "draft" | "submitted",
): QuestionnaireResponseRecord {
  const questionnaireKey = seededAssignmentQuestionnaires[assignmentId];

  if (!questionnaireKey) {
    throw new Error(status === "draft" ? "Nu am putut salva draftul." : "Nu am putut trimite răspunsurile.");
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
