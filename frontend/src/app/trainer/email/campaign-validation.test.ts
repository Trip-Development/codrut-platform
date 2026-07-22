import { describe, expect, it } from "vitest";

import {
  campaignSaveFailureFromError,
  campaignSendBlockedReason,
  campaignSendReadinessError,
  normalizeCampaignUrl,
  validateCampaignDraft,
} from "./campaign-validation";

describe("campaign validation", () => {
  it("reports errors on the exact invalid fields", () => {
    expect(validateCampaignDraft({
      name: " ",
      subject: "",
      videoUrl: "javascript:alert(1)",
      thumbnailUrl: "not-a-url",
      landingUrl: "ftp://example.com",
    })).toEqual({
      name: "Adaugă un nume pentru campanie.",
      subject: "Adaugă subiectul emailului.",
      videoUrl: "Linkul video trebuie să înceapă cu http:// sau https://.",
      thumbnailUrl: "Linkul imaginii trebuie să înceapă cu http:// sau https://.",
      landingUrl: "Linkul paginii trebuie să înceapă cu http:// sau https://.",
    });
  });

  it("accepts image-only and incomplete video drafts", () => {
    expect(validateCampaignDraft({
      name: "Campanie nouă",
      subject: "Salut",
      videoUrl: "https://video.example/demo",
      thumbnailUrl: "",
      landingUrl: "",
    })).toEqual({});

    expect(validateCampaignDraft({
      name: "Campanie imagine",
      subject: "Salut",
      videoUrl: "",
      thumbnailUrl: "https://cdn.example/image.jpg",
      landingUrl: "",
    })).toEqual({});
  });

  it("catches backend length limits before persistence", () => {
    expect(validateCampaignDraft({
      name: "n".repeat(256),
      subject: "s".repeat(256),
      videoUrl: `https://example.com/${"v".repeat(2040)}`,
      thumbnailUrl: "",
      landingUrl: "",
    })).toEqual({
      name: "Numele campaniei poate avea cel mult 255 de caractere.",
      subject: "Subiectul emailului poate avea cel mult 255 de caractere.",
      videoUrl: "Linkul poate avea cel mult 2048 de caractere.",
    });
  });

  it("requires a thumbnail only when a video campaign is sent", () => {
    const campaign = {
      id: "campaign-1",
      name: "Campanie video",
      segment: null,
      status: "draft" as const,
      subject: "Salut",
      html_body: "<p>Salut</p>",
      text_body: "Salut",
      video_url: "https://video.example/demo",
    };

    expect(campaignSendReadinessError(campaign)).toContain("imagine de previzualizare");
    expect(campaignSendReadinessError({ ...campaign, thumbnail_url: "https://cdn.example/thumb.jpg" })).toBeNull();
    expect(normalizeCampaignUrl(" https://codrut.ro/demo ")).toBe("https://codrut.ro/demo");
  });

  it("maps server validation details to Romanian campaign fields", () => {
    const error = Object.assign(new Error("Request validation failed."), {
      status: 422,
      details: [
        { loc: ["body", "subject"], message: "String should have at most 255 characters" },
        { loc: ["body", "thumbnail_url"], message: "Campaign asset URLs must be absolute HTTP(S) URLs." },
      ],
    });

    expect(campaignSaveFailureFromError(error, {
      name: "Campanie",
      subject: "Subiect",
      htmlBody: "<p>Mesaj</p>",
      textBody: "Mesaj",
      videoUrl: "",
      thumbnailUrl: "",
      landingUrl: "",
    })).toEqual({
      message: "Campania nu a fost salvată. Corectează câmpurile marcate.",
      fieldErrors: {
        subject: "Verifică subiectul emailului: valoarea este prea lungă.",
        thumbnailUrl: "Verifică imaginea campaniei.",
      },
      retryable: false,
    });
  });

  it("keeps network and server failures retryable without exposing technical copy", () => {
    const draft = {
      name: "Campanie",
      subject: "Subiect",
      htmlBody: "<p>Mesaj</p>",
      textBody: "Mesaj",
      videoUrl: "",
      thumbnailUrl: "",
      landingUrl: "",
    };

    expect(campaignSaveFailureFromError(new TypeError("Failed to fetch"), draft)).toEqual({
      message: "Nu ne-am putut conecta la server. Datele au rămas în formular.",
      fieldErrors: {},
      retryable: true,
    });
    expect(campaignSaveFailureFromError(Object.assign(new Error("Internal Server Error"), { status: 503 }), draft)).toEqual({
      message: "Serverul nu a putut salva campania. Datele au rămas în formular.",
      fieldErrors: {},
      retryable: true,
    });
  });

  it("explains each disabled send state", () => {
    const campaign = {
      id: "campaign-ready",
      name: "Campanie",
      segment: null,
      status: "ready" as const,
      subject: "Salut",
      html_body: "<p>Salut</p>",
      text_body: "Salut",
    };

    expect(campaignSendBlockedReason({
      campaign,
      mode: "selected",
      sendableRecipientCount: 0,
      activeRecipientCount: 2,
      isSending: false,
      isDeleting: false,
    })).toBe("Selectează cel puțin un destinatar care nu a primit campania.");
    expect(campaignSendBlockedReason({
      campaign,
      mode: "all",
      sendableRecipientCount: 0,
      activeRecipientCount: 0,
      isSending: false,
      isDeleting: false,
    })).toBe("Adaugă cel puțin un destinatar activ în lista campaniei.");
    expect(campaignSendBlockedReason({
      campaign: { ...campaign, video_url: "https://video.example/demo" },
      mode: "selected",
      sendableRecipientCount: 2,
      activeRecipientCount: 2,
      isSending: false,
      isDeleting: false,
    })).toContain("imagine de previzualizare");
  });

  it("covers subject, content, in-flight, deletion, and ready send states", () => {
    const campaign = {
      id: "campaign-ready",
      name: "Campanie",
      segment: null,
      status: "ready" as const,
      subject: "Salut",
      html_body: "<p>Salut</p>",
      text_body: "Salut",
    };
    const options = {
      campaign,
      mode: "selected" as const,
      sendableRecipientCount: 1,
      activeRecipientCount: 1,
      isSending: false,
      isDeleting: false,
    };

    expect(campaignSendReadinessError({ ...campaign, subject: " " })).toContain("subiectul");
    expect(campaignSendReadinessError({ ...campaign, html_body: "" })).toContain("mesajul");
    expect(campaignSendReadinessError({ ...campaign, text_body: "" })).toContain("mesajul");
    expect(campaignSendBlockedReason({ ...options, isSending: true })).toBe("Campania se trimite acum.");
    expect(campaignSendBlockedReason({ ...options, isDeleting: true })).toBe("Campania se șterge acum.");
    expect(campaignSendBlockedReason(options)).toBeNull();
  });

  it("maps every stable campaign persistence status to actionable copy", () => {
    const draft = {
      name: "Campanie",
      subject: "Subiect",
      htmlBody: "<p>Mesaj</p>",
      textBody: "Mesaj",
      videoUrl: "",
      thumbnailUrl: "",
      landingUrl: "",
    };

    for (const [status, message, retryable] of [
      [401, "Sesiunea a expirat", false],
      [403, "permisiunea", false],
      [404, "nu mai există", false],
      [409, "modificată între timp", false],
      [408, "Serverul nu a putut salva", true],
      [429, "Serverul nu a putut salva", true],
      [500, "Serverul nu a putut salva", true],
    ] as const) {
      const failure = campaignSaveFailureFromError(Object.assign(new Error("failure"), { status }), draft);
      expect(failure.message).toContain(message);
      expect(failure.retryable).toBe(retryable);
    }

    expect(campaignSaveFailureFromError(Object.assign(new Error("Campania este invalidă."), { status: 400 }), draft)).toMatchObject({
      message: "Campania este invalidă.",
      retryable: false,
    });
    expect(campaignSaveFailureFromError(Object.assign(new Error("invalid payload"), { status: 422 }), draft)).toMatchObject({
      message: "Datele campaniei au fost respinse. Verifică formularul și încearcă din nou.",
      retryable: false,
    });
  });

  it("infers unsupported-variable fields while ignoring malformed validation details", () => {
    const draft = {
      name: "Campanie",
      subject: "Salut {unknown_subject}",
      htmlBody: "<p>{unknown_body}</p>",
      textBody: "",
      videoUrl: "",
      thumbnailUrl: "",
      landingUrl: "",
    };
    const failure = campaignSaveFailureFromError(Object.assign(
      new Error("Unsupported variables: {unknown_subject}, {unknown_body}"),
      {
        status: 422,
        details: [null, "bad", { loc: "subject", message: 12 }, { loc: ["body", "unknown"], message: "ignored" }],
      },
    ), draft);

    expect(failure.fieldErrors).toEqual({
      subject: "Subiectul conține o variabilă neacceptată. Elimin-o și salvează din nou.",
      body: "Mesajul conține o variabilă neacceptată. Elimin-o și salvează din nou.",
    });
  });

  it("handles blank variables, Romanian retry copy, unknown failures, and URL boundaries", () => {
    const draft = {
      name: "Campanie",
      subject: "Subiect",
      htmlBody: "<p>Mesaj</p>",
      textBody: "Mesaj",
      videoUrl: "",
      thumbnailUrl: "",
      landingUrl: "",
    };

    expect(campaignSaveFailureFromError(new Error("Variabile neacceptate:"), draft).fieldErrors).toMatchObject({ body: expect.any(String) });
    expect(campaignSaveFailureFromError(new Error("Conexiune indisponibilă"), draft).message).toContain("conecta");
    expect(campaignSaveFailureFromError(new Error("Server temporar indisponibil"), draft).message).toBe(
      "Server temporar indisponibil Datele au rămas în formular.",
    );
    expect(campaignSaveFailureFromError({ unexpected: true }, draft).message).toContain("nu a putut fi salvată");
    expect(normalizeCampaignUrl(" ")).toBeUndefined();
    expect(normalizeCampaignUrl("mailto:test@example.com")).toBeUndefined();
    expect(normalizeCampaignUrl("not a url")).toBeUndefined();
  });

  it("marks every field named by a combined backend validation message", () => {
    const draft = {
      name: "Campanie",
      subject: "Subiect",
      htmlBody: "<p>Mesaj</p>",
      textBody: "Mesaj",
      videoUrl: "",
      thumbnailUrl: "",
      landingUrl: "",
    };
    const failure = campaignSaveFailureFromError(
      Object.assign(new Error("Nume, subiect, conținut, video, imagine și pagina campaniei invalide."), { status: 422 }),
      draft,
    );

    expect(Object.keys(failure.fieldErrors).sort()).toEqual([
      "body",
      "landingUrl",
      "name",
      "subject",
      "thumbnailUrl",
      "videoUrl",
    ]);
    expect(campaignSaveFailureFromError(new Error(" "), draft).message).toContain("nu a putut fi salvată");
  });
});
