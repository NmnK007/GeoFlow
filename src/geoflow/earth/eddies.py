"""Four-connected rotational candidates with SLA and rotation-sign consistency."""

from collections import deque

import numpy as np

from .geo import R, wrap


def edges(centers):
    mid = 0.5 * (centers[1:] + centers[:-1])
    return np.r_[2 * centers[0] - mid[0], mid, 2 * centers[-1] - mid[-1]]


def candidates(d, ow_threshold=0.0, sla_min=0.02, min_cells=4):
    if (
        ow_threshold > 0
        or sla_min < 0
        or min_cells < 1
        or not np.isfinite([ow_threshold, sla_min]).all()
    ):
        raise ValueError(
            "require nonpositive OW threshold, nonnegative amplitude and positive area count"
        )
    if "sla" not in d:
        raise ValueError("sea-level anomaly required for detection")
    z, ow, sla = (d[key].values for key in ("vorticity", "okubo_weiss", "sla"))
    lat, lon = d.lat.values, d.lon.values
    area = (
        R**2
        * np.diff(np.sin(np.radians(np.clip(edges(lat), -90, 90))))[:, None]
        * np.diff(np.radians(edges(lon)))
    )
    result = []
    for sign in (1, -1):
        mask = (
            (ow < ow_threshold)
            & (sign * z * lat[:, None] > 0)
            & (-sign * sla >= sla_min)
            & (abs(lat[:, None]) >= 3)
        )
        for iy, ix in zip(*np.where(mask), strict=True):
            if not mask[iy, ix]:
                continue
            queue = deque([(iy, ix)])
            mask[iy, ix] = False
            cells = []
            while queue:
                j, i = queue.popleft()
                cells.append((j, i))
                for y, x in ((j + 1, i), (j - 1, i), (j, i + 1), (j, i - 1)):
                    if 0 <= y < len(lat) and 0 <= x < len(lon) and mask[y, x]:
                        mask[y, x] = False
                        queue.append((y, x))
            if len(cells) < min_cells:
                continue
            j, i = np.array(cells).T
            weights = area[j, i]
            total = float(weights.sum())
            result.append(
                {
                    "classification": "cyclonic candidate"
                    if sign == 1
                    else "anticyclonic candidate",
                    "longitude": float(wrap(np.average(lon[i], weights=weights))),
                    "latitude": float(np.average(lat[j], weights=weights)),
                    "cells": len(cells),
                    "area_m2": total,
                    "radius_m": float(np.sqrt(total / np.pi)),
                    "mean_vorticity_s_inv": float(np.average(z[j, i], weights=weights)),
                }
            )
    return result
