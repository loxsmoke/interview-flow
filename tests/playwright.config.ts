import { defineConfig } from "@playwright/test";
import path from "node:path";

const testServerPath = path.join(__dirname, "e2e", "server.py");
const testServerCommand =
  `"${process.env.E2E_PYTHON ?? (process.platform === "win32" ? "python" : "python3")}" "${testServerPath}"`;

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  retries: 0,
  use: {
    baseURL: "http://localhost:8000",
    headless: true,
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium", channel: "chrome" },
    },
  ],
  // Start the FastAPI server before tests — uses the mock-backed test server
  webServer: {
    command: testServerCommand,
    port: 8000,
    timeout: 15_000,
    reuseExistingServer: false,
  },
});
