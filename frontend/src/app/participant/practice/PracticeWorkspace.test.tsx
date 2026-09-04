import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PracticeWorkspace } from "./PracticeWorkspace";

vi.mock("@/hooks/useVoiceToText", () => ({
  useVoiceToText: () => ({
    isListening: false,
    isTranscribing: false,
    startListening: vi.fn(),
    stopListening: vi.fn(),
    error: null,
  }),
}));

const api = vi.hoisted(() => ({
  startPracticeSession: vi.fn(),
  submitPracticeTurn: vi.fn(),
  endPracticeSession: vi.fn(),
}));

const { PracticeError } = vi.hoisted(() => ({
  PracticeError: class extends Error {
    code: string;
    details: Record<string, unknown>;
    constructor(message: string, code: string, details: Record<string, unknown>) {
      super(message);
      this.code = code;
      this.details = details;
    }
  },
}));

vi.mock("@/api/practice", () => ({ ...api, PracticeError }));

const SESIUNE_DESCHISA = {
  id: "sesiune-1",
  kind: "roleplay" as const,
  state: "open" as const,
  turnCount: 0,
};

beforeEach(() => {
  // jsdom nu are scrollIntoView, iar componenta il cheama la fiecare replica noua.
  Element.prototype.scrollIntoView = vi.fn();
  api.startPracticeSession.mockReset();
  api.submitPracticeTurn.mockReset();
  api.endPracticeSession.mockReset();
  api.startPracticeSession.mockResolvedValue(SESIUNE_DESCHISA);
});

afterEach(cleanup);

async function porneste() {
  render(<PracticeWorkspace projectId="proiect-1" />);
  fireEvent.click(screen.getByRole("button", { name: "Începe conversația" }));
  await waitFor(() => expect(api.startPracticeSession).toHaveBeenCalled());
}

