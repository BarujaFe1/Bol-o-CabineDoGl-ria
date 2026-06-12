from __future__ import annotations

import streamlit as st

def navigate_to(page: str, *, admin_mode: bool | None = None) -> None:
    """
    Centralized navigation function that updates current page and resets/synchronizes
    navigation keys across radio and selectbox controls before forcing a rerun.
    """
    st.session_state["nav_page"] = page
    if admin_mode is not None:
        st.session_state["admin_mode"] = admin_mode

    # We do NOT directly write to the widget keys (public_nav_radio_key, admin_nav_radio_key,
    # mobile_nav_selectbox_key) here because that raises a StreamlitAPIException if
    # the widget has already been instantiated on this run. Instead, the main script flow
    # in app.py handles setting these keys before drawing the widgets on the next rerun.
    st.rerun()
