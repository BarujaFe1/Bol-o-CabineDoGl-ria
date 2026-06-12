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

    # Synchronize keys with radio/selectbox widgets to prevent mismatch warnings
    for key in ["public_nav_radio_key", "admin_nav_radio_key", "mobile_nav_selectbox_key"]:
        if key in st.session_state:
            st.session_state[key] = page

    st.rerun()
