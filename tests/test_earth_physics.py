import numpy as np
import pytest

pytest.importorskip("xarray")
from geoflow.earth.diagnostics import current_means, fields
from geoflow.earth.fixture import fixture
from geoflow.earth.geo import R
from geoflow.earth.tracking import Current, track


def test_spherical_tensor_and_mask():
    ds = fixture()
    ds.u.values[:] = 2
    ds.v.values[:] = 3
    d = fields(ds, 1)
    factor = np.tan(np.radians(ds.lat[10])) / R
    for name, target in (
        ("vorticity", 2 * factor),
        ("divergence", -3 * factor),
        ("shear_strain", 2 * factor),
        ("normal_strain", -3 * factor),
        ("eke", 0.0),
    ):
        assert float(d[name][10, 10]) == pytest.approx(float(target), abs=1e-15)
    ds.u.values[:, 9, 10] = np.nan
    assert np.isnan(fields(ds, 0).vorticity[10, 10])


def test_tracking_and_mask_crossing():
    ds = fixture()
    ds.u.values[:] = 10.0
    ds.v.values[:] = 0
    ocean = Current(ds)
    r = track(ocean, 60.2, 12, 0, 6000, 6000)
    exact = 60.2 + np.degrees(60000 / R / np.cos(np.radians(12)))
    assert r.position[-1, 0] == pytest.approx(exact)
    back = track(ocean, *r.position[-1], 6000, 0, 1000)
    assert back.position[-1, 0] == pytest.approx(60.2)
    ds.u.values[:, :, 5] = np.nan
    for method in ("euler", "rk4"):
        blocked = track(Current(ds), 60.2, 12, 0, 6000, 6000, method)
        assert blocked.status == "missing current or land" and len(blocked.time) == 1


def test_time_interpolation():
    ds = fixture()
    ds.u.values[:] = np.arange(13)[:, None, None]
    ds.v.values[:] = 0.0
    ocean = Current(ds)
    assert ocean.sample(10800, [61, 12])[0] == pytest.approx(0.5)
    r = track(ocean, 61, 12, 0, 21600, 3600)
    assert r.position[-1, 0] == pytest.approx(
        61 + np.degrees(10800 / R / np.cos(np.radians(12)))
    )


def rotation_errors():
    # Prescribe an exact linear angular rotation on the sphere. Analytic provider
    # isolates integrator order from trilinear interpolation error.
    omega = 0.0001

    class Angular(Current):
        def sample(self, t, p):
            x, y = p - np.array([61.0, 12.0])
            return np.radians([-omega * y * np.cos(np.radians(p[1])), omega * x]) * R

    flow = Angular(fixture())
    exact = [61 + 0.5 * np.cos(1.0), 12 + 0.5 * np.sin(1.0)]
    return {
        method: [
            float(
                np.linalg.norm(
                    track(flow, 61.5, 12, 0, 10000, dt, method).position[-1] - exact
                )
            )
            for dt in (1000, 500, 250)
        ]
        for method in ("rk4", "euler")
    }


def test_convergence():
    errors = rotation_errors()
    for method, order in (("euler", 1), ("rk4", 4)):
        assert np.log2(errors[method][-2] / errors[method][-1]) == pytest.approx(
            order, abs=0.06
        )


def test_spacetime_interpolation_across_antimeridian():
    ds = fixture()
    # Use a continuous interpolation branch crossing 180 degrees.
    ds = ds.assign_coords(lon=ds.lon + 119)
    rel_lon = ds.lon.values[None, None, :] - 180
    rel_lat = ds.lat.values[None, :, None] - 12
    rel_time = np.arange(len(ds.time))[:, None, None]
    ds.u.values[:] = 2 * rel_lon - rel_lat + 0.125 * rel_lon * rel_lat * rel_time
    ds.v.values[:] = rel_time + rel_lat
    flow = Current(ds)
    lon, lat = -179.68, 12.38
    p = flow.origin(lon, lat)
    t = 1.65
    expected = [2 * 0.32 - 0.38 + 0.125 * 0.32 * 0.38 * t, t + 0.38]
    np.testing.assert_allclose(flow.sample(t * 21600, p), expected, rtol=0, atol=1e-13)


def test_temporal_means_pair_missing_velocity_components():
    ds = fixture()
    ds.u.values[0, 1, 2] = np.nan
    ds.v.values[2, 1, 2] = np.nan
    ds.v.values[:, 3, 4] = np.nan
    valid = ds.u.notnull() & ds.v.notnull()
    for actual, field in zip(current_means(ds), (ds.u, ds.v), strict=True):
        np.testing.assert_allclose(actual, field.where(valid).mean("time").values)


def test_preview_preserves_extent_and_full_color_range():
    from geoflow.earth.plots import regional_map

    ds = fixture()
    d = fields(ds, 0)
    d.speed.values[:] = 1
    d.speed.values[-1, 0] = 9
    full = regional_map(ds, d, "speed", 0).axes[0].collections[0]
    preview = regional_map(ds, d, "speed", 0, display_limit=5).axes[0].collections[0]
    assert preview.get_array().size == 25
    assert full.get_clim() == preview.get_clim() == (1, 9)
    for end in (0, -1):
        np.testing.assert_array_equal(
            full.get_coordinates()[end, end], preview.get_coordinates()[end, end]
        )
