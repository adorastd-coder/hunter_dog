from __future__ import annotations

import random
import re
import time
from typing import Any
from urllib.parse import urljoin

from playwright.sync_api import Browser, Page, sync_playwright

from hunterdog.pipeline import sheets_client


def enrich() -> list[dict[str, Any]]:
    enriched_rows: list[dict[str, Any]] = []

    try:
        leads = sheets_client.get_leads()
    except Exception as exc:
        _log_failure(f"Enrichment failed to read leads: {exc}")
        return []

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                for lead in leads:
                    if _status(lead) != "SCRAPED":
                        continue

                    try:
                        enriched_row = _enrich_lead(browser, lead)
                    except Exception as exc:
                        _log_failure(f"Enrichment failed for {_lead_label(lead)}: {exc}")
                        continue

                    lead.update(enriched_row)
                    enriched_rows.append(lead)
            finally:
                browser.close()
    except Exception as exc:
        _log_failure(f"Enrichment batch failed: {exc}")

    try:
        sheets_client.write_leads_batch(leads)
    except Exception as exc:
        _log_failure(f"Enrichment failed to write leads: {exc}")
        return []

    return enriched_rows


def run() -> list[dict[str, Any]]:
    return enrich()


def _enrich_lead(browser: Browser, lead: dict[str, Any]) -> dict[str, Any]:
    website = _row_value(lead, "website").strip()
    if not website:
        raise ValueError("missing website")

    result = _scrape_website_with_browser(browser, _normalize_url(website))
    enriched = dict(lead)
    _apply_result(enriched, result)
    enriched["status"] = "ENRICHED"
    return enriched


def _scrape_website_with_browser(browser: Browser, url: str) -> dict[str, Any]:
    result = _empty_result()
    context = browser.new_context(user_agent=_user_agent())
    page = context.new_page()
    page.set_default_timeout(15000)

    try:
        collected_text: list[str] = []
        collected_links: list[str] = []

        homepage_text, homepage_links = _collect_page_data(page, url)
        collected_text.append(homepage_text)
        collected_links.extend(homepage_links)

        result["email"] = _extract_email(homepage_text, homepage_links)

        if not result["email"]:
            for path in ("/contact", "/contact-us"):
                contact_url = urljoin(url, path)
                try:
                    contact_text, contact_links = _collect_page_data(page, contact_url)
                except Exception:
                    continue

                collected_text.append(contact_text)
                collected_links.extend(contact_links)
                result["email"] = _extract_email(contact_text, contact_links)
                if result["email"]:
                    break

        all_text = "\n".join(collected_text)
        result["whatsapp"] = _extract_whatsapp(all_text, collected_links)
        result["instagram"] = _extract_social_url(
            "instagram",
            all_text,
            collected_links,
        )
        result["facebook"] = _extract_social_url(
            "facebook",
            all_text,
            collected_links,
        )
        result["linkedin"] = _extract_social_url(
            "linkedin",
            all_text,
            collected_links,
        )
        result["copyright_year"] = _extract_copyright_year(all_text)
    finally:
        try:
            page.close()
        finally:
            context.close()

    return result


def _collect_page_data(page: Page, url: str) -> tuple[str, list[str]]:
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    time.sleep(random.uniform(2, 4))

    text = page.locator("body").inner_text(timeout=15000)
    links = page.eval_on_selector_all(
        "a[href]",
        "elements => elements.map(element => element.href)",
    )

    return text, [str(link) for link in links]


def _extract_email(text: str, links: list[str]) -> str:
    email_regex = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    for link in links:
        if link.lower().startswith("mailto:"):
            email = link.split(":", maxsplit=1)[1].split("?", maxsplit=1)[0]
            if email_regex.fullmatch(email):
                return email

    match = email_regex.search("\n".join([text, *links]))
    return match.group(0) if match else ""


def _extract_social_url(name: str, text: str, links: list[str]) -> str:
    social_patterns = {
        "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[^\s\"'<>]+", re.I),
        "facebook": re.compile(r"https?://(?:www\.)?facebook\.com/[^\s\"'<>]+", re.I),
        "linkedin": re.compile(r"https?://(?:www\.)?linkedin\.com/[^\s\"'<>]+", re.I),
    }
    combined = "\n".join([text, *links])
    match = social_patterns[name].search(combined)
    return _clean_url(match.group(0)) if match else ""


def _extract_whatsapp(text: str, links: list[str]) -> str:
    whatsapp_regex = re.compile(
        r"(?:https?://)?(?:wa\.me/\d+|(?:api\.)?whatsapp\.com/[^\s\"'<>]+)",
        re.I,
    )
    combined = "\n".join([text, *links])
    match = whatsapp_regex.search(combined)
    return _clean_url(match.group(0)) if match else ""


def _extract_copyright_year(text: str) -> int | None:
    copyright_year_regex = re.compile(r"Â©\s*(\d{4})")
    footer_matches = copyright_year_regex.findall(text)
    if not footer_matches:
        return None
    return int(footer_matches[-1])


def _apply_result(lead: dict[str, Any], result: dict[str, Any]) -> None:
    for key in ("email", "whatsapp", "instagram", "facebook", "linkedin"):
        value = str(result.get(key, "") or "").strip()
        if value:
            lead[key] = value

    copyright_year = result.get("copyright_year")
    if copyright_year is not None:
        lead["copyright_year"] = copyright_year


def _empty_result() -> dict[str, Any]:
    return {
        "email": "",
        "whatsapp": "",
        "instagram": "",
        "facebook": "",
        "linkedin": "",
        "copyright_year": None,
    }


def _normalize_url(url: str) -> str:
    if url.startswith(("http://", "https://")):
        return url
    return f"https://{url}"


def _clean_url(value: str) -> str:
    return value.rstrip("/.,;:)\"'")


def _status(lead: dict[str, Any]) -> str:
    return _row_value(lead, "status").strip().upper()


def _row_value(row: dict[str, Any], key: str) -> str:
    for candidate in (key, key.title(), key.upper()):
        if candidate in row:
            return str(row.get(candidate, "") or "")
    return ""


def _lead_label(lead: dict[str, Any]) -> str:
    name = _row_value(lead, "name").strip()
    website = _row_value(lead, "website").strip()
    return name or website or "unknown lead"


def _user_agent() -> str:
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )


def _log_failure(message: str) -> None:
    try:
        sheets_client.log_run(message=message, level="ERROR")
    except Exception:
        pass
