"""Create the browser benchmark's synthetic 256² map and operator registry."""

import json
from pathlib import Path

import numpy as np
import xarray as xr


def main():
    out = Path("outputs/beta-v07").resolve()
    out.mkdir(parents=True, exist_ok=True)
    axis = np.linspace(0, 2, 256)
    x, y = np.meshgrid(axis, axis)
    ds = xr.Dataset(
        coords={
            "lon": 60 + axis,
            "lat": 11 + axis,
            "time": np.array(["2020-07-01", "2020-07-02"], dtype="datetime64[D]"),
        }
    )
    ds.lon.attrs["units"] = "degrees_east"
    ds.lat.attrs["units"] = "degrees_north"
    for name, a in (("u", np.sin(x) * np.cos(y)), ("v", np.cos(x) * np.sin(y))):
        ds[name] = (("time", "lat", "lon"), np.stack([a, a]), {"units": "m/s"})
    region = out / "synthetic-map.nc"
    ds.to_netcdf(region)
    spec = {
        "path": str(region),
        "start": "2020-07-01",
        "end": "2020-07-02",
        "box": [60, 62, 11, 13],
    }
    (out / "registry.json").write_text(json.dumps({"benchmark": spec}))


if __name__ == "__main__":
    main()
