from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote_plus

from playwright.sync_api import Page, sync_playwright

from hunterdog.pipeline import sheets_client


@dataclass(frozen=True, slots=True)
class YellowPagesLead:
    name: str
    address: str
    phone: str = ""
    website: str = ""
    source: str = "YellowPages"

    def to_sheet_row(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "address": self.address,
            "phone": _clean_phone_number(self.phone),
            "website": _normalize_website_url(self.website),
            "email": "",
            "rating": "N/A",
            "source": self.source,
            "referenceLink": "",
            "scrapedAt": datetime.now(UTC).isoformat(),
            "status": "SCRAPED",
        }


def scrape_yellow_pages(
    search_query: str,
    location: str,
    max_results: int,
) -> list[YellowPagesLead]:
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            page = browser.new_page()
            try:
                page.goto(
                    "https://www.yellowpages.com/search"
                    f"?search_terms={quote_plus(search_query)}"
                    f"&geo_location_terms={quote_plus(location)}",
                    wait_until="networkidle",
                    timeout=60000,
                )
                page.wait_for_timeout(2000)
                leads = _extract_yellow_pages_results(page)[:max_results]
                _log_info(f"Discovery source YellowPages produced {len(leads)} leads.")
                return leads
            finally:
                page.close()
                browser.close()
    except Exception as exc:
        _log_failure(f"Yellow Pages discovery failed: {exc}")
        raise


def _extract_yellow_pages_results(page: Page) -> list[YellowPagesLead]:
    raw_results = page.evaluate(
        """
        () => {
          const results = [];
          const businessElements = document.querySelectorAll('.listing-item, .business-item');

          businessElements.forEach((element) => {
            const nameElement = element.querySelector('h3, .business-name, .listing-name');
            const addressElement = element.querySelector('.address, .business-address');
            const phoneElement = element.querySelector('.phone, .business-phone');
            const websiteElement = element.querySelector('a.track-visit-website, a[href^="http"]');

            const business = {
              name: nameElement ? nameElement.textContent.trim() : '',
              address: addressElement ? addressElement.textContent.trim() : '',
              phone: phoneElement ? phoneElement.textContent.trim() : '',
              website: websiteElement ? websiteElement.href : ''
            };

            if (business.name && business.address) {
              results.push(business);
            }
          });

          return results;
        }
        """
    )
    return [_yellow_pages_lead(result) for result in raw_results if isinstance(result, dict)]


def _yellow_pages_lead(raw_result: dict[str, Any]) -> YellowPagesLead:
    return YellowPagesLead(
        name=str(raw_result.get("name", "")).strip(),
        address=str(raw_result.get("address", "")).strip(),
        phone=str(raw_result.get("phone", "")).strip(),
        website=str(raw_result.get("website", "")).strip(),
    )


def _normalize_website_url(website: str) -> str:
    url = website.strip()
    if not url:
        return ""
    if url.startswith("//"):
        return f"https:{url}"
    if not url.lower().startswith(("http://", "https://")):
        return f"https://{url}"
    return url


def _clean_phone_number(phone: str) -> str:
    digits = "".join(character for character in phone if character.isdigit())
    if digits.startswith("1") and len(digits) > 10:
        return digits[1:]
    return digits


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
