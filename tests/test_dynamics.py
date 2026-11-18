from dataclasses import replace

import numpy as np
import pytest

from geoflow.comparison import common_times, export_comparison, frame
from geoflow.config import Config
from geoflow.physics import rotate
from geoflow.solver import advance, run_simulation


@pytest.mark.parametrize(
    "invalid",
    [
        {"plane": "beta"},
        {"reduced_gravity_m_s2": -1},
        {"experiment": "kelvin"},
        {"experiment": "rossby"},
        {"experiment": "poincare", "boundary_y": "wall"},
    ],
)
def test_incompatible_physics(invalid):
    with pytest.raises(ValueError):
        Config(**invalid)


def test_rotation_rows():
    c = Config(plane="beta", boundary_y="wall", latitude_deg=45, ny=4, nx=3)
    q = np.zeros((3, 4, 3))
    q[:2] = 1
    rotated = rotate(q, c.rotation * 100)
    assert np.all(np.diff(rotated[2, :, 0]) < 0)
    np.testing.assert_allclose(np.hypot(rotated[1], rotated[2]), 1.0)


def test_stage_retry_preserves_input():
    c = Config(scheme="muscl", nx=4, ny=4, lx_m=100, ly_m=100)
    q = np.zeros((3, 4, 4))
    q[0] = 100
    result, dt, rejected = advance(q, c, 0.0, 1.0)
    assert rejected > 0 and dt < 1.0
    np.testing.assert_equal(result, q)


def test_sync_and_export(tmp_path):
    c = Config(nx=6, ny=4, sample_s=400, duration_s=900)
    a = run_simulation(c)
    b = run_simulation(replace(c, nx=8, sample_s=300, duration_s=1500))
    np.testing.assert_equal(common_times(a, b), [0, 300, 400, 600, 800, 900])
    np.testing.assert_allclose(frame(a, 200).h[0], 0.5 * (a.h[0] + a.h[1]))
    export_comparison(a, b, tmp_path)
    assert (tmp_path / "A" / "fields.npz").exists() and (
        tmp_path / "comparison.csv"
    ).exists()
