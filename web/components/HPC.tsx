"use client";
import { useState } from "react";
import {
  Grid,
  MapView,
  extent,
  Heading,
  Notice,
  Select,
  api,
  useData,
} from "./shared";
type R = {
  run: string;
  grid: number;
  method: string;
  device: string;
  median_ms: number;
  sd_ms: number;
  peak_mib: number;
  parameters: number;
  groups: Record<
    string,
    {
      horizons: Record<
        string,
        { relative_l2: number; abs_mass: number; abs_energy: number }
      >;
    }
  >;
};
export default function HPC() {
  const data = useData<{ runs: R[] }>("/benchmarks"),
    [grid, change] = useState("64"),
    [method, pick] = useState("all"),
    [device, hardware] = useState("all"),
    [group, dist] = useState("id"),
    [step, time] = useState("24"),
    [stat, metric] = useState("Rollout (ms)");
  const all = data?.data?.runs || [];
  const rows = all.filter(
    (r) =>
      r.grid === +grid &&
      (method === "all" || r.method === method) &&
      (device === "all" || r.device === device),
  );
  function value(r: R) {
    return stat === "Rollout (ms)"
      ? r.median_ms
      : stat === "Peak RSS (MiB)"
        ? r.peak_mib
        : r.groups[group].horizons[step].relative_l2;
  }
  const [inspect, setInspect] = useState("");
  const selected = rows.some((r) => r.run === inspect) ? inspect : "";
  const pair = useData<Grid[]>(
    selected ? "/benchmarks/" + selected + "/comparison?step=" + step : null,
  );
  const limits = pair?.data?.map(extent),
    bounds = limits
      ? [
          Math.min(...limits.map((x) => x[0])),
          Math.max(...limits.map((x) => x[1])),
        ]
      : undefined;
  const max = Math.max(...rows.map(value), 1e-12);
  return (
    <>
      <Heading name="HPC">
        Explore measured speed, memory and accuracy across matched 96-minute
        rollouts.
      </Heading>
      <div className="workbench">
        <aside className="panel stack">
          <Select
            label="Grid width"
            options={["16", "32", "64"]}
            value={grid}
            onChange={change}
          />
          <Select
            label="Method"
            value={method}
            options={["all", ...new Set(all.map((r) => r.method))]}
            onChange={pick}
          />
          <Select
            label="Device"
            value={device}
            options={["all", "cpu", "cuda"]}
            onChange={hardware}
          />
          <Select
            label="Test distribution"
            value={group}
            options={["id", "amplitude", "position", "rotation"]}
            onChange={dist}
          />
          <Select
            label="Accuracy horizon (steps)"
            options={["1", "4", "16", "24"]}
            value={step}
            onChange={time}
          />
          <Select
            label="Plot metric"
            value={stat}
            options={["Rollout (ms)", "Peak RSS (MiB)", "Relative L2"]}
            onChange={metric}
          />
        </aside>
        <section className="stack">
          <Notice error={data?.error} />
          <div className="panel stack">
            <small>PRECOMPUTED · V0.5 SCALING STUDY</small>
            <h2>{stat}</h2>
            {!rows.length && <p>No matching measurements.</p>}
            {rows.map((r) => (
              <div key={r.run}>
                <small>
                  {r.run} · {value(r).toPrecision(4)}
                </small>
                <div
                  style={{
                    width: (100 * value(r)) / max + "%",
                    height: 5,
                    background: r.device === "cuda" ? "#97b8e6" : "#9cd49b",
                  }}
                />
              </div>
            ))}
          </div>
          <div className="panel stack">
            <h2>Accuracy versus runtime</h2>
            <svg
              viewBox="0 0 500 180"
              role="img"
              aria-label="Relative L2 error against warm rollout time"
            >
              <path d="M35 10 V150 H485" fill="none" stroke="#81988a" />
              {rows.map((r) => {
                const costs = rows.map((q) => Math.log10(q.median_ms));
                const x =
                  40 +
                  (430 * (Math.log10(r.median_ms) - Math.min(...costs))) /
                    (Math.max(...costs) - Math.min(...costs) || 1);
                const y =
                  145 -
                  (130 * r.groups[group].horizons[step].relative_l2) /
                    (Math.max(
                      ...rows.map(
                        (q) => q.groups[group].horizons[step].relative_l2,
                      ),
                    ) || 1);
                return (
                  <circle
                    key={r.run}
                    cx={x}
                    cy={y}
                    r={4}
                    fill={r.device === "cuda" ? "#97b8e6" : "#9cd49b"}
                  >
                    <title>
                      {r.run}: {r.median_ms.toPrecision(4)} ms, relative L2{" "}
                      {r.groups[group].horizons[step].relative_l2.toPrecision(
                        4,
                      )}
                    </title>
                  </circle>
                );
              })}
              <text x="200" y="176" fill="#adc0af" fontSize="11">
                Warm rollout (ms, log scale)
              </text>
            </svg>
            <small>
              Vertical axis: relative L2 (zero at bottom). Green: CPU. Blue:
              GPU. Hover for exact values.
            </small>
          </div>
          <div className="panel stack scroll">
            <h2>Accuracy and conservation</h2>
            <table>
              <thead>
                <tr>
                  {[
                    "Run",
                    "Warm ms",
                    "RSS MiB",
                    "Rel. L2",
                    "|ΔM/M₀|",
                    "|ΔE/E₀|",
                  ].map((s) => (
                    <th key={s}>{s}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.run}>
                    <td>{r.run}</td>
                    {[
                      r.median_ms,
                      r.peak_mib,
                      r.groups[group].horizons[step].relative_l2,
                      r.groups[group].horizons[step].abs_mass,
                      r.groups[group].horizons[step].abs_energy,
                    ].map((v, i) => (
                      <td key={i}>{v.toPrecision(3)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <p>
              Warm timing covers the full trajectory. Accuracy is evaluated
              against the target-grid MUSCL–MC reference. Paired CPU/GPU rows
              share weights and Torch build.
            </p>
            <a
              className="textlink"
              href={api + "/benchmarks"}
              download="hpc-results.json"
            >
              Export benchmark report
            </a>
          </div>
          <div className="panel stack">
            <Select
              label="Inspect a benchmark trajectory"
              value={selected}
              options={["", ...rows.map((r) => r.run)]}
              onChange={setInspect}
            />
            <Notice error={pair?.error} />
            {pair?.data && (
              <div className="pair">
                {pair.data.map((g, i) => (
                  <MapView
                    key={i}
                    g={g}
                    bounds={bounds}
                    title={i ? "Prediction" : "MUSCL–MC"}
                  />
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </>
  );
}
