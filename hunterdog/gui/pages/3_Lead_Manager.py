from __future__ import annotations

import pandas as pd
import streamlit as st

from hunterdog.gui.components.badges import bucket_badge, status_badge
from hunterdog.gui.components.css import inject_css
from hunterdog.gui.components.data import read_leads, write_leads
from hunterdog.gui.components.header import page_header

inject_css()


@st.cache_data(ttl=60)
def load_leads() -> list[dict[str, object]]:
    return read_leads()


def score_value(lead: dict[str, object]) -> int:
    try:
        return int(float(str(lead.get("score", "") or 0)))
    except ValueError:
        return 0


def filtered_leads(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    search = st.session_state.get("lead_search", "").lower().strip()
    status_filter = st.session_state.get("status_filter", "全部")
    bucket_filter = st.session_state.get("bucket_filter", "全部")
    min_score, max_score = st.session_state.get("score_filter", (0, 100))

    result = []
    for lead in rows:
        haystack = f"{lead.get('name', '')} {lead.get('email', '')}".lower()
        if search and search not in haystack:
            continue
        if status_filter != "全部" and str(lead.get("status", "")).upper() != status_filter:
            continue
        if bucket_filter != "全部" and str(lead.get("bucket", "")).upper() != bucket_filter:
            continue
        if not min_score <= score_value(lead) <= max_score:
            continue
        result.append(lead)
    return result


page_header("线索管理", "筛选、查看、编辑和批量处理线索")
leads = load_leads()

left, right = st.columns(2)
with left:
    st.text_input("搜索名称/邮箱", key="lead_search")
    st.selectbox("状态筛选", ["全部", "SCRAPED", "ENRICHED", "SCORED", "EMAIL_READY", "SENT", "REPLIED"], key="status_filter")
with right:
    st.selectbox("桶筛选", ["全部", "A+", "A", "B", "C", "D", "E"], key="bucket_filter")
    st.slider("评分范围", 0, 100, (0, 100), key="score_filter")

visible = filtered_leads(leads)
df = pd.DataFrame(visible)
st.download_button("导出CSV", df.to_csv(index=False).encode("utf-8"), "hunterdog_leads.csv", "text/csv")

if df.empty:
    st.info("没有匹配的线索")
    st.stop()

display_columns = [column for column in ["name", "email", "status", "bucket", "score", "phone", "website"] if column in df.columns]
selection = st.dataframe(
    df[display_columns],
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode=["single-row", "multi-row"],
)
selected_indexes = selection.selection.rows if selection else []

if selected_indexes:
    st.subheader("批量操作")
    batch_left, batch_right = st.columns(2)
    with batch_left:
        new_status = st.selectbox("批量改状态", ["SCRAPED", "ENRICHED", "SCORED", "EMAIL_READY", "SENT", "REPLIED"])
        if st.button("应用状态"):
            selected_keys = {(visible[index].get("name"), visible[index].get("email")) for index in selected_indexes}
            for lead in leads:
                if (lead.get("name"), lead.get("email")) in selected_keys:
                    lead["status"] = new_status
            write_leads(leads)
            st.rerun()
    with batch_right:
        if st.button("删除选中"):
            selected_keys = {(visible[index].get("name"), visible[index].get("email")) for index in selected_indexes}
            write_leads([lead for lead in leads if (lead.get("name"), lead.get("email")) not in selected_keys])
            st.rerun()

    lead = visible[selected_indexes[0]]
    st.subheader("详情面板")
    st.markdown(status_badge(str(lead.get("status", ""))) + " " + bucket_badge(str(lead.get("bucket", ""))), unsafe_allow_html=True)
    edit_mode = st.toggle("编辑模式")
    detail_left, detail_right = st.columns(2)
    editable_keys = ["name", "address", "phone", "email", "website", "score", "bucket", "status", "page_speed_score", "mobile_friendly"]
    edited: dict[str, object] = {}
    for index, key in enumerate(editable_keys):
        target = detail_left if index % 2 == 0 else detail_right
        with target:
            if edit_mode:
                edited[key] = st.text_input(key, value=str(lead.get(key, "") or ""), key=f"edit_{key}")
            else:
                st.write(f"**{key}**")
                st.caption(str(lead.get(key, "") or "-"))
    if edit_mode and st.button("保存详情", type="primary"):
        for row in leads:
            if row.get("name") == lead.get("name") and row.get("email") == lead.get("email"):
                row.update(edited)
                break
        write_leads(leads)
        st.rerun()

st.subheader("移动端卡片")
for lead in visible[:10]:
    st.markdown(
        f"<div class='hd-mobile-card'><b>{lead.get('name', '-')}</b><br>{lead.get('email', '-')}<br>{status_badge(str(lead.get('status', '')))}</div>",
        unsafe_allow_html=True,
    )
