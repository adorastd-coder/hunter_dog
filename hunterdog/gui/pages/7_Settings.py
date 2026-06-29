from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from hunterdog.gui.components.css import inject_css
from hunterdog.gui.components.data import clear_leads, clear_run_log, read_config, read_leads, read_run_log, write_config, write_leads
from hunterdog.gui.components.header import page_header

inject_css()


@st.cache_data(ttl=60)
def load_config() -> dict[str, str]:
    return read_config()


@st.cache_data(ttl=60)
def load_leads() -> list[dict[str, object]]:
    return read_leads()


@st.cache_data(ttl=60)
def load_logs() -> list[dict[str, str]]:
    return read_run_log(limit=50)


@st.dialog("确认危险操作")
def confirm_dialog(action: str) -> None:
    value = st.text_input("输入 CONFIRM")
    if st.button("确认执行", type="primary") and value == "CONFIRM":
        if action == "reset":
            leads = load_leads()
            for lead in leads:
                lead["status"] = "SCRAPED"
            write_leads(leads)
        elif action == "clear_leads":
            clear_leads()
        elif action == "clear_logs":
            clear_run_log()
        st.rerun()


def secret_ok(key: str) -> str:
    try:
        return "正常" if st.secrets.get(key, "") else "缺失"
    except Exception:
        return "缺失"


page_header("系统设置", "API健康检查、配置编辑和危险操作")
config = load_config()
leads = load_leads()

left, right = st.columns(2)
with left:
    st.subheader("API健康检查")
    checks = {
        "Sheets": secret_ok("GOOGLE_CREDS_JSON"),
        "Gmail": "正常" if secret_ok("GMAIL_USER") == "正常" and secret_ok("GMAIL_APP_PASSWORD") == "正常" else "缺失",
        "Groq": secret_ok("GROQ_API_KEY"),
        "Meta": secret_ok("META_ACCESS_TOKEN"),
        "GitHub": secret_ok("GITHUB_TOKEN"),
    }
    if st.button("测试API"):
        st.dataframe(pd.DataFrame([{"service": key, "status": value} for key, value in checks.items()]), use_container_width=True)

with right:
    st.subheader("Sheets信息")
    st.metric("线索行数", len(leads))
    logs = load_logs()
    st.metric("最后同步", logs[0].get("timestamp", "-") if logs else "-")

st.subheader("CONFIG编辑器")
config_df = pd.DataFrame([{"key": key, "value": value} for key, value in config.items()])
edited = st.data_editor(config_df, use_container_width=True, num_rows="dynamic")
if st.button("保存CONFIG", type="primary"):
    write_config(dict(zip(edited["key"], edited["value"])))
    st.success("已保存")

with st.expander("运行日志", expanded=False):
    st.dataframe(pd.DataFrame(load_logs()), use_container_width=True)

st.subheader("危险区")
danger_left, danger_right = st.columns(2)
with danger_left:
    if st.button("重置线索状态"):
        confirm_dialog("reset")
    if st.button("清空线索"):
        confirm_dialog("clear_leads")
with danger_right:
    if st.button("清空日志"):
        confirm_dialog("clear_logs")
