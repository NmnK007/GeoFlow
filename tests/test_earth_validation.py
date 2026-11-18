import numpy as np
import pytest

xr = pytest.importorskip("xarray")
from geoflow.earth.data import canonical
from geoflow.earth.diagnostics import fields
from geoflow.earth.fixture import fixture
from geoflow.earth.geo import R
from geoflow.earth.validation import observations, validate


def test_depth_land_mask_and_geostrophy():
    ds = fixture().rename({"u": "uo", "v": "vo"})
    ds = ds.expand_dims(depth=[1.0, 15.0])
    ds["mask"] = (
        ("lat", "lon"),
        np.ones((25, 25)),
        {"standard_name": "sea_binary_mask"},
    )
    ds["mask"].values[5, 5] = 0
    ds["adt"] = ds.sla.copy()
    ds.adt.values[:] = np.radians(ds.lat.values)[None, None, :, None] * R * 1e-8
    result = canonical(ds, (60, 62, 11, 13), "2020-07-01", "2020-07-03", 15.0)
    assert np.isnan(result.u[0, 5, 5])
    assert result.depth.item() == 15.0
    d = fields(result, 0)
    assert d.ug_adt[12, 12].item() == pytest.approx(
        -9.81e-8 / (2 * 7.292115e-5 * np.sin(np.radians(12)))
    )
    assert abs(d.vg_adt[12, 12].item()) < 1e-12
    eq = result.assign_coords(lat=result.lat - 12)
    assert np.isnan(fields(eq, 0).ug_adt).all()


def test_hourly_match_and_termination(tmp_path):
    ds = fixture()
    ds.u.values[:] = 0.0
    ds.v.values[:] = 0.0
    obs = xr.Dataset(
        {
            "ID": ("track", ["a", "b"]),
            "count": ("track", [4, 4], {"sample_dimension": "obs"}),
            "time": (
                "obs",
                np.tile(
                    np.datetime64("2020-07-01") + np.arange(4) * np.timedelta64(1, "h"),
                    2,
                ),
            ),
            "longitude": ("obs", [61.0] * 4 + [68.0] * 4),
            "latitude": ("obs", [12.0] * 8),
            "ve": ("obs", np.zeros(8)),
            "vn": ("obs", np.zeros(8)),
        }
    )
    path = tmp_path / "gdp.nc"
    obs.to_netcdf(path)
    report, rows = validate(ds, observations(path), hours=3)
    assert report["eligible"] == 2 and report["termination_rate"] == 0.5
    metric = report["methods"]["gridded_RK4"]
    assert (
        metric["coverage"] == 0.5
        and metric["rms_m"] == 0
        and metric["by_horizon"]["3"]["count"] == 1
    )
    assert len(rows) > 0
