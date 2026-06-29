from __future__ import annotations

import html

import streamlit as st


def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(
        (
            "<div class='hd-header'>"
            f"<h1>{html.escape(title)}</h1>"
            f"<div class='hd-subtitle'>{html.escape(subtitle)}</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