describe("PracticeWorkspace — drumul înapoi", () => {
  it("dintr-o sesiune deschisă se poate ieși la alegerea modului fără a o închide", async () => {
    // Pana la plicul 34 singura iesire dintr-o sesiune pornita era „Incheie
    // sesiunea". Butonul care ducea inapoi aparea abia dupa ce sesiunea era inchisa.
    await porneste();

    fireEvent.click(screen.getByRole("button", { name: /Înapoi/ }));

    expect(screen.getByText("Alege modul de antrenament")).toBeTruthy();
    // sesiunea NU s-a inchis
    expect(api.endPracticeSession).not.toHaveBeenCalled();
    // si se poate intoarce la ea
    expect(screen.getByText("Ai o sesiune deschisă.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Întoarce-te la sesiune" }));
    expect(screen.queryByText("Alege modul de antrenament")).toBeNull();
  });

  it("după încheiere, drumul înapoi e primul lucru de pe ecran, iar sinteza rămâne", async () => {
    api.endPracticeSession.mockResolvedValue({
      session: { ...SESIUNE_DESCHISA, state: "closed" },
      summary: "Ai condus discuția calm și ai propus un pas concret.",
    });
    await porneste();

    fireEvent.click(screen.getByRole("button", { name: /Încheie sesiunea/ }));
    await waitFor(() => expect(api.endPracticeSession).toHaveBeenCalled());

    const toate = await screen.findAllByRole("button", { name: /Înapoi la alegerea modului/ });
    const sinteza = screen.getByText("Ai condus discuția calm și ai propus un pas concret.");
    const stareaSesiunii = screen.getByText("Sesiune încheiată");

    // sinteza ramane vizibila
    expect(sinteza).toBeTruthy();
    // drumul inapoi vine INAINTEA ei pe ecran
    const primul = toate[0];
    expect(primul.compareDocumentPosition(sinteza) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // si sta sus, in bara de stare, langa eticheta sesiunii — nu doar in caseta de jos,
    // unde plicul 36 spune ca omul a derulat si tot nu l-a gasit
    expect(
      primul.compareDocumentPosition(stareaSesiunii) & Node.DOCUMENT_POSITION_PRECEDING,
    ).toBeTruthy();

    fireEvent.click(primul);
    expect(screen.getByText("Alege modul de antrenament")).toBeTruthy();
  });

  it("cand sesiunea e inchisa, corpul nu mai spune ca e deschisa", async () => {
    // Ecranul se contrazicea singur: sus „Sesiune încheiată", in corp „Sesiunea este
    // deschisă". Textul din corp era cel de stare goala si se arata in ambele cazuri.
    api.endPracticeSession.mockResolvedValue({
      session: { ...SESIUNE_DESCHISA, state: "closed" },
      summary: null,
    });
    await porneste();

    expect(screen.getByText("Sesiunea este deschisă.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Încheie sesiunea/ }));
    await waitFor(() => expect(api.endPracticeSession).toHaveBeenCalled());

    expect(await screen.findByText("Sesiune încheiată")).toBeTruthy();
    expect(screen.queryByText("Sesiunea este deschisă.")).toBeNull();
    expect(screen.getByText("Sesiunea s-a încheiat fără nicio replică.")).toBeTruthy();
  });
});

describe("PracticeWorkspace — refuzul spune de ce", () => {
  it("la plafonul zilnic scrie in romana cate sesiuni are si cate a facut", async () => {
    // Pana la plicul 35 clientul citea `err.detail`, camp care nu exista in plicul de
    // eroare al aplicatiei. Asa ca orice refuz ajungea pe ecran ca acelasi text
    // generic: omul apasa si parea ca nu se intampla nimic.
    api.startPracticeSession.mockRejectedValue(
      new PracticeError("Daily practice session limit of 5 reached", "practice_daily_limit", {
        max_sessions_per_day: 5,
        sessions_today: 5,
      }),
    );
    render(<PracticeWorkspace projectId="proiect-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Începe conversația" }));

    const text = await screen.findByText(/limita de sesiuni pe ziua de azi/i);
    expect(text.textContent).toContain("5 sesiuni pe zi");
    expect(text.textContent).toContain("azi ai făcut 5");
    expect(text.textContent).toContain("Numărătoarea se reia mâine");
    // si NU textul tehnic in engleza
    expect(text.textContent).not.toContain("Daily practice session limit");
  });

  it("la orice alta eroare arata mesajul venit de la server", async () => {
    api.startPracticeSession.mockRejectedValue(new Error("Programul nu e pornit."));
    render(<PracticeWorkspace projectId="proiect-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Începe conversația" }));

    expect(await screen.findByText("Programul nu e pornit.")).toBeTruthy();
  });
});

