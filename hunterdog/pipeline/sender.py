from __future__ import annotations

import os
import random
import smtplib
import time
from datetime import date
from email.mime.text import MIMEText
from typing import Any, Mapping

from hunterdog.pipeline import config as pipeline_config
from hunterdog.pipeline import sheets_client


def send_pending_emails() -> list[dict[str, Any]]:
    try:
        runtime_config = pipeline_config.get_config()
        leads = sheets_client.get_leads()
    except Exception as exc:
        _log_failure(f"Sender failed to initialize: {exc}")
        return []

    if runtime_config.CAMPAIGN_STATUS.strip().upper() == "PAUSED":
        _log_info("Sender skipped because CAMPAIGN_STATUS is PAUSED.")
        return []

    try:
        gmail_user = _gmail_user()
        gmail_app_password = _gmail_app_password()
    except Exception as exc:
        _log_failure(f"Sender credentials failed: {exc}")
        return []

    today = date.today().isoformat()
    daily_cap = _daily_send_cap(leads, runtime_config.RAMP_STEP, runtime_config.DAILY_LIMIT)
    already_sent_today = _sent_count_for_date(leads, today)
    remaining_today = max(daily_cap - already_sent_today, 0)
    pending_leads = _pending_leads(leads, runtime_config.MIN_SCORE, remaining_today)

    sent_rows: list[dict[str, Any]] = []
    failure_messages: list[str] = []
    for index, lead in enumerate(pending_leads, start=1):
        try:
            send_email(
                to_email=_row_value(lead, "email").strip(),
                subject=_email_subject(lead),
                body=_email_body(lead),
                gmail_user=gmail_user,
                gmail_app_password=gmail_app_password,
            )
        except Exception as exc:
            failure_messages.append(f"Sender failed for {_lead_label(lead)}: {exc}")
            continue

        lead["status"] = "SENT"
        lead["sent_date"] = today
        sent_rows.append(lead)

        if index < len(pending_leads):
            time.sleep(random.uniform(runtime_config.GAP_MIN, runtime_config.GAP_MAX))

    try:
        sheets_client.write_leads_batch(leads)
    except Exception as exc:
        _log_failure(f"Sender failed to write leads: {exc}")
        return []

    if failure_messages:
        _log_failure("; ".join(failure_messages))

    _log_info(
        f"Sender sent {len(sent_rows)} leads; cap {daily_cap}; already sent today {already_sent_today}."
    )
    return sent_rows


def run() -> list[dict[str, Any]]:
    return send_pending_emails()


def send_email(
    to_email: str,
    subject: str,
    body: str,
    gmail_user: str | None = None,
    gmail_app_password: str | None = None,
) -> None:
    sender_user = gmail_user or _gmail_user()
    sender_password = gmail_app_password or _gmail_app_password()

    if not to_email:
        raise ValueError("recipient email is required.")
    if not subject:
        raise ValueError("email subject is required.")
    if not body:
        raise ValueError("email body is required.")

    message = MIMEText(body, "plain", "utf-8")
    message["From"] = sender_user
    message["To"] = to_email
    message["Subject"] = subject

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(sender_user, sender_password)
        smtp.send_message(message)


def _pending_leads(
    leads: list[dict[str, Any]],
    minimum_score: int,
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    pending: list[dict[str, Any]] = []
    for lead in leads:
        if _status(lead) != "EMAIL_READY":
            continue
        if _score(lead) < minimum_score:
            continue
        if not _row_value(lead, "email").strip():
            continue
        if not _email_body(lead):
            continue

        pending.append(lead)
        if len(pending) >= limit:
            break
    return pending


def _daily_send_cap(leads: list[dict[str, Any]], ramp_step: int, daily_limit: int) -> int:
    safe_ramp_step = max(ramp_step, 1)
    safe_daily_limit = max(daily_limit, 0)
    if safe_daily_limit == 0:
        return 0

    prior_send_dates = {
        sent_date
        for lead in leads
        for sent_date in [_row_value(lead, "sent_date").strip()]
        if sent_date
    }
    campaign_day = len(prior_send_dates) + 1
    return min(safe_daily_limit, safe_ramp_step * campaign_day)


def _sent_count_for_date(leads: list[dict[str, Any]], sent_date: str) -> int:
    count = 0
    for lead in leads:
        if _status(lead) == "SENT" and _row_value(lead, "sent_date").strip() == sent_date:
            count += 1
    return count


def _email_subject(lead: Mapping[str, Any]) -> str:
    return _row_value(lead, "generated_subject").strip()


def _email_body(lead: Mapping[str, Any]) -> str:
    return _row_value(lead, "generated_body").strip()


def _score(lead: Mapping[str, Any]) -> int:
    raw_score = _row_value(lead, "score").strip()
    try:
        return int(float(raw_score))
    except ValueError:
        return 0


def _gmail_user() -> str:
    value = os.environ.get("GMAIL_USER", "").strip()
    if not value:
        raise RuntimeError("GMAIL_USER environment variable is required.")
    if value.startswith("PASTE_"):
        raise RuntimeError("GMAIL_USER environment variable must contain a real value.")
    return value


def _gmail_app_password() -> str:
    value = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if not value:
        raise RuntimeError("GMAIL_APP_PASSWORD environment variable is required.")
    if value.startswith("PASTE_"):
        raise RuntimeError("GMAIL_APP_PASSWORD environment variable must contain a real value.")
    return value


def _status(lead: Mapping[str, Any]) -> str:
    return _row_value(lead, "status").strip().upper()


def _row_value(row: Mapping[str, Any], key: str) -> str:
    for candidate in _key_variants(key):
        if candidate in row:
            return str(row.get(candidate, "") or "")
    return ""


def _key_variants(key: str) -> tuple[str, ...]:
    words = key.split("_")
    camel_case = words[0] + "".join(word.capitalize() for word in words[1:])
    return (key, key.title(), key.upper(), camel_case)


def _lead_label(lead: Mapping[str, Any]) -> str:
    name = _row_value(lead, "name").strip()
    email = _row_value(lead, "email").strip()
    return name or email or "unknown lead"


def _log_info(message: str) -> None:
    sheets_client.log_run(message=message, level="INFO")


def _log_failure(message: str) -> None:
    try:
        sheets_client.log_run(message=message, level="ERROR")
    except Exception as exc:
        raise RuntimeError(
            f"{message}; additionally failed to write RUN_LOG: {exc}"
        ) from exc
