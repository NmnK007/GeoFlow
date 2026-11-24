import { defineConfig } from "@playwright/test";
import path from "node:path";
const web = path.resolve(__dirname),
  root = process.env.GEOFLOW_ROOT || path.resolve(web, "..");
const python =
  process.env.GEOFLOW_PYTHON ||
  path.join(
    root,
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  expect: {timeout: 20000},
  timeout: 90000,
  use: {
    baseURL: "http://127.0.0.1:3071",
    actionTimeout: 10000,
    viewport: { width: 1360, height: 900 },
    launchOptions: { executablePath: process.env.GEOFLOW_CHROME },
  },
  webServer: [
    {
      command:
        '"' +
        python +
        '" -m uvicorn geoflow.web.api:app --host 127.0.0.1 --port 8000',
      cwd: root,
      url: "http://127.0.0.1:8000/api/v1/health",
      timeout: 60000,
    },
    {
      command:
        "node node_modules/next/dist/bin/next start -H 127.0.0.1 -p 3071",
      cwd: web,
      url: "http://127.0.0.1:3071",
      timeout: 60000,
    },
  ],
});
