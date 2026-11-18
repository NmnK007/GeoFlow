"""Local Streamlit entry point. The CLI and UI share run_simulation and export."""

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import streamlit as st
from matplotlib.figure import Figure

from geoflow.comparison import common_times, export_comparison, frame
from geoflow.config import load_config
from geoflow.io import export, output_directory
from geoflow.plotting import LABELS, heatmap, limits
from geoflow.solver import run_simulation

ROOT = Path(__file__).resolve().parent
PRESETS = sorted((ROOT / "configs").glob("*.json"))
st.set_page_config(page_title="GeoFlow v0.3", layout="wide")
st.title("GeoFlow v0.3")
mode = st.sidebar.radio("Laboratory", ["Idealized simulation", "Earth"], key="lab_mode")
if mode == "Earth":
    try:
        from geoflow.earth.ui import laboratory

        laboratory()
    except ImportError as exc:
        st.error(
            f'Install the optional Earth packages with python -m pip install -e ".[earth,ui]". {exc}'
        )
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        st.error(str(exc))
    st.stop()

st.caption("Single-layer rotating shallow water · flat bottom · local Cartesian grid")


def reset():
    for key in list(st.session_state):
        del st.session_state[key]


with st.sidebar:
    st.button("Reset laboratory", on_click=reset, key="reset_lab")
    preset = st.selectbox(
        "Experiment preset",
        [p.stem for p in PRESETS],
        key="preset",
        index=[p.stem for p in PRESETS].index("gaussian_bump"),
    )
    base = load_config(ROOT / "configs" / f"{preset}.json")

    def control(label, name, low, high):
        return st.number_input(
            label,
            min_value=low,
            max_value=high,
            value=type(low)(getattr(base, name)),
            key=f"{preset}_{name}",
        )

    values = {
        "nx": control("East–west cells", "nx", 2, 128),
        "ny": control("North–south cells", "ny", 2, 128),
        "lx_m": control("East–west length (m)", "lx_m", 1.0, 1e8),
        "ly_m": control("North–south length (m)", "ly_m", 1.0, 1e8),
        "depth_m": control("Reference depth (m)", "depth_m", 0.01, 1e4),
        "gravity_m_s2": control("Gravity (m/s²)", "gravity_m_s2", 0.01, 50.0),
        "latitude_deg": control("Latitude (degrees)", "latitude_deg", -90.0, 90.0),
        "duration_s": control("Duration (s)", "duration_s", 0.01, 1e6),
        "sample_s": control("Output interval (s)", "sample_s", 0.01, 1e6),
    }
    if base.experiment == "gaussian":
        values["amplitude_m"] = control(
            "Peak anomaly (m)", "amplitude_m", -100.0, 100.0
        )
        values["sigma_m"] = control("Gaussian width σ (m)", "sigma_m", 1.0, 1e7)
    values["scheme"] = st.selectbox(
        "Transport scheme",
        ["rusanov", "muscl"],
        index=int(base.scheme == "muscl"),
        key=f"{preset}_scheme",
        help="Rusanov is the v0.1 baseline. MUSCL adds limited reconstruction and SSP-RK2.",
    )
    values["limiter"] = st.selectbox(
        "Slope limiter",
        ["mc", "minmod"],
        disabled=values["scheme"] != "muscl",
        key=f"{preset}_limiter",
        help="MC retains more smooth structure. Minmod limits slopes more strongly.",
    )
    if base.experiment in (
        "wave",
        "rossby",
        "kelvin",
        "poincare",
        "balanced",
        "vortices",
    ):
        values["epsilon"] = st.number_input(
            "Relative height amplitude (η/H)",
            value=base.epsilon,
            format="%.7f",
            key=f"{preset}_epsilon",
        )
    if base.experiment in ("uniform", "shear"):
        values["u0_m_s"] = control(
            "Eastward velocity scale (m/s)", "u0_m_s", -20.0, 20.0
        )
    with st.expander("Rotation and layer physics"):
        values["plane"] = st.selectbox(
            "Rotation model",
            ["f", "beta"],
            index=int(base.plane == "beta"),
            key=f"{preset}_plane",
            help="Beta uses the latitude gradient of planetary rotation and requires a channel.",
        )
        values["boundary_y"] = st.selectbox(
            "North–south boundary",
            ["periodic", "wall"],
            index=int(base.boundary_y == "wall"),
            key=f"{preset}_boundary",
        )
        if st.toggle("Override central f", key=f"{preset}_override"):
            values["f_override_s_inv"] = st.number_input(
                "Central f (1/s)", value=base.f, format="%.8f", key=f"{preset}_f"
            )
        if st.toggle(
            "Reduced-gravity layer",
            value=base.reduced_gravity_m_s2 is not None,
            key=f"{preset}_reduced",
        ):
            values["reduced_gravity_m_s2"] = st.number_input(
                "Buoyancy restoring acceleration (m/s²)",
                min_value=0.00001,
                value=base.reduced_gravity_m_s2 or 0.1,
                format="%.5f",
                key=f"{preset}_gprime",
            )
        else:
            values["reduced_gravity_m_s2"] = None
    run = st.button("Run Simulation", type="primary", key="run_lab")
