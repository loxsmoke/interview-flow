import { test, expect, Page } from "@playwright/test";

let testCounter = 0;

async function setupWorkflow(page: Page): Promise<string> {
  const companyName = `MockTest_${++testCounter}_${Date.now()}`;
  const response = await page.request.post("/api/setup", {
    data: {
      job_posting:
        "Senior Engineer role. Requirements: Python, distributed systems.",
      resume: "8 years building distributed systems.",
      company_name: companyName,
    },
  });
  const { id } = await response.json();

  await page.goto("/");
  await page.locator("summary", { hasText: "Previous applications" }).click();
  const row = page
    .getByText(companyName, { exact: false })
    .locator("xpath=ancestor::div[contains(@class, 'p-3')][1]");
  await row.getByRole("button", { name: "Select" }).click();
  await expect(page.locator("text=1/12 steps")).toBeVisible({ timeout: 5000 });
  return id;
}

test.describe("Mock Interview", () => {
  test("shows format selection before starting", async ({ page }) => {
    await setupWorkflow(page);

    await page.click("nav >> button:has-text('Mock Interview')");
    await expect(page.locator("h2")).toContainText("Mock Interview");

    // All 5 format option cards should be visible (use .first() since button text also appears in start button)
    await expect(page.locator("div.font-medium", { hasText: "Behavioral" })).toBeVisible();
    await expect(page.locator("div.font-medium", { hasText: "System Design" })).toBeVisible();
    await expect(page.locator("div.font-medium", { hasText: "Case Study" })).toBeVisible();
    await expect(page.locator("div.font-medium", { hasText: "Panel" })).toBeVisible();
    await expect(page.locator("div.font-medium", { hasText: "Bar Raiser" })).toBeVisible();
  });

  test("starts a behavioral interview and shows opening question", async ({
    page,
  }) => {
    await setupWorkflow(page);

    await page.click("nav >> button:has-text('Mock Interview')");

    // Default is behavioral — click start
    await page.click("button:has-text('Start Behavioral Interview')");

    // Wait for the interviewer's opening message
    await expect(page.locator("text=Sarah")).toBeVisible({ timeout: 10000 });
    await expect(page.locator("text=Tell me about a time")).toBeVisible();
    // "Interviewer" label appears under the chat bubble
    await expect(page.locator("text=Interviewer").first()).toBeVisible();
  });

  test("conducts a full multi-turn mock interview through to debrief", async ({
    page,
  }) => {
    await setupWorkflow(page);

    await page.click("nav >> button:has-text('Mock Interview')");
    await page.click("button:has-text('Start Behavioral Interview')");

    // Wait for opening question
    await expect(page.locator("text=Tell me about a time")).toBeVisible({
      timeout: 10000,
    });

    // Send first answer
    const inputArea = page.locator(
      'textarea[placeholder*="Type your answer"]'
    );
    await inputArea.fill(
      "At my previous company, we had a critical database migration that needed to be completed in 6 weeks. I led the effort by breaking it into 3 sprints..."
    );
    await page.click("button:has-text('Send')");

    // Should receive follow-up question (unique text from the follow-up)
    await expect(page.locator("text=disagreements")).toBeVisible({
      timeout: 10000,
    });

    // User message should be in chat
    await expect(page.locator("text=critical database migration")).toBeVisible();

    // Send second answer — this triggers the debrief
    await inputArea.fill(
      "I facilitated a technical design review where each team member presented their approach. We used a decision matrix to evaluate the tradeoffs objectively."
    );
    await page.click("button:has-text('Send')");

    // Should show debrief with scores
    await expect(page.locator("text=Interview Debrief")).toBeVisible({
      timeout: 10000,
    });
    await expect(page.locator("text=Substance")).toBeVisible();
    await expect(page.locator("text=Primary Bottleneck")).toBeVisible();
    await expect(page.getByText("Differentiation", { exact: true }).first()).toBeVisible();

    // Complete indicator should appear (green text in header)
    await expect(page.locator("text=Complete — see debrief below")).toBeVisible();

    // Input area should be hidden when interview is complete
    await expect(inputArea).not.toBeVisible();
  });

  test("can start a new interview after completing one", async ({ page }) => {
    await setupWorkflow(page);

    await page.click("nav >> button:has-text('Mock Interview')");
    await page.click("button:has-text('Start Behavioral Interview')");
    await expect(page.locator("text=Tell me about a time")).toBeVisible({
      timeout: 10000,
    });

    // Click "New Interview" to go back to format selection
    await page.click("button:has-text('New Interview')");
    await expect(
      page.locator("button:has-text('Start Behavioral Interview')")
    ).toBeVisible();
  });

  test("can select a different interview format", async ({ page }) => {
    await setupWorkflow(page);

    await page.click("nav >> button:has-text('Mock Interview')");

    // Select System Design format
    await page.click("button:has-text('System Design')");

    // The start button should reflect the selected format
    await expect(
      page.locator("button:has-text('Start System Design Interview')")
    ).toBeVisible();
  });
});
