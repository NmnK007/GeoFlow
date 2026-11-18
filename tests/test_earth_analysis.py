import numpy as np
import pytest

pytest.importorskip("xarray")
from geoflow.earth.diagnostics import fields
from geoflow.earth.eddies import candidates
from geoflow.earth.fixture import fixture
from geoflow.earth.validation import constant_position, summary


def test_candidates_and_threshold():
    d = fields(fixture(), 0)
    (a,) = candidates(d)
    assert a["classification"] == "cyclonic candidate" and a[
        "longitude"
    ] == pytest.approx(61, abs=0.001)
    assert a["area_m2"] == pytest.approx(np.pi * a["radius_m"] ** 2)
    assert not candidates(d, ow_threshold=-1)
    south = d.assign_coords(lat=-d.lat[::-1].values)
    south["vorticity"] = -south.vorticity
    assert candidates(south)[0]["classification"] == "cyclonic candidate"


def test_metrics():
    assert summary([3.0, 4.0])["rms_m"] == pytest.approx(np.sqrt(12.5))
    x, y = constant_position(179.99, 0, 1, 0, np.array([0, 3600]))
    assert x[1] < -179 and y[1] == 0