try:
    config = replace(
        base, **values, max_steps=10000, snapshot_mib=64, working_mib=64, max_frames=256
    )
except ValueError as exc:
    st.error(str(exc))
    config = None

if run and config is not None:
    progress = st.progress(0.0)
    try:
        result = run_simulation(config, progress.progress)
        st.session_state["result"] = result
        st.session_state["result_name"] = preset
        st.session_state["snapshot"] = 0
        st.session_state["bounds"] = {}
        st.session_state.pop("export_path", None)
    except (ValueError, ArithmeticError, RuntimeError) as exc:
        st.error(str(exc))
    finally:
        progress.empty()

if "result" in st.session_state:
    r = st.session_state["result"]
    if config != r.config or preset != st.session_state["result_name"]:
        st.warning("Settings changed. Displaying the previous run until you run again.")
    st.subheader(st.session_state["result_name"].replace("_", " ").title())
    if st.button(
        "Pin current run as A",
        help="Keep A, change any settings and run again to compare with B.",
    ):
        st.session_state["reference_run"] = r
        st.session_state["reference_bounds"] = {}
    a = st.session_state.get("reference_run")
    comparing = a is not None and a is not r
    name = st.selectbox("Field", list(LABELS), key="field")
    times = common_times(a, r) if comparing else r.time
    index = st.slider("Snapshot", 0, len(times) - 1, key="snapshot")
    time_s = times[index]
    arrows = st.checkbox("Overlay velocity arrows")
    bounds = st.session_state["bounds"]
    if name not in bounds:
        bounds[name] = limits(r, name)
    if comparing:
        previous = st.session_state["reference_bounds"]
        if name not in previous:
            previous[name] = limits(a, name)
        shared = (
            min(previous[name][0], bounds[name][0]),
            max(previous[name][1], bounds[name][1]),
        )
        for col, label, run_data in zip(st.columns(2), ("A", "B"), (a, r), strict=True):
            col.write(
                f"{label} · {run_data.config.experiment} · {run_data.config.scheme} · {run_data.config.nx}×{run_data.config.ny}"
            )
            col.pyplot(heatmap(frame(run_data, time_s), name, 0, arrows, shared))
        st.caption(
            "Shared colour scale and simulated time. Between outputs, primitive fields are linearly interpolated. Arrows show local direction with panel-specific autoscaling."
        )
        st.json({"A": a.metadata, "B": r.metadata}, expanded=False)
    else:
        st.pyplot(heatmap(r, name, index, arrows, bounds[name]))
    row = r.diagnostics[int(r.time.searchsorted(time_s))]
    st.caption(
        f"B diagnostics at {row['time_s']:.6g} s · Minimum depth {row['min_h_m']:.6g} m · Solver runtime {r.metadata['runtime_s']:.4g} s · "
        f"Accepted steps {row['steps']} · Rejected trials {row['rejected_steps']}"
    )
    fig = Figure(figsize=(8, 3.2), layout="constrained")
    axes = fig.subplots(1, 2)
    for ax, key, label in zip(
        axes,
        ("volume_drift", "energy"),
        ("Relative volume drift", "Energy / density (m⁵/s²)"),
        strict=True,
    ):
        ax.plot(r.time / 3600, [d[key] for d in r.diagnostics])
        ax.set(xlabel="Simulated time (h)", ylabel=label)
    st.pyplot(fig)
    if comparing:
        key = st.selectbox(
            "Compare diagnostics",
            [
                "kinetic_energy",
                "potential_energy",
                "energy",
                "volume_drift",
                "relative_enstrophy_change",
                "height_reference_relative_l2",
                "wall_time_s",
            ],
        )
        comparison = Figure(figsize=(8, 3), layout="constrained")
        ax = comparison.subplots()
        for label, data in (("A", a), ("B", r)):
            series = [d[key] for d in data.diagnostics]
            if any(v is not None for v in series):
                ax.plot(data.time / 3600, series, label=label)
            else:
                st.caption(f"{label}: {key} undefined for this experiment.")
        ax.set(xlabel="Simulated time (h)", ylabel=key)
        if ax.lines:
            ax.legend()
        st.pyplot(comparison)
        if st.button("Save comparison artifacts"):
            path = ROOT / "outputs" / f"comparison-{uuid4().hex[:12]}"
            try:
                with output_directory(path, False):
                    export_comparison(a, r, path)
                st.code(str(path))
            except OSError as exc:
                st.error(str(exc))
    with st.expander("Run metadata"):
        st.json(r.metadata)
    if st.button("Save run artifacts"):
        path = ROOT / "outputs" / f"ui-{uuid4().hex[:12]}"
        try:
            with output_directory(path, False):
                export(r, path)
            st.session_state["export_path"] = str(path)
        except OSError as exc:
            st.error(str(exc))
    if "export_path" in st.session_state:
        st.code(st.session_state["export_path"])
