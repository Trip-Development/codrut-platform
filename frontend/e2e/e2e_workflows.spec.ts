import { test, expect } from "@playwright/test";
import { execSync } from "child_process";
import { LoginPage } from "./pom/LoginPage";
import { TrainerDashboardPage } from "./pom/TrainerDashboardPage";
import { ParticipantPage } from "./pom/ParticipantPage";

test.describe("Security and Auth Workflows", () => {
  test("should redirect unauthenticated users to /login", async ({ page }) => {
    // Attempting to access trainer panel directly
    await page.goto("/trainer");
    await expect(page).toHaveURL(/\/login/);

    // Attempting to access participant panel directly
    await page.goto("/participant");
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("Complete End-to-End Workflow with Confidentiality Thresholds", () => {
  test.setTimeout(180000);
  let aliceUrl = "";
  let bobUrl = "";
  let charlieUrl = "";
  let projectId = "";

  test.beforeAll(() => {
    // Seed the database with a clean E2E company and retrieve the magic URLs
    console.log("Seeding E2E test database state...");
    const stdout = execSync(
      "docker compose -f ../compose.yaml -f ../compose.dev.yaml exec -T backend uv run python -m codrut.tools.seed_e2e_state",
      { encoding: "utf8" }
    );
    console.log("Seeder execution completed.");

    const aliceMatch = stdout.match(/Alice Popescu.*?:\s*(https?:\/\/[^\s]+)/);
    const bobMatch = stdout.match(/Bob Ionescu.*?:\s*(https?:\/\/[^\s]+)/);
    const charlieMatch = stdout.match(/Charlie Vasilescu.*?:\s*(https?:\/\/[^\s]+)/);
    const projectMatch = stdout.match(/Project ID:\s*([0-9a-f-]+)/i);

    if (!aliceMatch || !bobMatch || !charlieMatch || !projectMatch) {
      throw new Error("Could not parse seeded invite URLs from seeder output:\n" + stdout);
    }

    aliceUrl = aliceMatch[1];
    bobUrl = bobMatch[1];
    charlieUrl = charlieMatch[1];
    projectId = projectMatch[1];
    console.log(`Parsed seeded project ID for tests: ${projectId}`);
  });

  test("should complete surveys for Alice and Bob, verify confidentiality threshold, and then complete Charlie's to reveal aggregate dashboard", async ({ page }) => {
    const participantPage = new ParticipantPage(page);

    // 1. Alice Popescu fills her assignments (Distress Drivers and Lencioni)
    console.log("Filling surveys for Alice Popescu...");
    await page.goto(aliceUrl);
    await page.waitForLoadState("networkidle");
    await participantPage.startFilling();

    // Fill Distress Drivers (uses dropdown selects)
    await participantPage.fillCurrentQuestionnaire();
    // Test draft saving functionality
    await participantPage.saveDraft();
    await participantPage.startFilling();
    // Submit the task resumed from draft
    await participantPage.submitResponse();

    // Navigate back to invite URL to get the clean updated tasks list
    await page.goto(aliceUrl);
    await page.waitForLoadState("networkidle");

    // Start next task (Lencioni - uses Likert buttons)
    await participantPage.startNextTask();
    await participantPage.fillCurrentQuestionnaire();
    await participantPage.submitResponse();
    console.log("Alice Popescu completed all surveys.");

    // 2. Bob Ionescu fills his assignments
    console.log("Filling surveys for Bob Ionescu...");
    await page.goto(bobUrl);
    await page.waitForLoadState("networkidle");
    await participantPage.startFilling();

    // Fill Distress Drivers
    await participantPage.fillCurrentQuestionnaire();
    await participantPage.submitResponse();

    // Navigate back to invite URL
    await page.goto(bobUrl);
    await page.waitForLoadState("networkidle");

    // Fill Lencioni
    await participantPage.startNextTask();
    await participantPage.fillCurrentQuestionnaire();
    await participantPage.submitResponse();
    console.log("Bob Ionescu completed all surveys.");

    // 3. Trainer logs in and verifies reports page (completions = 2 < 3, warning should be active)
    console.log("Verifying confidentiality warning as trainer (completions = 2)...");
    const loginPage = new LoginPage(page);
    const trainerPage = new TrainerDashboardPage(page);

    await loginPage.goto();
    await loginPage.login("trainer@example.com", "replace-with-a-long-test-password");
    await trainerPage.verifyOnDashboard();

    // Navigate to E2E project reports
    await trainerPage.goToReports(projectId);
    await trainerPage.verifyConfidentialityWarning(2);
    console.log("Confidentiality warning verified successfully.");

    // Logout trainer by clearing cookies/session (going back to invite will login as user again)
    await page.context().clearCookies();

    // 4. Charlie Vasilescu fills his assignments (third completion)
    console.log("Filling surveys for Charlie Vasilescu (3rd respondent)...");
    await page.goto(charlieUrl);
    await page.waitForLoadState("networkidle");
    await participantPage.startFilling();

    // Fill Distress Drivers
    await participantPage.fillCurrentQuestionnaire();
    await participantPage.submitResponse();

    // Navigate back to invite URL
    await page.goto(charlieUrl);
    await page.waitForLoadState("networkidle");

    // Fill Lencioni
    await participantPage.startNextTask();
    await participantPage.fillCurrentQuestionnaire();
    await participantPage.submitResponse();
    console.log("Charlie Vasilescu completed all surveys.");

    // 5. Trainer logs back in and verifies Lencioni averages are visible
    console.log("Verifying aggregate averages are visible as trainer (completions = 3)...");
    await loginPage.goto();
    await loginPage.login("trainer@example.com", "replace-with-a-long-test-password");
    await trainerPage.verifyOnDashboard();

    await trainerPage.goToReports(projectId);
    await trainerPage.verifyLencioniResultsVisible();
    console.log("Aggregate results verified. E2E workflow succeeded.");
  });
});
