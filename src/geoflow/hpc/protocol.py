import numpy as np

from geoflow.neural.data import groups
from geoflow.neural.metrics import diagnostics


def device_name(request, available):
    if request == "auto":
        return "cuda" if available else "cpu"
    if request == "cuda" and not available:
        raise ValueError("CUDA unavailable in this runtime")
    if request not in ("cpu", "cuda"):
        raise ValueError("unknown device")
    return request


def compatible(source, target, architecture):
    a, b = source["config"], target["config"]
    if (
        {k: v for k, v in a.items() if k not in ("nx", "ny")}
        != {k: v for k, v in b.items() if k not in ("nx", "ny")}
        or source["times"] != target["times"]
        or source["channels"] != target["channels"]
    ):
        raise ValueError(
            "domain, physical parameters, channels and timestamps must match"
        )
    cross = (a["nx"], a["ny"]) != (b["nx"], b["ny"])
    if cross and architecture["kind"] != "fno":
        raise ValueError("resolution transfer tested only for FNO")
    if architecture["kind"] == "fno" and (
        2 * architecture["modes"] > b["ny"] or architecture["modes"] > b["nx"] // 2 + 1
    ):
        raise ValueError("Fourier modes exceed target grid")
    training = {
        q["seed"]
        for q in source["trajectories"]
        if q["group"] in ("train", "validation")
    }
    if any(
        q["seed"] in training
        for q in target["trajectories"]
        if q["group"] in groups(target)[2:]
    ):
        raise ValueError("overlapping training and evaluation seeds")


def score(pred, ref, m):
    if pred.shape != ref.shape or len(ref) != len(m["times"]):
        raise ValueError("mismatched rollout")
    rows = diagnostics(pred, ref, m)
    scale = np.array(m["std"])[:, None, None]
    background = np.array([m["config"]["depth_m"], 0, 0])[:, None, None]
    for r, p, t in zip(rows, pred, ref, strict=True):
        denom = np.sum(abs((t - background) / scale))
        r["relative_l1"] = (
            float(np.sum(abs((p - t) / scale)) / denom)
            if r["finite"] and denom
            else None
        )
    return rows
