import {
  type APIRequestContext,
  expect,
  type Page,
  type Response,
  test,
} from "@playwright/test";
import { execFileSync } from "child_process";
import { randomUUID } from "crypto";
import { LoginPage } from "./pom/LoginPage";
import { ParticipantPage } from "./pom/ParticipantPage";

type SeededPilot = {
  companyId: string;
  companyName: string;
  projectId: string;
  projectName: string;
};

function seedPilotUiState(): SeededPilot {
  const runId = randomUUID();
  const stdout = execFileSync(
    "docker",
    [
      "compose",
      "-f",
      "../compose.yaml",
      "-f",
      "../compose.e2e.yaml",
      "exec",
      "-T",
      "backend",
      "python",
      "-m",
      "codrut.tools.seed_pilot_ui_e2e_state",
    ],
    {
      encoding: "utf8",
      timeout: 60_000,
      env: {
        ...process.env,
        CODRUT_E2E_PILOT_RUN_ID: runId,
      },
    },
  );

  const outputLine = stdout
    .trim()
    .split("\n")
    .reverse()
    .find((line: string) => line.trim().startsWith("{"));
  if (!outputLine) {
    throw new Error(`Could not parse pilot UI seed output:\n${stdout}`);
  }
  return JSON.parse(outputLine) as SeededPilot;
}

type MailpitMessage = {
  ID: string;
  Subject?: string;
};

const mailpitApiUrl = (
  process.env.CODRUT_E2E_MAILPIT_API_URL ?? "http://127.0.0.1:8025"
).replace(/\/$/, "");

async function mailpitMessagesForCompany(request: APIRequestContext, companyName: string) {
  let messages: MailpitMessage[] = [];
  await expect
    .poll(
      async () => {
        const response = await request.get(`${mailpitApiUrl}/api/v1/messages`);
        expect(response.ok()).toBeTruthy();
        const payload = await response.json();
        messages = (payload.messages ?? []).filter((message: MailpitMessage) =>
          message.Subject?.includes(companyName),
        );
        return messages.length;
      },
      {
        message: `Expected six invitation messages for ${companyName}`,
        timeout: 10_000,
      },
    )
    .toBe(6);
  return messages;
}

async function secureInvitePath(request: APIRequestContext, messages: MailpitMessage[]) {
  const taskMessage = messages.find((message) => message.Subject?.includes("chestionare"));
  expect(taskMessage).toBeDefined();

  const response = await request.get(`${mailpitApiUrl}/api/v1/message/${taskMessage?.ID}`);
  expect(response.ok()).toBeTruthy();
  const payload = await response.json();
  const body = `${payload.Text ?? ""}\n${payload.HTML ?? ""}`.replaceAll("&amp;", "&");
  const inviteUrl = body.match(/https?:\/\/[^\s"'<>]+\/invite\/[^\s"'<>]+/)?.[0];
  expect(inviteUrl).toBeDefined();
  const parsed = new URL(inviteUrl ?? "http://localhost/");
  return `${parsed.pathname}${parsed.search}`;
}

async function expectApiMutation(
  page: Page,
  matches: (response: Response) => boolean,
  action: () => Promise<void>,
) {
  const [response] = await Promise.all([page.waitForResponse(matches), action()]);
  expect(
    response.ok(),
    `API mutation failed with ${response.status()}: ${await response.text()}`,
  ).toBe(true);
}

test.describe.serial("Pilot delivery and completion journey", () => {
  test.setTimeout(90_000);

  let seeded: SeededPilot;
  let invitePath: string;

  test.beforeAll(() => {
    seeded = seedPilotUiState();
  });

  test("trainer generates assignments and queues project invitations", async ({ page, request }) => {
    const loginPage = new LoginPage(page);
    await loginPage.gotoTrainer();
    await loginPage.login("trainer@example.com", "replace-with-a-long-test-password");
    await expect(page).toHaveURL(/\/trainer\/?$/);

    await page.goto(`/trainer/projects/${seeded.projectId}`);
    await expect(page.getByRole("heading", { name: seeded.projectName })).toBeVisible();
    await expect(page.getByRole("link", { exact: true, name: "Asignări" })).toBeVisible();
    await expect(page.getByRole("link", { exact: true, name: "Invitații" })).toBeVisible();

    await page.getByRole("link", { exact: true, name: "Asignări" }).click();
    await expect(page).toHaveURL(new RegExp(`/trainer/projects/${seeded.projectId}/assignments$`));
    await expect(page.getByRole("heading", { name: "Plan de asignări" })).toBeVisible();
    await page.getByRole("button", { name: "Asignare individuală" }).click();
    await expect(page.getByRole("heading", { name: "Asignare individuală" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Autoevaluare/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Persoană/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Echipă/ })).toBeVisible();
    await expect(page).toHaveURL(/modal=advanced-assignment/);
    await page.getByRole("button", { name: "Închide" }).click();
    await expect(page).not.toHaveURL(/modal=advanced-assignment/);

    await expectApiMutation(
      page,
      (response) =>
        response.url().includes(`/api/companies/${seeded.companyId}/assignments/default-plan`) &&
        response.request().method() === "GET",
      () => page.getByRole("button", { name: "Generează plan" }).click(),
    );
    await expect(page.getByText("Leadership", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Echipa Mara Ionescu QA", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Echipa Sorin Pavel QA", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Salvează 24 asignări" })).toBeEnabled();

    await expectApiMutation(
      page,
      (response) =>
        response.url().includes(`/api/companies/${seeded.companyId}/assignments/default-plan`) &&
        response.request().method() === "POST",
      () => page.getByRole("button", { name: "Salvează 24 asignări" }).click(),
    );
    await expect(page.getByText("24 create, 0 deja existente.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Regenerează planul" })).toBeEnabled();
    await expect(page.getByRole("button", { name: /Salvează \d+ asignări/ })).toHaveCount(0);

    await page.getByRole("link", { exact: true, name: "Invitații" }).click();
    await expect(page).toHaveURL(new RegExp(`/trainer/projects/${seeded.projectId}/invitations$`));
    await expect(page.getByRole("heading", { name: "Livrare invitații" })).toBeVisible();
    await expectApiMutation(
      page,
      (response) =>
        response.url().includes(`/api/companies/${seeded.companyId}/participants/invitations`) &&
        response.request().method() === "POST",
      () => page.getByRole("button", { name: "Trimite tuturor" }).click(),
    );
    await expect(page.getByText("0 acceptate de furnizor, 6 în coadă, 0 eșuate.")).toBeVisible();

    const messages = await mailpitMessagesForCompany(request, seeded.companyName);
    const subjects = messages.map((message) => message.Subject ?? "");
    expect(subjects).toHaveLength(6);
    expect(subjects.filter((subject: string) => subject.includes("activează contul"))).toHaveLength(3);
    expect(subjects.filter((subject: string) => subject.includes("chestionare"))).toHaveLength(3);

    invitePath = await secureInvitePath(request, messages);
  });

  test("secure-link participant consents, completes, and submits a questionnaire", async ({
    page,
  }) => {
    expect(invitePath).toBeTruthy();
    await page.context().clearCookies();
    await page.goto(invitePath);
    const participantPage = new ParticipantPage(page);
    await participantPage.startFirstTask();
    await participantPage.answerCurrentQuestionnaire();
    await participantPage.submit();
  });
});
