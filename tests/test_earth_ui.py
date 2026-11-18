from pathlib import Path

import pytest


def test_earth_mode():
    pytest.importorskip("xarray")
    t = pytest.importorskip("streamlit.testing.v1")
    app = t.AppTest.from_file(Path("app.py").resolve(), default_timeout=30).run()
    app.radio(key="lab_mode").set_value("Earth").run()
    next(w for w in app.selectbox if w.label == "Current source").select(
        "Synthetic verification fixture"
    ).run()
    next(w for w in app.button if w.label == "Load region").click().run()
    assert not app.exception and not app.error
    next(w for w in app.button if w.label == "Integrate particles").click().run()
    assert not app.exception and not app.error
    assert app.session_state["earth_tracks"][0].status == "completed"
    app.radio(key="lab_mode").set_value("Idealized simulation").run()
    assert app.button(key="run_lab")
