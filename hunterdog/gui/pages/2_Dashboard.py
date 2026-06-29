from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from hunterdog.gui.components.css import inject_css
from hunterdog.gui.components.data import read_leads, read_run_log
from hunterdog.gui.components.header import page_header
from hunterdog.gui.components.kpi_card import kpi_card

inject_css()


@st.cache_data(ttl=60)
def load_leads() -> list[dict[str, object]]:
    return read_leads()


@st.cache_data(ttl=60)
def load_logs() -> list[dict[str, str]]:
    return read_run_log(limit=7)


def within_range(lead: dict[str, object], label: str) -> bool:
    if label == "全部":
        return True
    days = {"今天": 0, "7天": 7, "30天": 30}[label]
    raw = str(lead.get("sent_date") or lead.get("scrapedAt") or "")
    try:
        item_date = datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return label != "今天"
    return item_date >= date.today() - timedelta(days=days)


page_header("数据总览", "漏斗、桶分布和最近活动")
range_label = st.radio("日期筛选", ["今天", "7天", "30天", "全部"], horizontal=True)
leads = [lead for lead in load_leads() if within_range(lead, range_label)]
statuses = ["SCRAPED", "ENRICHED", "SCORED", "EMAIL_READY", "SENT", "REPLIED"]
counts = {status: sum(1 for lead in leads if str(lead.get("status", "")).upper() == status) for status in statuses}

for row in range(0, 6, 2):
    left, right = st.columns(2)
    with left:
        kpi_card(statuses[row], counts[statuses[row]])
    with right:
        kpi_card(statuses[row + 1], counts[statuses[row + 1]])

left, right = st.columns(2)
with left:
    funnel_df = pd.DataFrame({"stage": statuses, "count": [counts[status] for status in statuses]})
    fig = px.bar(funnel_df, x="count", y="stage", orientation="h", template="plotly_dark")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

with right:
    bucket_order = ["A+", "A", "B", "C", "D", "E"]
    bucket_df = pd.DataFrame(
        {
            "bucket": bucket_order,
            "count": [sum(1 for lead in leads if str(lead.get("bucket", "")).upper() == bucket) for bucket in bucket_order],
        }
    )
    fig = px.pie(bucket_df, names="bucket", values="count", hole=.55, template="plotly_dark")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

bottom_left, bottom_right = st.columns(2)
with bottom_left:
    st.subheader("最近回复")
    replies = [lead for lead in leads if str(lead.get("status", "")).upper() == "REPLIED"]
    st.dataframe(pd.DataFrame(replies[-10:]), use_container_width=True)
with bottom_right:
    st.subheader("最近7次运行")
    st.dataframe(pd.DataFrame(load_logs()), use_container_width=True)
