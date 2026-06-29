from __future__ import annotations

import copy
import sys
import types
from datetime import date, timedelta
from typing import Any
from unittest.mock import patch

import pytest


def _install_optional_dependency_stubs() -> None:
    if "gspread" not in sys.modules:
        gspread = types.ModuleType("gspread")
        gspread.Worksheet = object
        gspread.Spreadsheet = object
        gspread.Client = object
        gspread.authorize = lambda credentials: None
        sys.modules["gspread"] = gspread

    if "google.oauth2.service_account" not in sys.modules:
        google = sys.modules.setdefault("google", types.ModuleType("google"))
        google_auth = sys.modules.setdefault("google.auth", types.ModuleType("google.auth"))
        oauth2 = sys.modules.setdefault("google.oauth2", types.ModuleType("google.oauth2"))
        service_account = types.ModuleType("google.oauth2.service_account")

        class Credentials:
            @classmethod
            def from_service_account_info(cls, info: dict[str, Any], scopes: list[str]) -> Credentials:
                return cls()

        service_account.Credentials = Credentials
        google.auth = google_auth
        google.oauth2 = oauth2
        oauth2.service_account = service_account
        sys.modules["google.oauth2.service_account"] = service_account

    if "playwright.sync_api" not in sys.modules:
        playwright = sys.modules.setdefault("playwright", types.ModuleType("playwright"))
        sync_api = types.ModuleType("playwright.sync_api")
        sync_api.Browser = object
        sync_api.Page = object
        sync_api.sync_playwright = lambda: None
        playwright.sync_api = sync_api
        sys.modules["playwright.sync_api"] = sync_api


_install_optional_dependency_stubs()


FAKE_CONFIG = {
    "TARGET_NICHE": "dental",
    "TARGET_CITY": "New York",
    "DAILY_LIMIT": 25,
    "CAMPAIGN_STATUS": "ACTIVE",
    "GAP_MIN": 1,
    "GAP_MAX": 2,
    "MIN_SCORE": 40,
    "RAMP_STEP": 5,
    "LIGHTHOUSE_MAX_PER_RUN": 5,
    "DAYS_BEFORE_DM": 4,
    "SENDER_NAME": "Alex",
    "TEMPLATE_AP_SUBJECT": "Hey {first_name}, quick question",
    "TEMPLATE_AP_BODY": "Hi {first_name},\n\n{ai_opening}\n\nBest, {SENDER_NAME}",
    "TEMPLATE_A_SUBJECT": "Hey {first_name}, quick question",
    "TEMPLATE_A_BODY": "Hi {first_name},\n\n{ai_opening}\n\nBest, {SENDER_NAME}",
    "TEMPLATE_B_SUBJECT": "Hi {first_name}",
    "TEMPLATE_B_BODY": "Hi {first_name},\n\n{ai_opening}\n\nBest, {SENDER_NAME}",
    "TEMPLATE_C_SUBJECT": "Hi {first_name}",
    "TEMPLATE_C_BODY": "Hi {first_name},\n\n{ai_opening}\n\nBest, {SENDER_NAME}",
    "TEMPLATE_D_SUBJECT": "Hi {first_name}",
    "TEMPLATE_D_BODY": "Hi {first_name},\n\n{ai_opening}\n\nBest, {SENDER_NAME}",
    "TEMPLATE_E_SUBJECT": "Hi {first_name}",
    "TEMPLATE_E_BODY": "Hi {first_name},\n\n{ai_opening}\n\nBest, {SENDER_NAME}",
}

FAKE_LEADS = [
    {
        "id": "lead_001",
        "business_name": "Smile Dental NYC",
        "name": "Smile Dental NYC",
        "address": "123 Main St, New York, NY",
        "city": "New York",
        "phone": "(555) 123-4567",
        "website": "https://smiledental.com",
        "email": "",
        "instagram": "",
        "facebook": "",
        "score": 0,
        "bucket": "",
        "status": "SCRAPED",
        "page_speed_score": 0,
        "mobile_friendly": None,
        "ads_running": None,
        "generated_subject": "",
        "generated_body": "",
        "sent_date": "",
        "dm_sent": False,
    }
]

