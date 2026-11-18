import numpy as np
import pytest

pytest.importorskip("xarray")
from geoflow.earth.data import import_region
from geoflow.earth.fixture import fixture
from geoflow.earth.geo import R, distance, wrap


def test_spherical_seam():
    assert distance(179, 0, -179, 0) == pytest.approx(R * np.radians(2))
    assert wrap(181) == -179


def test_cf_subset_and_cache(tmp_path):
    ds = fixture().rename({"lon": "longitude", "lat": "latitude", "u": "uo", "v": "vo"})
    ds = ds.assign_coords(longitude=np.linspace(179, 181, 25) % 360)
    ds.longitude.attrs["units"] = "degrees_east"
    ds["uo"] *= 100
    ds.uo.attrs["units"] = "cm/s"
    path = tmp_path / "test.nc"
    ds.to_netcdf(path)
    args = (path, (179, -179, 11, 13), "2020-07-01", "2020-07-02")
    a = import_region(*args, cache=tmp_path / "cache")
    b = import_region(*args, cache=tmp_path / "cache")
    assert a.identical(b) and a.sizes["time"] == 5
    np.testing.assert_allclose(a.u, ds.uo.values[:5] / 100)
