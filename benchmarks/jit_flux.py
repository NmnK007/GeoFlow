"""Optional benchmark only. Use a disposable environment with Numba installed."""

from dataclasses import replace
from pathlib import Path
from statistics import median
from time import perf_counter

import numpy as np
from numba import njit

from geoflow import boundaries, muscl
from geoflow.config import load_config
from geoflow.solver import run_simulation


@njit(fastmath=False)
def compiled(left, right, g, d, speed=None):
    out = np.empty_like(left)
    for j in range(left.shape[1]):
        for i in range(left.shape[2]):
            hl, hr = left[0, j, i], right[0, j, i]
            vl, vr = left[d + 1, j, i] / hl, right[d + 1, j, i] / hr
            a = (
                max(abs(vl) + np.sqrt(g * hl), abs(vr) + np.sqrt(g * hr))
                if speed is None
                else speed[j, i]
            )
            for k in range(3):
                fl = left[k, j, i] * vl
                fr = right[k, j, i] * vr
                if k == 0:
                    fl, fr = left[d + 1, j, i], right[d + 1, j, i]
                if k == d + 1:
                    fl += 0.5 * g * (hl * hl)
                    fr += 0.5 * g * (hr * hr)
                out[k, j, i] = 0.5 * ((fl + fr) - a * (right[k, j, i] - left[k, j, i]))
    return out


if __name__ == "__main__":
    native = boundaries.rusanov
    for scheme in ("rusanov", "muscl"):
        cfg = replace(load_config(Path("configs/gaussian_bump.json")), scheme=scheme)
        for fn in (native, compiled):
            boundaries.rusanov = muscl.rusanov = fn
            times = []
            for _ in range(6):
                start = perf_counter()
                r = run_simulation(cfg)
                times.append(1000 * (perf_counter() - start))
            if fn is native:
                reference = r
            else:
                for a, b in zip(
                    (r.h, r.u, r.v),
                    (reference.h, reference.u, reference.v),
                    strict=True,
                ):
                    np.testing.assert_allclose(a, b, rtol=1e-12, atol=1e-12)
            print(scheme, fn.__name__, round(times[0], 2), round(median(times[1:]), 2))
