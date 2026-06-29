from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any

from hunterdog.pipeline import config as pipeline_config
from hunterdog.pipeline import sheets_client


@dataclass(frozen=True, slots=True)
class LighthouseResult:
    page_speed_score: int
    mobile_friendly: bool


def check_speed() -> list[dict[str, Any]]:
    try:
        runtime_config = pipeline_config.get_config()
        leads = sheets_client.get_leads()
    except Exception as exc:
        _log_failure(f"Speed check failed to initialize: {exc}")
        return []

    updated_rows: list[dict[str, Any]] = []
    audits_run = 0

    for lead in leads:
        if audits_run >= runtime_config.LIGHTHOUSE_MAX_PER_RUN:
            break
        if _status(lead) != "ENRICHED":
            continue
        if _already_checked(lead):
            continue

        website = _row_value(lead, "website").strip()
        if not website:
            continue

        audits_run += 1
        normalized_website = _normalize_url(website)
        try:
            result = _run_lighthouse(normalized_website)
        except Exception as exc:
            _log_failure(f"Lighthouse failed for {_lead_label(lead)}: {exc}")
            continue

        lead["website"] = normalized_website
        lead["page_speed_score"] = result.page_speed_score
        lead["mobile_friendly"] = result.mobile_friendly
        updated_rows.append(lead)

    try:
        sheets_client.write_leads_batch(leads)
    except Exception as exc:
        _log_failure(f"Speed check failed to write leads: {exc}")
        return []

    _log_info(f"Speed check audited {audits_run} leads; updated {len(updated_rows)} leads.")
    return updated_rows


def run() -> list[dict[str, Any]]:
    return check_speed()


def _run_lighthouse(url: str) -> LighthouseResult:
    completed = subprocess.run(
        _lighthouse_command(url),
        capture_output=True,
        check=False,
        text=True,
        timeout=180,
    )
    if completed.returncode != 0:
        error_text = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(error_text or f"npx lighthouse exited with {completed.returncode}")

    report = _parse_lighthouse_json(completed.stdout)
    return LighthouseResult(
        page_speed_score=_performance_score(report),
        mobile_friendly=_mobile_friendly(report),
    )


def _lighthouse_command(url: str) -> list[str]:
    return [
        "npx",
        "lighthouse",
        url,
        "--output=json",
        "--output-path=stdout",
        "--quiet",
        "--form-factor=mobile",
        "--chrome-flags=--headless --no-sandbox",
    ]


def _parse_lighthouse_json(output: str) -> dict[str, Any]:
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ValueError("Lighthouse did not return valid JSON output.") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Lighthouse JSON output must be an object.")
    return parsed


def _performance_score(report: dict[str, Any]) -> int:
    categories = report.get("categories", {})
    if not isinstance(categories, dict):
        raise ValueError("Lighthouse report missing categories.")

    performance = categories.get("performance", {})
    if not isinstance(performance, dict):
        raise ValueError("Lighthouse report missing performance category.")

    raw_score = performance.get("score")
    if not isinstance(raw_score, int | float):
        raise ValueError("Lighthouse performance score is missing.")

    return round(float(raw_score) * 100)


def _mobile_friendly(report: dict[str, Any]) -> bool:
    audits = report.get("audits", {})
    if not isinstance(audits, dict):
        return False

    mobile_audit_ids = ("viewport", "content-width", "tap-targets", "font-size")
    scored_audits = [_audit_score(audits, audit_id) for audit_id in mobile_audit_ids]
    available_scores = [score for score in scored_audits if score is not None]
    if not available_scores:
        return False
    return all(score == 1 for score in available_scores)


def _audit_score(audits: dict[str, Any], audit_id: str) -> float | None:
    audit = audits.get(audit_id)
    if not isinstance(audit, dict):
        return None

    score = audit.get("score")
    if isinstance(score, int | float):
        return float(score)
    return None


def _normalize_url(url: str) -> str:
    if url.startswith(("http://", "https://")):
        return url
    return f"https://{url}"


def _status(lead: dict[str, Any]) -> str:
    return _row_value(lead, "status").strip().upper()


def _already_checked(lead: dict[str, Any]) -> bool:
    return (
        _row_value(lead, "page_speed_score").strip() != ""
        and _row_value(lead, "mobile_friendly").strip() != ""
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
