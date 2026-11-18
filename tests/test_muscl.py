import numpy as np
import pytest

from geoflow.config import Config
from geoflow.muscl import slope
from geoflow.solver import run_simulation


@pytest.mark.parametrize(
    "limiter,expected", [("mc", [1.5, 0, -1.5]), ("minmod", [1, 0, -1])]
)
def test_limiter(limiter, expected):
    np.testing.assert_equal(
        slope(np.array([1, 2, -1]), np.array([2, -3, -2]), limiter), expected
    )


@pytest.mark.parametrize("boundary", ["wall", "periodic"])
def test_muscl_volume(boundary):
    r = run_simulation(
        Config(nx=17, ny=13, scheme="muscl", boundary_y=boundary, latitude_deg=45)
    )
    assert r.h.min() > 0 and max(row["volume_drift"] for row in r.diagnostics) < 1e-12
