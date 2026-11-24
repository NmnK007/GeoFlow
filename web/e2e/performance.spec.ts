import { test, expect } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

for (const rate of [1, 4]) {
  test(`matched browser workflows at CPU throttle ${rate}`, async ({page}, info) => {
    test.skip(!process.env.GEOFLOW_BENCH_OUT, "Opt-in benchmark with the synthetic map registry");
    const times: Record<string, number> = {};
    const session = await page.context().newCDPSession(page);
    await session.send("Emulation.setCPUThrottlingRate", {rate});
    if (rate === 4) await page.setViewportSize({width: 390, height: 844});
    async function measure(label: string, work: () => Promise<void>) {
      const start = performance.now();
      await work();
      times[label] = performance.now() - start;
    }
    await measure("landing_ms", async () => {
      await page.goto("/", {waitUntil:"domcontentloaded"});
      await expect(page.locator("h1")).toBeVisible();
    });
    await expect(page.locator(".art-scene canvas")).toBeVisible();
    times.animation_frame_interval_ms = await page.evaluate(() => new Promise<number>((resolve) => {
      const stamps: number[] = [];
      function frame(t: number) {
        stamps.push(t);
        if (stamps.length === 31) resolve((t - stamps[0]) / 30);
        else requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);
    }));
    const nav = page.getByRole("navigation");
    const canvas = page.locator(".map canvas").first();
    await measure("navigation_to_map_ms", async () => {
      await nav.getByText("Simulation").click();
      await expect(canvas).toHaveAttribute("width","32");
    });
    await measure("submit_ms", async () => {
      const response = page.waitForResponse(r => r.url().endsWith("/simulations") && r.status() === 202);
      await page.getByRole("button",{name:"Run simulation"}).click();
      await response;
    });
    await expect(canvas).toHaveAttribute("width","64");
    await measure("field_ms", async () => {
      await page.getByLabel("Scientific field").selectOption("Relative vorticity");
      await expect(page.getByRole("heading",{name:/Relative vorticity/})).toBeVisible();
      await expect(canvas).toHaveAttribute("data-draw-ms",/.+/);
    });
    await measure("export_ms", async () => {
      const download = page.waitForEvent("download");
      await page.getByText("Download full-resolution results").click();
      expect(await (await download).failure()).toBeNull();
    });
    await nav.getByText("Earth").click();
    await expect(canvas).toBeVisible();
    await measure("regional_map_ms", async () => {
      await page.getByLabel("Current source").selectOption("benchmark");
      await expect(canvas).toHaveAttribute("width","256");
    });
    await nav.getByText("Neural").click();
    await expect(page.locator(".map canvas")).toHaveCount(2);
    await measure("neural_compare_ms", async () => {
      await page.getByLabel("Model",{exact:true}).selectOption("cnn");
      await expect(page.getByRole("heading",{name:/CNN · m/})).toBeVisible();
      await expect(page.locator(".map canvas")).toHaveCount(2);
    });
    await nav.getByText("HPC").click();
    await expect(page.locator("tbody tr").first()).toBeVisible();
    await measure("hpc_filter_ms", async () => {
      await page.getByLabel("Device",{exact:true}).selectOption("cuda");
      await expect(page.locator("tbody")).toContainText("cuda");
      await expect(page.locator("tbody")).not.toContainText("cpu");
    });
    const out = process.env.GEOFLOW_BENCH_OUT!;
    await mkdir(out, {recursive:true});
    await writeFile(path.join(out,`cpu-${rate}-${info.repeatEachIndex}.json`), JSON.stringify(times,null,2));
  });
}
