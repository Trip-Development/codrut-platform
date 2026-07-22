import { expect, type Page } from "@playwright/test";

export class ParticipantPage {
  constructor(private readonly page: Page) {}

  private taskLink() {
    return this.page.getByRole("link", { name: /^(Deschide|Continuă)/i }).first();
  }

  async startFirstTask() {
    const consentButton = this.page.getByRole("button", { name: "Continuă la chestionare" });
    await Promise.race([
      consentButton.waitFor({ state: "visible", timeout: 5_000 }).catch(() => undefined),
      this.taskLink().waitFor({ state: "visible", timeout: 5_000 }).catch(() => undefined),
    ]);
    if (await consentButton.isVisible()) {
      const consentCheckbox = this.page.getByRole("checkbox").first();
      await consentCheckbox.check();
      await expect(consentCheckbox).toBeChecked();
      await expect(consentButton).toBeEnabled();
      await consentButton.click();
    }

    await expect(this.taskLink()).toBeVisible();
    await this.taskLink().click();
    await expect(this.page.getByRole("button", { name: "Trimite răspunsurile" })).toBeVisible();
  }

  async answerCurrentQuestionnaire() {
    const groups = this.page.getByTestId("question-response-group");
    await expect(groups.first()).toBeVisible();

    for (let index = 0; index < await groups.count(); index += 1) {
      const group = groups.nth(index);
      const slider = group.getByRole("slider");
      if (await slider.count()) {
        await slider.press("End");
        await expect(group).toHaveAttribute("data-selected", "true");
        continue;
      }

      const buttonRadio = group.getByRole("radio").filter({ visible: true }).first();
      await expect(buttonRadio).toBeVisible();
      await buttonRadio.click();
      await expect(buttonRadio).toBeChecked();
    }
  }

  async submit() {
    const submitButton = this.page.getByRole("button", { name: "Trimite răspunsurile" });
    await expect(submitButton).toBeEnabled();
    await submitButton.click();

    const confirmButton = this.page.getByRole("button", { name: "Trimite", exact: true });
    await expect(confirmButton).toBeVisible();
    await Promise.all([
      this.page.waitForResponse(
        (response) =>
          response.url().includes("/response/submit") &&
          response.request().method() === "POST" &&
          response.ok(),
      ),
      confirmButton.click(),
    ]);

    await expect(this.page.getByRole("heading", { name: "Chestionarele tale" })).toBeVisible();
  }
}
