"""Analytical verification fixture on an Indian Ocean coordinate grid."""

import numpy as np
import xarray as xr

from .geo import R


def fixture():
    lon = np.linspace(60, 62, 25)
    lat = np.linspace(11, 13, 25)
    x, y = np.meshgrid(
        R * np.radians(lon - 61) * np.cos(np.radians(12)), R * np.radians(lat - 12)
    )
    shape = np.exp(-(x * x + y * y) / (2 * 40000**2))
    time = np.datetime64("2020-07-01") + np.arange(13) * np.timedelta64(6, "h")
    factor = np.linspace(1, 1.1, len(time))[:, None, None]
    ds = xr.Dataset(
        coords={"lon": lon, "lat": lat, "time": time},
        attrs={
            "title": "Synthetic Gaussian vortex verification fixture",
            "source_kind": "synthetic",
            "license": "Generated analytical test field",
        },
    )
    for key, arr, unit in (
        ("u", -y * shape * 1e-5, "m/s"),
        ("v", x * shape * 1e-5, "m/s"),
        ("sla", -0.1 * shape, "m"),
    ):
        ds[key] = (("time", "lat", "lon"), factor * arr, {"units": unit})
    ds.lon.attrs["units"] = "degrees_east"
    ds.lat.attrs["units"] = "degrees_north"
    return ds
