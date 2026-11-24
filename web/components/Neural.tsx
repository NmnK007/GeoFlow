"use client";
import { useState } from "react";
import {
  Grid,
  Trace,
  Heading,
  JobState,
  MapView,
  Notice,
  Select,
  Slider,
  api,
  extent,
  useData,
  useJob,
} from "./shared";
type Models = Record<
  string,
  {
    live: boolean;
    run: {
      fingerprint: string;
      parameters: number;
      architecture: Record<string, string | number>;
      groups: { id: { horizons: Record<string, { relative_l2: number }> } };
    };
  }
>;
export default function Neural() {
  const [kind, model] = useState("fno"),
    [step, slide] = useState(24),
    [channel, field] = useState("Depth"),
    [group, choose] = useState("id"),
    [member, seed] = useState("0");
  const info = useData<Models>("/models"),
    runner = useJob(),
    live = runner.job?.state === "completed",
    base = live ? "/jobs/" + runner.job?.id : "/models/" + kind;
  const pair = useData<Grid[]>(
    base +
      "/comparison?step=" +
      step +
      "&channel=" +
      ["Depth", "East velocity", "North velocity"].indexOf(channel),
  );
  const details = useData<{
      times: number[];
      diagnostics: {
        relative_l2: number;
        mass_drift: number;
        energy_drift: number;
        rmse: number[];
      }[];
      history: { epoch: number; validation: number }[];
    }>(base + "/result"),
    [diagnostic, setDiag] = useState("relative_l2"),
    [showError, toggle] = useState(false);
  const errGrid =
    pair?.data && showError
      ? {
          ...pair.data[1],
          values: pair.data[1].values.map((r, y) =>
            r.map((v, x) => (v ?? 0) - (pair.data![0].values[y][x] ?? 0)),
          ),
        }
      : undefined;
  const row = info?.data?.[kind]?.run,
    ranges = pair?.data?.map(extent),
    bounds = ranges
      ? [
          Math.min(...ranges.map((v) => v[0])),
          Math.max(...ranges.map((v) => v[1])),
        ]
      : undefined;
  return (
    <>
      <Heading name="Neural">
        Compare learned forecasts with the MUSCL–MC trajectory on the same
        periodic grid.
      </Heading>
      <div className="workbench">
        <aside className="stack">
          <fieldset className="stack" disabled={runner.busy}>
            <legend>Operator comparison</legend>
            <Select
              label="Model"
              value={kind}
              options={["fno", "cnn"]}
              onChange={(k) => {
                model(k);
                runner.clear();
              }}
            />
            <Select
              label="Prediction field"
              value={channel}
              options={["Depth", "East velocity", "North velocity"]}
              onChange={field}
            />
            <Slider max={24} value={step} onChange={slide} />
            <button onClick={() => runner.clear()}>
              Show precomputed case
            </button>
          </fieldset>
          <fieldset className="stack" disabled={runner.busy}>
            <legend>New CPU inference</legend>
            <Select
              label="Test distribution"
              options={["id", "amplitude", "position", "rotation"]}
              value={group}
              onChange={choose}
            />
            <Select
              label="Trajectory member"
              options={["0", "1", "2"]}
              value={member}
              onChange={seed}
            />
            <button
              className="primary"
              disabled={!info?.data?.[kind]?.live}
              onClick={() =>
                runner.submit("/inference", {
                  model: kind,
                  group,
                  member: +member,
                })
              }
            >
              Run inference
            </button>
            {info?.data && !info.data[kind].live && (
              <small>Fresh inference requires the local v0.5 study.</small>
            )}
          </fieldset>
          <JobState job={runner.job} cancel={runner.cancel} />
        </aside>
        <section className="stack">
          <Notice error={info?.error || pair?.error || runner.error} />
          <div className="panel stack">
            <small>
              {live ? "COMPUTED JOB" : "PRECOMPUTED · FIRST FAMILIAR CASE"} · 16
              × 16 · {step * 240} s
            </small>
            <div className="pair">
              {pair?.data?.map((g, i) => (
                <MapView
                  key={i}
                  title={i ? kind.toUpperCase() : "MUSCL–MC reference"}
                  g={g}
                  bounds={bounds}
                />
              ))}
            </div>
            <label>
              <span>
                <input
                  type="checkbox"
                  checked={showError}
                  onChange={(e) => toggle(e.target.checked)}
                />{" "}
                Show prediction error
              </span>
            </label>
            {errGrid && (
              <MapView g={errGrid} title="Prediction minus reference" />
            )}
            <p>
              Both fields share one colour scale. Predictions advance without
              observations after initialization.
            </p>
            <a className="textlink" href={api + base + "/export"}>
              Download paired trajectory
            </a>
          </div>
          {details?.data && (
            <div className="panel stack">
              <Select
                label="Rollout diagnostic"
                value={diagnostic}
                options={[
                  "relative_l2",
                  "mass_drift",
                  "energy_drift",
                  "field_rmse",
                ]}
                onChange={setDiag}
              />
              <Trace
                label={diagnostic}
                x={details.data.times}
                y={details.data.diagnostics.map((d) =>
                  diagnostic === "field_rmse"
                    ? d.rmse[
                        ["Depth", "East velocity", "North velocity"].indexOf(
                          channel,
                        )
                      ]
                    : d[
                        diagnostic as
                          "relative_l2" | "energy_drift" | "mass_drift"
                      ],
                )}
              />
              <details>
                <summary>Validation loss by epoch</summary>
                <pre>{JSON.stringify(details.data.history, null, 2)}</pre>
              </details>
            </div>
          )}
          {row && (
            <div className="panel stack">
              <h2>Training record</h2>
              <p>
                {row.parameters.toLocaleString()} parameters · width{" "}
                {row.architecture.width} · depth {row.architecture.depth} · 24
                training trajectories · seed 11
              </p>
              <p>
                Mean familiar-case relative L2 at 96 min ·{" "}
                {row.groups.id.horizons["24"].relative_l2.toFixed(3)}
              </p>
              <details>
                <summary>Dataset fingerprint</summary>
                <pre>{row.fingerprint}</pre>
              </details>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
