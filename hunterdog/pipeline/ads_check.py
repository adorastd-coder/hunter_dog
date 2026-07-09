from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus

from playwright.sync_api import Page, sync_playwright

from hunterdog.pipeline import sheets_client


_RESULTS_COUNT_PATTERN = re.compile(r"~?\s*([\d,]+)\s+results?", re.IGNORECASE)
_NO_RESULTS_PATTERN = re.compile(
    r"no ads match your search|0\s+results", re.IGNORECASE
)


def check_ads() -> list[dict[str, Any]]:
    try:
        leads = sheets_client.get_leads()
    except Exception as exc:
        _log_failure(f"Ads check failed to read leads: {exc}")
        return []

    updated_rows: list[dict[str, Any]] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/115.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            try:
                for lead in leads:
                    business_name = _row_value(lead, "name").strip()
                    if not business_name:
                        lead["ads_running"] = "unknown"
                        updated_rows.append(lead)
                        continue

                    try:
                        lead["ads_running"] = _ads_running_status(page, business_name)
                    except Exception as exc:
                        lead["ads_running"] = "unknown"
                        _log_failure(
                            f"Meta ads check failed for {_lead_label(lead)}: {exc}"
                        )
                    updated_rows.append(lead)
            finally:
                page.close()
                browser.close()
    except Exception as exc:
        _log_failure(f"Ads check browser session failed: {exc}")
        for lead in leads[len(updated_rows):]:
            lead["ads_running"] = "unknown"
            updated_rows.append(lead)

    try:
        sheets_client.write_leads_batch(leads)
    except Exception as exc:
        _log_failure(f"Ads check failed to write leads: {exc}")
        return []

    _log_info(f"Ads check updated {len(updated_rows)} leads.")
    return updated_rows


def run() -> list[dict[str, Any]]:
    return check_ads()


def _ads_running_status(page: Page, business_name: str) -> str:
    page.goto(_ad_library_url(business_name), wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)

    body_text = page.locator("body").inner_text(timeout=15000)

    if _NO_RESULTS_PATTERN.search(body_text):
        return "false"

    match = _RESULTS_COUNT_PATTERN.search(body_text)
    if match:
        count = int(match.group(1).replace(",", ""))
        return "true" if count > 0 else "false"

    return "unknown"


def _ad_library_url(business_name: str) -> str:
    return (
        "https://www.facebook.com/ads/library/"
        "?active_status=active&ad_type=all&country=ALL"
        f"&q={quote_plus(business_name)}"
        "&search_type=keyword_unordered&media_type=all"
    )


def _row_value(row: dict[str, Any], key: str) -> str:
    for candidate in (key, key.title(), key.upper()):
        if candidate in row:
            return str(row.get(candidate, "") or "")
    return ""


def _lead_label(lead: dict[str, Any]) -> str:
    name = _row_value(lead, "name").strip()
    website = _row_value(lead, "website").strip()
    return name or website or "unknown lead"


def _log_info(message: str) -> None:
    try:
        sheets_client.log_run(message=message, level="INFO")
    except Exception:
        pass


def _log_failure(message: str) -> None:
    try:
        sheets_client.log_run(message=message, level="ERROR")
    except Exception:
        pass