describe("PracticeWorkspace — ecranul de final", () => {
  it("titlurile sintezei se vad ca titluri, nu ca text cu diez", async () => {
    // Pe ecran scria literal „##Concluzie" si „##Recomandări", cu diez cu tot, pentru
    // ca sunt titluri de markdown pe care caseta nu le interpreta.
    api.endPracticeSession.mockResolvedValue({
      session: { ...SESIUNE_DESCHISA, state: "closed" },
      summary:
        "##Concluzie\nAi condus discuția calm.\n\n##Recomandări\nPune mai multe întrebări deschise.",
    });
    await porneste();

    fireEvent.click(screen.getByRole("button", { name: /Încheie sesiunea/ }));
    await waitFor(() => expect(api.endPracticeSession).toHaveBeenCalled());

    expect(await screen.findByRole("heading", { name: "Concluzie" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Recomandări" })).toBeTruthy();
    expect(screen.getByText("Ai condus discuția calm.")).toBeTruthy();
    expect(screen.getByText("Pune mai multe întrebări deschise.")).toBeTruthy();
    // si niciun diez ramas la vedere
    expect(screen.queryByText(/##/)).toBeNull();
  });

  it("nu pierde text cand sinteza n-are titluri", async () => {
    api.endPracticeSession.mockResolvedValue({
      session: { ...SESIUNE_DESCHISA, state: "closed" },
      summary: "O sinteză scrisă fără niciun titlu.",
    });
    await porneste();

    fireEvent.click(screen.getByRole("button", { name: /Încheie sesiunea/ }));
    await waitFor(() => expect(api.endPracticeSession).toHaveBeenCalled());

    expect(await screen.findByText("O sinteză scrisă fără niciun titlu.")).toBeTruthy();
  });

  it("cât se generează sinteza, ecranul spune ce se întâmplă", async () => {
    // Dupa „Încheie sesiunea" trec cateva secunde bune — doua cereri catre model — si
    // ecranul nu spunea nimic.
    let deblocheaza: (v: unknown) => void = () => {};
    api.endPracticeSession.mockReturnValue(
      new Promise((resolve) => {
        deblocheaza = resolve;
      }),
    );
    await porneste();

    fireEvent.click(screen.getByRole("button", { name: /Încheie sesiunea/ }));

    expect(await screen.findByText("Se închide sesiunea.")).toBeTruthy();
    expect(
      screen.getByText("Cody se uită peste ce ai lucrat. Durează câteva secunde."),
    ).toBeTruthy();

    deblocheaza({
      session: { ...SESIUNE_DESCHISA, state: "closed" },
      summary: "Gata.",
    });
    await waitFor(() => expect(screen.queryByText("Se închide sesiunea.")).toBeNull());
  });
});

describe("PracticeWorkspace — pornirea în doi pași", () => {
  const SCENA = {
    id: "cody-2",
    sessionId: "sesiune-1",
    ordinal: 3,
    role: "actor" as const,
    text: "Setup: ești managerul lui Vali. Obiectivul tău: să ceri raportul asertiv.",
    createdAt: "2026-09-04T10:00:05Z",
    expiresAt: "2026-10-04T10:00:05Z",
  };
  const SALUT = {
    id: "cody-1",
    sessionId: "sesiune-1",
    ordinal: 1,
    role: "actor" as const,
    text: "Salut! Ești gata să începem un joc de rol?",
    createdAt: "2026-09-04T09:59:00Z",
    expiresAt: "2026-10-04T09:59:00Z",
  };

  async function pornesteCuIntrebarea(kind: "roleplay" | "coaching" | "knowledge" = "roleplay") {
    api.startPracticeSession.mockResolvedValue({ ...SESIUNE_DESCHISA, kind, firstTurn: SALUT });
    render(<PracticeWorkspace projectId="proiect-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Începe conversația" }));
    await waitFor(() => expect(api.startPracticeSession).toHaveBeenCalled());
  }

  it("cele două butoane apar sub PRIMA replică, nu sub cea care pornește scena", async () => {
    await pornesteCuIntrebarea();

    expect(await screen.findByRole("button", { name: "Da, hai" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Vreau să spun eu tema" })).toBeTruthy();
  });

  it("butonul Da, hai trimite confirmarea", async () => {
    await pornesteCuIntrebarea();
    api.submitPracticeTurn.mockResolvedValue({
      participantTurn: {
        ...SALUT, id: "om-1", ordinal: 2, role: "participant" as const, text: "Da, hai.",
      },
      actorTurn: SCENA,
      sessionState: "open" as const,
    });

    fireEvent.click(await screen.findByRole("button", { name: "Da, hai" }));

    await waitFor(() =>
      expect(api.submitPracticeTurn).toHaveBeenCalledWith("sesiune-1", "Da, hai."),
    );
    // si dispar dupa ce a apasat
    await waitFor(() => expect(screen.queryByRole("button", { name: "Da, hai" })).toBeNull());
  });

  it("butonul Vreau sa spun eu tema pune textul in caseta si NU trimite", async () => {
    await pornesteCuIntrebarea();
    api.submitPracticeTurn.mockClear();

    fireEvent.click(await screen.findByRole("button", { name: "Vreau să spun eu tema" }));

    const caseta = screen.getByPlaceholderText(/Scrie un mesaj/) as HTMLTextAreaElement;
    expect(caseta.value).toBe("Vreau să exersăm altceva: ");
    expect(api.submitPracticeTurn).not.toHaveBeenCalled();
  });

  it("nu apar la coaching sau la quiz", async () => {
    for (const kind of ["coaching", "knowledge"] as const) {
      cleanup();
      await pornesteCuIntrebarea(kind);
      expect(screen.queryByRole("button", { name: "Da, hai" })).toBeNull();
      expect(screen.queryByRole("button", { name: "Vreau să spun eu tema" })).toBeNull();
    }
  });
});
