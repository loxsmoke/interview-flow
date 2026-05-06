import { test, expect, Page } from "@playwright/test";

let testCounter = 0;

async function setupWorkflow(page: Page): Promise<string> {
  const companyName = `DebriefTest_${++testCounter}_${Date.now()}`;
  const response = await page.request.post("/api/setup", {
    data: {
      job_posting: "Senior Engineer role.",
      resume: "8 years experience.",
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

test.describe("Debrief", () => {
  test("saves debrief notes", async ({ page }) => {
    await setupWorkflow(page);

    await page.click("nav >> button:has-text('Debrief')");
    await expect(page.locator("h2")).toContainText("Post-Interview Debrief");

    await page.fill(
      'textarea[placeholder*="What questions"]',
      "They asked about distributed systems scaling. I felt good about my database migration story but could have been more specific about metrics."
    );

    await page.click("button:has-text('Save Debrief')");
    await expect(page.locator("text=Saved!")).toBeVisible({ timeout: 5000 });
  });

  test("debrief textarea is initially empty", async ({ page }) => {
    await setupWorkflow(page);

    await page.click("nav >> button:has-text('Debrief')");
    const textarea = page.locator('textarea[placeholder*="What questions"]');
    await expect(textarea).toHaveValue("");
  });
});

test.describe("File Upload", () => {
  test("uploads a text resume file", async ({ page }) => {
    await page.goto("/");

    // Create a fake text file and upload it
    const buffer = Buffer.from(
      "Jane Smith\n\n8 years of experience in distributed systems.\nLed zero-downtime migrations."
    );

    // Use the API directly since drag-and-drop is complex in Playwright
    const response = await page.request.post("/api/upload-resume", {
      multipart: {
        file: {
          name: "resume.txt",
          mimeType: "text/plain",
          buffer,
        },
      },
    });

    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.text).toContain("Jane Smith");
    expect(data.filename).toBe("resume.txt");
    expect(data.chars).toBeGreaterThan(0);
  });

  test("rejects unsupported file types", async ({ page }) => {
    const response = await page.request.post("/api/upload-resume", {
      multipart: {
        file: {
          name: "photo.jpg",
          mimeType: "image/jpeg",
          buffer: Buffer.from("fake image data"),
        },
      },
    });

    expect(response.status()).toBe(400);
    const data = await response.json();
    expect(data.detail).toContain("Unsupported file type");
  });

  test("rejects empty files", async ({ page }) => {
    const response = await page.request.post("/api/upload-resume", {
      multipart: {
        file: {
          name: "empty.txt",
          mimeType: "text/plain",
          buffer: Buffer.from(""),
        },
      },
    });

    expect(response.status()).toBe(400);
    expect((await response.json()).detail).toContain("Could not extract");
  });
});

test.describe("State Management", () => {
  test("deletes a workflow", async ({ page }) => {
    // Create via API
    const createResp = await page.request.post("/api/setup", {
      data: {
        job_posting: "Job to delete",
        company_name: "Delete Me Corp",
      },
    });
    const { id } = await createResp.json();

    // Verify it exists
    const getResp = await page.request.get(`/api/state/${id}`);
    expect(getResp.ok()).toBeTruthy();

    // Delete
    const delResp = await page.request.delete(`/api/state/${id}`);
    expect(delResp.ok()).toBeTruthy();

    // Verify gone
    const gone = await page.request.get(`/api/state/${id}`);
    expect(gone.status()).toBe(404);
  });

  test("returns 404 for nonexistent state", async ({ page }) => {
    const resp = await page.request.get("/api/state/000000000000");
    expect(resp.status()).toBe(404);
  });
});
