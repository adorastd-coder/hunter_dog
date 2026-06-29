from __future__ import annotations

import streamlit as st

from hunterdog.gui.components.css import inject_css
from hunterdog.gui.components.data import read_config, upload_flyer_to_drive, write_config
from hunterdog.gui.components.header import page_header

inject_css()


@st.cache_data(ttl=60)
def load_config() -> dict[str, str]:
    return read_config()


page_header("传单管理", "上传传单并分配给桶")
config = load_config()
buckets = ["A+", "A", "B", "C", "D", "E"]

left, right = st.columns(2)
with left:
    uploaded = st.file_uploader("上传PNG/JPG/PDF", type=["png", "jpg", "jpeg", "pdf"])
with right:
    target_bucket = st.selectbox("分配到桶", buckets)
    if uploaded and st.button("上传到Google Drive", type="primary"):
        try:
            url = upload_flyer_to_drive(uploaded, target_bucket)
            write_config({f"FLYER_{target_bucket.replace('+', 'PLUS')}_URL": url})
            st.success("已上传")
        except Exception as exc:
            st.error(str(exc))

st.subheader("传单网格")
for row in range(0, len(buckets), 2):
    col1, col2 = st.columns(2)
    for bucket, column in zip(buckets[row:row + 2], [col1, col2]):
        with column:
            config_key = f"FLYER_{bucket.replace('+', 'PLUS')}_URL"
            url = config.get(config_key, "")
            st.markdown(f"**桶 {bucket}**")
            if url:
                if url.lower().endswith((".png", ".jpg", ".jpeg")):
                    st.image(url, use_container_width=True)
                else:
                    st.link_button("打开传单", url)
            else:
                st.caption("未分配")

st.subheader("分配状态")
summary = {bucket: "已分配" if config.get(f"FLYER_{bucket.replace('+', 'PLUS')}_URL") else "未分配" for bucket in buckets}
st.dataframe(summary, use_container_width=True)