_in_memory_leads: list[dict[str, Any]] = []
_run_log: list[tuple[str, str]] = []


def mock_get_leads() -> list[dict[str, Any]]:
    return copy.deepcopy(_in_memory_leads)


def mock_write_leads_batch(rows: list[dict[str, Any]]) -> None:
    global _in_memory_leads
    updated = {str(row["id"]): row for row in _in_memory_leads}
    for row in rows:
        updated[str(row["id"])] = copy.deepcopy(row)
    _in_memory_leads = list(updated.values())


def mock_log_run(message: str, level: str = "INFO") -> None:
    _run_log.append((level, message))


class FakePlaywright:
    def __enter__(self) -> FakePlaywright:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    @property
    def chromium(self) -> FakePlaywright:
        return self

    def launch(self, headless: bool = True) -> FakeBrowser:
        return FakeBrowser()


class FakeBrowser:
    def close(self) -> None:
        return None


@pytest.fixture(autouse=True)
def reset_leads(monkeypatch: pytest.MonkeyPatch) -> None:
    global _in_memory_leads, _run_log
    _in_memory_leads = copy.deepcopy(FAKE_LEADS)
    _run_log = []
    monkeypatch.setenv("META_ACCESS_TOKEN", "meta-token")
    monkeypatch.setenv("GROQ_API_KEY", "groq-token")
    monkeypatch.setenv("GMAIL_USER", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    yield
    _in_memory_leads = []
    _run_log = []


@pytest.fixture()
def sheets_mocks() -> Any:
    with patch("hunterdog.pipeline.sheets_client.get_config", return_value=FAKE_CONFIG), patch(
        "hunterdog.pipeline.sheets_client.get_leads", side_effect=mock_get_leads
    ), patch(
        "hunterdog.pipeline.sheets_client.write_leads_batch", side_effect=mock_write_leads_batch
    ) as write_mock, patch(
        "hunterdog.pipeline.sheets_client.log_run", side_effect=mock_log_run
    ):
        yield write_mock


def test_full_pipeline_status_flow(sheets_mocks: Any) -> None:
    from hunterdog.pipeline import enricher, speed_check
    from hunterdog.pipeline.run_pipeline import run

    with patch("hunterdog.pipeline.discovery.run", return_value=[]), patch(
        "hunterdog.pipeline.enricher.sync_playwright", return_value=FakePlaywright()
    ), patch(
        "hunterdog.pipeline.enricher._scrape_website_with_browser",
        return_value={"email": "dr@smiledental.com", "instagram": "@smile"},
    ), patch(
        "hunterdog.pipeline.speed_check._run_lighthouse",
        return_value=speed_check.LighthouseResult(page_speed_score=45, mobile_friendly=False),
    ), patch(
        "hunterdog.pipeline.ads_check._ads_running_status", return_value="false"
    ), patch(
        "hunterdog.pipeline.groq_writer._personalized_opening_line",
        return_value="I noticed your clinic may be missing a few easy growth opportunities.",
    ), patch(
        "hunterdog.pipeline.sender.send_email"
    ), patch(
        "hunterdog.pipeline.sender.time.sleep"
    ), patch(
        "hunterdog.pipeline.tracker._gmail_service", return_value=object()
    ), patch(
        "hunterdog.pipeline.tracker._has_reply_from", return_value=False
    ), patch(
        "hunterdog.pipeline.tracker.sender.send_email"
    ), patch(
        "hunterdog.pipeline.tracker.time.sleep"
    ):
        run()

    final_leads = mock_get_leads()
    assert len(final_leads) == 1

    lead = final_leads[0]
    assert lead["status"] == "SENT"
    assert lead["score"] >= 40
    assert lead["bucket"] in ["A+", "A", "B", "C", "D", "E"]
    assert lead["generated_subject"] != ""
    assert lead["generated_body"] != ""
    assert lead["sent_date"] != ""
    assert enricher is not None


def test_sender_skips_when_paused() -> None:
    paused_config = {**FAKE_CONFIG, "CAMPAIGN_STATUS": "PAUSED"}
    _in_memory_leads[0]["status"] = "EMAIL_READY"
    _in_memory_leads[0]["score"] = 80
    _in_memory_leads[0]["bucket"] = "A"
    _in_memory_leads[0]["generated_subject"] = "Test subject"
    _in_memory_leads[0]["generated_body"] = "Test body"

    with patch("hunterdog.pipeline.sheets_client.get_config", return_value=paused_config), patch(
        "hunterdog.pipeline.sheets_client.get_leads", side_effect=mock_get_leads
    ), patch(
        "hunterdog.pipeline.sheets_client.write_leads_batch", side_effect=mock_write_leads_batch
    ), patch(
        "hunterdog.pipeline.sheets_client.log_run", side_effect=mock_log_run
    ), patch(
        "hunterdog.pipeline.sender.send_email"
    ) as send_mock:
        from hunterdog.pipeline import sender

        sender.run()

    send_mock.assert_not_called()
    assert _in_memory_leads[0]["status"] == "EMAIL_READY"


def test_sender_skips_low_score() -> None:
    strict_config = {**FAKE_CONFIG, "MIN_SCORE": 90}
    _in_memory_leads[0]["status"] = "EMAIL_READY"
    _in_memory_leads[0]["score"] = 45
    _in_memory_leads[0]["bucket"] = "C"
    _in_memory_leads[0]["email"] = "dr@smile.com"
    _in_memory_leads[0]["generated_subject"] = "Test subject"
    _in_memory_leads[0]["generated_body"] = "Test body"

    with patch("hunterdog.pipeline.sheets_client.get_config", return_value=strict_config), patch(
        "hunterdog.pipeline.sheets_client.get_leads", side_effect=mock_get_leads
    ), patch(
        "hunterdog.pipeline.sheets_client.write_leads_batch", side_effect=mock_write_leads_batch
    ), patch(
        "hunterdog.pipeline.sheets_client.log_run", side_effect=mock_log_run
    ), patch(
        "hunterdog.pipeline.sender.send_email"
    ) as send_mock:
        from hunterdog.pipeline import sender

        sender.run()

    send_mock.assert_not_called()


def test_enricher_sets_status(sheets_mocks: Any) -> None:
    assert _in_memory_leads[0]["status"] == "SCRAPED"

    with patch("hunterdog.pipeline.enricher.sync_playwright", return_value=FakePlaywright()), patch(
        "hunterdog.pipeline.enricher._scrape_website_with_browser",
        return_value={"email": "dr@smile.com", "instagram": "@smile"},
    ):
        from hunterdog.pipeline import enricher

        enricher.run()

    assert _in_memory_leads[0]["status"] == "ENRICHED"
    assert _in_memory_leads[0]["email"] == "dr@smile.com"
    assert _in_memory_leads[0]["instagram"] == "@smile"


def test_tracker_marks_replied(sheets_mocks: Any) -> None:
    _in_memory_leads[0]["status"] = "SENT"
    _in_memory_leads[0]["email"] = "dr@smile.com"
    _in_memory_leads[0]["sent_date"] = str(date.today() - timedelta(days=5))

    with patch("hunterdog.pipeline.tracker._gmail_service", return_value=object()), patch(
        "hunterdog.pipeline.tracker._has_reply_from", return_value=True
    ):
        from hunterdog.pipeline import tracker

        tracker.run()

    assert _in_memory_leads[0]["status"] == "REPLIED"


def test_enricher_writes_once_not_per_row(sheets_mocks: Any) -> None:
    global _in_memory_leads
    _in_memory_leads = [
        {**copy.deepcopy(FAKE_LEADS[0]), "id": f"lead_{index:03d}"}
        for index in range(10)
    ]

    with patch("hunterdog.pipeline.enricher.sync_playwright", return_value=FakePlaywright()), patch(
        "hunterdog.pipeline.enricher._scrape_website_with_browser",
        return_value={"email": "dr@smile.com", "instagram": ""},
    ):
        from hunterdog.pipeline import enricher

        enricher.run()

    assert sheets_mocks.call_count == 1
