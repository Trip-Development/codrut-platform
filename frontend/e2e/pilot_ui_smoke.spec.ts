import { type APIRequestContext, expect, test } from "@playwright/test";
import { execSync } from "child_process";
import { LoginPage } from "./pom/LoginPage";

type SeededPilot = {
  companyId: string;
  companyName: string;
  projectId: string;
  projectName: string;
};

function seedPilotUiState(): SeededPilot {
  const runId = Date.now().toString(36);
  const stdout = execSync(
    "docker compose -f ../compose.yaml -f ../compose.dev.yaml exec -T backend uv run python -m codrut.tools.seed_pilot_ui_e2e_state",
    {
      encoding: "utf8",
      env: {
        ...process.env,
        CODRUT_E2E_PILOT_RUN_ID: runId,
      },
    },
  );

  const companyId = stdout.match(/Company ID:\s*([0-9a-f-]+)/i)?.[1];
  const companyName = stdout.match(/Company Name:\s*(.+)/)?.[1]?.trim();
  const projectId = stdout.match(/Project ID:\s*([0-9a-f-]+)/i)?.[1];
  const projectName = stdout.match(/Project Name:\s*(.+)/)?.[1]?.trim();

  if (!companyId || !companyName || !projectId || !projectName) {
    throw new Error(`Could not parse pilot UI seed output:\n${stdout}`);
  }

  return { companyId, companyName, projectId, projectName };
}

async function mailpitSubjectsForCompany(request: APIRequestContext, companyName: string) {
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    const response = await request.get("http://localhost:8025/api/v1/messages");
    expect(response.ok()).toBeTruthy();
    const payload = await response.json();
    const subjects: string[] = (payload.messages ?? [])
      .map((message: { Subject?: string }) => message.Subject ?? "")
      .filter((subject: string) => subject.includes(companyName));
    if (subjects.length >= 6) {
      return subjects;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return [];
}

test.describe("Pilot trainer UI smoke", () => {
  test.setTimeout(90_000);

  let seeded: SeededPilot;

  test.beforeAll(() => {
    seeded = seedPilotUiState();
  });

  test("generates assignments, saves them, and sends project invitations", async ({ page, request }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login("trainer@example.com", "replace-with-a-long-test-password");
    await expect(page).toHaveURL(/\/trainer/);

    await page.goto(`/trainer/projects/${seeded.projectId}`);
    await expect(page.getByRole("heading", { name: seeded.projectName })).toBeVisible();
    await expect(page.getByRole("link", { exact: true, name: "Asignări" })).toBeVisible();
    await expect(page.getByRole("link", { exact: true, name: "Invitații" })).toBeVisible();

    await page.getByRole("link", { exact: true, name: "Asignări" }).click();
    await expect(page).toHaveURL(new RegExp(`/trainer/projects/${seeded.projectId}/assignments$`));
    await expect(page.getByRole("heading", { name: "Configurează asignările înainte de trimitere" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Autoevaluare/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Persoană/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Echipă/ })).toBeVisible();

    await Promise.all([
      page.waitForResponse(
        (response) =>
          response.url().includes(`/api/companies/${seeded.companyId}/assignments/default-plan`) &&
          response.request().method() === "GET" &&
          response.ok(),
      ),
      page.getByRole("button", { name: "Generează plan de asignări" }).click(),
    ]);
    await expect(page.getByText("Leadership", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Leadership · 3 rânduri")).toBeVisible();
    await expect(page.getByText("Echipa Ilinca Corbu QA", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Echipă manager · 2 rânduri").first()).toBeVisible();
    await expect(page.getByText("Echipa Vlad Soimu QA", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Echipă manager · 1 rânduri").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Salvează asignările bifate (24)" })).toBeEnabled();

    await Promise.all([
      page.waitForResponse(
        (response) =>
          response.url().includes(`/api/companies/${seeded.companyId}/assignments/default-plan`) &&
          response.request().method() === "POST" &&
          response.ok(),
      ),
      page.getByRole("button", { name: "Salvează asignările bifate (24)" }).click(),
    ]);
    await expect(page.getByText("Asignări totale").locator("xpath=..").getByText("24")).toBeVisible();
    await expect(page.getByText("Persoane fără sarcini").locator("xpath=..").getByText("0")).toBeVisible();
    await expect(page.getByRole("button", { name: "Salvează asignările bifate (0)" })).toBeDisabled();

    await page.getByRole("link", { exact: true, name: "Invitații" }).click();
    await expect(page).toHaveURL(new RegExp(`/trainer/projects/${seeded.projectId}/invitations$`));
    await expect(page.getByRole("heading", { name: "Persoane invitate" })).toBeVisible();
    await Promise.all([
      page.waitForResponse(
        (response) =>
          response.url().includes(`/api/companies/${seeded.companyId}/participants/invitations`) &&
          response.request().method() === "POST" &&
          response.ok(),
      ),
      page.getByRole("button", { name: "Trimite email tuturor" }).click(),
    ]);
    await expect(page.getByText("6/6 emailuri trimise.")).toBeVisible();

    const subjects = await mailpitSubjectsForCompany(request, seeded.companyName);
    expect(subjects).toHaveLength(6);
    expect(subjects.filter((subject: string) => subject.includes("activează contul"))).toHaveLength(3);
    expect(subjects.filter((subject: string) => subject.includes("chestionare"))).toHaveLength(3);
  });
});
