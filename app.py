"""Local Streamlit entry point. The CLI and UI share run_simulation and export."""

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import streamlit as st
from matplotlib.figure import Figure

from geoflow.config import load_config
from geoflow.io import export, output_directory
from geoflow.plotting import LABELS, heatmap, limits
from geoflow.solver import run_simulation

ROOT = Path(__file__).resolve().parent
PRESETS = sorted((ROOT / "configs").glob("*.json"))
st.set_page_config(page_title="GeoFlow v0.1", layout="wide")
st.title("GeoFlow v0.1")
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
    name = st.selectbox("Field", list(LABELS), key="field")
    index = st.slider("Snapshot", 0, len(r.time) - 1, key="snapshot")
    arrows = st.checkbox("Overlay velocity arrows")
    bounds = st.session_state["bounds"]
    if name not in bounds:
        bounds[name] = limits(r, name)
    st.pyplot(heatmap(r, name, index, arrows, bounds[name]))
    row = r.diagnostics[index]
    st.caption(
        f"Minimum depth {row['min_h_m']:.6g} m · Solver runtime {r.metadata['runtime_s']:.4g} s · "
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
