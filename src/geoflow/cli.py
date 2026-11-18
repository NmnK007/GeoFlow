import argparse
import sys
from pathlib import Path
from time import perf_counter

from .config import load_config
from .io import export, output_directory, write_csv, write_json
from .plotting import convergence_plot
from .solver import metadata, run_simulation
from .verification import verify


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="GeoFlow rotating shallow-water laboratory"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--config", required=True, type=Path)
    for cmd in (run, sub.add_parser("verify")):
        cmd.add_argument("--out", required=True, type=Path)
        cmd.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        with output_directory(args.out, args.overwrite) as out:
            if args.command == "verify":
                report = verify()
                write_json(out / "verification.json", report)
                write_csv(
                    out / "convergence.csv",
                    report["convergence"],
                    ["nx", "relative_l2", "speed_m_s", "order"],
                )
                convergence_plot(report["convergence"]).savefig(out / "convergence.png")
                print(
                    f"Verification {'passed' if report['passed'] else 'failed'}: {out}"
                )
                return 0 if report["passed"] else 1
            start = perf_counter()
            info = {"config_path": str(args.config)}
            try:
                c = load_config(args.config)
                info.update(metadata(c))
                write_json(out / "metadata.json", dict(info, status="running"))
                result = run_simulation(c)
                export(result, out)
            except (
                OSError,
                ValueError,
                TypeError,
                ArithmeticError,
                RuntimeError,
            ) as exc:
                write_json(
                    out / "metadata.json",
                    dict(
                        info,
                        status="failed",
                        error=str(exc),
                        runtime_s=perf_counter() - start,
                    ),
                )
                raise
            print(
                f"Completed {result.diagnostics[-1]['steps']} steps; artifacts in {out}"
            )
    except (OSError, ValueError, TypeError, ArithmeticError, RuntimeError) as exc:
        print(f"GeoFlow: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
