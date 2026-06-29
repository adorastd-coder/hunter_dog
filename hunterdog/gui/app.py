from __future__ import annotations

import streamlit as st

from hunterdog.gui.components.css import inject_css
from hunterdog.gui.components.data import configure_secrets
from hunterdog.gui.components.header import page_header
from hunterdog.gui.components.kpi_card import kpi_card

inject_css()
configure_secrets()


@st.cache_data(ttl=60)
def load_summary() -> tuple[int, int, int]:
    from hunterdog.gui.components.data import read_leads

    leads = read_leads()
    sent = sum(1 for lead in leads if str(lead.get("status", "")).upper() == "SENT")
    replied = sum(1 for lead in leads if str(lead.get("status", "")).upper() == "REPLIED")
    ready = sum(1 for lead in leads if str(lead.get("status", "")).upper() == "EMAIL_READY")
    return sent, replied, ready


page_header("Hunter Dog", "销售线索自动化控制台")
sent_count, replied_count, ready_count = load_summary()

left, right = st.columns(2)
with left:
    kpi_card("已发送", sent_count)
    kpi_card("待发送", ready_count)
with right:
    kpi_card("已回复", replied_count)
    rate = f"{round(replied_count / sent_count * 100, 1)}%" if sent_count else "0%"
    kpi_card("回复率", rate)

st.markdown("使用左侧页面进入活动控制、数据总览、线索管理和系统设置。")
