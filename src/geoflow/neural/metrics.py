"""Per-output scientific diagnostics for fixed-grid operator experiments."""

import numpy as np


def diagnostics(pred, ref, m):
    """Return per-time physical RMSE, scaled relative anomaly norm and conservation diagnostics."""
    H, g = m["config"]["depth_m"], m["config"]["gravity_m_s2"]
    scale = np.array(m["std"])[:, None, None]
    background = np.array([H, 0, 0])[:, None, None]

    def energy(s):
        h, u, v = s
        return np.mean(0.5 * (h * (u * u + v * v) + g * (h - H) ** 2))

    start_mass = ref[0, 0].mean()
    e0 = energy(ref[0])
    rows = []
    for t, p, r in zip(m["times"], pred, ref, strict=False):
        row = {"time_s": t, "finite": bool(np.isfinite(p).all())}
        if row["finite"]:
            err = p - r
            norm = np.linalg.norm((r - background) / scale)
            row.update(
                rmse=np.sqrt(np.mean(err**2, axis=(-1, -2))).tolist(),
                scaled_rmse=float(np.sqrt(np.mean((err / scale) ** 2))),
                relative_l2=float(np.linalg.norm(err / scale) / norm) if norm else None,
                mass_drift=float((p[0].mean() - start_mass) / start_mass),
                energy_drift=float((energy(p) - e0) / e0) if e0 else None,
                min_h=float(p[0].min()),
            )
        rows.append(row)
    return rows
