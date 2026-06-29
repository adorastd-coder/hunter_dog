from __future__ import annotations

import io
import json
import os
from datetime import datetime
from typing import Any, Mapping
from urllib.request import Request, urlopen

import streamlit as st

from hunterdog.pipeline import sheets_client


def configure_secrets() -> None:
    for key in (
        "GOOGLE_CREDS_JSON",
        "GOOGLE_SHEET_ID",
        "GROQ_API_KEY",
        "GMAIL_USER",
        "GMAIL_APP_PASSWORD",
        "META_ACCESS_TOKEN",
    ):
        value = _secret(key)
        if value:
            os.environ[key] = value


def read_leads() -> list[dict[str, Any]]:
    configure_secrets()
    return sheets_client.get_leads()


def write_leads(rows: list[dict[str, Any]]) -> None:
    configure_secrets()
    sheets_client.write_leads_batch(rows)
    st.cache_data.clear()


def read_config() -> dict[str, str]:
    configure_secrets()
    return sheets_client.get_config()


def write_config(updates: Mapping[str, Any]) -> None:
    configure_secrets()
    current = sheets_client.get_config()
    for key, value in updates.items():
        current[str(key)] = str(value)
    rows = [["key", "value"], *[[key, value] for key, value in current.items()]]
    worksheet = sheets_client._worksheet("CONFIG")
    worksheet.clear()
    worksheet.update(rows)
    st.cache_data.clear()


def read_run_log(limit: int | None = None) -> list[dict[str, str]]:
    configure_secrets()
    worksheet = sheets_client._worksheet("RUN_LOG")
    values = worksheet.get_all_values()
    if not values:
        return []
    headers = [str(value or "").strip().lower() for value in values[0]]
    if "timestamp" not in headers:
        headers = ["timestamp", "level", "message"]
        rows = values
    else:
        rows = values[1:]
    parsed = [
        {
            headers[index] if index < len(headers) else f"column_{index}": str(cell or "")
            for index, cell in enumerate(row)
        }
        for row in rows
        if any(str(cell).strip() for cell in row)
    ]
    parsed.reverse()
    return parsed[:limit] if limit is not None else parsed


def clear_run_log() -> None:
    configure_secrets()
    worksheet = sheets_client._worksheet("RUN_LOG")
    worksheet.clear()
    worksheet.update([["timestamp", "level", "message"]])
    st.cache_data.clear()


def clear_leads() -> None:
    configure_secrets()
    worksheet = sheets_client._worksheet("LEADS")
    worksheet.clear()
    st.cache_data.clear()


def trigger_github_workflow() -> tuple[bool, str]:
    token = _secret("GITHUB_TOKEN")
    repository = _secret("GITHUB_REPOSITORY")
    workflow_id = _secret("GITHUB_WORKFLOW_ID") or "run.yml"
    ref = _secret("GITHUB_REF") or "main"
    if not token or not repository:
        return False, "缺少 GITHUB_TOKEN 或 GITHUB_REPOSITORY"

    body = json.dumps({"ref": ref}).encode("utf-8")
    request = Request(
        f"https://api.github.com/repos/{repository}/actions/workflows/{workflow_id}/dispatches",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        if response.status in {200, 201, 204}:
            return True, "已触发 GitHub Actions"
        return False, f"GitHub 返回状态 {response.status}"


def upload_flyer_to_drive(file: Any, bucket: str) -> str:
    configure_secrets()
    folder_id = _secret("GOOGLE_DRIVE_FOLDER_ID")
    if not folder_id:
        raise RuntimeError("缺少 GOOGLE_DRIVE_FOLDER_ID")

    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload

    credentials_info = json.loads(_secret("GOOGLE_CREDS_JSON"))
    credentials = Credentials.from_service_account_info(
        credentials_info,
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )
    service = build("drive", "v3", credentials=credentials)
    media = MediaIoBaseUpload(io.BytesIO(file.getvalue()), mimetype=file.type, resumable=False)
    metadata = {
        "name": f"{bucket}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file.name}",
        "parents": [folder_id],
    }
    created = (
        service.files()
        .create(body=metadata, media_body=media, fields="id, webViewLink")
        .execute()
    )
    return str(created.get("webViewLink", ""))


def _secret(key: str) -> str:
    try:
        value = st.secrets.get(key, "")
    except Exception:
        return ""
    if isinstance(value, dict):
        return json.dumps(dict(value))
    return str(value or "").strip()
