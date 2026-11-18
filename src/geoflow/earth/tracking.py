"""Advection in longitude/latitude using seconds since the first source sample."""

from dataclasses import dataclass

import numpy as np

from .geo import rates


class Unavailable(ValueError):
    """An interpolation footprint reached missing data or the domain boundary."""


@dataclass
class Track:
    time: np.ndarray
    position: np.ndarray
    status: str


class Current:
    def __init__(self, ds):
        self.epoch = ds.time.values[0]
        self.axes = (
            (ds.time.values - self.epoch) / np.timedelta64(1, "s"),
            ds.lat.values,
            ds.lon.values,
        )
        self.velocity = np.stack((ds.u.values, ds.v.values), axis=-1)
        if any(len(a) < 2 or not np.all(np.diff(a) > 0) for a in self.axes):
            raise ValueError("tracking requires two increasing samples on every axis")

    def seconds(self, time):
        return float((np.datetime64(time) - self.epoch) / np.timedelta64(1, "s"))

    def origin(self, lon, lat):
        west = self.axes[2][0]
        return np.array([west + (lon - west) % 360, lat], dtype=float)

    def sample(self, t, p):
        coords = (t, p[1], p[0])
        indices = []
        weights = []
        for axis, value in zip(self.axes, coords, strict=True):
            if not axis[0] <= value <= axis[-1]:
                raise Unavailable("outside velocity domain")
            i = min(
                len(axis) - 2, max(0, np.searchsorted(axis, value, side="right") - 1)
            )
            indices.append(i)
            weights.append((value - axis[i]) / (axis[i + 1] - axis[i]))
        i, j, k = indices
        block = self.velocity[i : i + 2, j : j + 2, k : k + 2]
        wt, wy, wx = (np.array([1 - w, w]) for w in weights)
        w = wt[:, None, None] * wy[None, :, None] * wx[None, None, :]
        use = w > 0
        if not np.all(np.isfinite(block[use])):
            raise Unavailable("missing current or land")
        return w[use] @ block[use]

    def segment(self, t, p, s, q):
        # Partition a straight space-time segment at every interpolation-cell face.
        # Every open piece has one fixed set of supporting corners.
        cuts = [0.0, 1.0]
        for axis, left, right in zip(
            self.axes, (t, p[1], p[0]), (s, q[1], q[0]), strict=True
        ):
            if left != right:
                lo, hi = sorted((left, right))
                inner = axis[
                    np.searchsorted(axis, lo, side="right") : np.searchsorted(axis, hi)
                ]
                cuts.extend((inner - left) / (right - left))
        cuts = np.unique(cuts)
        for a in (cuts[1:] + cuts[:-1]) / 2:
            self.sample(t + a * (s - t), p + a * (q - p))
        self.sample(s, q)


def track(current: Current, lon, lat, start, end, dt=900.0, method="rk4"):
    if (
        method not in ("rk4", "euler")
        or not np.isfinite([lon, lat, start, end, dt]).all()
        or dt <= 0
        or abs(end - start) / dt > 200000
    ):
        raise ValueError("invalid release, method or step budget")
    p = current.origin(lon, lat)
    t = float(start)
    times = [t]
    positions = [p]
    status = "completed"

    def rhs(s, q):
        vel = current.sample(s, q)
        return rates(*vel, q[1])

    def stage(t, p, offset, velocity):
        point = p + offset * velocity
        current.segment(t, p, t + offset, point)
        return rhs(t + offset, point)

    try:
        current.sample(t, p)
        while t != end:
            h = np.sign(end - t) * min(dt, abs(end - t))
            s = end if abs(h) == abs(end - t) else t + h
            if s == t:
                raise ValueError("time step underflow")
            a = rhs(t, p)
            if method == "euler":
                q = p + h * a
            else:
                b = stage(t, p, h / 2, a)
                c = stage(t, p, h / 2, b)
                d = stage(t, p, h, c)
                q = p + h * (a + 2 * b + 2 * c + d) / 6
            current.segment(t, p, s, q)
            t, p = s, q
            times.append(t)
            positions.append(p)
    except Unavailable as exc:
        status = str(exc)
    return Track(np.array(times), np.array(positions), status)


def ensemble(current, releases, start, end, dt, method):
    releases = list(releases)
    if (
        len(releases) > 256
        or len(releases) * abs(end - start) / max(dt, 1e-30) > 250000
    ):
        raise ValueError("ensemble step budget exceeded")
    return [track(current, *p, start, end, dt, method) for p in releases]
