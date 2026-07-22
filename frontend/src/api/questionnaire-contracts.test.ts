import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  activateQuestionnaireDefinitionOnServer,
  clearQuestionnaireDefinitionCache,
  createQuestionnaireDefinitionOnServer,
  deleteQuestionnaireDefinitionOnServer,
  getAssignedQuestionnaireDefinition,
  getQuestionnaireDefinition,
  getQuestionnaireResponse,
  getSecureQuestionnaireDefinition,
  getSecureQuestionnaireResponse,
  isQuestionnaireSessionError,
  listQuestionnaireDefinitionStubs,
  saveSecureQuestionnaireResponse,
  submitQuestionnaireResponse,
  submitSecureQuestionnaireResponse,
  updateQuestionnaireDefinitionOnServer,
  type QuestionnaireDefinition,
} from "./questionnaires";

function response({
  ok,
  status = ok ? 200 : 400,
  payload,
  jsonError,
}: {
  ok: boolean;
  status?: number;
  payload?: unknown;
  jsonError?: unknown;
}): Response {
  return {
    ok,
    status,
    json: jsonError
      ? vi.fn().mockRejectedValue(jsonError)
      : vi.fn().mockResolvedValue(payload),
  } as unknown as Response;
}

const definition: QuestionnaireDefinition = {
  key: "synthetic_pulse",
  version: 2,
  title: "Chestionar sintetic",
  description: "Fixture sintetic pentru contractul API.",
  active: true,
  schema: {
    schema_version: "questionnaire.v1",
    audience: "participant",
    sections: [
      {
        id: "synthetic_section",
        title: "Secțiune sintetică",
        questions: [
          {
            id: "sample_rating",
            code: "Q1",
            type: "likert",
            label: "Afirmație sintetică pentru verificarea salvării.",
            required: true,
            scale: [{ value: 1, label: "Rar" }, { value: 5, label: "Constant" }],
          },
        ],
      },
    ],
  },
};

const savedResponse = {
  id: "response-1",
  assignment_id: "assignment-1",
  questionnaire_key: "synthetic_pulse",
  questionnaire_version: 2,
  status: "draft" as const,
  answers: { sample_rating: 5 },
};

describe("questionnaire definition persistence contracts", () => {
  beforeEach(() => {
    clearQuestionnaireDefinitionCache();
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    document.cookie = "codrut_csrf=; Max-Age=0; path=/";
  });

  afterEach(() => {
    clearQuestionnaireDefinitionCache();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete process.env.CODRUT_FRONTEND_DEMO_FALLBACK;
    delete process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK;
  });

  it("creates inactive drafts with the exact participant schema", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ ok: true, payload: { ...definition, active: false } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createQuestionnaireDefinitionOnServer({ ...definition, active: false })).resolves.toMatchObject({
      key: "synthetic_pulse",
      active: false,
    });
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      key: definition.key,
      title: definition.title,
      description: definition.description,
      schema: definition.schema,
      active: false,
    });
  });

  it.each([
    [{ error: { message: "Cheia există deja." } }, "Cheia există deja."],
    [undefined, "Nu am putut crea chestionarul pe server."],
  ])("reports definition creation failures without claiming persistence", async (payload, message) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      ok: false,
      status: 422,
      payload,
      jsonError: payload === undefined ? new Error("invalid json") : undefined,
    })));

    await expect(createQuestionnaireDefinitionOnServer(definition)).rejects.toThrow(message);
  });

  it("targets a specific immutable version when updating", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ ok: true, payload: { ...definition, title: "Chestionar sintetic revizuit" } }));
    vi.stubGlobal("fetch", fetchMock);

    await updateQuestionnaireDefinitionOnServer("synthetic_pulse", { title: "Chestionar sintetic revizuit" }, 2);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/forms\/definitions\/synthetic_pulse\?version=2$/),
      expect.objectContaining({ method: "PUT" }),
    );
  });

  it("maps update, activation, and retirement rejection messages", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: false, status: 409, payload: { error: { message: "Versiunea este deja folosită." } } }))
      .mockResolvedValueOnce(response({ ok: false, status: 403, jsonError: new Error("invalid json") }))
      .mockResolvedValueOnce(response({ ok: false, status: 409, payload: { error: { message: "Definiția are asignări active." } } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(updateQuestionnaireDefinitionOnServer("synthetic_pulse", { title: "Nou" }, 2)).rejects.toThrow(
      "Versiunea este deja folosită.",
    );
    await expect(activateQuestionnaireDefinitionOnServer("synthetic_pulse", 2)).rejects.toThrow(
      "Nu am putut activa versiunea chestionarului.",
    );
    await expect(deleteQuestionnaireDefinitionOnServer("synthetic_pulse", 2)).rejects.toThrow(
      "Definiția are asignări active.",
    );
    expect(fetchMock.mock.calls[2]?.[0]).toMatch(/synthetic_pulse\?version=2$/);
  });

  it("activates and retires exact versions on success", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: true, payload: definition }))
      .mockResolvedValueOnce(response({ ok: true, payload: { ...definition, active: false } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(activateQuestionnaireDefinitionOnServer("synthetic_pulse", 2)).resolves.toMatchObject({ active: true });
    await expect(deleteQuestionnaireDefinitionOnServer("synthetic_pulse")).resolves.toMatchObject({ active: false });
  });

  it("keeps trainer catalog permission and server failures visible and retryable", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({
        ok: false,
        status: 403,
        payload: { error: { code: "http_403", message: "Nu ai acces la catalog." } },
      }))
      .mockResolvedValueOnce(response({
        ok: false,
        status: 500,
        payload: { error: { code: "server_error", message: "Catalog indisponibil." } },
      }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listQuestionnaireDefinitionStubs()).rejects.toMatchObject({
      status: 403,
      code: "http_403",
    });
    await expect(getQuestionnaireDefinition("synthetic_pulse")).rejects.toMatchObject({
      status: 500,
      code: "server_error",
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("returns null only for missing trainer questionnaire definitions", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ ok: false, status: 404 })));

    await expect(getQuestionnaireDefinition("missing_definition")).resolves.toBeNull();
  });
});

