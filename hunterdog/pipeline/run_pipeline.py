from __future__ import annotations

import importlib
from typing import Any

from hunterdog.pipeline import sheets_client


def run_pipeline() -> dict[str, int]:
    results: dict[str, int] = {}
    for step_name, module_name in _pipeline_steps():
        _log_info(f"{step_name} started.")
        try:
            module = importlib.import_module(f"hunterdog.pipeline.{module_name}")
            result = module.run()
            lead_count = _lead_count(result)
            results[step_name] = lead_count
            _log_info(f"{step_name} ended; lead count: {lead_count}.")
        except Exception as exc:
            results[step_name] = 0
            _log_failure(f"{step_name} failed: {exc}")
            _log_info(f"{step_name} ended; lead count: 0.")
    return results


def run() -> dict[str, int]:
    return run_pipeline()


def _pipeline_steps() -> tuple[tuple[str, str], ...]:
    return (
        ("discovery", "discovery"),
        ("enricher", "enricher"),
        ("speed_check", "speed_check"),
        ("ads_check", "ads_check"),
        ("scorer", "scorer"),
        ("groq_writer", "groq_writer"),
        ("sender", "sender"),
        ("tracker", "tracker"),
    )


def _lead_count(result: Any) -> int:
    if isinstance(result, list):
        return len(result)
    if isinstance(result, dict):
        return sum(value for value in result.values() if isinstance(value, int))
    if result is None:
        return 0
    return 1


def _log_info(message: str) -> None:
    sheets_client.log_run(message=message, level="INFO")


def _log_failure(message: str) -> None:
    try:
        sheets_client.log_run(message=message, level="ERROR")
    except Exception as exc:
        raise RuntimeError(
            f"{message}; additionally failed to write RUN_LOG: {exc}"
        ) from exc


if __name__ == "__main__":
    run_pipeline()
