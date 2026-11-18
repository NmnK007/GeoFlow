import numpy as np
from matplotlib.figure import Figure


def regional_map(ds, d, name, index, tracks=(), eddies=(), records=()):
    fig = Figure(figsize=(7, 5), layout="constrained")
    ax = fig.subplots()
    a = d[name]
    vals = a.values[np.isfinite(a.values)]
    if len(vals) and vals.min() < 0 < vals.max():
        limit = float(abs(vals).max())
        opts = {"cmap": "RdBu_r", "vmin": -limit, "vmax": limit}
    else:
        opts = {"cmap": "viridis"}
    m = ax.pcolormesh(ds.lon, ds.lat, a, shading="auto", **opts)
    fig.colorbar(m, ax=ax, label=f"{name} ({a.attrs['units']})")
    center = float(ds.lon.mean())

    def longitude(x):
        return center + (np.asarray(x) - center + 180) % 360 - 180

    # Local equirectangular projection at the latitude of the panel centre.
    ax.set_aspect(1 / np.cos(np.radians(float(ds.lat.mean()))))
    skip = (
        slice(None, None, max(1, len(ds.lat) // 15)),
        slice(None, None, max(1, len(ds.lon) // 20)),
    )
    x, y = np.meshgrid(ds.lon, ds.lat)
    ax.quiver(
        x[skip],
        y[skip],
        ds.u.values[index][skip],
        ds.v.values[index][skip],
        color="0.25",
    )
    for tr in tracks:
        ax.plot(tr.position[:, 0], tr.position[:, 1], ".-", lw=1)
    for candidate in eddies:
        ax.plot(
            longitude(candidate["longitude"]),
            candidate["latitude"],
            "o",
            mfc="none",
            mec="black",
        )
    if records:
        for ident in sorted({row["ID"] for row in records}):
            subset = [r for r in records if r["ID"] == ident]
            obs = [r for r in subset if r["method"] == "stationary"]
            ax.plot(
                longitude([r["observed_lon"] for r in obs]),
                [r["observed_lat"] for r in obs],
                color="black",
                label=f"{ident} observed",
            )
            for method in (
                "gridded_RK4",
                "constant_initial_observed_velocity",
                "stationary",
            ):
                pts = [r for r in subset if r["method"] == method]
                if pts:
                    ax.plot(
                        longitude([r["longitude"] for r in pts]),
                        [r["latitude"] for r in pts],
                        ".--",
                        label=f"{ident} {method}",
                    )
        ax.legend(fontsize=6)
    ax.set(
        xlabel="Longitude (°E, continuous branch)",
        ylabel="Latitude (°N)",
        title=str(ds.time.values[index])[:19] + " UTC",
    )
    return fig


def separation_plot(report):
    fig = Figure(figsize=(6, 3.6), layout="constrained")
    ax = fig.subplots()
    labels = {
        "gridded_RK4": "Imported currents · RK4",
        "stationary": "Stationary",
        "constant_initial_observed_velocity": "Constant initial velocity",
    }
    for method, summary in report["methods"].items():
        series = summary["by_horizon"]
        y = [
            np.nan if row["mean_m"] is None else row["mean_m"] / 1000
            for row in series.values()
        ]
        ax.plot([int(h) for h in series], y, label=labels[method])
    ax.set(
        xlabel="Integration horizon (hours)",
        ylabel="Mean separation (km)",
        title=f"{report['eligible']} eligible drifter releases",
    )
    ax.legend()
    return fig
