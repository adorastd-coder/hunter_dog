from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from hunterdog.pipeline import sheets_client


def check_ads() -> list[dict[str, Any]]:
    try:
        leads = sheets_client.get_leads()
    except Exception as exc:
        _log_failure(f"Ads check failed to read leads: {exc}")
        return []

    token = os.environ.get("META_ACCESS_TOKEN", "").strip()
    updated_rows: list[dict[str, Any]] = []
    for lead in leads:
        if _status(lead) not in {"ENRICHED", "SCORED"}:
            updated_rows.append(lead)
            continue
        if _row_value(lead, "ads_running").strip():
            updated_rows.append(lead)
            continue

        business_name = _row_value(lead, "name").strip()
        if not token:
            lead["ads_running"] = "unknown"
            updated_rows.append(lead)
            continue
        if not business_name:
            lead["ads_running"] = "unknown"
            updated_rows.append(lead)
            continue

        try:
            lead["ads_running"] = _ads_running_status(business_name, token)
        except Exception as exc:
            lead["ads_running"] = "unknown"
            _log_failure(f"Meta ads check failed for {_lead_label(lead)}: {exc}")
        updated_rows.append(lead)

    try:
        sheets_client.write_leads_batch(leads)
    except Exception as exc:
        _log_failure(f"Ads check failed to write leads: {exc}")
        return []

    if not token:
        _log_failure(
            "Ads check set ads_running=unknown: META_ACCESS_TOKEN environment variable is required."
        )
    _log_info(f"Ads check updated {len(updated_rows)} leads.")
    return updated_rows


def run() -> list[dict[str, Any]]:
    return check_ads()


def _ads_running_status(business_name: str, token: str) -> str:
    payload = _meta_ads_archive_response(business_name, token)
    data = payload.get("data")
    if not isinstance(data, list):
        return "unknown"
    return "true" if data else "false"


def _meta_ads_archive_response(business_name: str, token: str) -> dict[str, Any]:
    request = Request(
        _ads_archive_url(business_name),
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw_body = response.read().decode("utf-8")
    except HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        parsed_error = _try_parse_json_object(raw_body)
        if parsed_error and "error" in parsed_error:
            raise RuntimeError(_meta_error_message(parsed_error["error"])) from exc
        raise RuntimeError(f"Meta ads_archive HTTP error {exc.code}.") from exc
    except URLError as exc:
        reason = str(getattr(exc, "reason", exc)).strip()
        raise RuntimeError(f"Meta ads_archive request failed: {reason}") from exc

    parsed = _parse_json_object(raw_body)
    if parsed is None:
        raise ValueError("Meta ads_archive JSON response must be an object.")
    if "error" in parsed:
        raise RuntimeError(_meta_error_message(parsed["error"]))
    return parsed


def _parse_json_object(raw_body: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ValueError("Meta ads_archive returned invalid JSON.") from exc

    if not isinstance(parsed, dict):
        return None
    return parsed


def _try_parse_json_object(raw_body: str) -> dict[str, Any] | None:
    try:
        return _parse_json_object(raw_body)
    except ValueError:
        return None


def _ads_archive_url(business_name: str) -> str:
    query = urlencode(
        {
            "ad_active_status": "ACTIVE",
            "ad_reached_countries": '["ALL"]',
            "ad_type": "ALL",
            "fields": "id,page_id,page_name",
            "limit": "1",
            "search_terms": business_name,
        }
    )
    return f"https://graph.facebook.com/ads_archive?{query}"


def _meta_error_message(error: Any) -> str:
    if isinstance(error, dict):
        message = str(error.get("message", "")).strip()
        code = str(error.get("code", "")).strip()
        if message and code:
            return f"Meta API error {code}: {message}"
        if message:
            return f"Meta API error: {message}"
    return "Meta API returned an error response."


def _status(lead: dict[str, Any]) -> str:
    return _row_value(lead, "status").strip().upper()


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
