from __future__ import annotations

import json
import os
import re
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from hunterdog.pipeline import config as pipeline_config
from hunterdog.pipeline import sheets_client


def write_emails() -> list[dict[str, Any]]:
    try:
        runtime_config = pipeline_config.get_config()
        leads = sheets_client.get_leads()
        groq_api_key = _groq_api_key()
    except Exception as exc:
        _log_failure(f"Groq writer failed to initialize: {exc}")
        return []

    updated_rows: list[dict[str, Any]] = []
    failure_messages: list[str] = []

    for lead in leads:
        if _status(lead) != "SCORED":
            continue

        try:
            subject_template, body_template = _templates_for_lead(lead, runtime_config)
            opening_line = _personalized_opening_line(lead, groq_api_key)
            subject = _fill_template(subject_template, lead, opening_line)
            body = _body_with_opening_line(
                _fill_template(body_template, lead, opening_line),
                opening_line,
            )
        except Exception as exc:
            failure_messages.append(f"Groq writer failed for {_lead_label(lead)}: {exc}")
            continue

        lead["generated_subject"] = subject
        lead["generated_body"] = body
        lead["status"] = "EMAIL_READY"
        updated_rows.append(lead)

    try:
        sheets_client.write_leads_batch(leads)
    except Exception as exc:
        _log_failure(f"Groq writer failed to write leads: {exc}")
        return []

    if failure_messages:
        _log_failure("; ".join(failure_messages))

    _log_info(f"Groq writer prepared {len(updated_rows)} leads.")
    return updated_rows


def run() -> list[dict[str, Any]]:
    return write_emails()


def _templates_for_lead(
    lead: Mapping[str, Any],
    runtime_config: pipeline_config.Config,
) -> tuple[str, str]:
    bucket = _template_bucket(_row_value(lead, "bucket"))
    subject_key = f"TEMPLATE_{bucket}_SUBJECT"
    body_key = f"TEMPLATE_{bucket}_BODY"
    subject = str(getattr(runtime_config, subject_key))
    body = str(getattr(runtime_config, body_key))
    return subject, body


def _template_bucket(bucket: str) -> str:
    normalized_bucket = str(bucket or "").strip().upper()
    if normalized_bucket == "A+":
        return "A"
    if normalized_bucket in {"A", "B", "C", "D", "E"}:
        return normalized_bucket
    raise ValueError(f"Unsupported bucket: {bucket}")


def _fill_template(template: str, lead: Mapping[str, Any], opening_line: str) -> str:
    values = _template_values(lead, opening_line)

    def replace_placeholder(match: re.Match[str]) -> str:
        key = match.group("key").strip()
        return values.get(_normalize_key(key), "")

    return re.sub(r"{(?P<key>[^{}]+)}", replace_placeholder, template)


def _template_values(lead: Mapping[str, Any], opening_line: str) -> dict[str, str]:
    values: dict[str, str] = {"opening_line": opening_line}
    for key, value in lead.items():
        normalized_key = _normalize_key(str(key))
        values[normalized_key] = str(value or "").strip()
    return values


def _body_with_opening_line(body: str, opening_line: str) -> str:
    if not opening_line:
        return body.strip()
    if opening_line in body:
        return body.strip()
    return f"{opening_line}\n\n{body.strip()}"


def _personalized_opening_line(lead: Mapping[str, Any], groq_api_key: str) -> str:
    payload = {
        "model": _groq_model(),
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _opening_line_prompt(lead)},
        ],
        "temperature": 0.7,
    }
    response = _groq_chat_completion(payload, groq_api_key)
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError(f"Groq returned no choices for lead: {_lead_label(lead)}")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ValueError("Groq choice must be an object.")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise ValueError("Groq choice missing message.")

    content = str(message.get("content", "") or "").strip()
    if not content:
        raise ValueError("Groq returned an empty opening line.")
    return _clean_opening_line(content)


