from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from hunterdog.pipeline import sheets_client


@dataclass(frozen=True, slots=True)
class Config:
    TARGET_NICHE: str
    TARGET_CITY: str
    DAILY_LIMIT: int
    CAMPAIGN_STATUS: str
    GAP_MIN: int
    GAP_MAX: int
    MIN_SCORE: int
    SENDER_NAME: str
    DAYS_BEFORE_DM: int
    RAMP_STEP: int
    LIGHTHOUSE_MAX_PER_RUN: int
    TEMPLATE_A_SUBJECT: str
    TEMPLATE_A_BODY: str
    TEMPLATE_B_SUBJECT: str
    TEMPLATE_B_BODY: str
    TEMPLATE_C_SUBJECT: str
    TEMPLATE_C_BODY: str
    TEMPLATE_D_SUBJECT: str
    TEMPLATE_D_BODY: str
    TEMPLATE_E_SUBJECT: str
    TEMPLATE_E_BODY: str

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> Config:
        _require_keys(values)
        return cls(
            TARGET_NICHE=_string_value(values, "TARGET_NICHE"),
            TARGET_CITY=_string_value(values, "TARGET_CITY"),
            DAILY_LIMIT=_int_value(values, "DAILY_LIMIT"),
            CAMPAIGN_STATUS=_string_value(values, "CAMPAIGN_STATUS"),
            GAP_MIN=_int_value(values, "GAP_MIN"),
            GAP_MAX=_int_value(values, "GAP_MAX"),
            MIN_SCORE=_int_value(values, "MIN_SCORE"),
            SENDER_NAME=_string_value(values, "SENDER_NAME"),
            DAYS_BEFORE_DM=_int_value(values, "DAYS_BEFORE_DM"),
            RAMP_STEP=_int_value(values, "RAMP_STEP"),
            LIGHTHOUSE_MAX_PER_RUN=_int_value(values, "LIGHTHOUSE_MAX_PER_RUN"),
            TEMPLATE_A_SUBJECT=_string_value(values, "TEMPLATE_A_SUBJECT"),
            TEMPLATE_A_BODY=_string_value(values, "TEMPLATE_A_BODY"),
            TEMPLATE_B_SUBJECT=_string_value(values, "TEMPLATE_B_SUBJECT"),
            TEMPLATE_B_BODY=_string_value(values, "TEMPLATE_B_BODY"),
            TEMPLATE_C_SUBJECT=_string_value(values, "TEMPLATE_C_SUBJECT"),
            TEMPLATE_C_BODY=_string_value(values, "TEMPLATE_C_BODY"),
            TEMPLATE_D_SUBJECT=_string_value(values, "TEMPLATE_D_SUBJECT"),
            TEMPLATE_D_BODY=_string_value(values, "TEMPLATE_D_BODY"),
            TEMPLATE_E_SUBJECT=_string_value(values, "TEMPLATE_E_SUBJECT"),
            TEMPLATE_E_BODY=_string_value(values, "TEMPLATE_E_BODY"),
        )


def get_config() -> Config:
    try:
        return Config.from_mapping(sheets_client.get_config())
    except Exception as exc:
        _log_failure(f"Config load failed: {exc}")
        raise


def _require_keys(values: Mapping[str, str]) -> None:
    for key in _required_keys():
        if key not in values or str(values[key]).strip() == "":
            raise KeyError(f"Missing required CONFIG key: {key}")


def _required_keys() -> tuple[str, ...]:
    return (
        "TARGET_NICHE",
        "TARGET_CITY",
        "DAILY_LIMIT",
        "CAMPAIGN_STATUS",
        "GAP_MIN",
        "GAP_MAX",
        "MIN_SCORE",
        "SENDER_NAME",
        "DAYS_BEFORE_DM",
        "RAMP_STEP",
        "LIGHTHOUSE_MAX_PER_RUN",
        "TEMPLATE_A_SUBJECT",
        "TEMPLATE_A_BODY",
        "TEMPLATE_B_SUBJECT",
        "TEMPLATE_B_BODY",
        "TEMPLATE_C_SUBJECT",
        "TEMPLATE_C_BODY",
        "TEMPLATE_D_SUBJECT",
        "TEMPLATE_D_BODY",
        "TEMPLATE_E_SUBJECT",
        "TEMPLATE_E_BODY",
    )


def _string_value(values: Mapping[str, str], key: str) -> str:
    return str(values[key]).strip()


def _int_value(values: Mapping[str, str], key: str) -> int:
    raw_value = _string_value(values, key)
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"CONFIG key {key} must be an integer.") from exc


def _log_failure(message: str) -> None:
    try:
        sheets_client.log_run(message=message, level="ERROR")
    except Exception as exc:
        raise RuntimeError(
            f"{message}; additionally failed to write RUN_LOG: {exc}"
        ) from exc
