"use client";
import { useState } from "react";
import {
  Grid,
  Heading,
  MapView,
  Notice,
  Select,
  Slider,
  JobState,
  api,
  request,
  useData,
  useJob,
} from "./shared";
type Ocean = {
  sources: string[];
  times: string[];
  fields: Record<string, string>;
  provenance: { title: string; institution: string };
  matches: Record<string, string>[];
  validation: { eligible: number };
};
type Track = { positions: number[][]; status: string; time_s: number[] };
export default function Earth() {
  const [source, setSource] = useState("arabian"),
    runner = useJob(),
    info = useData<Ocean>("/earth?dataset=" + encodeURIComponent(source)),
    [step, slide] = useState(0),
    [field, select] = useState("speed"),
    [lon, setLon] = useState("70.0814"),
    [lat, setLat] = useState("10.539413"),
    [method, setMethod] = useState("rk4"),
    [hours, duration] = useState("24"),
    [track, result] = useState<Track>(),
    [busy, pending] = useState(false),
    [err, fail] = useState(""),
    [id, pick] = useState(""),
    [show, setShow] = useState(false);
  const [ow, threshold] = useState("0"),
    [sla, seaLevel] = useState("0.02"),
    [cells, minCells] = useState("4"),
    [dt, interval] = useState("900"),
    [ensemble, seeds] = useState("");
  const ds = "&dataset=" + encodeURIComponent(source);
  const g = useData<Grid>("/earth/field?step=" + step + "&name=" + field + ds),
    candidates = useData<
      {
        longitude: number;
        latitude: number;
        radius_m: number;
        classification: string;
      }[]
    >(
      show
        ? "/earth/eddies?step=" +
            step +
            ds +
            "&ow=" +
            Number(ow) * 1e-10 +
            "&sla=" +
            sla +
            "&cells=" +
            cells
        : null,
    );
  const points = (info?.data?.matches || []).filter(
    (r) => r.ID === id && r.method === "gridded_RK4",
  );
  const report = useData<{ tracks: Track[] }>(
    runner.job?.state === "completed"
      ? "/jobs/" + runner.job.id + "/result"
      : null,
  );
  const lines = [
    points.map((r) => [+r.observed_lon, +r.observed_lat]),
    points.map((r) => [+r.longitude, +r.latitude]),
    track?.positions || [],
    ...(report?.data?.tracks || []).map((t) => t.positions),
  ];
  return (
    <>
      <Heading name="Earth">
        Explore Arabian Sea altimetry and compare observed drifters with
        trajectories integrated through gridded surface currents.
      </Heading>
      <div className="workbench">
        <aside className="stack">
          <fieldset className="stack">
            <legend>Regional dataset</legend>
            <Select
              label="Current source"
              value={source}
              options={info?.data?.sources || [source]}
              onChange={(v) => {
                setSource(v);
                slide(0);
                result(undefined);
                runner.clear();
                pick("");
                select("speed");
                setLon(v === "fixture" ? "61" : "70.0814");
                setLat(v === "fixture" ? "12" : "10.539413");
              }}
            />
            <Select
              label="Ocean field"
              options={Object.keys(info?.data?.fields || { speed: "" })}
              value={field}
              onChange={select}
            />
            <Slider
              max={(info?.data?.times.length || 1) - 1}
              value={step}
              onChange={slide}
            />
            <Select
              label="Historical drifter"
              options={[
                "",
                ...new Set(info?.data?.matches.map((x) => x.ID) || []),
              ]}
              value={id}
              onChange={pick}
            />
            <label>
              <span>
                <input
                  type="checkbox"
                  checked={show}
                  onChange={(e) => setShow(e.target.checked)}
                />{" "}
                Eddy candidates
              </span>
            </label>
            {show && (
              <>
                <label>
                  OW ceiling (10⁻¹⁰ s⁻²)
                  <input
                    type="number"
                    max="0"
                    value={ow}
                    onChange={(e) => threshold(e.target.value)}
                  />
                </label>
                <label>
                  Minimum |SLA| (m)
                  <input
                    type="number"
                    value={sla}
                    onChange={(e) => seaLevel(e.target.value)}
                  />
                </label>
                <label>
                  Minimum cells
                  <input
                    type="number"
                    value={cells}
                    onChange={(e) => minCells(e.target.value)}
                  />
                </label>
              </>
            )}
          </fieldset>
          <fieldset className="stack">
            <legend>New particle release</legend>
            <label>
              Longitude (°E)
              <input
                type="number"
                value={lon}
                onChange={(e) => setLon(e.target.value)}
              />
            </label>
            <label>
              Latitude (°N)
              <input
                type="number"
                value={lat}
                onChange={(e) => setLat(e.target.value)}
              />
            </label>
            <label>
              Integration duration (hours)
              <input
                type="number"
                value={hours}
                onChange={(e) => duration(e.target.value)}
              />
            </label>
            <Select
              label="Integrator"
              value={method}
              onChange={setMethod}
              options={["rk4", "euler"]}
            />
            <button
              disabled={busy}
              className="primary"
              onClick={async () => {
                pending(true);
                fail("");
                try {
                  result(
                    await request<Track>("/earth/tracks", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        dataset: source,
                        longitude: +lon,
                        latitude: +lat,
                        start: step,
                        hours: +hours,
                        dt_s: +dt,
                        method,
                      }),
                    }),
                  );
                } catch (e) {
                  fail(String(e));
                } finally {
                  pending(false);
                }
              }}
            >
              Integrate particle
            </button>
            <details>
              <summary>Ensemble and analysis export</summary>
              <div className="stack">
                <label>
                  Time step (s)
                  <input
                    type="number"
                    value={dt}
                    onChange={(e) => interval(e.target.value)}
                  />
                </label>
                <label>
                  Additional release locations (longitude, latitude per line)
                  <textarea
                    value={ensemble}
                    onChange={(e) => seeds(e.target.value)}
                  />
                </label>
                <button
                  disabled={runner.busy}
                  onClick={() =>
                    runner.submit("/earth/analyses", {
                      dataset: source,
                      start: step,
                      hours: +hours,
                      dt_s: +dt,
                      method,
                      ow: +ow * 1e-10,
                      sla: +sla,
                      cells: +cells,
                      releases: [
                        [+lon, +lat],
                        ...ensemble
                          .split("\n")
                          .filter((s) => s.trim())
                          .map((s) => s.split(",").map(Number)),
                      ],
                    })
                  }
                >
                  Compute analysis archive
                </button>
                <JobState job={runner.job} cancel={runner.cancel} />
                {report?.data && (
                  <a
                    className="textlink"
                    href={api + "/jobs/" + runner.job?.id + "/export"}
                  >
                    Download regional analysis
                  </a>
                )}
              </div>
            </details>
          </fieldset>
        </aside>
        <section className="stack">
          <Notice
            error={
              err ||
              runner.error ||
              report?.error ||
              info?.error ||
              g?.error ||
              candidates?.error
            }
          />
          <div className="panel stack">
            <small>
              {source === "fixture"
                ? "SYNTHETIC VERIFICATION"
                : source === "arabian"
                  ? "HISTORICAL DATA"
                  : "REGISTERED DATASET"}{" "}
              · {info?.data?.times[step]?.slice(0, 10)} UTC
            </small>
            {!g && <p role="status">Loading regional currents…</p>}
              {g?.data && <MapView g={g.data} lines={lines} />}
            <p>
              Dark cells indicate missing measurements.{" "}
              {id &&
                "White: observed GDP drifter. Orange: archived RK4 trajectory."}{" "}
              {track && "Blue: new particle, " + track.status + "."}
            </p>
            {track && (
              <details>
                <summary>
                  Integrated trajectory ({track.positions.length} points)
                </summary>
                <pre>{JSON.stringify(track, null, 2)}</pre>
              </details>
            )}
            {show && candidates?.data && (
              <details open>
                <summary>{candidates.data.length} eddy candidates</summary>
                <div className="scroll">
                  <table>
                    <tbody>
                      {candidates.data.map((r, i) => (
                        <tr key={i}>
                          <td>{r.classification}</td>
                          <td>{r.longitude.toFixed(2)}°E</td>
                          <td>{r.latitude.toFixed(2)}°N</td>
                          <td>{(r.radius_m / 1000).toFixed(1)} km</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}
          </div>
          <div className="panel stack">
            <h2>Source and coverage</h2>
            <p>
              {info?.data?.provenance.title}.{" "}
              {info?.data?.provenance.institution}.{" "}
              {source === "arabian" &&
                "Observations from NOAA Global Drifter Program. Two eligible drifters, including one with prior drogue loss. Surface geostrophic currents omit wind-driven drift."}
            </p>
            <details>
              <summary>Scientific metadata</summary>
              <pre>{JSON.stringify(info?.data?.provenance, null, 2)}</pre>
            </details>
            {source === "arabian" && (
              <a className="textlink" href={api + "/earth/export"}>
                Download regional NetCDF
              </a>
            )}
          </div>
        </section>
      </div>
    </>
  );
}
