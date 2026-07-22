import { type Locator, type Page, expect } from "@playwright/test";

export class LoginPage {
  readonly page: Page;
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly submitButton: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    this.page = page;
    this.emailInput = page.locator("#login-email, #trainer-login-email").first();
    this.passwordInput = page.locator('input[type="password"]').first();
    this.submitButton = page.locator('button[type="submit"]');
    this.errorMessage = page.locator("p.text-red-700");
  }

  async goto() {
    await this.page.goto("/login");
  }

  async gotoTrainer() {
    await this.page.goto("/trainer/login");
  }

  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    const [response] = await Promise.all([
      this.page.waitForResponse(
        (candidate) =>
          candidate.url().endsWith("/api/auth/login") &&
          candidate.request().method() === "POST",
      ),
      this.submitButton.click(),
    ]);
    expect(response.ok()).toBeTruthy();
  }

  async verifyErrorContains(text: string) {
    await expect(this.errorMessage).toContainText(text);
  }
}
