"use client";
import { useEffect, useRef, useState } from "react";
export const api = "/api/v1";
export type Grid = {
  vectors?: number[][] | null;
  values: (number | null)[][];
  x: number[];
  y: number[];
  axes: string[];
  unit: string;
  name: string;
};
export type Job = {
  id: string;
  state: string;
  progress: number;
  error: string | null;
};
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(api + path, init);
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    throw Error(
      typeof e.detail === "string"
        ? e.detail
        : "Request failed (" +
            r.status +
            "). Check parameters and API availability.",
    );
  }
  return r.json();
}
export function useData<T>(path: string | null) {
  const [state, set] = useState<{ path: string; data?: T; error?: string }>();
  useEffect(() => {
    if (!path) return;
    const c = new AbortController();
    request<T>(path, { signal: c.signal })
      .then((data) => set({ path, data }))
      .catch((e) => {
        if (!c.signal.aborted) set({ path, error: e.message });
      });
    return () => c.abort();
  }, [path]);
  return state?.path === path ? state : undefined;
}
export function useJob() {
  const [job, set] = useState<Job | null>(null),
    [error, err] = useState(""),
    [sending, send] = useState(false);
  const busy = sending || job?.state === "running" || job?.state === "queued";
  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.state)) return;
    const c = new AbortController();
    const timer = setTimeout(() => {
      request<Job>("/jobs/" + job.id, { signal: c.signal })
        .then(set)
        .catch((e) => {
          if (!c.signal.aborted) {
            err(e.message);
            set(null);
          }
        });
    }, 160);
    return () => {
      clearTimeout(timer);
      c.abort();
    };
  }, [job]);
  async function submit(path: string, body: unknown) {
    err("");
    send(true);
    try {
      set(
        await request<Job>(path, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }),
      );
    } catch (e) {
      err(String(e));
    } finally {
      send(false);
    }
  }
  async function cancel() {
    if (job)
      try {
        set(await request<Job>("/jobs/" + job.id, { method: "DELETE" }));
      } catch (e) {
        err(String(e));
      }
  }
  return {
    job,
    busy,
    error: error || job?.error,
    submit,
    cancel,
    clear: () => set(null),
  };
}
export function Notice({ error }: { error?: string | null }) {
  return error ? (
    <p role="alert" className="error">
      {error}
    </p>
  ) : null;
}
export function JobState({
  job,
  cancel,
}: {
  job: Job | null;
  cancel: () => void;
}) {
  return job ? (
    <div role="status" className="meta">
      Job {job.state} · {Math.round(job.progress * 100)}%{" "}
      {["running", "queued"].includes(job.state) && (
        <button onClick={cancel}>Cancel</button>
      )}
    </div>
  ) : null;
}
export function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => (
          <option key={o}>{o}</option>
        ))}
      </select>
    </label>
  );
}
export function Slider({
  value,
  max,
  onChange,
}: {
  value: number;
  max: number;
  onChange: (v: number) => void;
}) {
  return (
    <label>
      Output frame · {value} / {max}
      <input
        type="range"
        min={0}
        max={max}
        value={value}
        onChange={(e) => onChange(+e.target.value)}
      />
    </label>
  );
}
export function Heading({
  name,
  children,
}: {
  name: string;
  children: React.ReactNode;
}) {
  return (
    <>
      <h1>{name} Laboratory</h1>
      <p className="intro">{children}</p>
    </>
  );
}
export function extent(g: Grid) {
  let lo = Infinity,
    hi = -Infinity;
  for (const row of g.values)
    for (const v of row)
      if (v !== null) {
        lo = Math.min(lo, v);
        hi = Math.max(hi, v);
      }
  return [lo, hi] as const;
}
const viridis = [
  [68, 1, 84],
  [59, 82, 139],
  [33, 145, 140],
  [94, 201, 98],
  [253, 231, 37],
];
const diverging = [
  [48, 104, 161],
  [229, 236, 231],
  [166, 63, 52],
];
export function MapView({
  g,
  bounds,
  title,
  lines,
}: {
  g: Grid;
  bounds?: number[];
  title?: string;
  lines?: number[][][];
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [hover, setHover] = useState("");
  let [lo, hi] = bounds || extent(g);
  const signed = lo < 0 && hi > 0;
  if (signed) {
    hi = Math.max(-lo, hi);
    lo = -hi;
  }
  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const start = performance.now();
    const w = g.x.length,
      h = g.y.length;
    c.width = w;
    c.height = h;
    const im = ctx.createImageData(w, h),
      colors = signed ? diverging : viridis;
    for (let y = 0; y < h; y++)
      for (let x = 0; x < w; x++) {
        const v = g.values[h - 1 - y][x],
          i = (y * w + x) * 4;
        const t =
          Math.min(1, Math.max(0, ((v ?? lo) - lo) / (hi - lo || 1))) *
          (colors.length - 1);
        const k = Math.min(Math.floor(t), colors.length - 2);
        for (let j = 0; j < 3; j++)
          im.data[i + j] =
            v === null
              ? 20
              : colors[k][j] + (colors[k + 1][j] - colors[k][j]) * (t - k);
        im.data[i + 3] = 255;
      }
    ctx.putImageData(im, 0, 0);
    const shades = ["white", "#ff9b4a", "#81dcff", "#ff8fc9"];
    lines?.forEach((line, i) => {
      ctx.beginPath();
      ctx.strokeStyle = shades[i % shades.length];
      ctx.lineWidth = 0.65;
      line.forEach(([a, b], j) => {
        const x = ((a - g.x[0]) / (g.x[w - 1] - g.x[0])) * (w - 1) + 0.5,
          y = ((g.y[h - 1] - b) / (g.y[h - 1] - g.y[0])) * (h - 1) + 0.5;
        if (!j) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    });
    if (g.vectors) {
      const mx = Math.max(
        1e-12,
        ...g.vectors.map(([, , u, v]) => Math.hypot(u, v)),
      );
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 0.45;
      for (const [ix, iy, u, v] of g.vectors) {
        const dx = u / (g.x[1] - g.x[0]),
          dy = -v / (g.y[1] - g.y[0]),
          a = Math.atan2(dy, dx),
          len = ((Math.hypot(u, v) / mx) * Math.max(w, h)) / 19;
        if (len < 0.15) continue;
        const x = ix + 0.5,
          y = h - iy - 0.5,
          ex = x + len * Math.cos(a),
          ey = y + len * Math.sin(a);
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(ex, ey);
        for (const angle of [-0.5, 0.5]) {
          ctx.moveTo(ex, ey);
          ctx.lineTo(
            ex - 0.35 * len * Math.cos(a + angle),
            ey - 0.35 * len * Math.sin(a + angle),
          );
        }
        ctx.stroke();
      }
    }
    c.dataset.drawMs = String(performance.now() - start);
  }, [g, lo, hi, signed, lines]);
  return (
    <figure className="map stack">
      <h3>
        {title || g.name} · {g.unit}
      </h3>
      <canvas
        aria-label={(title || g.name) + " field"}
        ref={canvas}
        style={{
          aspectRatio: String(
            Math.abs(
              ((g.x[1] - g.x[0]) * g.x.length) /
                ((g.y[1] - g.y[0]) * g.y.length),
            ),
          ),
          height: "auto",
          maxHeight: "none",
        }}
        onPointerLeave={() => setHover("")}
        onPointerMove={(e) => {
          const b = e.currentTarget.getBoundingClientRect();
          const x = Math.min(
            g.x.length - 1,
            Math.max(
              0,
              Math.floor(((e.clientX - b.left) / b.width) * g.x.length),
            ),
          );
          const y =
            g.y.length -
            1 -
            Math.min(
              g.y.length - 1,
              Math.max(
                0,
                Math.floor(((e.clientY - b.top) / b.height) * g.y.length),
              ),
            );
          setHover(
            g.x[x].toPrecision(5) +
              ", " +
              g.y[y].toPrecision(5) +
              " · " +
              (g.values[y][x]?.toPrecision(5) ?? "masked") +
              " " +
              g.unit,
          );
        }}
      />
      <div>
        <div className={"legend " + (signed ? "signed" : "")} />
        <div className="scale meta">
          <span>{lo.toPrecision(4)}</span>
          <span>
            {hi.toPrecision(4)} {g.unit}
          </span>
        </div>
      </div>
      <figcaption>
        {g.axes[0]} {g.x[0].toPrecision(4)} … {g.x.at(-1)?.toPrecision(4)} ·{" "}
        {g.axes[1]} {g.y[0].toPrecision(4)} … {g.y.at(-1)?.toPrecision(4)}
        <br />
        {hover || g.x.length + " × " + g.y.length + " cell centers"}
      </figcaption>
    </figure>
  );
}
export function Trace({
  x,
  y,
  label,
}: {
  x: number[];
  y: (number | null)[];
  label: string;
}) {
  const pairs = x
    .map((a, i) => [a, y[i]] as const)
    .filter((p): p is readonly [number, number] => typeof p[1] === "number");
  if (!pairs.length) return <p>{label} unavailable</p>;
  const lo = Math.min(...pairs.map((p) => p[1])),
    hi = Math.max(...pairs.map((p) => p[1]));
  const points = pairs
    .map(([a, b]) =>
      [
        5 + (490 * (a - x[0])) / (x[x.length - 1] - x[0] || 1),
        95 - (85 * (b - lo)) / (hi - lo || 1),
      ].join(","),
    )
    .join(" ");
  return (
    <figure>
      <h3>{label}</h3>
      <svg
        className="chart"
        viewBox="0 0 500 100"
        preserveAspectRatio="none"
        role="img"
        aria-label={label}
      >
        <polyline
          points={points}
          fill="none"
          stroke="#b4ed99"
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <figcaption>
        {x[0]} – {x.at(-1)} s · range {lo.toPrecision(4)} to {hi.toPrecision(4)}
      </figcaption>
    </figure>
  );
}
