"""Summarize the pilot report over all initialization and trajectory seeds."""

import json
import sys
from pathlib import Path
from statistics import mean, median, pstdev


def summarize(folder, report_name="report.json"):
    report = json.loads((folder / report_name).read_text())
    result = {}
    for kind in (
        "muscl",
        "persistence",
        "cnn",
        "fno",
        "physics",
        "mass",
        "energy",
        "positive",
        "multi",
    ):
        names = [n for n in report["models"] if n.split("-")[0] == kind]
        if not names:
            continue
        models = [report["models"][n] for n in names]
        cases = [case for model in models for case in model["cases"]]
        fits = [
            json.loads((folder / (n + ".json")).read_text()) for n in names if "-" in n
        ]
        entry = {
            "params": models[0].get("params", 0),
            "load_ms": mean(m["load_ms"] for m in models),
            "warmup_ms": mean(m["warmup_ms"] for m in models),
            "median_ms": median(c["runtime_ms"] for c in cases),
            "training_s": [m["training_s"] for m in fits],
            "training_peak_mib": [m["process_peak_mib"] for m in fits],
            "groups": {},
        }
        for group in ("id", "amplitude_location", "rotation"):
            rows = [c["metrics"] for c in cases if c["group"] == group]
            finite = all(r["finite"] for trajectory in rows for r in trajectory)
            group_result = {"finite": finite}
            if finite:
                group_result["relative_l2"] = {}
                for step in (1, 4, -1):
                    err = [trajectory[step]["relative_l2"] for trajectory in rows]
                    group_result["relative_l2"][str(step)] = [mean(err), pstdev(err)]
                last = [tr[-1] for tr in rows]
                group_result.update(
                    abs_final_mass=mean(abs(r["mass_drift"]) for r in last),
                    abs_final_energy=mean(abs(r["energy_drift"]) for r in last),
                    min_h=min(r["min_h"] for tr in rows for r in tr),
                    final_rmse=[mean(r["rmse"][j] for r in last) for j in range(3)],
                )
            entry["groups"][group] = group_result
        result[kind] = entry
    return result


if __name__ == "__main__":
    print(json.dumps(summarize(Path(sys.argv[1]), *sys.argv[2:]), indent=2))
