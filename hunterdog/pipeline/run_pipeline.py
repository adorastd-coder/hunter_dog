from __future__ import annotations

from typing import Any, Callable

from hunterdog.pipeline import (
    ads_check,
    discovery,
    enricher,
    groq_writer,
    scorer,
    sender,
    sheets_client,
    speed_check,
    tracker,
)


def run() -> dict[str, Any]:
    """Run every Hunter Dog pipeline stage once, in order.

    Each stage already reads the full Sheets tab once and writes back once,
    and each stage already catches and logs its own failures to RUN_LOG
    without raising. So stages here run unconditionally in sequence: a
    failure inside one stage (already logged by that stage) does not
    prevent later stages from running against whatever state the sheet is
    currently in.
    """
    results: dict[str, Any] = {}

    stages: list[tuple[str, Callable[[], Any]]] = [
        ("discovery", discovery.run),
        ("enricher", enricher.run),
        ("speed_check", speed_check.run),
        ("ads_check", ads_check.run),
        ("scorer", scorer.run),
        ("groq_writer", groq_writer.run),
        ("sender", sender.run),
        ("tracker", tracker.run),
    ]

    for stage_name, stage_run in stages:
        try:
            results[stage_name] = stage_run()
        except Exception as exc:
            _log_failure(f"Pipeline stage '{stage_name}' raised unexpectedly: {exc}")
            results[stage_name] = None

    _log_info(f"Pipeline run complete: {_summarize(results)}")
    return results


def _summarize(results: dict[str, Any]) -> str:
    parts: list[str] = []
    for stage_name, result in results.items():
        if isinstance(result, list):
            parts.append(f"{stage_name}={len(result)}")
        elif isinstance(result, dict):
            parts.append(f"{stage_name}={result}")
        else:
            parts.append(f"{stage_name}=failed")
    return ", ".join(parts)


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


if __name__ == "__main__":
    run()
