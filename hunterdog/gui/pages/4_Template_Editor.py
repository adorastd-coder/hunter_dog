from __future__ import annotations

import re

import streamlit as st

from hunterdog.gui.components.css import inject_css
from hunterdog.gui.components.data import read_config, read_leads, write_config
from hunterdog.gui.components.header import page_header

inject_css()


@st.cache_data(ttl=60)
def load_config() -> dict[str, str]:
    return read_config()


@st.cache_data(ttl=60)
def load_leads() -> list[dict[str, object]]:
    return read_leads()


def fill_preview(template: str, lead: dict[str, object]) -> str:
    values = {str(key).lower(): str(value or "") for key, value in lead.items()}
    values.setdefault("first_name", str(lead.get("name", "")).split(" ")[0])
    values.setdefault("business_name", str(lead.get("name", "")))
    values.setdefault("ai_opening", "我注意到你们的线上展示还有提升空间。")
    values.setdefault("opening_line", values["ai_opening"])

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip().lower()
        return values.get(key, "")

    return re.sub(r"{([^{}]+)}", replace, template)


page_header("邮件模板", "按桶编辑主题和正文")
config = load_config()
leads = load_leads()
sample = leads[0] if leads else {"name": "Sample Clinic", "email": "owner@example.com", "score": "88"}

tabs = st.tabs(["A+", "A", "B", "C", "D", "E"])
for bucket, tab in zip(["A+", "A", "B", "C", "D", "E"], tabs):
    key_bucket = "A" if bucket == "A+" else bucket
    subject_key = f"TEMPLATE_{key_bucket}_SUBJECT"
    body_key = f"TEMPLATE_{key_bucket}_BODY"
    with tab:
        left, right = st.columns(2)
        with left:
            subject = st.text_input("主题行", value=config.get(subject_key, ""), key=f"{bucket}_subject")
            body = st.text_area("正文", value=config.get(body_key, ""), height=360, key=f"{bucket}_body")
            if st.button("保存模板", key=f"{bucket}_save", type="primary"):
                write_config({subject_key: subject, body_key: body})
                st.success("已保存")
        with right:
            st.subheader("实时预览")
            st.write(f"**{fill_preview(subject, sample)}**")
            st.markdown(fill_preview(body, sample).replace("\n", "  \n"))
            st.caption("{first_name} {business_name} {ai_opening} {opening_line} {score} {city}")
