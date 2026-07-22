import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  activateEmailTemplateOnServer,
  CampaignPersistenceError,
  createCampaignOnServer,
  deleteCampaignAssetOnServer,
  deleteEmailTemplateOnServer,
  getEmailTemplateOnServer,
  listCampaignRecipientMembershipOnServer,
  replaceCampaignRecipientMembershipOnServer,
  sendCampaignOnServer,
  updateCampaignOnServer,
  updateCampaignRecipientOnServer,
  updateEmailTemplateOnServer,
  uploadCampaignAssetOnServer,
  type CampaignCreate,
  type EmailTemplate,
} from "./email";

function response({
  ok,
  status = ok ? 200 : 400,
  payload,
  text = "",
  jsonError,
}: {
  ok: boolean;
  status?: number;
  payload?: unknown;
  text?: string;
  jsonError?: unknown;
}): Response {
  return {
    ok,
    status,
    json: jsonError
      ? vi.fn().mockRejectedValue(jsonError)
      : vi.fn().mockResolvedValue(payload),
    text: vi.fn().mockResolvedValue(text),
    headers: new Headers(),
  } as unknown as Response;
}

const campaign: CampaignCreate = {
  name: "Campanie sintetică",
  segment: "past_customer",
  subject: "Subiect sintetic pentru ${first_name}",
  html_body: "<p>Conținut sintetic pentru ${first_name}</p>",
  text_body: "Conținut sintetic pentru ${first_name}",
  thumbnail_url: "https://assets.example/pilot.png",
};

const template: EmailTemplate = {
  id: "synthetic_notice@2",
  baseKey: "synthetic_notice",
  version: 2,
  name: "Șablon sintetic",
  subject: "Subiect sintetic pentru {first_name}",
  body: "<p>Conținut sintetic pentru {first_name}</p>",
  textBody: "Conținut sintetic pentru {first_name}",
  placeholders: ["{first_name}"],
  lane: "campaign",
  audience: "campaign:past_customer",
};

