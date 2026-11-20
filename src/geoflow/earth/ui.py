"""Streamlit Earth mode; optional numerical dependencies are imported on selection."""

from pathlib import Path
from uuid import uuid4

import streamlit as st
import xarray as xr

from geoflow.ui_render import panel

from .cases import CASES
from .data import import_region
from .diagnostics import current_means, fields
from .eddies import candidates
from .fixture import fixture
from .lab import analyze, match_observations
from .plots import regional_map, separation_plot
from .tracking import Current, ensemble


@st.cache_data(max_entries=32, show_spinner=False)
def depth_levels(path, signature):
    with xr.open_dataset(path) as raw:
        depth = next(
            (
                v
                for k, v in raw.coords.items()
                if k == "depth" or v.attrs.get("standard_name") == "depth"
            ),
            None,
        )
        return (
            list(map(float, depth.values))
            if depth is not None and depth.ndim == 1
            else []
        )


def laboratory(root):
    st.header("Earth · regional ocean analysis")
    source = st.selectbox(
        "Current source", ["Local NetCDF", "Synthetic verification fixture"]
    )
    directory = root / "data" / "arabian-july-2020"
    spec = {}
    path = None
    signature = None
    level = None
    if source == "Local NetCDF":
        path = Path(st.text_input("Local current file", str(directory / "currents.nc")))
        case = st.selectbox("Historical study", list(CASES))
        default = CASES[case]
        box = st.text_input(
            "West, east, south, north (degrees)",
            ",".join(map(str, default["box"])),
            key="box_" + case,
        )
        start = st.text_input("Start UTC", default["start"], key="start_" + case)
        end = st.text_input("End UTC", default["end"], key="end_" + case)
        if path.is_file():
            stat = path.stat()
            signature = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            levels = depth_levels(str(path.resolve()), signature)
            if levels:
                level = st.selectbox("Depth level (m)", levels)
        spec = {"box": [float(v) for v in box.split(",")], "start": start, "end": end}
    key = (source, str(path.resolve()) if path else None, signature, str(spec), level)
    if st.button("Load region"):
        old = st.session_state.get("earth_loaded")
        if old is None or old[0] != key:
            with st.spinner("Loading region and computing temporal means…"):
                ds = (
                    fixture()
                    if path is None
                    else import_region(
                        path, **spec, depth_m=level, cache=root / "data" / "cache"
                    )
                )
                st.session_state["earth_means"] = current_means(ds)
                st.session_state["earth_loaded"] = (key, ds)
                st.session_state["earth_id"] = uuid4().hex
                st.session_state.pop("earth_fields", None)
                st.session_state.pop("earth_candidates", None)
        if (
            old is None
            or old[0] != key
            or any(k in st.session_state for k in ("earth_tracks", "earth_validation"))
        ):
            st.session_state["overlay_id"] = uuid4().hex
        for k in ("earth_tracks", "earth_validation", "earth_particle_config"):
            st.session_state.pop(k, None)
    if "earth_loaded" not in st.session_state:
        return
    loaded, ds = st.session_state["earth_loaded"]
    if loaded != key:
        st.info("Showing the previously loaded region until Load region is selected.")
    region_view(ds, root)


@st.fragment
def region_view(ds, root):
    try:
        display_region(ds, root)
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        st.error(str(exc))


