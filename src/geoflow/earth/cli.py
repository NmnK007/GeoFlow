import argparse
from pathlib import Path

from .acquire import acquire
from .cases import CASES
from .data import CATALOG, import_region
from .fixture import fixture
from .lab import analyze
from .tracking import Current, ensemble


def main():
    p = argparse.ArgumentParser(description="GeoFlow Earth regional analysis")
    sub = p.add_subparsers(dest="cmd", required=True)
    fetch = sub.add_parser("fetch")
    fetch.add_argument("--dir", type=Path, default=Path("data/arabian-july-2020"))
    cm = sub.add_parser(
        "subset",
        help="Regional NetCDF download using the optional official Copernicus Marine CLI",
    )
    cm.add_argument("--product", choices=CATALOG, required=True)
    cm.add_argument("--case", choices=CASES, default="Arabian Sea")
    cm.add_argument("--out", type=Path, required=True)
    run = sub.add_parser("analyze")
    source = run.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path)
    source.add_argument("--fixture", action="store_true")
    run.add_argument("--case", choices=CASES, default="Arabian Sea")
    run.add_argument("--box", nargs=4, type=float)
    run.add_argument("--start")
    run.add_argument("--end")
    run.add_argument("--depth", type=float)
    run.add_argument("--drifters", type=Path)
    run.add_argument("--index", type=int, default=0)
    run.add_argument("--hours", type=int, default=24)
    run.add_argument(
        "--release",
        action="append",
        nargs=2,
        type=float,
        metavar=("LON", "LAT"),
        help="repeat for an ensemble",
    )
    run.add_argument(
        "--end-index",
        type=int,
        default=-1,
        help="particle end time index; releases start at --index",
    )
    run.add_argument("--method", choices=("euler", "rk4"), default="rk4")
    run.add_argument("--dt", type=float, default=900.0)
    run.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.cmd == "fetch":
        acquire(args.dir)
        return
    if args.cmd == "subset":
        import shutil
        import subprocess

        tool = shutil.which("copernicusmarine")
        if tool is None:
            p.error(
                "Install the official Copernicus Marine Toolbox or import a local NetCDF"
            )
        if args.out.exists():
            p.error("select a new output filename")
        case = CASES[args.case]
        west, east, south, north = case["box"]
        cmd = [
            tool,
            "subset",
            "--dataset-id",
            CATALOG[args.product][0],
            "--minimum-longitude",
            str(west),
            "--maximum-longitude",
            str(east),
            "--minimum-latitude",
            str(south),
            "--maximum-latitude",
            str(north),
            "--start-datetime",
            case["start"],
            "--end-datetime",
            case["end"],
            "--output-directory",
            str(args.out.parent),
            "--output-filename",
            args.out.name,
        ]
        variables = (
            ("uo", "vo", "zos")
            if args.product == "glorys"
            else ("ugos", "vgos", "adt", "sla")
        )
        if args.product == "glorys":
            cmd.extend(["--minimum-depth", "0", "--maximum-depth", "1"])
        for variable in variables:
            cmd.extend(["--variable", variable])
        subprocess.run(cmd, check=True)
        return
    spec = CASES[args.case].copy()
    for key in ("box", "start", "end"):
        if getattr(args, key) is not None:
            spec[key] = getattr(args, key)
    ds = (
        fixture()
        if args.fixture
        else import_region(args.file, **spec, depth_m=args.depth, cache="data/cache")
    )
    tracks = []
    particle_config = {}
    if args.release:
        flow = Current(ds)
        t0, t1 = flow.axes[0][[args.index, args.end_index]]
        tracks = ensemble(flow, args.release, t0, t1, args.dt, args.method)
        particle_config = {
            "releases": args.release,
            "start_s": t0,
            "end_s": t1,
            "dt_s": args.dt,
            "method": args.method,
        }
    analyze(
        ds,
        args.out,
        args.index,
        args.drifters,
        args.hours,
        args.dt,
        tracks=tracks,
        particle_config=particle_config,
    )
    print(f"Research artifacts: {args.out}")


if __name__ == "__main__":
    main()
