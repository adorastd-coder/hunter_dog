from __future__ import annotations

import json
import os
import random
import time
from datetime import date, datetime
from typing import Any, Mapping

from hunterdog.pipeline import config as pipeline_config
from hunterdog.pipeline import sender
from hunterdog.pipeline import sheets_client


def track_replies_and_followups() -> dict[str, int]:
    try:
        runtime_config = pipeline_config.get_config()
        leads = sheets_client.get_leads()
        gmail_service = _gmail_service()
    except Exception as exc:
        _log_failure(f"Tracker failed to initialize: {exc}")
        return {"replies_found": 0, "followups_sent": 0}

    today = date.today()
    replies_found = 0
    followups_sent = 0
    failure_messages: list[str] = []

    due_followups = _due_followup_leads(leads, today, runtime_config.DAYS_BEFORE_DM)
    for lead in leads:
        if _status(lead) != "SENT":
            continue

        email = _row_value(lead, "email").strip()
        if not email:
            continue

        try:
            if _has_reply_from(gmail_service, email):
                lead["status"] = "REPLIED"
                lead["replied"] = True
                lead["reply_date"] = today.isoformat()
                replies_found += 1
                continue

            sent_date = _parse_date(_row_value(lead, "sent_date"))
            if sent_date is None:
                continue

            days_since_sent = (today - sent_date).days
            followup_column = _due_followup_column(
                lead,
                days_since_sent,
                runtime_config.DAYS_BEFORE_DM,
            )
            if followup_column is None:
                continue

            _send_followup(lead)
            lead[followup_column] = True
            lead[f"{followup_column}_date"] = today.isoformat()
            followups_sent += 1
            if followups_sent < due_followups:
                time.sleep(random.uniform(runtime_config.GAP_MIN, runtime_config.GAP_MAX))
        except Exception as exc:
            failure_messages.append(f"Tracker failed for {_lead_label(lead)}: {exc}")

    try:
        sheets_client.write_leads_batch(leads)
    except Exception as exc:
        _log_failure(f"Tracker failed to write leads: {exc}")
        return {"replies_found": replies_found, "followups_sent": followups_sent}

    if failure_messages:
        _log_failure("; ".join(failure_messages))

    _log_info(
        f"Tracker found {replies_found} replies and sent {followups_sent} follow-ups."
    )
    return {"replies_found": replies_found, "followups_sent": followups_sent}


def run() -> dict[str, int]:
    return track_replies_and_followups()


def _gmail_service() -> Any:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    credentials_info = _gmail_token_info()
    credentials = Credentials.from_authorized_user_info(
        credentials_info,
        scopes=_gmail_readonly_scopes(),
    )
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if not credentials.valid:
        raise RuntimeError("GMAIL_TOKEN_JSON did not produce valid Gmail credentials.")
    return build("gmail", "v1", credentials=credentials)


def _has_reply_from(service: Any, email: str) -> bool:
    query = f"in:inbox from:{email} newer_than:30d -from:me"
    response = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=1)
        .execute()
    )
    messages = response.get("messages") if isinstance(response, dict) else None
    return bool(messages)


def _send_followup(lead: Mapping[str, Any]) -> None:
    email = _row_value(lead, "email").strip()
    name = _row_value(lead, "name").strip()
    original_subject = _row_value(lead, "generated_subject").strip()
    fallback_subject = f"Quick question for {name}"
    subject = f"Re: {original_subject or fallback_subject}"
    sender.send_email(email, subject, _followup_body(name))


def _followup_body(name: str) -> str:
    business_name = name or "your business"
    return (
        f"Just checking if you saw my previous email about {business_name}; "
        "I would still be happy to offer a free 20-minute audit."
    )


def _due_followup_column(
    lead: Mapping[str, Any],
    days_since_sent: int,
    days_before_dm: int,
) -> str | None:
    if days_since_sent < days_before_dm:
        return None

    for minimum_days, followup_column in _followup_schedule():
        if days_since_sent < minimum_days:
            continue
        if not _truthy(_row_value(lead, followup_column)):
            return followup_column
    return None


def _due_followup_leads(
    leads: list[dict[str, Any]],
    today: date,
    days_before_dm: int,
) -> int:
    due_count = 0
    for lead in leads:
        if _status(lead) != "SENT":
            continue
        sent_date = _parse_date(_row_value(lead, "sent_date"))
        if sent_date is None:
            continue
        if _due_followup_column(lead, (today - sent_date).days, days_before_dm):
            due_count += 1
    return due_count


def _followup_schedule() -> tuple[tuple[int, str], ...]:
    return ((3, "followup_1"), (6, "followup_2"), (10, "followup_3"))


def _gmail_token_info() -> dict[str, Any]:
    raw_token = os.environ.get("GMAIL_TOKEN_JSON", "").strip()
    if not raw_token:
        raise RuntimeError("GMAIL_TOKEN_JSON environment variable is required.")

    try:
        parsed = json.loads(raw_token)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GMAIL_TOKEN_JSON must contain valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("GMAIL_TOKEN_JSON must decode to a JSON object.")
    return parsed


def _gmail_readonly_scopes() -> list[str]:
    return ["https://www.googleapis.com/auth/gmail.readonly"]


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    raw_value = str(value or "").strip()
    if not raw_value:
        return None

    try:
        return datetime.fromisoformat(raw_value).date()
    except ValueError:
        return None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"true", "yes", "1"}


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
