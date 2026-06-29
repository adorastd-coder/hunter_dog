from __future__ import annotations

from datetime import date

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from hunterdog.gui.components.css import inject_css
from hunterdog.gui.components.data import read_config, read_leads, read_run_log, trigger_github_workflow, write_config
from hunterdog.gui.components.header import page_header
from hunterdog.gui.components.kpi_card import kpi_card
from hunterdog.gui.components.timeline import timeline

inject_css()


@st.cache_data(ttl=60)
def load_config() -> dict[str, str]:
    return read_config()


@st.cache_data(ttl=60)
def load_leads() -> list[dict[str, object]]:
    return read_leads()


@st.cache_data(ttl=60)
def load_logs() -> list[dict[str, str]]:
    return read_run_log(limit=8)


def today_sent(leads: list[dict[str, object]]) -> int:
    today = date.today().isoformat()
    return sum(1 for lead in leads if str(lead.get("sent_date", "")) == today)


def reply_rate(leads: list[dict[str, object]]) -> str:
    sent = sum(1 for lead in leads if str(lead.get("status", "")).upper() in {"SENT", "REPLIED"})
    replied = sum(1 for lead in leads if str(lead.get("status", "")).upper() == "REPLIED")
    return f"{round(replied / sent * 100, 1)}%" if sent else "0%"


page_header("活动控制", "管理发送状态、关键参数和手动运行")
config = load_config()
leads = load_leads()
status = str(config.get("CAMPAIGN_STATUS", "PAUSED")).upper()

banner_class = "hd-running" if status != "PAUSED" else "hd-paused"
banner_text = "运行中" if status != "PAUSED" else "已暂停"
st.markdown(f"<div class='hd-banner {banner_class}'>当前活动：{banner_text}</div>", unsafe_allow_html=True)
if st.button("切换活动状态", type="primary"):
    write_config({"CAMPAIGN_STATUS": "PAUSED" if status != "PAUSED" else "ACTIVE"})
    st.rerun()

top_left, top_right = st.columns(2)
with top_left:
    kpi_card("今日发送", today_sent(leads))
    kpi_card("热门线索", sum(1 for lead in leads if str(lead.get("bucket", "")).upper() in {"A+", "A"}))
with top_right:
    kpi_card("回复数", sum(1 for lead in leads if str(lead.get("status", "")).upper() == "REPLIED"))
    kpi_card("回复率", reply_rate(leads))

left, right = st.columns(2)
with left:
    st.subheader("快速配置")
    daily_limit = st.number_input("发送上限", min_value=0, value=int(config.get("DAILY_LIMIT", 0) or 0))
    gap_min = st.number_input("最小间隔秒", min_value=0, value=int(config.get("GAP_MIN", 0) or 0))
    gap_max = st.number_input("最大间隔秒", min_value=0, value=int(config.get("GAP_MAX", 0) or 0))
    min_score = st.number_input("最低评分", min_value=0, max_value=100, value=int(config.get("MIN_SCORE", 0) or 0))
    city = st.text_input("目标城市", value=str(config.get("TARGET_CITY", "")))
    if st.button("保存配置", type="primary"):
        write_config(
            {
                "DAILY_LIMIT": daily_limit,
                "GAP_MIN": gap_min,
                "GAP_MAX": gap_max,
                "MIN_SCORE": min_score,
                "TARGET_CITY": city,
            }
        )
        st.success("已保存")

with right:
    st_autorefresh(interval=60_000, key="campaign_log_refresh")
    st.subheader("活动日志")
    timeline(load_logs(), limit=8)

st.divider()
if st.button("立即运行 Pipeline", type="primary"):
    ok, message = trigger_github_workflow()
    st.success(message) if ok else st.error(message)