describe("campaign persistence and dispatch contracts", () => {
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

  it("preserves the complete validation envelope when campaign creation is blocked", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      ok: false,
      status: 422,
      payload: {
        error: {
          code: "campaign_invalid",
          message: "Campania nu este validă.",
          request_id: "req-campaign-create",
          details: [
            { path: ["thumbnail_url"], message: "Thumbnailul este obligatoriu pentru video." },
            { loc: ["body", "subject"], message: "Subiectul este prea lung." },
          ],
        },
      },
    })));

    const error = await createCampaignOnServer(campaign).catch((caught) => caught);
    expect(error).toBeInstanceOf(CampaignPersistenceError);
    expect(error).toMatchObject({
      status: 422,
      code: "campaign_invalid",
      message: "Campania nu este validă.",
      requestId: "req-campaign-create",
      details: [
        { loc: ["thumbnail_url"], message: "Thumbnailul este obligatoriu pentru video." },
        { loc: ["body", "subject"], message: "Subiectul este prea lung." },
      ],
    });
  });

  it("preserves validation details when campaign update is blocked", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      ok: false,
      status: 422,
      payload: {
        error: {
          code: "validation_error",
          message: "Date invalide.",
          details: [{ loc: ["body", "video_url"], message: "Link invalid." }],
        },
      },
    })));

    await expect(updateCampaignOnServer("campaign-1", { video_url: "bad" })).rejects.toMatchObject({
      code: "validation_error",
      details: [{ loc: ["body", "video_url"], message: "Link invalid." }],
    });
  });

  it("falls back to stable campaign errors when the server payload is malformed", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: false, status: 500, jsonError: new Error("invalid json") }))
      .mockResolvedValueOnce(response({ ok: false, status: 503, jsonError: new Error("invalid json") }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createCampaignOnServer(campaign)).rejects.toMatchObject({
      name: "CampaignPersistenceError",
      status: 500,
      message: "Nu am putut crea campania (500).",
    });
    await expect(updateCampaignOnServer("campaign-1", { subject: "Subiect nou" })).rejects.toMatchObject({
      name: "CampaignPersistenceError",
      status: 503,
      message: "Nu am putut actualiza campania (503).",
    });
  });

  it("dispatches selected recipients with a caller-supplied idempotency key", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({
      ok: true,
      payload: {
        campaign_id: "campaign-1",
        total: 2,
        sent: 2,
        failed: 0,
        skipped: 0,
        dry_run: false,
        results: [],
      },
    }));
    vi.stubGlobal("fetch", fetchMock);

    await sendCampaignOnServer("campaign-1", {
      recipientIds: ["recipient-1", "recipient-2"],
      idempotencyKey: "campaign-send-test-1",
    });

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(init.headers).get("Idempotency-Key")).toBe("campaign-send-test-1");
    expect(JSON.parse(String(init.body))).toEqual({
      dry_run: false,
      recipient_ids: ["recipient-1", "recipient-2"],
      mode: "selected",
    });
  });

  it("maps dispatch permission and network failures without false success", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: false, status: 403, payload: { error: { message: "Nu ai acces la această campanie." } } }))
      .mockRejectedValueOnce(new TypeError("network unavailable"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(sendCampaignOnServer("campaign-1", { mode: "all" })).rejects.toThrow(
      "Nu ai acces la această campanie.",
    );
    await expect(sendCampaignOnServer("campaign-1")).rejects.toThrow("network unavailable");
  });

  it("uploads raw media metadata and reports decoding or persistence failures", async () => {
    const uploaded = {
      url: "/api/communications/campaign-assets/image.png",
      file_name: "image.png",
      content_type: "image/png",
      size_bytes: 3,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: true, payload: uploaded }))
      .mockResolvedValueOnce(response({ ok: false, status: 415, payload: { error: { message: "Fișierul nu este o imagine validă." } } }));
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["png"], "", { type: "" });
    await expect(uploadCampaignAssetOnServer(file)).resolves.toEqual(uploaded);
    const headers = new Headers(fetchMock.mock.calls[0]?.[1]?.headers);
    expect(headers.get("Content-Type")).toBe("application/octet-stream");
    expect(headers.get("X-File-Name")).toBe("thumbnail");
    await expect(uploadCampaignAssetOnServer(new File(["bad"], "bad.txt"))).rejects.toThrow(
      "Fișierul nu este o imagine validă.",
    );
  });

  it("ignores already-removed media but surfaces cleanup failures", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: false, status: 404 }))
      .mockResolvedValueOnce(response({ ok: false, status: 500 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteCampaignAssetOnServer("missing.png")).resolves.toBeUndefined();
    await expect(deleteCampaignAssetOnServer("owned.png")).rejects.toThrow(
      "Nu am putut curăța imaginea campaniei (500).",
    );
  });

  it("accepts wrapped recipient membership payloads and an empty 204 replacement", async () => {
    const rows = [{ id: "recipient-1", email: "ana@example.com", selected: true }];
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: true, payload: { recipients: rows } }))
      .mockResolvedValueOnce(response({ ok: true, status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listCampaignRecipientMembershipOnServer("campaign-1")).resolves.toEqual(rows);
    await expect(replaceCampaignRecipientMembershipOnServer("campaign-1", [])).resolves.toEqual([]);
  });

  it("surfaces contact edit validation and transport failures", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: false, status: 422, payload: { error: { message: "Emailul nu este valid." } } }))
      .mockRejectedValueOnce(new TypeError("offline"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(updateCampaignRecipientOnServer("recipient-1", { email: "invalid" })).rejects.toThrow(
      "Emailul nu este valid.",
    );
    await expect(updateCampaignRecipientOnServer("recipient-1", { email: "ana@example.com" })).rejects.toThrow("offline");
  });
});

describe("email template persistence contracts", () => {
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

  it("requests an exact template version and returns null for missing or unreachable versions", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: false, status: 404 }))
      .mockRejectedValueOnce(new TypeError("offline"));
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    await expect(getEmailTemplateOnServer("synthetic_notice", 2)).resolves.toBeNull();
    expect(fetchMock.mock.calls[0]?.[0]).toMatch(/synthetic_notice\?version=2$/);
    await expect(getEmailTemplateOnServer("synthetic_notice")).resolves.toBeNull();
  });

  it("distinguishes expired authentication from template validation failures", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: false, status: 401 }))
      .mockResolvedValueOnce(response({ ok: false, status: 422, payload: { error: { message: "Lipsește placeholderul obligatoriu." } } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(updateEmailTemplateOnServer(template)).rejects.toThrow(
      "Nu sunteți autentificat. Vă rugăm să vă reconectați.",
    );
    await expect(activateEmailTemplateOnServer("synthetic_notice", 2)).rejects.toThrow(
      "Lipsește placeholderul obligatoriu.",
    );
  });

  it("reports unauthorized retirement instead of silently hiding a template", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ ok: false, status: 401 })));
    await expect(deleteEmailTemplateOnServer("synthetic_notice", 2)).rejects.toThrow(
      "Nu sunteți autentificat. Vă rugăm să vă reconectați.",
    );
  });
});