def display_region(ds, root):
    directory = root / "data" / "arabian-july-2020"
    st.write(ds.attrs.get("title", ds.attrs.get("source_file", "Local currents")))
    index = st.select_slider(
        "Current field time (UTC)",
        options=range(len(ds.time)),
        format_func=lambda i: str(ds.time.values[i])[:19],
    )
    latest = st.session_state.get("earth_fields")
    if latest is None or latest[0] != index:
        latest = (index, fields(ds, index, st.session_state["earth_means"]))
        st.session_state["earth_fields"] = latest
    d = latest[1]
    name = st.selectbox("Ocean field", list(d.data_vars))
    tracks = st.session_state.get("earth_tracks", [])
    with st.expander("Particle release"), st.form("release_form"):
        seeds = st.text_area(
            "Locations, one longitude,latitude pair per line",
            f"{float(ds.lon.values[2 * len(ds.lon) // 3]):.4f},{float(ds.lat.mean()):.4f}",
        )
        end = st.selectbox(
            "End time (UTC)",
            range(len(ds.time)),
            index=len(ds.time) - 1,
            format_func=lambda i: str(ds.time.values[i])[:19],
        )
        method = st.selectbox("Particle integrator", ["rk4", "euler"])
        dt = st.number_input("Particle step (s)", min_value=1.0, value=900.0)
        if st.form_submit_button("Integrate particles"):
            releases = [
                list(map(float, line.split(",")))
                for line in seeds.splitlines()
                if line.strip()
            ]
            if not releases or any(len(s) != 2 for s in releases):
                raise ValueError("supply longitude,latitude pairs")
            flow = Current(ds)
            t0, t1 = flow.axes[0][[index, end]]
            with st.spinner("Integrating particle paths…"):
                tracks = ensemble(flow, releases, t0, t1, dt, method)
            st.session_state["overlay_id"] = uuid4().hex
            st.session_state["earth_tracks"] = tracks
            st.session_state["earth_particle_config"] = {
                "releases": releases,
                "start_s": t0,
                "end_s": t1,
                "dt_s": dt,
                "method": method,
            }
        if tracks:
            st.write([tr.status for tr in tracks])
    ow, sla, minimum = 0.0, 0.02, 4
    found = []
    if "sla" in d:
        with st.expander("Exploratory eddy candidates"):
            ow = (
                st.number_input("OW ceiling (10⁻¹⁰ s⁻²)", max_value=0.0, value=0.0)
                * 1e-10
            )
            sla = st.number_input("Minimum |SLA| (m)", min_value=0.0, value=0.02)
            minimum = st.number_input("Minimum connected cells", min_value=1, value=4)
            ckey = (index, ow, sla, minimum)
            cached = st.session_state.get("earth_candidates")
            if cached is None or cached[0] != ckey:
                cached = (ckey, candidates(d, ow, sla, minimum))
                st.session_state["earth_candidates"] = cached
            found = cached[1]
            st.write(f"{len(found)} candidates")
            if found:
                st.dataframe(found)
    match = st.session_state.get("earth_validation")
    if ds.attrs.get("source_kind") != "synthetic":
        with st.expander("Observed drifter comparison"):
            obs = st.text_input("NOAA GDP file", str(directory / "drifters.csv"))
            hours = st.number_input(
                "Observation horizon (hours)", min_value=1, max_value=168, value=24
            )
            if st.button("Compare observed tracks"):
                with st.spinner("Matching observed drifters…"):
                    report, rows = match_observations(ds, obs, hours, 900.0)
                st.session_state["overlay_id"] = uuid4().hex
                st.session_state["match_id"] = uuid4().hex
                match = (obs, hours, report, rows)
                st.session_state["earth_validation"] = match
            if match:
                panel(
                    "earth_separation_png",
                    st.session_state["match_id"],
                    lambda: separation_plot(match[2]),
                )
                st.write(f"Matched {match[2]['eligible']} tracks · {match[1]} h")
                st.dataframe(
                    [
                        dict(
                            method=k,
                            **{
                                n: v[n]
                                for n in (
                                    "mean_m",
                                    "rms_m",
                                    "final_mean_separation_m",
                                    "coverage",
                                )
                            },
                        )
                        for k, v in match[2]["methods"].items()
                    ]
                )

    display_limit = 640

    def build_map(limit=None):
        return regional_map(
            ds,
            d,
            name,
            index,
            tracks,
            found,
            match[3] if match else (),
            display_limit=limit,
        )

    panel(
        "earth_map_png",
        (
            st.session_state["earth_id"],
            index,
            name,
            ow,
            sla,
            minimum,
            st.session_state["overlay_id"],
        ),
        lambda: build_map(display_limit),
    )
    if max(d[name].shape) > display_limit:
        st.caption(
            f"Map preview samples at most {display_limit} cells per axis. Calculations, colour limits and exports use the full {ds.sizes['lon']} × {ds.sizes['lat']} grid."
        )
    with st.expander("Dataset provenance"):
        st.json(dict(ds.attrs))
    if st.button("Export Earth analysis"):
        out = root / "outputs" / ("earth-" + uuid4().hex[:12])
        analyze(
            ds,
            out,
            index,
            match[0] if match else None,
            match[1] if match else 24,
            900.0,
            ow,
            sla,
            minimum,
            tracks,
            st.session_state.get("earth_particle_config", {}),
            prepared=(d, found),
            matched=match[2:] if match else None,
        )
        build_map().savefig(out / "selected_field.png", dpi=140)
        st.code(str(out.resolve()))
