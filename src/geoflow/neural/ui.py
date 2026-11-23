"""Local held-out comparison. Training is available exclusively through the CLI."""

from pathlib import Path
from time import perf_counter

import numpy as np
import streamlit as st
import torch
from matplotlib.figure import Figure

from geoflow.ui_render import panel

from .data import groups, load
from .evaluate import diagnostics, rollout
from .train import read_checkpoint


def laboratory(root):
    st.header("Neural Laboratory")
    folder = Path(
        st.text_input(
            "Neural experiment directory", str(root / "outputs" / "neural-pilot")
        )
    )
    data = Path(st.text_input("Trajectory dataset", str(folder / "data")))
    if not (data / "manifest.json").is_file():
        st.info(
            "Dataset unavailable. Generate trajectories with geoflow-neural generate."
        )
        return
    key = tuple(
        (str(p.resolve()), p.stat().st_mtime_ns, p.stat().st_size)
        for p in (data / "manifest.json", data / "states.npy")
    )
    if st.session_state.get("neural_data_key") != key:
        st.session_state["neural_data"] = load(data)
        st.session_state["neural_data_key"] = key
    m, states = st.session_state["neural_data"]
    paths = sorted(folder.glob("*.pt"))
    if not paths:
        st.info("Model unavailable. Train a checkpoint with geoflow-neural train.")
        return
    path = st.selectbox("Trained checkpoint", paths, format_func=lambda p: p.name)
    ids = [i for i, s in enumerate(m["trajectories"]) if s["group"] in groups(m)[2:]]
    idx = st.selectbox(
        "Held-out trajectory",
        ids,
        format_func=lambda i: (
            f"{m['trajectories'][i]['group']} · seed {m['trajectories'][i]['seed']}"
        ),
    )
    spec = m["trajectories"][idx]
    run_key = (key, str(path.resolve()), path.stat().st_mtime_ns, idx)
    if st.button("Compare rollout on CPU"):
        with st.spinner("Loading checkpoint and evaluating held-out trajectory…"):
            model, ck = read_checkpoint(path, m)
            torch.set_num_threads(1)
            start = perf_counter()
            p = rollout(model, m, states[idx, 0], spec["f"], len(m["times"]) - 1)
            ms = (perf_counter() - start) * 1000
            st.session_state["neural_result"] = (
                run_key,
                p,
                ms,
                ck["history"],
                {
                    k: ck[k]
                    for k in (
                        "architecture",
                        "settings",
                        "best_epoch",
                        "best_loss",
                        "precision",
                        "dataset",
                    )
                },
            )
    previous = st.session_state.get("neural_result")
    if previous is None or previous[0] != run_key:
        st.caption(
            "Select Compare rollout on CPU to load the checkpoint and verify its training record."
        )
        return
    _, p, ms, history, meta = previous
    st.write(
        f"Trained model · selected epoch {meta['best_epoch']} · CPU rollout {ms:.2f} ms"
    )
    if not np.isfinite(p).all():
        st.error("Nonfinite prediction encountered in the rollout.")
        return
    reference = states[idx]
    frame = st.slider("Neural output step", 0, len(p) - 1, value=1)
    name = st.selectbox(
        "Comparison field",
        ["Height anomaly (m)", "East velocity (m/s)", "North velocity (m/s)"],
    )
    field = ("Height anomaly (m)", "East velocity (m/s)", "North velocity (m/s)").index(
        name
    )
    offset = m["config"]["depth_m"] if field == 0 else 0.0

    def figure():
        fig = Figure(figsize=(9, 3.2), layout="constrained")
        axes = fig.subplots(1, 3)
        a, b = reference[frame, field] - offset, p[frame, field] - offset
        limit = max(float(np.max(np.abs(a))), float(np.max(np.abs(b))), 1e-12)
        err = max(float(np.max(np.abs(b - a))), 1e-12)
        extent = (0, m["config"]["lx_m"] / 1000, 0, m["config"]["ly_m"] / 1000)
        for ax, arr, title, vmax in zip(
            axes,
            (a, b, b - a),
            ("MUSCL–MC", "Neural", "Prediction error"),
            (limit, limit, err),
            strict=True,
        ):
            im = ax.imshow(
                arr, origin="lower", extent=extent, vmin=-vmax, vmax=vmax, cmap="RdBu_r"
            )
            ax.set(xlabel="x (km)", ylabel="y (km)", title=title)
            fig.colorbar(im, ax=ax, shrink=0.7)
        fig.suptitle(f"{name} · {m['times'][frame]:g} s")
        return fig

    panel("neural_png", (run_key, frame, field), figure)
    import pandas as pd

    pred = diagnostics(p, reference, m)
    truth = diagnostics(reference, reference, m)
    t = m["times"]

    def chart(title, cols):
        st.caption(title)
        st.line_chart(pd.DataFrame(cols, index=pd.Index(t, name="Time (s)")))

    chart(
        "Relative L2 · scaled anomaly state",
        {"prediction": [r["relative_l2"] for r in pred]},
    )
    chart("RMSE · " + name, {"prediction": [r["rmse"][field] for r in pred]})
    for key, label in (
        ("mass_drift", "Relative mass drift"),
        ("energy_drift", "Relative mechanical energy drift"),
    ):
        chart(
            label,
            {"MUSCL–MC": [r[key] for r in truth], "neural": [r[key] for r in pred]},
        )
    with st.expander("Training history and metadata"):
        st.line_chart(pd.DataFrame(history).set_index("epoch"))
        st.json(meta)
