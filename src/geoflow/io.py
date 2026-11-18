import csv
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from .plotting import heatmap
from .solver import SimulationResult


@contextmanager
def output_directory(path: Path, overwrite: bool) -> Iterator[Path]:
    path.mkdir(parents=True, exist_ok=True)
    lock = path / ".geoflow-running"
    with lock.open("x"):
        pass
    try:
        if not overwrite and any(p != lock for p in path.iterdir()):
            raise FileExistsError(
                f"output directory is nonempty: {path} (choose another or use --overwrite)"
            )
        yield path
    finally:
        lock.unlink()


def write_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def export(r: SimulationResult, path: Path) -> None:
    """Write into a reserved run directory; metadata is the completion marker."""
    np.savez_compressed(
        path / "fields.npz", time=r.time, x=r.x, y=r.y, h=r.h, u=r.u, v=r.v
    )
    write_csv(path / "diagnostics.csv", r.diagnostics, list(r.diagnostics[0]))
    heatmap(r, "Height anomaly", -1).savefig(path / "height_anomaly.png", dpi=120)
    write_json(path / "metadata.json", r.metadata)
