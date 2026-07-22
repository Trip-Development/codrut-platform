import { test, expect } from "@playwright/test";

test.describe("Security and Auth Workflows", () => {
  test("should redirect unauthenticated users to /login", async ({ page }) => {
    test.skip(
      process.env.CI !== "true" && process.env.CODRUT_FRONTEND_DEMO_FALLBACK !== "false",
      "Local dev enables demo fallback; CI or CODRUT_FRONTEND_DEMO_FALLBACK=false covers auth redirects.",
    );

    // Attempting to access trainer panel directly
    await page.goto("/trainer");
    await expect(page).toHaveURL(/\/login/);

    // Attempting to access participant panel directly
    await page.goto("/participant");
    await expect(page).toHaveURL(/\/login/);
  });
});
