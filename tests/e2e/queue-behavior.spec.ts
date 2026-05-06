import { test, expect, Page } from "@playwright/test";

let testCounter = 0;
let createdStateIds: string[] = [];

async function setupWorkflow(
  page: Page,
  options: { customAction?: boolean } = {}
): Promise<string> {
  const companyName = `QueueTest_${++testCounter}_${Date.now()}`;
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
  createdStateIds.push(id);

  if (options.customAction) {
    const created = await page.request.post("/api/custom-actions", {
      data: { name: `Queue Custom ${testCounter}` },
    });
    const { action } = await created.json();
    await page.request.put(`/api/custom-actions/${action.id}`, {
      data: {
        name: action.name,
        description: "Queue behavior custom action",
        prompt_template: "Summarize {{resume}} for {{company}}.",
      },
    });
  }

  await page.goto("/");
  await page.locator("summary", { hasText: "Previous applications" }).click();
  const row = page
    .getByText(companyName, { exact: false })
    .locator("xpath=ancestor::div[contains(@class, 'p-3')][1]");
  await row.getByRole("button", { name: "Select" }).click();
  await expect(page.locator("text=1/12 steps")).toBeVisible({ timeout: 5000 });
  return id;
}

async function queuedSectionKeys(page: Page): Promise<string[]> {
  const response = await page.request.get("/api/queue");
  const queue = await response.json();
  return queue.queued.map((item: { section_key: string }) => item.section_key);
}

async function queueSnapshot(page: Page): Promise<{
  running: { id: string; state_id: string; section_key: string } | null;
  queued: Array<{ id: string; state_id: string; section_key: string }>;
}> {
  const response = await page.request.get("/api/queue");
  return response.json();
}

