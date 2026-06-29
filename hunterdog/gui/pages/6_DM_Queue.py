from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from hunterdog.gui.components.css import inject_css
from hunterdog.gui.components.data import read_config, read_leads, write_leads
from hunterdog.gui.components.header import page_header

inject_css()


@st.cache_data(ttl=60)
def load_leads() -> list[dict[str, object]]:
    return read_leads()


@st.cache_data(ttl=60)
def load_config() -> dict[str, str]:
    return read_config()


def dm_script(lead: dict[str, object]) -> str:
    name = str(lead.get("name", "there") or "there")
    return f"Hi {name}, quick note: I noticed a few growth opportunities and can share a free 20-minute audit."


page_header("私信队列", "按社交链接处理待发送私信")
leads = load_leads()
config = load_config()
today = date.today().isoformat()
target = int(config.get("DAILY_LIMIT", 0) or 0)
sent_today = sum(1 for lead in leads if str(lead.get("dm_sent_date", "")) == today)
st.progress(min(sent_today / target, 1.0) if target else 0, text=f"今日已DM {sent_today}/{target}")

queue = [
    lead for lead in leads
    if str(lead.get("status", "")).upper() in {"SCORED", "EMAIL_READY", "SENT"}
    and not lead.get("dm_sent_date")
    and str(lead.get("dm_skip_until", "")) <= today
    and (lead.get("instagram") or lead.get("facebook") or lead.get("linkedin"))
]

if not queue:
    st.markdown("<div style='font-size:3rem'>🐕</div>", unsafe_allow_html=True)
    st.info("今天没有待处理私信")
    st.stop()

for index in range(0, len(queue), 2):
    columns = st.columns(2)
    for lead, column in zip(queue[index:index + 2], columns):
        with column:
            st.markdown(f"<div class='hd-card'><b>{lead.get('name', '-')}</b><br>评分：{lead.get('score', '-')}</div>", unsafe_allow_html=True)
            st.caption(f"Instagram: {lead.get('instagram', '-')}")
            st.caption(f"Facebook: {lead.get('facebook', '-')}")
            script = dm_script(lead)
            st.code(script, language="text")
            st.components.v1.html(
                f"<button onclick=\"navigator.clipboard.writeText({script!r})\">复制DM脚本</button>",
                height=36,
            )
            if st.button("标记已发送", key=f"dm_sent_{index}_{lead.get('name')}"):
                for row in leads:
                    if row.get("name") == lead.get("name"):
                        row["dm_sent_date"] = today
                        break
                write_leads(leads)
                st.rerun()
            if st.button("跳过", key=f"dm_skip_{index}_{lead.get('name')}"):
                for row in leads:
                    if row.get("name") == lead.get("name"):
                        row["dm_skip_until"] = (date.today() + timedelta(days=1)).isoformat()
                        break
                write_leads(leads)
                st.rerun()
