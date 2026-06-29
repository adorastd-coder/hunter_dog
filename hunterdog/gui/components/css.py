from __future__ import annotations

import streamlit as st


def inject_css() -> None:
    st.set_page_config(page_title="Hunter Dog", page_icon="HD", layout="wide")
    st.markdown(
        """
        <style>
        :root {
          --hd-bg: #0f1216;
          --hd-panel: #171b21;
          --hd-panel-2: #1f252d;
          --hd-text: #eef2f7;
          --hd-muted: #9aa4b2;
          --hd-border: #303844;
          --hd-green: #26a269;
          --hd-red: #e05d5d;
          --hd-amber: #d9a441;
          --hd-blue: #5b8def;
        }
        .block-container { padding-top: 1.4rem; max-width: 1240px; }
        [data-testid="stSidebar"] { background: #12161b; }
        .hd-header { margin-bottom: 1rem; }
        .hd-header h1 { font-size: 1.7rem; margin: 0; letter-spacing: 0; }
        .hd-subtitle { color: var(--hd-muted); margin-top: .25rem; }
        .hd-card {
          border: 1px solid var(--hd-border);
          background: var(--hd-panel);
          border-radius: 8px;
          padding: 1rem;
          min-height: 92px;
        }
        .hd-kpi-label { color: var(--hd-muted); font-size: .82rem; }
        .hd-kpi-value { color: var(--hd-text); font-size: 1.65rem; font-weight: 700; }
        .hd-kpi-delta { color: var(--hd-muted); font-size: .8rem; margin-top: .25rem; }
        .hd-badge {
          display: inline-block;
          padding: .2rem .5rem;
          border-radius: 999px;
          font-size: .78rem;
          border: 1px solid transparent;
          white-space: nowrap;
        }
        .hd-banner {
          padding: .9rem 1rem;
          border-radius: 8px;
          font-weight: 700;
          margin-bottom: 1rem;
        }
        .hd-running { background: rgba(38, 162, 105, .16); border: 1px solid rgba(38, 162, 105, .5); }
        .hd-paused { background: rgba(224, 93, 93, .16); border: 1px solid rgba(224, 93, 93, .5); }
        .hd-table-note { color: var(--hd-muted); font-size: .85rem; }
        .hd-mobile-card { border: 1px solid var(--hd-border); border-radius: 8px; padding: .85rem; margin-bottom: .75rem; }
        .stPlotlyChart { background: transparent; }
        button[kind="primary"] { border-radius: 8px; }
        </style>
        """,
        unsafe_allow_html=True,
    )
