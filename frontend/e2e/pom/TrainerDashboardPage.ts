import { type Locator, type Page, expect } from "@playwright/test";

export class TrainerDashboardPage {
  readonly page: Page;
  readonly companyGrid: Locator;
  readonly companyCards: Locator;

  constructor(page: Page) {
    this.page = page;
    this.companyGrid = page.locator("div.grid");
    this.companyCards = page.locator("a[href*='/trainer/companies/']");
  }

  async verifyOnDashboard() {
    await expect(this.page).toHaveURL(/\/trainer/);
  }

  async verifyCompanyExists(name: string) {
    const card = this.page.getByRole("heading", { name });
    await expect(card).toBeVisible();
  }

  async openCompany(name: string) {
    const card = this.page.locator("a", { has: this.page.getByRole("heading", { name }) });
    await card.first().click();
  }

  async goToReports(companyId: string) {
    await this.page.goto(`/trainer/companies/${companyId}/reports`);
    await this.page.waitForLoadState("networkidle");
  }

  async verifyConfidentialityWarning(completionsCount: number) {
    const warning = this.page.getByText(`Rezultatele agregate vor fi afișate după ce minim 3 participanți completează chestionarul (în prezent: ${completionsCount})`);
    await expect(warning.first()).toBeVisible();
  }

  async verifyLencioniResultsVisible() {
    // The warning message should be hidden/not present
    const warning = this.page.locator("text=Rezultatele agregate vor fi afișate după ce minim 3 participanți");
    await expect(warning).toBeHidden();
    
    // Core disfunctions averages should now be visible
    const trustLabel = this.page.getByText("Absența încrederii (Trust)");
    await expect(trustLabel).toBeVisible();
  }
}
