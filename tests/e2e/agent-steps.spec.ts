import { test, expect, Page } from "@playwright/test";

/**
 * Helper: create a workflow via API and navigate to the app with state loaded.
 */
let testCounter = 0;

async function setupWorkflow(page: Page): Promise<string> {
  const companyName = `AgentTest_${++testCounter}_${Date.now()}`;
  const response = await page.request.post("/api/setup", {
    data: {
      job_posting:
        "Senior Engineer role. Requirements: Python, distributed systems, 5+ years.",
      resume:
        "8 years building distributed systems. Led zero-downtime database migration at 10K QPS.",
      company_name: companyName,
    },
  });
  const { id } = await response.json();

  // Load the state directly via API then navigate
  await page.goto("/");
  await page.locator("summary", { hasText: "Previous applications" }).click();
  const row = page
    .getByText(companyName, { exact: false })
    .locator("xpath=ancestor::div[contains(@class, 'p-3')][1]");
  await row.getByRole("button", { name: "Select" }).click();
  await expect(page.locator("text=1/12 steps")).toBeVisible({ timeout: 5000 });
  return id;
}

test.describe("Company Research", () => {
  test("runs research agent and displays report", async ({ page }) => {
    await setupWorkflow(page);

    // Navigate to research step via sidebar
    await page.click("nav >> button:has-text('Research')");
    await expect(page.locator("h2")).toContainText("Company Research");

    // Run the agent
    await page.click("button:has-text('Run AI')");

    // Wait for the report to render as markdown
    await expect(page.locator("text=Company Overview")).toBeVisible({
      timeout: 15000,
    });
    await expect(page.locator("text=Fit Score")).toBeVisible();
    await expect(page.locator("text=82/100")).toBeVisible();
  });
});

test.describe("Job Decoder", () => {
  test("runs JD decode and shows six-lens analysis", async ({ page }) => {
    await setupWorkflow(page);

    await page.click("nav >> button:has-text('Job Decoder')");
    await expect(page.locator("h2")).toContainText("Job Decoder");

    await page.click("button:has-text('Run AI')");

    await expect(page.locator("text=Repetition Frequency")).toBeVisible({
      timeout: 15000,
    });
    // Multiple elements contain "distributed systems" — just check the analysis rendered
    await expect(page.locator("text=Order & Emphasis")).toBeVisible();
  });
});

test.describe("Story Bank", () => {
  test("mines stories and displays them as expandable cards", async ({
    page,
  }) => {
    await setupWorkflow(page);

    await page.click("nav >> button:has-text('Story Bank')");
    await expect(page.locator("h2")).toContainText("Story Bank");

    // Mine stories
    await page.click("button:has-text('Run AI')");

    // Wait for stories to appear
    await expect(page.locator("text=Led Database Migration")).toBeVisible({
      timeout: 15000,
    });
    await expect(
      page.locator("text=Debugging Production Outage")
    ).toBeVisible();
    await expect(page.locator("text=2 stories in your bank")).toBeVisible();

    // Expand the first story
    await page.click("button:has-text('Led Database Migration')");
    await expect(page.locator("text=Legacy MySQL")).toBeVisible();
    await expect(page.locator("text=zero-downtime migration")).toBeVisible();
    // Check for earned secret
    await expect(
      page.locator("text=convincing the team to stop feature work")
    ).toBeVisible();
  });
});

test.describe("Pitch Building", () => {
  test("runs pitch agent and shows pitch variants", async ({ page }) => {
    await setupWorkflow(page);

    await page.click("nav >> button:has-text('Pitch')");
    await expect(page.locator("h2")).toContainText("Pitch Builder");

    await page.click("button:has-text('Run AI')");

    await expect(page.locator("text=Core Value Proposition")).toBeVisible({
      timeout: 15000,
    });
    await expect(page.locator("text=10-Second Elevator")).toBeVisible();
    await expect(page.locator("text=90-Second Interview")).toBeVisible();
  });
});

test.describe("Concerns", () => {
  test("runs concerns agent and shows anticipated concerns", async ({
    page,
  }) => {
    await setupWorkflow(page);

    await page.click("nav >> button:has-text('Concerns')");
    await expect(page.locator("h2")).toContainText("Interviewer Concerns");

    await page.click("button:has-text('Run AI')");

    await expect(page.locator("text=Anticipated Concerns")).toBeVisible({
      timeout: 15000,
    });
    await expect(page.locator("text=Recent Job Hop")).toBeVisible();
    await expect(page.locator("text=Management Gap")).toBeVisible();
  });
});

test.describe("Salary Coaching", () => {
  test("runs salary agent and shows negotiation guidance", async ({
    page,
  }) => {
    await setupWorkflow(page);

    await page.click("nav >> button:has-text('Salary')");
    await expect(page.locator("h2")).toContainText("Salary Coaching");

    await page.click("button:has-text('Run AI')");

    await expect(
      page.locator("text=Salary Negotiation Guide")
    ).toBeVisible({ timeout: 15000 });
    await expect(page.locator("text=Post-Offer Script")).toBeVisible();
  });
});
