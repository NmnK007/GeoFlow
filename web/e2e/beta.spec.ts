import {test, expect} from "@playwright/test";

test("research displays every archive cell exactly and fits a phone", async ({page, request}) => {
  await page.setViewportSize({width:390,height:844});
  await page.goto("/research");
  const report = await (await request.get("/api/v1/research")).json();
  await expect(page.getByRole("table")).toHaveCount(report.length);
  for(let i=0;i<report.length;i++) {
    const rows = page.getByRole("table").nth(i).locator("tbody tr");
    expect(await rows.evaluateAll(items => items.map(r => Array.from(r.children, c => c.textContent))))
      .toEqual(report[i].rows.map((r: unknown[]) => r.map(v => v === null ? "—" : String(v))));
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press("Tab");
  await expect(page.getByText("Skip to content")).toBeFocused();
});

test("job survives a reload and a temporary polling failure", async ({page}) => {
  test.skip(process.env.GEOFLOW_READ_ONLY === "1");
  await page.goto("/simulation");
  await page.getByRole("button",{name:"Run simulation"}).click();
  await page.waitForFunction(() => sessionStorage.getItem("geoflow:job:simulation"));
  await page.route("**/api/v1/jobs/*", route => route.abort(), {times:1});
  await page.reload();
  await expect(page.getByText(/reconnecting to your job/i)).toBeVisible();
  await expect(page.getByText(/Job completed/)).toBeVisible();
  await expect(page.locator(".map canvas").first()).toHaveAttribute("width","64");
});

test("public visitor journey uses only archived data", async ({page}) => {
  test.skip(process.env.GEOFLOW_READ_ONLY !== "1");
  const mutations:string[] = [];
  page.on("request", r => {if (r.url().includes("/api/v1/") && r.method() !== "GET") mutations.push(r.url());});
  await page.goto("/");
  await expect(page.getByText(/Public demo ·/)).toBeVisible();
  const nav = page.getByRole("navigation");
  await nav.getByText("Simulation").click();
  await page.getByRole("button",{name:/45°/}).click();
  await expect(page.locator(".map canvas")).toBeVisible();
  await expect(page.getByRole("button",{name:"Run simulation"})).toHaveCount(0);
  await nav.getByText("Earth").click();
  await page.getByLabel("Historical drifter").selectOption({index:1});
  await expect(page.locator(".map canvas")).toBeVisible();
  await expect(page.getByText("New particle release")).toHaveCount(0);
  await nav.getByText("Neural").click();
  await expect(page.locator(".map canvas")).toHaveCount(2);
  await expect(page.getByText("New CPU inference")).toHaveCount(0);
  await nav.getByText("HPC").click();
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await nav.getByText("Research").click();
  await expect(page.getByRole("table")).toHaveCount(6);
  expect(mutations).toEqual([]);
});

test("all labs fit tablet and phone widths", async ({page}) => {
  for (const width of [768,390]) {
    await page.setViewportSize({width, height:900});
    for (const lab of ["simulation","earth","neural","hpc"]) {
      await page.goto("/"+lab);
      await expect(page.locator(lab === "hpc" ? "tbody tr" : ".map canvas").first()).toBeVisible();
      const size = await page.evaluate(() => document.documentElement.scrollWidth);
      expect(size, lab+" at "+width).toBeLessThanOrEqual(width);
    }
  }
});
