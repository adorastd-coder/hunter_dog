from __future__ import annotations

import html


def status_badge(status: str) -> str:
    value = str(status or "UNKNOWN").strip().upper()
    colors = {
        "SCRAPED": ("#5b8def", "rgba(91,141,239,.16)"),
        "ENRICHED": ("#8fb95b", "rgba(143,185,91,.16)"),
        "SCORED": ("#d9a441", "rgba(217,164,65,.16)"),
        "EMAIL_READY": ("#a477d5", "rgba(164,119,213,.16)"),
        "SENT": ("#26a269", "rgba(38,162,105,.16)"),
        "REPLIED": ("#36c2b4", "rgba(54,194,180,.16)"),
    }
    border, background = colors.get(value, ("#9aa4b2", "rgba(154,164,178,.12)"))
    return (
        f"<span class='hd-badge' style='color:{border};"
        f"background:{background};border-color:{border};'>{html.escape(value)}</span>"
    )


def bucket_badge(bucket: str) -> str:
    value = str(bucket or "-").strip().upper()
    colors = {
        "A+": "#26a269",
        "A": "#49a86d",
        "B": "#5b8def",
        "C": "#d9a441",
        "D": "#df7d45",
        "E": "#e05d5d",
    }
    color = colors.get(value, "#9aa4b2")
    return (
        f"<span class='hd-badge' style='color:{color};"
        f"background:rgba(255,255,255,.04);border-color:{color};'>{html.escape(value)}</span>"
    )
