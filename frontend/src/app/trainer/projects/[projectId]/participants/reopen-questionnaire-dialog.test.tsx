import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { reopenErrorMessage, reopenParticipantAssignment, type CompanyParticipant } from "@/api/companies";
import {
  ReopenQuestionnaireDialog,
  questionnaireName,
  reopenSummaryText,
} from "./reopen-questionnaire-dialog";

vi.mock("@/api/companies", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/companies")>();
  return { ...original, reopenParticipantAssignment: vi.fn() };
});

function participant(overrides: Partial<CompanyParticipant> = {}): CompanyParticipant {
  return {
    id: "om-1",
    full_name: "Ana Popescu",
    email: "ana@example.test",
    reports_to_name: null,
    position: null,
    location: null,
    role_group: null,
    pcm_profile: null,
    user_id: null,
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("textele de sub numele omului", () => {
  it("nu scrie nimic daca nu i s-a redeschis nimic", () => {
    expect(reopenSummaryText(participant())).toBeNull();
    expect(reopenSummaryText(participant({ reopen_count: 0 }))).toBeNull();
  });

  it("scrie de cate ori si cand ultima data, in romana", () => {
    expect(
      reopenSummaryText(
        participant({ reopen_count: 1, last_reopened_at: "2026-08-15T12:00:00Z" }),
      ),
    ).toBe("Redeschis o dată · ultima pe 15.08.2026");
    expect(
      reopenSummaryText(
        participant({ reopen_count: 3, last_reopened_at: "2026-08-20T12:00:00Z" }),
      ),
    ).toBe("Redeschis de 3 ori · ultima pe 20.08.2026");
  });

  it("da numele chestionarului in romana, nu cheia tehnica", () => {
    expect(questionnaireName("lencioni")).toBe("Lencioni");
    expect(questionnaireName("distress_drivers")).toBe("Driveri de stres");
    expect(questionnaireName("icare")).toBe("iCARE 360");
  });
});

describe("mesajele de refuz ale serverului", () => {
  it("traduce 'se proceseaza chiar acum' intr-o propozitie pentru om", () => {
    expect(reopenErrorMessage("reopen_submission_processing")).toBe(
      "Chestionarul se calculează chiar acum. Mai încearcă peste un minut.",
    );
  });

  it("nu lasa niciun cod tehnic sa ajunga pe ecran", () => {
    for (const code of [
      "reopen_submission_processing",
      "reopen_no_response",
      "company_access_denied",
      "assignment_not_found",
      undefined,
    ]) {
      const message = reopenErrorMessage(code, 400);
      expect(message).not.toContain("_");
      expect(message.length).toBeGreaterThan(20);
    }
  });
});

describe("fereastra de confirmare", () => {
  const cuUnChestionar = participant({
    reopenable_assignments: [
      { assignment_id: "a-1", questionnaire_key: "lencioni", reopen_count: 0 },
    ],
  });

  it("spune limpede pentru cine, ce chestionar, si ce se intampla", () => {
    render(
      <ReopenQuestionnaireDialog
        companyId="c-1"
        participant={cuUnChestionar}
        onClose={() => {}}
        onDone={() => {}}
      />,
    );

    expect(screen.getByText("Ana Popescu")).toBeTruthy();
    expect(screen.getByText("Lencioni")).toBeTruthy();
    expect(screen.getByText(/se păstrează într-o arhivă/i)).toBeTruthy();
    expect(screen.getByText(/pornește de la zero/i)).toBeTruthy();
    expect(screen.getByText(/niciun email/i)).toBeTruthy();
  });

  it("NU avertizeaza la prima redeschidere", () => {
    render(
      <ReopenQuestionnaireDialog
        companyId="c-1"
        participant={cuUnChestionar}
        onClose={() => {}}
        onDone={() => {}}
      />,
    );

    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("avertizeaza la a treia, dar lasa butonul apasabil", () => {
    const dejaDeDouaOri = participant({
      reopenable_assignments: [
        { assignment_id: "a-1", questionnaire_key: "lencioni", reopen_count: 2 },
      ],
    });
    render(
      <ReopenQuestionnaireDialog
        companyId="c-1"
        participant={dejaDeDouaOri}
        onClose={() => {}}
        onDone={() => {}}
      />,
    );

    expect(screen.getByRole("alert").textContent).toContain("a 3-a oară");
    const confirma = screen.getByRole("button", { name: "Da, redeschide" });
    expect((confirma as HTMLButtonElement).disabled).toBe(false);
  });

  it("arata mesajul in romana cand serverul spune ca se proceseaza acum", async () => {
    vi.mocked(reopenParticipantAssignment).mockRejectedValueOnce(
      new Error(reopenErrorMessage("reopen_submission_processing")),
    );
    const onDone = vi.fn();
    render(
      <ReopenQuestionnaireDialog
        companyId="c-1"
        participant={cuUnChestionar}
        onClose={() => {}}
        onDone={onDone}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Da, redeschide" }));

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toBe(
        "Chestionarul se calculează chiar acum. Mai încearcă peste un minut.",
      );
    });
    expect(onDone).not.toHaveBeenCalled();
  });

  it("trimite redeschiderea pentru chestionarul ales", async () => {
    vi.mocked(reopenParticipantAssignment).mockResolvedValueOnce({
      assignment_id: "a-1",
      status: "invited",
      reopen_count: 1,
      archived_response_id: "r-1",
      archived_had_score: true,
    });
    const onDone = vi.fn();
    render(
      <ReopenQuestionnaireDialog
        companyId="c-1"
        participant={cuUnChestionar}
        onClose={() => {}}
        onDone={onDone}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Da, redeschide" }));

    await waitFor(() => {
      expect(reopenParticipantAssignment).toHaveBeenCalledWith("c-1", "a-1");
    });
    expect(onDone).toHaveBeenCalled();
  });
});
