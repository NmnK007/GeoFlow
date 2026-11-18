"""CF-decoded regional surface or single-level rectilinear datasets."""

import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
import xarray as xr

from .geo import bounds

CATALOG = {
    "glorys": (
        "cmems_mod_glo_phy_my_0.083deg_P1D-m",
        "GLOBAL_MULTIYEAR_PHY_001_030",
        "ocean reanalysis",
    ),
    "duacs": (
        "cmems_obs-sl_glo_phy-ssh_my_allsat-l4-duacs-0.125deg_P1D",
        "SEALEVEL_GLO_PHY_L4_MY_008_047",
        "satellite-derived geostrophic currents",
    ),
}
ALIASES = {
    "u": ("u", "uo", "ugos"),
    "v": ("v", "vo", "vgos"),
    "adt": ("adt",),
    "ssh": ("zos", "ssh"),
    "sla": ("sla",),
}
STANDARD = {
    "u": (
        "eastward_sea_water_velocity",
        "surface_geostrophic_eastward_sea_water_velocity",
    ),
    "v": (
        "northward_sea_water_velocity",
        "surface_geostrophic_northward_sea_water_velocity",
    ),
}


def fingerprint(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical(ds, box, start, end, depth_m=None):
    if len(box) != 4:
        raise ValueError("box requires west, east, south, north")
    west, _east, south, north = box
    width = bounds(*box)
    coords = {}
    for key, names in {
        "lon": ("longitude", "lon"),
        "lat": ("latitude", "lat"),
        "time": ("time",),
        "depth": ("depth",),
    }.items():
        name = next(
            (
                n
                for n in ds.coords
                if n in names or ds[n].attrs.get("standard_name") == names[0]
            ),
            None,
        )
        if name is None:
            if key == "depth":
                continue
            raise ValueError(f"missing {key} coordinate")
        if ds[name].dims != (name,):
            raise ValueError("rectilinear dimension coordinates required")
        if name != key:
            coords[name] = key
    ds = ds.rename(coords)
    if not np.issubdtype(ds.time.dtype, np.datetime64):
        raise ValueError("Gregorian decoded time required")
    for key, expected in (("lon", "east"), ("lat", "north")):
        unit = ds[key].attrs.get("units", "").lower()
        if unit not in (
            "degrees_" + expected,
            "degree_" + expected,
            "degrees_" + expected[0],
            "degrees",
            "degree",
        ):
            raise ValueError(f"unrecognized {key} angular units: {unit}")
    if "depth" in ds.dims:
        if (
            ds.depth.attrs.get("units", "m") not in ("m", "metres", "meters")
            or ds.depth.attrs.get("positive", "down") != "down"
        ):
            raise ValueError("depth must be metres positive down")
        level = float(ds.depth.min()) if depth_m is None else float(depth_m)
        if level not in ds.depth.values:
            raise ValueError("selected depth absent")
        ds = ds.sel(depth=level)
    elif depth_m is not None:
        raise ValueError("dataset has no depth axis")
    lon = west + (ds.lon.values - west) % 360
    ds = ds.assign_coords(lon=lon)
    indices = {}
    for key, lo, hi in (
        ("lon", west, west + width),
        ("lat", south, north),
        ("time", np.datetime64(start), np.datetime64(end)),
    ):
        val = ds[key].values
        idx = np.flatnonzero((val >= lo) & (val <= hi))
        idx = idx[np.argsort(val[idx])]
        if len(idx) < (1 if key == "time" else 2) or np.any(
            val[idx][1:] == val[idx][:-1]
        ):
            raise ValueError(f"empty, insufficient or duplicate {key} coordinates")
        indices[key] = idx
    ds = ds.isel(indices)
    data = {}
    for key, names in ALIASES.items():
        n = next((n for n in names if n in ds), None)
        if n is None:
            n = next(
                (
                    n
                    for n in ds.data_vars
                    if ds[n].attrs.get("standard_name") in STANDARD.get(key, ())
                ),
                None,
            )
        if n is None:
            continue
        arr = ds[n].transpose("time", "lat", "lon")
        if arr.size * 8 * len(ALIASES) > 256 * 2**20:
            raise ValueError("subset exceeds memory budget")
        unit = (
            arr.attrs.get("units", "")
            .lower()
            .replace(" ", "")
            .replace("**", "")
            .replace("^", "")
        )
        factors = (
            {"ms-1": 1, "m/s": 1, "cms-1": 0.01, "cm/s": 0.01}
            if key in ("u", "v")
            else {"m": 1, "cm": 0.01}
        )
        if unit not in factors:
            raise ValueError(f"unsupported units for {n}: {unit}")
        data[key] = (arr.astype(float) * factors[unit]).assign_attrs(
            source_variable=n, units="m/s" if key in ("u", "v") else "m"
        )
    if not {"u", "v"} <= data.keys():
        raise ValueError("paired eastward and northward currents required")
    result = xr.Dataset(data, attrs={k: str(v) for k, v in ds.attrs.items()})
    for variable in ds.data_vars.values():
        kind = variable.attrs.get("standard_name")
        if kind in ("sea_binary_mask", "land_binary_mask"):
            if not set(variable.dims) <= set(result.dims):
                raise ValueError("unsupported land mask dimensions")
            result = result.where(variable == (1 if kind == "sea_binary_mask" else 0))
    result.attrs.setdefault(
        "source_kind",
        {
            "ugos": "satellite-derived geostrophic currents",
            "uo": "external ocean model currents",
        }.get(data["u"].attrs["source_variable"], "imported prescribed currents"),
    )
    result.lon.attrs.update(units="degrees_east", standard_name="longitude")
    result.lat.attrs.update(units="degrees_north", standard_name="latitude")
    return result.load()


def import_region(path, box, start, end, depth_m=None, cache=None):
    path = Path(path)
    digest = fingerprint(path)
    spec = json.dumps(
        {
            "sha256": digest,
            "box": list(box),
            "start": str(start),
            "end": str(end),
            "depth_m": depth_m,
        },
        sort_keys=True,
    )
    dest = (
        Path(cache) / (hashlib.sha256(("earth-1:" + spec).encode()).hexdigest() + ".nc")
        if cache
        else None
    )
    if dest and dest.exists():
        return xr.load_dataset(dest)
    with xr.open_dataset(path) as ds:
        result = canonical(ds, box, start, end, depth_m)
    result.attrs.update(import_spec=spec, source_file=path.name)
    result.attrs.setdefault("license", "Unspecified by source")
    if dest:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=dest.parent, suffix=".nc", delete=False) as f:
            tmp = Path(f.name)
        try:
            result.to_netcdf(tmp)
            tmp.replace(dest)
        finally:
            tmp.unlink(missing_ok=True)
    return result
