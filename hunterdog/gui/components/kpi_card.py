from __future__ import annotations

import html

import streamlit as st


def kpi_card(label: str, value: str | int | float, delta: str = "") -> None:
    st.markdown(
        (
            "<div class='hd-card'>"
            f"<div class='hd-kpi-label'>{html.escape(str(label))}</div>"
            f"<div class='hd-kpi-value'>{html.escape(str(value))}</div>"
            f"<div class='hd-kpi-delta'>{html.escape(str(delta))}</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
