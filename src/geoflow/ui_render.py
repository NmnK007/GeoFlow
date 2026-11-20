"""Session-local PNGs keep interactive reruns independent of Matplotlib figures."""

from io import BytesIO
from threading import RLock

import streamlit as st


@st.cache_resource
def render_lock():
    return RLock()


def png(build):
    with render_lock():
        fig = build()
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=120)
        return buf.getvalue()


def panel(slot, key, build):
    previous = st.session_state.get(slot)
    if previous is None or previous[0] != key:
        previous = (key, png(build))
        st.session_state[slot] = previous
    st.image(previous[1])
    return previous[1]
