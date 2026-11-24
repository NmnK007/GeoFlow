"use client";
import { useState } from "react";
import {
  Grid,
  Heading,
  JobState,
  MapView,
  Notice,
  Select,
  Slider,
  Trace,
  api,
  extent,
  useData,
  useJob,
} from "./shared";
type Info = {
  times: number[];
  metadata: { config: Record<string, string | number>; scheme: string };
  fields: Record<string, string>;
  diagnostics: Record<string, number | null>[];
};
export default function Simulation() {
  const presets =
      useData<Record<string, Record<string, number | string>>>("/experiments"),
    runner = useJob();
  const [preset, choose] = useState("gaussian_bump"),
    [lat, latitude] = useState("0"),
    [scheme, method] = useState("rusanov"),
    [advanced, options] = useState("{}"),
    [invalid, fail] = useState("");
  const [demo, selectDemo] = useState("gaussian"),
    [step, slide] = useState(0),
    [name, field] = useState("Height anomaly"),
    [metric, diagnose] = useState("volume_drift"),
    [compare, setCompare] = useState(false);
  const base =
    runner.job?.state === "completed"
      ? "/jobs/" + runner.job.id
      : "/demos/" + demo;
  const info = useData<Info>(base + "/result"),
    i = Math.min(step, (info?.data?.times.length || 1) - 1);
  const [arrows, setArrows] = useState(false),
    [pinned, pin] = useState("");
  const query =
    "/field?step=" +
    i +
    "&name=" +
    encodeURIComponent(name) +
    "&vectors=" +
    arrows;
  const active = useData<Grid>(info?.data ? base + query : null);
  const other = "/demos/" + (demo === "gaussian" ? "rotating" : "gaussian");
  const pairAllowed = base.startsWith("/demos/");
  const pinnedActive = Boolean(pinned && pinned !== base);
  const pair = useData<Grid>(
    info?.data && pinnedActive
      ? pinned +
          "/field?step=0&name=" +
          encodeURIComponent(name) +
          "&at_s=" +
          info.data.times[i] +
          "&vectors=" +
          arrows
      : compare && pairAllowed
        ? other + query
        : null,
  );
  const bounds =
    active?.data && pair?.data
      ? [
          Math.min(extent(active.data)[0], extent(pair.data)[0]),
          Math.max(extent(active.data)[1], extent(pair.data)[1]),
        ]
      : undefined;
  return (
    <>
      <Heading name="Simulation">
        Integrate rotating shallow water and inspect the evolution of mass,
        energy and vorticity.
      </Heading>
      <div className="workbench">
        <aside className="stack">
          <fieldset className="stack">
            <legend>New simulation</legend>
            <Select
              label="Experiment"
              value={preset}
              options={Object.keys(presets?.data || { gaussian_bump: {} })}
              onChange={(p) => {
                choose(p);
                latitude(String(presets?.data?.[p].latitude_deg));
                method(String(presets?.data?.[p].scheme));
                options("{}");
              }}
            />
            <label>
              Latitude (°)
              <input
                type="number"
                min="-90"
                max="90"
                value={lat}
                onChange={(e) => latitude(e.target.value)}
              />
            </label>
            <Select
              label="Transport scheme"
              value={scheme}
              options={["rusanov", "muscl"]}
              onChange={method}
            />
            <details>
              <summary>Solver parameters</summary>
              <label>
                Additional overrides (JSON)
                <textarea
                  value={advanced}
                  onChange={(e) => options(e.target.value)}
                />
              </label>
              <pre>{JSON.stringify(presets?.data?.[preset], null, 2)}</pre>
            </details>
            <button
              className="primary"
              disabled={runner.busy}
              onClick={() => {
                try {
                  const p = JSON.parse(advanced);
                  if (
                    p === null ||
                    Array.isArray(p) ||
                    typeof p !== "object" ||
                    lat === ""
                  )
                    throw Error("Enter valid parameters");
                  fail("");
                  slide(0);
                  runner.submit("/simulations", {
                    preset,
                    parameters: { ...p, latitude_deg: Number(lat), scheme },
                  });
                } catch (e) {
                  fail(String(e));
                }
              }}
            >
              Run simulation
            </button>
            <JobState job={runner.job} cancel={runner.cancel} />
          </fieldset>
          <fieldset className="stack">
            <legend>Precomputed demos</legend>
            {["gaussian", "rotating"].map((d, i) => (
              <button
                key={d}
                disabled={runner.busy}
                onClick={() => {
                  runner.clear();
                  selectDemo(d);
                  slide(0);
                }}
              >
                {i ? "Rotating bump · 45°" : "Gaussian bump · 0°"}
              </button>
            ))}
            {pairAllowed && (
              <label>
                <span>
                  <input
                    type="checkbox"
                    checked={compare}
                    onChange={(e) => setCompare(e.target.checked)}
                  />{" "}
                  Compare 0° and 45°
                </span>
              </label>
            )}
          </fieldset>
        </aside>
        <section className="stack">
          <Notice
            error={
              invalid ||
              runner.error ||
              presets?.error ||
              info?.error ||
              active?.error ||
              pair?.error
            }
          />
          {info?.data && (
            <>
              <div className="panel stack">
                <small>
                  {pairAllowed ? "PRECOMPUTED" : "COMPUTED JOB"} ·{" "}
                  {info.data.metadata.config.nx} ×{" "}
                  {info.data.metadata.config.ny} ·{" "}
                  {info.data.metadata.config.latitude_deg}° ·{" "}
                  {info.data.times[i]} s
                </small>
                <Select
                  label="Scientific field"
                  value={name}
                  options={Object.keys(info.data.fields)}
                  onChange={field}
                />
                <div className="actions">
                  <label>
                    <span>
                      <input
                        type="checkbox"
                        checked={arrows}
                        onChange={(e) => setArrows(e.target.checked)}
                      />{" "}
                      Velocity arrows
                    </span>
                  </label>
                  <button onClick={() => pin(base)}>
                    Pin current run as A
                  </button>
                  {pinned && (
                    <button onClick={() => pin("")}>Clear pinned run</button>
                  )}
                </div>
                <Slider
                  value={i}
                  max={info.data.times.length - 1}
                  onChange={slide}
                />
                <div className="pair">
                  {active?.data && (
                    <MapView
                      g={active.data}
                      bounds={bounds}
                      title={
                        name +
                        " · " +
                        info.data.metadata.config.latitude_deg +
                        "°"
                      }
                    />
                  )}{" "}
                  {pair?.data && (
                    <MapView
                      g={pair.data}
                      bounds={bounds}
                      title={
                        pinnedActive
                          ? name + " · pinned A"
                          : name + " · " + (demo === "gaussian" ? 45 : 0) + "°"
                      }
                    />
                  )}
                </div>
              </div>
              <div className="panel stack">
                <Select
                  label="Diagnostic"
                  value={metric}
                  options={Object.keys(info.data.diagnostics[0])}
                  onChange={diagnose}
                />
                {pinnedActive && (
                  <a className="textlink" href={api + pinned + "/export"}>
                    Download pinned run A
                  </a>
                )}
                <Trace
                  label={metric}
                  x={info.data.times}
                  y={info.data.diagnostics.map((r) => r[metric])}
                />
                <a className="textlink" href={api + base + "/export"}>
                  Download full-resolution results (.zip)
                </a>
              </div>
            </>
          )}
        </section>
      </div>
    </>
  );
}