test.describe("AI Queue", () => {
  test.afterEach(async ({ page }) => {
    const initialQueue = await queueSnapshot(page);
    if (
      initialQueue.running &&
      createdStateIds.includes(initialQueue.running.state_id)
    ) {
      await page.request
        .post(`/api/queue/${initialQueue.running.id}/cancel`)
        .catch(() => undefined);
    }
    await expect
      .poll(async () => Boolean((await queueSnapshot(page)).running), {
        timeout: 10000,
      })
      .toBe(false);

    for (const stateId of createdStateIds) {
      await page.request.delete(`/api/state/${stateId}`).catch(() => undefined);
    }
    createdStateIds = [];
    await expect
      .poll(async () => {
        const queue = await queueSnapshot(page);
        return {
          running: Boolean(queue.running),
          queued: queue.queued.length,
        };
      }, { timeout: 10000 })
      .toEqual({ running: false, queued: 0 });
  });

  test("queued Story Bank run does not show progress until it starts", async ({
    page,
  }) => {
    const stateId = await setupWorkflow(page);

    await page.click("nav >> button:has-text('Resume Tailor')");
    await page.click("button:has-text('Run AI')");
    await expect
      .poll(async () => (await queueSnapshot(page)).running?.section_key, {
        timeout: 3000,
      })
      .toBe("resume_tailor");
    await page.request.post("/api/queue", {
      data: { state_id: stateId, section_key: "stories", title: "Story Bank" },
    });

    await page.click("nav >> button:has-text('Story Bank')");
    await expect(page.locator("button:has-text(\"Don't Run AI\")")).toBeVisible();
    await expect(
      page.locator("nav >> button:has-text('Story Bank') >> span[title='Queued']").first()
    ).toBeVisible();
    await expect(page.locator("text=Mining stories from your experience")).toHaveCount(0);
    await expect(page.locator("text=Story Mining Live Trace")).toHaveCount(0);

    await expect.poll(() => queuedSectionKeys(page)).toContain("stories");
  });

  test("queued Pitch run can be removed before it starts", async ({ page }) => {
    await setupWorkflow(page);

    await page.click("nav >> button:has-text('Resume Tailor')");
    await page.click("button:has-text('Run AI')");
    await expect(page.locator("button:has-text('Stop AI')")).toBeVisible({
      timeout: 3000,
    });

    await page.click("nav >> button:has-text('Pitch')");
    await page.click("button:has-text('Run AI Later')");
    await expect(page.locator("button:has-text(\"Don't Run AI\")")).toBeVisible();

    await page.click("button:has-text(\"Don't Run AI\")");
    await expect(page.locator("button:has-text(\"Don't Run AI\")")).toHaveCount(0);
    await expect(
      page.locator("nav >> button:has-text('Pitch') >> span[title='Queued']")
    ).toHaveCount(0);
  });

  test("waiting items stay sorted by sidebar order after requeue", async ({ page }) => {
    const stateId = await setupWorkflow(page);

    await page.click("nav >> button:has-text('Resume Tailor')");
    await page.click("button:has-text('Run AI')");
    await expect
      .poll(async () => (await queueSnapshot(page)).running?.section_key)
      .toBe("resume_tailor");

    await page.request.post("/api/queue", {
      data: { state_id: stateId, section_key: "salary", title: "Salary" },
    });
    await page.request.post("/api/queue", {
      data: { state_id: stateId, section_key: "pitch", title: "Pitch" },
    });
    await expect.poll(() => queuedSectionKeys(page)).toEqual(["pitch", "salary"]);

    const salaryItem = (await queueSnapshot(page)).queued.find(
      (item) => item.section_key === "salary"
    );
    expect(salaryItem).toBeTruthy();
    await page.request.delete(`/api/queue/${salaryItem!.id}`);
    await expect.poll(() => queuedSectionKeys(page)).toEqual(["pitch"]);

    await page.request.post("/api/queue", {
      data: { state_id: stateId, section_key: "salary", title: "Salary" },
    });
    await expect.poll(() => queuedSectionKeys(page)).toEqual(["pitch", "salary"]);
  });

  test("research keeps running after navigating away", async ({ page }) => {
    await setupWorkflow(page);

    await page.click("nav >> button:has-text('Research')");
    await page.click("button:has-text('Run AI')");
    await expect(page.locator("button:has-text('Stop AI')")).toBeVisible({
      timeout: 3000,
    });

    await page.click("nav >> button:has-text('Story Bank')");
    await expect(
      page.locator("nav >> button:has-text('Research') >> span[title='Running']").first()
    ).toBeVisible();

    await page.click("nav >> button:has-text('Research')");
    await expect(page.locator("text=Company Overview")).toBeVisible({
      timeout: 15000,
    });
  });

  test("current run can be stopped", async ({ page }) => {
    await setupWorkflow(page);

    await page.click("nav >> button:has-text('Resume Tailor')");
    await page.click("button:has-text('Run AI')");
    await expect(page.locator("button:has-text('Stop AI')")).toBeVisible({
      timeout: 3000,
    });

    await page.click("button:has-text('Stop AI')");
    await expect(page.locator("button:has-text('Stop AI')")).toHaveCount(0, {
      timeout: 5000,
    });
  });

  test("queued custom action runs after a built-in section", async ({ page }) => {
    await setupWorkflow(page, { customAction: true });

    await page.click("nav >> button:has-text('Resume Tailor')");
    await page.click("button:has-text('Run AI')");
    await expect(page.locator("button:has-text('Stop AI')")).toBeVisible({
      timeout: 3000,
    });

    await page.click("nav >> button:has-text('Queue Custom')");
    await page.click("button:has-text('Run AI Later')");
    await expect(page.locator("button:has-text(\"Don't Run AI\")")).toBeVisible();
    await expect(page.locator("text=Custom output")).toBeVisible({ timeout: 15000 });
  });

  test("interactive sections are not queueable", async ({ page }) => {
    await setupWorkflow(page);

    await page.click("nav >> button:has-text('Resume Tailor')");
    await page.click("button:has-text('Run AI')");
    await expect(page.locator("button:has-text('Stop AI')")).toBeVisible({
      timeout: 3000,
    });

    await page.click("nav >> button:has-text('Mock Interview')");
    await expect(page.locator("button:has-text('Run AI Later')")).toHaveCount(0);
    await expect(page.locator("button:has-text('Start Behavioral Interview')")).toBeVisible();

    await page.click("nav >> button:has-text('Resume Tailor')");
    await expect(page.locator("button:has-text('Chat with Coach')")).toBeVisible();
  });
});
