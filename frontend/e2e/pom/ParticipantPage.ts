import { type Page, expect } from "@playwright/test";

export class ParticipantPage {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async gotoInvite(token: string) {
    await this.page.goto(`/invite/${token}`);
    await this.page.waitForLoadState("networkidle");
  }

  async startFilling() {
    const button = this.page.getByRole("link", { name: "Continuă următoarea sarcină" });
    await expect(button).toBeVisible();
    await button.click();
    await this.page.waitForLoadState("networkidle");
  }

  async startNextTask() {
    const continuaLink = this.page.getByRole("link", { name: "Continuă următoarea sarcină" });
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
    // Wait for the form to render by checking for either a Likert container or a select element
    await this.page.locator("div.grid.gap-2.sm\\:grid-cols-3, select").first().waitFor({ state: "visible" });

    // 1. Answer Likert scale questions (click first option button in each grid)
    const likertContainers = this.page.locator("div.grid.gap-2.sm\\:grid-cols-3");
    const likertCount = await likertContainers.count();
    for (let i = 0; i < likertCount; i++) {
      const buttons = likertContainers.nth(i).locator("button");
      if ((await buttons.count()) > 0) {
        await buttons.first().click();
        await this.page.waitForTimeout(50); // Small delay to avoid event clashing
      }
    }

    // 2. Answer statement set questions (select first valid value in each dropdown)
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

  async saveDraft() {
    const btn = this.page.getByRole("button", { name: "Salvează draft" });
    await expect(btn).toBeEnabled();
    await btn.click();
    // Wait for the draft saved confirmation text
    await expect(this.page.locator("p.text-foreground\\/55")).toContainText(/Draft salvat/i);
  }

  async submitResponse() {
    const btn = this.page.getByRole("button", { name: "Trimite răspunsurile" });
    await expect(btn).toBeEnabled();
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
