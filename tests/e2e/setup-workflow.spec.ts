import { test, expect } from "@playwright/test";

test.describe("Setup & Navigation", () => {
  test("loads the homepage with setup form", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h2")).toContainText("Setup");
    await expect(page.locator('input[placeholder*="Stripe"]')).toBeVisible();
    await expect(
      page.locator('textarea[placeholder*="Paste the full job"]')
    ).toBeVisible();
  });

  test("requires job posting to submit", async ({ page }) => {
    await page.goto("/");
    const submitBtn = page.locator("button", {
      hasText: "Save & Continue",
    });
    await expect(submitBtn).toBeDisabled();
  });

  test("creates a workflow and navigates to resume step", async ({
    page,
  }) => {
    await page.goto("/");

    await page.fill('input[placeholder*="Stripe"]', "Acme Corp");
    await page.fill(
      'textarea[placeholder*="Paste the full job"]',
      "Senior Engineer role at Acme Corp. Requirements: Python, distributed systems, 5+ years experience."
    );

    await page.click("button:has-text('Save & Continue')");

    // Should navigate to resume step after setup
    await expect(page.locator("h2")).toContainText("Resume", {
      timeout: 5000,
    });
    // Sidebar should show setup as completed
    await expect(page.locator("text=1/12 steps")).toBeVisible();
  });

  test("sidebar steps are locked before setup", async ({ page }) => {
    await page.goto("/");
    // Research button in sidebar should be disabled
    const researchBtn = page.locator("button:has-text('Research')").first();
    await expect(researchBtn).toBeDisabled();
  });

  test("shows existing workflows for resuming", async ({ page }) => {
    // Create a workflow with a unique name
    const uniqueName = `ResumeTestCo_${Date.now()}`;
    const response = await page.request.post("/api/setup", {
      data: {
        job_posting: "Test job posting",
        company_name: uniqueName,
      },
    });
    expect(response.ok()).toBeTruthy();

    // Now load the page — should show the existing workflow
    await page.goto("/");
    await page.locator("summary", { hasText: "Previous applications" }).click();
    await expect(page.locator(`text=${uniqueName}`)).toBeVisible({
      timeout: 5000,
    });
  });
});
