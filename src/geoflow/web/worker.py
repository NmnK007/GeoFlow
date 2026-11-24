"""Isolated, terminable scientific worker. Accept only supervisor-created directories."""

import sys
from pathlib import Path

from geoflow.config import Config

from . import service


def execute(out):
    request = service.read(out / "request.json")
    if request["kind"] == "simulation":

        def progress(fraction):
            # One small append per output; Windows permits concurrent readers.
            with (out / "progress").open("ab") as stream:
                stream.write(f"{fraction}\n".encode("ascii"))

        service.simulation(out, Config(**request["config"]), progress)
    elif request["kind"] == "inference":
        service.inference(out, request["model"], request["group"], request["member"])
    elif request["kind"] == "earth":
        from zipfile import ZipFile

        from geoflow.earth.lab import analyze
        from geoflow.earth.tracking import Current, ensemble

        ds = service.earth_data(request["dataset"])
        current = Current(ds)
        start = current.axes[0][request["start"]]
        releases = request["releases"] or [(request["longitude"], request["latitude"])]
        tracks = ensemble(
            current,
            releases,
            start,
            start + request["hours"] * 3600,
            request["dt_s"],
            request["method"],
        )
        directory = out / "analysis"
        analyze(
            ds,
            directory,
            index=request["start"],
            hours=request["hours"],
            dt=request["dt_s"],
            ow=request["ow"],
            sla=request["sla"],
            minimum=request["cells"],
            tracks=tracks,
            particle_config=request,
        )
        service.write(
            out / "result.json",
            {
                "metadata": service.read(directory / "analysis.json"),
                "tracks": [
                    {
                        "positions": t.position.tolist(),
                        "time_s": t.time.tolist(),
                        "status": t.status,
                    }
                    for t in tracks
                ],
            },
        )
        with ZipFile(out / "export.zip", "w") as archive:
            for p in directory.iterdir():
                archive.write(p, p.name)
    else:
        raise ValueError("unknown work type")


if __name__ == "__main__":
    execute(Path(sys.argv[1]))
