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

  async goToReports(projectId: string) {
    await this.page.goto(`/trainer/projects/${projectId}/reports`);
    await this.page.waitForLoadState("networkidle");
  }

  async verifyConfidentialityWarning(completionsCount: number) {
    await expect(this.page.getByText(`${completionsCount} răspunsuri`).first()).toBeVisible();
    await expect(
      this.page.getByText("Rezultatele sunt ascunse până există cel puțin 3 răspunsuri pentru acest instrument.").first(),
    ).toBeVisible();
  }

  async verifyLencioniResultsVisible() {
    // Suppression should be lifted after the minimum cohort size is reached.
    const warning = this.page.locator("text=Rezultatele sunt ascunse până există cel puțin 3 răspunsuri pentru acest instrument.");
    await expect(warning).toBeHidden();
    
    await expect(this.page.getByRole("heading", { name: "Rezultate" })).toBeVisible();
  }
}
