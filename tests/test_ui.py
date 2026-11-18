"""Optional integration check. Core CI works without the ui extra."""

from pathlib import Path

import pytest


def test_lab_interactions():
    testing = pytest.importorskip("streamlit.testing.v1")
    app = testing.AppTest.from_file(Path("app.py").resolve(), default_timeout=30).run()
    assert not app.exception and "result" not in app.session_state
    app.button(key="run_lab").click().run()
    assert not app.exception
    runtime = app.session_state["result"].metadata["runtime_s"]
    app.selectbox(key="field").select("Potential vorticity").run()
    app.slider[0].set_value(2).run()
    app.checkbox[0].check().run()
    assert not app.exception
    assert app.session_state["result"].metadata["runtime_s"] == runtime
    app.number_input[0].set_value(40).run()
    assert app.warning and not app.exception
    app.button(key="run_lab").click().run()
    assert not app.warning and app.session_state["result"].config.nx == 40
    app.button(key="reset_lab").click().run()
    assert not app.exception and "result" not in app.session_state
