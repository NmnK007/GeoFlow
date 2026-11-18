from dataclasses import replace

import numpy as np
import pytest

from geoflow import solver
from geoflow.config import Config
from geoflow.diagnostics import potential_vorticity, vorticity


@pytest.mark.parametrize(
    "kwargs",
    [
        {"nx": 1},
        {"ny": 2.5},
        {"cfl": 0.51},
        {"cfl": 0},
        {"duration_s": 0},
        {"depth_m": -1},
        {"latitude_deg": 91},
        {"f_override_s_inv": np.nan},
        {"nx": 100000},
        {"max_frames": 3},
        {"nx": 2048, "ny": 2048, "max_frames": 512},
        {"snapshot_mib": 1, "nx": 128},
        {"working_mib": 1, "nx": 128},
        {"sample_s": 1e-300},
        {"boundary_y": "open"},
    ],
)
def test_invalid_config(kwargs):
    with pytest.raises(ValueError):
        Config(**kwargs)


def test_bad_initial_and_step_limit():
    with pytest.raises(ValueError, match="initial"):
        solver.run_simulation(Config(experiment="wave", epsilon=3))
    with pytest.raises(RuntimeError, match="step limit"):
        solver.run_simulation(Config(max_steps=1))


def test_retry(monkeypatch):
    c = Config()
    q = np.ones((3, 2, 3))

    def threshold(q, c, dt):
        return q.copy() if dt <= 0.5 else -q

    monkeypatch.setattr(solver, "trial", threshold)
    result, dt, rejected = solver.advance(q, c, 0.0, 1.0)
    np.testing.assert_equal(result, q)
    assert (dt, rejected) == (0.5, 1)
    with pytest.raises(RuntimeError, match="invalid trial"):
        solver.advance(q, replace(c, max_retries=0), 0.0, 1.0)
    with pytest.raises(RuntimeError, match="cannot advance"):
        solver.advance(q, c, 1e20, 1.0)


def test_output_times_and_f_precedence():
    c = Config(
        nx=6, ny=3, duration_s=0.31, sample_s=0.1, latitude_deg=65, f_override_s_inv=0
    )
    r = solver.run_simulation(c)
    np.testing.assert_allclose(r.time, [0, 0.1, 0.2, 0.3, 0.31], atol=1e-16, rtol=0)
    assert r.time[-1] == c.duration_s and r.metadata["resolved_f_s_inv"] == 0
    assert not np.shares_memory(r.h[0], r.h[-1])


def test_y_transport_matches_transposed_x():
    rng = np.random.default_rng(0)
    q = rng.uniform(1, 3, (3, 5, 8))
    c = Config(nx=8, ny=5, lx_m=3000, ly_m=1000, boundary_y="wall")
    swapped = replace(
        c, nx=5, ny=8, lx_m=1000, ly_m=3000, boundary_x="wall", boundary_y="periodic"
    )

    def transpose(a):
        return a[[0, 2, 1]].transpose(0, 2, 1)

    np.testing.assert_allclose(
        solver.trial(q, c, 0.1), transpose(solver.trial(transpose(q), swapped, 0.1))
    )


def test_diagnostic_stencil():
    c = Config(nx=8, ny=3, lx_m=8, ly_m=6, boundary_y="wall", latitude_deg=45)
    h = np.ones((3, 8)) * 2
    u = np.broadcast_to(np.arange(3.0)[:, None], h.shape)
    v = np.broadcast_to(np.sin(2 * np.pi * np.arange(8) / 8), h.shape)
    exact = (
        np.cos(2 * np.pi * np.arange(8) / 8) * np.sin(np.pi / 4)
        - np.array([0.25, 0.5, 0.25])[:, None]
    )
    np.testing.assert_allclose(
        vorticity(h, u, v, c), exact, rtol=0, atol=4 * np.finfo(float).eps
    )
    np.testing.assert_allclose(potential_vorticity(h, u, v, c), (exact + c.f) / 2)