def _groq_chat_completion(payload: dict[str, Any], groq_api_key: str) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        _groq_chat_completions_url(),
        data=body,
        headers={
            "Authorization": f"Bearer {groq_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            raw_body = response.read().decode("utf-8")
    except HTTPError as exc:
        raw_error = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(_groq_error_message(raw_error, exc.code)) from exc
    except URLError as exc:
        reason = str(getattr(exc, "reason", exc)).strip()
        raise RuntimeError(f"Groq request failed: {reason}") from exc

    parsed = _parse_json_object(raw_body)
    if "error" in parsed:
        raise ValueError(f"Groq API error: {parsed['error']}")
    return parsed


def _opening_line_prompt(lead: Mapping[str, Any]) -> str:
    name = _row_value(lead, "name")
    city = _row_value(lead, "city") or _city_from_address(_row_value(lead, "address"))
    country = _row_value(lead, "country")
    bucket = _row_value(lead, "bucket")
    score = _row_value(lead, "score")
    gap = _lead_gap(lead)
    return (
        f"Business name: {name}, City: {city}, Country: {country}, "
        f"Bucket: {bucket}, Score: {score}, Gap: {gap}. "
        "Write one short, natural opening line for a cold email from a paid ads agency. "
        "Mention the business name or city if useful. No buzzwords. No subject line. "
        "Return only the opening line."
    )


def _lead_gap(lead: Mapping[str, Any]) -> str:
    gaps: list[str] = []
    if _is_false(_row_value(lead, "ads_running")):
        gaps.append("not currently running Meta ads")
    if _is_false(_row_value(lead, "mobile_friendly")):
        gaps.append("site is not mobile friendly")

    page_speed_score = _optional_float(_row_value(lead, "page_speed_score"))
    if page_speed_score is not None and page_speed_score < 60:
        gaps.append(f"slow page speed score of {round(page_speed_score)}")

    if not _row_value(lead, "website").strip():
        gaps.append("missing website")
    if not _row_value(lead, "email").strip():
        gaps.append("limited contact details")

    if gaps:
        return ", ".join(gaps)
    return "average digital presence"


def _clean_opening_line(content: str) -> str:
    line = content.strip().strip('"').strip("'")
    line = re.sub(r"\s+", " ", line)
    return line


def _groq_api_key() -> str:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable is required.")
    if api_key.startswith("PASTE_"):
        raise RuntimeError("GROQ_API_KEY environment variable must contain a real key.")
    return api_key


def _groq_chat_completions_url() -> str:
    return "https://api.groq.com/openai/v1/chat/completions"


def _groq_model() -> str:
    return "llama-3.3-70b-versatile"


def _system_prompt() -> str:
    return (
        "You are a professional cold email writer. Write short, natural, "
        "non-salesy cold emails for a paid ads agency."
    )


def _parse_json_object(raw_body: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ValueError("Groq returned invalid JSON.") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Groq JSON response must be an object.")
    return parsed


def _groq_error_message(raw_body: str, status_code: int) -> str:
    try:
        parsed = _parse_json_object(raw_body)
    except ValueError:
        return f"Groq HTTP error {status_code}."

    error = parsed.get("error")
    if isinstance(error, dict):
        message = str(error.get("message", "")).strip()
        if message:
            return f"Groq HTTP error {status_code}: {message}"
    return f"Groq HTTP error {status_code}."


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


def _normalize_key(key: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z]+", "_", key).strip("_").lower()
    words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+", key)
    if "_" not in normalized and len(words) > 1:
        return "_".join(word.lower() for word in words)
    return normalized


def _city_from_address(address: str) -> str:
    parts = [part.strip() for part in address.split(",") if part.strip()]
    if len(parts) >= 2:
        return parts[-2]
    return ""


def _optional_float(value: Any) -> float | None:
    raw_value = str(value or "").strip()
    if not raw_value:
        return None
    try:
        return float(raw_value)
    except ValueError:
        return None


def _is_false(value: Any) -> bool:
    return str(value or "").strip().lower() in {"false", "no", "0"}


def _lead_label(lead: Mapping[str, Any]) -> str:
    name = _row_value(lead, "name").strip()
    website = _row_value(lead, "website").strip()
    return name or website or "unknown lead"


def _log_info(message: str) -> None:
    sheets_client.log_run(message=message, level="INFO")


def _log_failure(message: str) -> None:
    try:
        sheets_client.log_run(message=message, level="ERROR")
    except Exception as exc:
        raise RuntimeError(
            f"{message}; additionally failed to write RUN_LOG: {exc}"
        ) from exc
