"""Retrieve only a small predefined Arabian Sea study, independently of the solver."""

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

from .data import fingerprint

CASE = {"box": [55, 73, 8, 20], "start": "2020-07-01", "end": "2020-07-04"}
GDP = "https://erddap.aoml.noaa.gov/gdp/erddap/tabledap/drifter_hourly_qc"
GRID = "https://erddap.aoml.noaa.gov/hdb/erddap/griddap/SEA_SURFACE_HEIGHT_2020_v3"


def acquire(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    section = "[(2020-07-01):1:(2020-07-04)][(8):1:(20)][(55):1:(73)]"
    queries = {
        "currents.nc": (
            GRID + ".nc",
            ",".join(v + section for v in ("ugos", "vgos", "adt", "sla")),
        ),
        "drifters.csv": (
            GDP + ".csv",
            "ID,time,longitude,latitude,ve,vn,drogue_lost_date&time>=2020-07-01T00:00:00Z&time<=2020-07-04T00:00:00Z&latitude>=8&latitude<=20&longitude>=55&longitude<=73",
        ),
    }
    errors = []
    for file, (base, query) in queries.items():
        url = base + "?" + quote(query, safe=",:&=")
        target = directory / file
        if target.exists():
            manifest = target.with_suffix(target.suffix + ".json")
            if manifest.exists() and json.loads(manifest.read_text()).get(
                "sha256"
            ) == fingerprint(target):
                continue
            raise ValueError(
                f"existing download lacks matching provenance: {target}; choose a fresh directory"
            )
        try:
            with urlopen(url, timeout=60) as response:
                content = response.read(10_000_001)
            if len(content) > 10_000_000:
                raise ValueError("response exceeds regional limit")
            if file.endswith(".nc") and not content.startswith((b"CDF", b"\x89HDF")):
                raise ValueError("expected NetCDF")
            if file.endswith(".csv") and not content.startswith(b"ID,"):
                raise ValueError("expected GDP CSV")
            target.write_bytes(content)
            target.with_suffix(target.suffix + ".json").write_text(
                json.dumps(
                    {
                        "url": url,
                        "sha256": fingerprint(target),
                        "retrieved_utc": datetime.now(UTC).isoformat(),
                        "dataset": "drifter_hourly_qc"
                        if file.endswith(".csv")
                        else "SEA_SURFACE_HEIGHT_2020_v3",
                        "attribution": "NOAA GDP, Elipot et al., doi:10.25921/x46c-3620, CC BY 4.0"
                        if file.endswith(".csv")
                        else "E.U. Copernicus Marine Service, SSALTO/DUACS via NOAA AOML; see NetCDF licence attribute",
                    },
                    indent=2,
                )
            )
        except (OSError, ValueError) as exc:
            errors.append(f"{file}: {exc}")
    if errors:
        raise RuntimeError("; ".join(errors))
