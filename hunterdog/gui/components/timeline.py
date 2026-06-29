from __future__ import annotations

from typing import Mapping

import streamlit as st


def timeline(events: list[Mapping[str, object]], limit: int = 8) -> None:
    if not events:
        st.caption("暂无日志")
        return

    for event in events[:limit]:
        timestamp = str(event.get("timestamp", "") or "")
        level = str(event.get("level", "") or "")
        message = str(event.get("message", "") or "")
        st.markdown(f"**{level}** · `{timestamp}`")
        st.caption(message)
