import { expect, test } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
const out = path.resolve(
  process.env.GEOFLOW_ROOT || path.resolve(__dirname, "../.."),
  "outputs/beta-v07/browser",
);
test("navigate, integrate, inspect a frame and export", async ({
  page,
}, testInfo) => {
  const results: Record<string, unknown> = {},
    errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.emulateMedia({ reducedMotion: "reduce" });
  let start = performance.now();
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  results.landing_ms = performance.now() - start;
  await mkdir(out, { recursive: true });
  await page.screenshot({ path: path.join(out, "landing.png") });
  start = performance.now();
  await page.getByRole("navigation").getByText("Simulation").click();
  await expect(
    page.getByRole("heading", { name: "Simulation Laboratory" }),
  ).toBeVisible();
  results.navigation_ms = performance.now() - start;
  const canvas = page.locator(".map canvas").first();
  await expect(canvas).toHaveAttribute("width", "32");
  results.navigation_to_first_map_ms = performance.now() - start;
  const button = page.getByRole("button", { name: "Run simulation" });
  const submitted = page.waitForResponse(
    (r) => r.url().endsWith("/simulations") && r.request().method() === "POST",
  );
  start = performance.now();
  await button.click();
  const response = await submitted;
  expect(response.status()).toBe(202);
  results.submit_ms = performance.now() - start;
  await expect(page.getByRole("status")).toContainText("completed");
  results.job_observed_ms = performance.now() - start;
  await expect(canvas).toHaveAttribute("width", "64");
  results.run_to_map_ms = performance.now() - start;
  const slider = page.getByRole("slider");
  const samples: number[] = [];
  for (let i = 0; i < 3; i++) {
    const before = await canvas.evaluate((c: HTMLCanvasElement) =>
      c.toDataURL(),
    );
    start = performance.now();
    await slider.press("ArrowRight");
    await page.waitForFunction(
      (old) =>
        (
          document.querySelector(".map canvas") as HTMLCanvasElement
        )?.toDataURL() !== old &&
        document.querySelector(".map canvas") !== null,
      before,
    );
    samples.push(performance.now() - start);
  }
  results.slider_ms = samples;
  start = performance.now();
  await page.getByLabel("Scientific field").selectOption("Relative vorticity");
  await expect(
    page.getByRole("heading", { name: /Relative vorticity/ }),
  ).toBeVisible();
  results.field_selection_ms = performance.now() - start;
  results.field_draw_ms = Number(await canvas.getAttribute("data-draw-ms"));
  const dl = page.waitForEvent("download");
  await page.getByText("Download full-resolution results").click();
  expect((await dl).suggestedFilename()).toMatch(/zip$/);
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Performance.enable");
  const metrics = await cdp.send("Performance.getMetrics");
  results.browser_heap_mib =
    metrics.metrics.find((x) => x.name === "JSHeapUsedSize")!.value / 2 ** 20;
  await page.getByRole("navigation").getByText("Earth").click();
  await expect(page.locator(".map canvas")).toBeVisible();
  await page.getByRole("button", { name: "Integrate particle" }).click();
  await expect(page.getByText(/Blue: new particle, completed/)).toBeVisible();
  await page.getByRole("navigation").getByText("Neural").click();
  await expect(page.locator(".map canvas")).toHaveCount(2);
  await page
    .getByRole("combobox", { name: "Model", exact: true })
    .selectOption("cnn");
  await expect(page.getByRole("heading", { name: /CNN · m/ })).toBeVisible();
  await page.getByRole("navigation").getByText("HPC").click();
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await page
    .getByRole("combobox", { name: "Device", exact: true })
    .selectOption("cuda");
  await expect(page.locator("tbody")).toContainText("cuda");
  expect(errors).toEqual([]);
  await writeFile(
    path.join(out, "browser-" + testInfo.repeatEachIndex + ".json"),
    JSON.stringify(results, null, 2),
  );
});
test("mobile landing and reduced motion", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(
    page.getByRole("link", { name: "Open simulation" }),
  ).toBeVisible();
  expect(await page.locator(".art-scene canvas").count()).toBe(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("navigation").getByText("Neural").click();
  await expect(page.locator(".map canvas")).toHaveCount(2);
});
test("bounded concurrent clients leave health responsive", async ({
  request,
}) => {
  const t = performance.now();
  const results = await Promise.all(
    Array.from({ length: 5 }, () =>
      request.post("/api/v1/simulations", { data: {} }),
    ),
  );
  const h = performance.now();
  expect((await request.get("/api/v1/health")).ok()).toBeTruthy();
  const health = performance.now() - h;
  const codes = results.map((r) => r.status());
  expect(codes.filter((s) => s === 202)).toHaveLength(4);
  expect(codes).toContain(429);
  const submitted = performance.now() - t;
  for (const r of results.filter((r) => r.status() === 202)) {
    const { id } = await r.json();
    await expect
      .poll(
        async () =>
          (await (await request.get("/api/v1/jobs/" + id)).json()).state,
        { timeout: 60000 },
      )
      .toBe("completed");
  }
  await writeFile(
    path.join(out, "concurrency.json"),
    JSON.stringify({
      codes,
      submit_and_health_ms: submitted,
      health_ms: health,
      all_observed_ms: performance.now() - t,
    }),
  );
});
test("motion runs only on landing and can be paused", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/");
  await expect(page.locator(".art-scene canvas")).toBeVisible({
    timeout: 20000,
  });
  await page.getByRole("button", { name: "Pause illustration" }).click();
  await expect(page.locator(".art-scene canvas")).toHaveCount(0);
  await page.getByRole("button", { name: "Play illustration" }).click();
  await expect(page.locator(".art-scene canvas")).toBeVisible();
  await page.getByRole("navigation").getByText("Simulation").click();
  await expect(page.locator(".art-scene")).toHaveCount(0);
});

test("direct scientific workspace entry", async ({page}, info) => {
  const t = performance.now();
  await page.goto("/simulation", {waitUntil:"domcontentloaded"});
  await expect(page.getByRole("button",{name:"Run simulation"})).toBeVisible();
  const controls = performance.now() - t;
  await expect(page.locator(".map canvas")).toHaveAttribute("width","32");
  await mkdir(out,{recursive:true});
  await writeFile(path.join(out,"direct-"+info.repeatEachIndex+".json"),JSON.stringify({controls_ms:controls,first_map_ms:performance.now()-t}));
});
