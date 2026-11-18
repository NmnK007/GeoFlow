"""Covariant derivatives of physical east and north velocity on a sphere."""

import numpy as np
import xarray as xr

from .geo import R


def fields(ds, index):
    u, v = (ds[n].values[index] for n in ("u", "v"))
    lat = np.radians(ds.lat.values)[:, None]
    lon = np.radians(ds.lon.values)
    if min(u.shape) < 3:
        raise ValueError("derivatives require three cells along each axis")

    def grad(a):
        dx = np.gradient(a, lon, axis=1) / (R * np.cos(lat))
        dy = np.gradient(a, lat[:, 0], axis=0) / R
        # Only centred stencils with valid center and neighbours.
        dx[:, [0, -1]] = np.nan
        dy[[0, -1], :] = np.nan
        return np.where(np.isfinite(a), dx, np.nan), np.where(
            np.isfinite(a), dy, np.nan
        )

    ux, uy = grad(u)
    vx, vy = grad(v)
    ux -= v * np.tan(lat) / R
    vx += u * np.tan(lat) / R
    zeta = vx - uy
    normal, shear = ux - vy, vx + uy
    f = 2 * 7.292115e-5 * np.sin(lat)
    vel = ds[["u", "v"]].where(ds.u.notnull() & ds.v.notnull())
    mean = vel.mean("time", skipna=True)
    result = xr.Dataset(coords={"lat": ds.lat, "lon": ds.lon})

    def add(n, a, unit):
        result[n] = (("lat", "lon"), np.asarray(a), {"units": unit})

    add("speed", np.hypot(u, v), "m/s")
    add(
        "bearing",
        np.where(np.hypot(u, v) > 0, np.degrees(np.arctan2(u, v)) % 360, np.nan),
        "degrees clockwise from north",
    )
    add("ke", 0.5 * (u * u + v * v), "m2/s2")
    add("eke", 0.5 * ((u - mean.u) ** 2 + (v - mean.v) ** 2), "m2/s2")
    for n, a in (
        ("vorticity", zeta),
        ("absolute_vorticity", zeta + f),
        ("divergence", ux + vy),
        ("normal_strain", normal),
        ("shear_strain", shear),
        ("strain", np.hypot(normal, shear)),
    ):
        add(n, a, "1/s")
    add("okubo_weiss", normal**2 + shear**2 - zeta**2, "1/s2")
    for n in ("adt", "sla", "ssh"):
        if n in ds:
            a = ds[n].values[index]
            add(n, a, "m")
            if n in ("adt", "sla"):
                gx, gy = grad(a)
                denom = np.where(abs(lat) >= np.radians(3), f, np.nan)
                add("ug_" + n, -9.81 * gy / denom, "m/s")
                add("vg_" + n, 9.81 * gx / denom, "m/s")
    result.attrs.update(
        time=str(ds.time.values[index]),
        eke_mean="arithmetic valid paired current samples over selected time axis",
    )
    return result
