import { type Page, expect } from "@playwright/test";

export class ParticipantPage {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  private continueTaskLink() {
    return this.page.getByRole("link", { name: /^Continuă/i }).first();
  }

  async gotoInvite(token: string) {
    await this.page.goto(`/invite/${token}`);
    await this.page.waitForLoadState("networkidle");
  }

  async acceptConsentIfShown() {
    const consentButton = this.page.getByRole("button", { name: "Continuă la chestionare" });
    await Promise.race([
      consentButton.waitFor({ state: "visible", timeout: 5000 }).catch(() => undefined),
      this.continueTaskLink().waitFor({ state: "visible", timeout: 5000 }).catch(() => undefined),
    ]);
    if (!(await consentButton.isVisible())) {
      return;
    }

    const consentCheckbox = this.page.locator("input[type='checkbox']").first();
    await consentCheckbox.check();
    await expect(consentCheckbox).toBeChecked();
    await expect(consentButton).toBeEnabled();
    await consentButton.click();
    await this.page.waitForLoadState("networkidle");
    await expect(this.continueTaskLink()).toBeVisible();
  }

  async startFilling() {
    await this.acceptConsentIfShown();
    const button = this.continueTaskLink();
    await expect(button).toBeVisible();
    await button.click();
    await this.page.waitForLoadState("networkidle");
  }

  async startNextTask() {
    await this.acceptConsentIfShown();
    const continuaLink = this.continueTaskLink();
    if (await continuaLink.isVisible()) {
      await continuaLink.click();
    } else {
      const button = this.page.getByRole("link", { name: "Continuă" }).first();
      await expect(button).toBeVisible();
      await button.click();
    }
    await this.page.waitForLoadState("networkidle");
  }

  async fillCurrentQuestionnaire() {
    // Wait for the form to render by checking for either answer-button groups or legacy selects.
    await this.page.locator("[data-testid='question-response-group'], select").first().waitFor({ state: "visible" });

    // 1. Answer button-based questions, including Likert, single-choice, and statement sets.
    const responseGroups = this.page.getByTestId("question-response-group");
    const responseGroupCount = await responseGroups.count();
    for (let i = 0; i < responseGroupCount; i++) {
      const buttons = responseGroups.nth(i).locator("button");
      if ((await buttons.count()) > 0) {
        await buttons.first().click();
        await this.page.waitForTimeout(50); // Small delay to avoid event clashing
      }
    }

    // 2. Answer legacy dropdown questions if any older questionnaire still renders them.
    const selects = this.page.locator("select");
    const selectCount = await selects.count();
    for (let i = 0; i < selectCount; i++) {
      const sel = selects.nth(i);
      const options = sel.locator("option");
      const optCount = await options.count();
      if (optCount > 1) {
        // Option index 0 is "Alege scorul" (placeholder), index 1 is first value
        const val = await options.nth(1).getAttribute("value");
        if (val) {
          await sel.selectOption(val);
          // Wait briefly after selecting to allow state update/autosave debouncing to process
          await this.page.waitForTimeout(100);
        }
      }
    }
  }

  async saveDraftAndExit() {
    const btn = this.page.getByRole("button", { name: /^Înapoi la/ });
    await expect(btn).toBeEnabled();
    await btn.click();
    await this.page.waitForLoadState("networkidle");
    await expect(this.continueTaskLink()).toBeVisible();
  }

  async submitResponse() {
    const btn = this.page.getByRole("button", { name: "Trimite răspunsurile" });
    await expect(btn).toBeEnabled();
    this.page.once("dialog", async (dialog) => {
      await dialog.accept();
    });
    await btn.click();
    // Verify confirmation screen is shown
    await expect(this.page.locator("h3")).toContainText("Răspunsurile au fost trimise");
  }

  async backToTasks() {
    const btn = this.page.getByRole("link", { name: "Înapoi la sarcinile mele" });
    await expect(btn).toBeVisible();
    await btn.click();
    await this.page.waitForLoadState("networkidle");
  }
}
