from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping

import gspread
from google.oauth2.service_account import Credentials


@dataclass(slots=True)
class Lead:
    row_number: int | None = None
    fields: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        value = self.fields.get("status", "")
        return str(value or "").strip()

    def to_dict(self) -> dict[str, Any]:
        return dict(self.fields)


@dataclass(frozen=True, slots=True)
class RunLogEntry:
    timestamp: str
    level: str
    message: str

    @classmethod
    def create(cls, message: str, level: str) -> RunLogEntry:
        return cls(
            timestamp=datetime.now(UTC).isoformat(),
            level=level.strip().upper(),
            message=message,
        )

    def to_row(self) -> list[str]:
        return [self.timestamp, self.level, self.message]


def get_config() -> dict[str, str]:
    worksheet = _worksheet("CONFIG")
    values = worksheet.get_all_values()
    return _parse_config_values(values)


def get_leads() -> list[dict[str, Any]]:
    worksheet = _worksheet("LEADS")
    values = worksheet.get_all_values()
    return [lead.to_dict() for lead in _parse_leads_values(values)]


def write_leads_batch(rows: list[dict[str, Any]]) -> None:
    worksheet = _worksheet("LEADS")
    headers = _headers_from_rows(rows)
    values = [headers, *[_row_values(row, headers) for row in rows]] if headers else []
    worksheet.spreadsheet.batch_update(
        {
            "requests": [
                {
                    "updateCells": {
                        "range": {"sheetId": worksheet.id},
                        "rows": [_sheet_row(value_row) for value_row in values],
                        "fields": "userEnteredValue",
                    }
                }
            ]
        }
    )


def log_run(message: str, level: str) -> None:
    worksheet = _worksheet("RUN_LOG")
    entry = RunLogEntry.create(message=message, level=level)
    worksheet.append_row(entry.to_row(), value_input_option="USER_ENTERED")


def _worksheet(title: str) -> gspread.Worksheet:
    spreadsheet = _spreadsheet()
    return spreadsheet.worksheet(title)


def _spreadsheet() -> gspread.Spreadsheet:
    credentials_info = _credentials_info()
    client = _client(credentials_info)
    spreadsheet_id = _spreadsheet_id(credentials_info)
    return client.open_by_key(spreadsheet_id)


def _credentials_info() -> dict[str, Any]:
    raw_credentials = os.environ.get("GOOGLE_CREDS_JSON", "").strip()
    if not raw_credentials:
        raise RuntimeError("GOOGLE_CREDS_JSON environment variable is required.")

    try:
        parsed = json.loads(raw_credentials)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GOOGLE_CREDS_JSON must contain valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("GOOGLE_CREDS_JSON must decode to a JSON object.")

    return parsed


def _client(credentials_info: Mapping[str, Any]) -> gspread.Client:
    credentials = Credentials.from_service_account_info(
        dict(credentials_info),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return gspread.authorize(credentials)


def _spreadsheet_id(credentials_info: Mapping[str, Any]) -> str:
    spreadsheet_id = str(
        credentials_info.get("spreadsheet_id")
        or credentials_info.get("sheet_id")
        or os.environ.get("GOOGLE_SHEET_ID", "")
    ).strip()
    if not spreadsheet_id:
        raise RuntimeError(
            "Spreadsheet id is required as spreadsheet_id in GOOGLE_CREDS_JSON or GOOGLE_SHEET_ID."
        )
    return spreadsheet_id


def _parse_config_values(values: list[list[str]]) -> dict[str, str]:
    if not values:
        return {}

    first_row = [_normalize_header(value) for value in values[0]]
    if "key" in first_row and "value" in first_row:
        key_index = first_row.index("key")
        value_index = first_row.index("value")
        data_rows = values[1:]
    else:
        key_index = 0
        value_index = 1
        data_rows = values

    config: dict[str, str] = {}
    for row in data_rows:
        key = _cell(row, key_index).strip()
        if key:
            config[key] = _cell(row, value_index).strip()
    return config


def _parse_leads_values(values: list[list[str]]) -> list[Lead]:
    if not values:
        return []

    headers = [_normalize_header(header) for header in values[0]]
    leads: list[Lead] = []
    for index, row in enumerate(values[1:], start=2):
        if not any(str(cell).strip() for cell in row):
            continue
        fields = {
            header: _cell(row, column_index)
            for column_index, header in enumerate(headers)
            if header
        }
        leads.append(Lead(row_number=index, fields=fields))
    return leads


def _headers_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    headers: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            header = str(key).strip()
            if header and header not in seen:
                headers.append(header)
                seen.add(header)
    return headers


def _row_values(row: Mapping[str, Any], headers: list[str]) -> list[Any]:
    return [row.get(header, "") for header in headers]


def _sheet_row(values: list[Any]) -> dict[str, list[dict[str, dict[str, Any]]]]:
    return {"values": [_sheet_cell(value) for value in values]}


def _sheet_cell(value: Any) -> dict[str, dict[str, Any]]:
    if value is None:
        return {}
    if isinstance(value, bool):
        return {"userEnteredValue": {"boolValue": value}}
    if isinstance(value, int | float) and not isinstance(value, bool):
        return {"userEnteredValue": {"numberValue": value}}
    return {"userEnteredValue": {"stringValue": str(value)}}


def _cell(row: list[str], index: int) -> str:
    if index >= len(row):
        return ""
    return str(row[index] or "")


def _normalize_header(value: str) -> str:
    return str(value or "").strip()