describe("questionnaire response contracts", () => {
  beforeEach(() => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    document.cookie = "codrut_csrf=; Max-Age=0; path=/";
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete process.env.CODRUT_FRONTEND_DEMO_FALLBACK;
    delete process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK;
  });

  it("loads secure definitions and drafts without session cookies", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: true, payload: definition }))
      .mockResolvedValueOnce(response({ ok: true, payload: savedResponse }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getSecureQuestionnaireDefinition("invite/token", "assignment/1")).resolves.toMatchObject({
      key: "synthetic_pulse",
    });
    await expect(getSecureQuestionnaireResponse("invite/token", "assignment/1")).resolves.toMatchObject({
      status: "draft",
    });
    expect(fetchMock.mock.calls[0]?.[0]).toContain("secure-links/invite%2Ftoken/assignments/assignment%2F1/definition");
    expect(fetchMock.mock.calls[1]?.[1]).toEqual({ cache: "no-store" });
  });

  it("loads participant definitions through the assigned resource", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ ok: true, payload: definition }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getAssignedQuestionnaireDefinition("assignment/1")).resolves.toMatchObject({
      key: "synthetic_pulse",
    });
    expect(fetchMock.mock.calls[0]?.[0]).toContain(
      "/forms/assignments/assignment%2F1/definition",
    );
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      cache: "no-store",
      credentials: "include",
    });
  });

  it.each([
    ["assigned", () => getAssignedQuestionnaireDefinition("assignment/1")],
    ["secure", () => getSecureQuestionnaireDefinition("invite-token", "assignment/1")],
  ])("strips private scoring metadata from %s participant definitions", async (_label, load) => {
    const privateDefinition = {
      ...definition,
      private_config: { scoring: { formula: "never expose" } },
      schema: {
        ...definition.schema,
        source: { path: "/protected/source.json" },
        scoring: { formula: "never expose" },
        sections: [{
          ...definition.schema.sections[0],
          questions: [{
            ...definition.schema.sections[0].questions[0],
            scoring: { reverse: "true" },
          }],
        }],
      },
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ ok: true, payload: privateDefinition })));

    const result = await load();

    expect(result).not.toHaveProperty("private_config");
    expect(result?.schema).not.toHaveProperty("source");
    expect(result?.schema).not.toHaveProperty("scoring");
    expect(result?.schema.sections[0].questions[0]).not.toHaveProperty("scoring");
  });

  it("rejects malformed participant questionnaire payloads", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      ok: true,
      payload: { key: "synthetic_pulse", schema: { sections: [] } },
    })));

    await expect(getAssignedQuestionnaireDefinition("assignment/1")).rejects.toMatchObject({
      status: 502,
      code: "invalid_definition_response",
    });
  });

  it("preserves server authentication headers for assigned definitions and drafts", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: true, payload: definition }))
      .mockResolvedValueOnce(response({ ok: true, payload: savedResponse }));
    vi.stubGlobal("fetch", fetchMock);
    const serverHeaders = new Headers({ "X-Codrut-Dev-Role": "participant" });

    await getAssignedQuestionnaireDefinition("assignment-1", { headers: serverHeaders });
    await getQuestionnaireResponse("assignment-1", { headers: serverHeaders });

    expect(new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get("X-Codrut-Dev-Role")).toBe(
      "participant",
    );
    expect(new Headers(fetchMock.mock.calls[1]?.[1]?.headers).get("X-Codrut-Dev-Role")).toBe(
      "participant",
    );
  });

  it("returns null only when questionnaire resources are missing or retired", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: false, status: 404, payload: {} }))
      .mockResolvedValueOnce(response({ ok: false, status: 410, payload: {} }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getQuestionnaireResponse("missing-assignment")).resolves.toBeNull();
    await expect(getSecureQuestionnaireResponse("token", "retired-assignment")).resolves.toBeNull();
  });

  it.each([
    ["assigned", () => getAssignedQuestionnaireDefinition("assignment-1")],
    ["secure", () => getSecureQuestionnaireDefinition("token", "assignment-1")],
    ["response", () => getQuestionnaireResponse("assignment-1")],
  ])("does not hide authorization failures while loading %s resources", async (_label, load) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      ok: false,
      status: 403,
      payload: { error: { code: "http_403", message: "Accesul la sarcină a expirat." } },
    })));

    await expect(load()).rejects.toMatchObject({
      name: "QuestionnaireRequestError",
      status: 403,
      code: "http_403",
      message: "Accesul la sarcină a expirat.",
    });
  });

  it("reports questionnaire load network failures as retryable errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    await expect(getSecureQuestionnaireDefinition("token", "assignment-1")).rejects.toMatchObject({
      name: "QuestionnaireRequestError",
      status: 0,
      code: "network_error",
      message: "offline",
    });
  });

  it("saves a secure draft with its exact answer payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ ok: true, payload: savedResponse }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(saveSecureQuestionnaireResponse("invite-token", "assignment-1", { sample_rating: 5 })).resolves.toEqual(savedResponse);
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({ answers: { sample_rating: 5 } });
    expect(fetchMock.mock.calls[0]?.[1]).not.toHaveProperty("credentials");
  });

  it("preserves field validation detail and machine-readable response codes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      ok: false,
      status: 422,
      payload: { detail: "Câmpul sintetic este obligatoriu.", error: { code: "answer_required" } },
    })));

    const error = await submitSecureQuestionnaireResponse("invite-token", "assignment-1", {}).catch((caught) => caught);
    expect(error).toMatchObject({
      name: "QuestionnaireRequestError",
      status: 422,
      code: "answer_required",
      message: "Câmpul sintetic este obligatoriu.",
    });
    expect(isQuestionnaireSessionError(error)).toBe(false);
  });

  it("uses stable fallback messages for malformed errors and preserves network failures", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: false, status: 500, jsonError: new Error("invalid json") }))
      .mockRejectedValueOnce(new TypeError("offline"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(submitQuestionnaireResponse("assignment-1", { sample_rating: 5 })).rejects.toMatchObject({
      status: 500,
      message: "Nu am putut trimite răspunsurile.",
    });
    await expect(saveSecureQuestionnaireResponse("token", "assignment-1", { sample_rating: 5 })).rejects.toThrow("offline");
  });

  it("submits secure responses and returns the persisted status", async () => {
    const submitted = { ...savedResponse, status: "submitted" as const };
    const fetchMock = vi.fn().mockResolvedValue(response({ ok: true, payload: submitted }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(submitSecureQuestionnaireResponse("token", "assignment-1", { sample_rating: 5 })).resolves.toMatchObject({
      status: "submitted",
    });
    expect(fetchMock.mock.calls[0]?.[0]).toMatch(/\/response\/submit$/);
  });
});
