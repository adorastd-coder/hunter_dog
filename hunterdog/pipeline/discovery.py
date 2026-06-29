from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import quote_plus

from playwright.sync_api import Page, sync_playwright

from hunterdog.pipeline import config as pipeline_config
from hunterdog.pipeline import discovery_fallback
from hunterdog.pipeline import sheets_client


@dataclass(frozen=True, slots=True)
class DiscoveryLead:
    name: str
    address: str
    phone: str = ""
    website: str = ""
    email: str = ""
    rating: str = ""
    source: str = "Google Maps"
    referenceLink: str = ""

    def to_sheet_row(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "address": self.address,
            "phone": _clean_phone_number(self.phone),
            "website": _normalize_website_url(self.website),
            "email": self.email,
            "rating": self.rating or "N/A",
            "source": self.source,
            "referenceLink": self.referenceLink,
            "scrapedAt": datetime.now(UTC).isoformat(),
            "status": "SCRAPED",
        }


class SheetWritableLead(Protocol):
    def to_sheet_row(self) -> dict[str, Any]:
        pass


def discover() -> list[dict[str, Any]]:
    try:
        config = pipeline_config.get_config()
        existing_leads = sheets_client.get_leads()
        query = _build_query(config.TARGET_NICHE, config.TARGET_CITY)

        discovered_leads = _scrape_google_maps(query, config.DAILY_LIMIT)
        if not discovered_leads:
            discovered_leads = discovery_fallback.scrape_yellow_pages(
                config.TARGET_NICHE,
                config.TARGET_CITY,
                config.DAILY_LIMIT,
            )

        new_rows = _deduplicate_new_leads(existing_leads, discovered_leads)
        sheets_client.write_leads_batch([*existing_leads, *new_rows])
        return new_rows
    except Exception as exc:
        _log_failure(f"Discovery failed: {exc}")
        return []


def run() -> list[dict[str, Any]]:
    return discover()


def _scrape_google_maps(query: str, max_results: int) -> list[DiscoveryLead]:
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/115.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            try:
                page.goto(
                    f"https://www.google.com/maps/search/{quote_plus(query)}?hl=en",
                    wait_until="networkidle",
                    timeout=60000,
                )
                page.wait_for_timeout(3000)
                _scroll_google_maps_results(page, max_results)
                leads = _extract_google_maps_results(page)[:max_results]
                _log_info(f"Discovery source Google Maps produced {len(leads)} leads.")
                return leads
            finally:
                page.close()
                browser.close()
    except Exception as exc:
        _log_failure(f"Google Maps discovery failed: {exc}")
        return []


def _scroll_google_maps_results(page: Page, max_results: int) -> None:
    scroll_container = _first_scroll_container(page)
    if scroll_container is None:
        for _ in range(10):
            page.evaluate("window.scrollBy(0, 1000)")
            page.wait_for_timeout(2000)
        return

    previous_count = 0
    unchanged_count = 0
    for _ in range(50):
        scroll_container.evaluate("(container) => container.scrollTop = container.scrollHeight")
        page.wait_for_timeout(2000)
        result_count = page.locator(".TFQHme").count()
        if result_count >= max_results:
            break
        if result_count == previous_count:
            unchanged_count += 1
            if unchanged_count >= 3:
                break
        else:
            unchanged_count = 0
        previous_count = result_count


def _first_scroll_container(page: Page) -> Any | None:
    for selector in _scroll_selectors():
        element = page.query_selector(selector)
        if element is not None:
            return element
    return None


def _extract_google_maps_results(page: Page) -> list[DiscoveryLead]:
    raw_results = page.evaluate(
        """
        () => {
          const results = [];

          function normalizeUrl(url) {
            return url ? url.trim() : '';
          }

          function isValidWebsiteLink(href) {
            if (!href) return false;
            const lower = href.toLowerCase();
            if (lower.startsWith('mailto:') || lower.startsWith('tel:')) return false;
            if (lower.includes('google.com/maps') || lower.includes('maps.google.com')) return false;
            if (lower.includes('facebook.com') || lower.includes('instagram.com')) return false;
            if (lower.includes('youtube.com') || lower.includes('wa.me') || lower.includes('m.me')) return false;
            return /\\.[a-z]{2,}(\\/|$|\\?)/.test(lower);
          }

          function normalizeEmail(email) {
            return email ? email.trim().replace(/^mailto:/i, '').split('?')[0] : '';
          }

          function isReferenceLink(href) {
            if (!href) return false;
            const lower = href.toLowerCase();
            return lower.includes('google.com/maps/place') || lower.includes('maps.app.goo.gl') || lower.includes('/place/');
          }

          function collectEmail(value, emails) {
            const normalized = normalizeEmail(value);
            if (/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(normalized) && !emails.includes(normalized)) {
              emails.push(normalized);
            }
          }

          function extractBusinessFromCard(card) {
            const nameElement = card.querySelector('.qBF1Pd.fontHeadlineSmall');
            const name = nameElement ? nameElement.textContent.trim() : '';
            const allSpans = Array.from(card.querySelectorAll('span'));

            let address = '';
            for (const span of allSpans) {
              const text = span.textContent.trim();
              if (text.includes('Street') || text.includes('Road') || text.includes('Ave') || text.includes('Blvd') || text.includes('Dr') || text.includes('St,') || text.includes('Suite') || text.includes('Rd') || text.includes('Lane') || /\\d{1,5}\\s+\\w/.test(text)) {
                address = text.replace(/^[^A-Za-z0-9]+\\s*/, '');
                break;
              }
            }

            let phone = '';
            for (const span of allSpans) {
              const text = span.textContent.trim();
              if (/[\\+\\(]?\\d[\\d\\s\\-\\(\\)]{7,}\\d/.test(text)) {
                phone = text;
                break;
              }
            }

            const ratingElement = card.querySelector('.MW4etd');
            const emails = [];
            let website = '';
            let referenceLink = '';

            for (const link of Array.from(card.querySelectorAll('a'))) {
              const href = link.href || '';
              const text = link.textContent.trim();
              if (isReferenceLink(href) && !referenceLink) referenceLink = href;
              if (href.toLowerCase().startsWith('tel:') && !phone) {
                phone = href.replace(/^tel:/i, '').trim();
              }
              if (href.toLowerCase().startsWith('mailto:')) collectEmail(href, emails);
              if (text.includes('@')) collectEmail(text, emails);
              if (!website && isValidWebsiteLink(href)) website = normalizeUrl(href);
            }

            if (!referenceLink) {
              const cardLink = card.querySelector('a[href]');
              const href = cardLink ? cardLink.href : '';
              if (isReferenceLink(href)) referenceLink = href;
            }

            const textEmails = Array.from(new Set((card.textContent || '').match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/g) || []));
            textEmails.forEach((email) => collectEmail(email, emails));

            return {
              name,
              address,
              phone,
              website,
              email: emails[0] || '',
              rating: ratingElement ? ratingElement.textContent.trim() : '',
              referenceLink
            };
          }

          const separators = Array.from(document.querySelectorAll('.TFQHme'));
          for (const separator of separators) {
            const businessCard = separator.nextElementSibling
              ? separator.nextElementSibling.querySelector('.Nv2PK')
              : null;
            if (businessCard) {
              const business = extractBusinessFromCard(businessCard);
              if (business.name && business.address) results.push(business);
            }
          }

          if (results.length === 0) {
            for (const card of Array.from(document.querySelectorAll('.Nv2PK'))) {
              const business = extractBusinessFromCard(card);
              if (business.name && business.address) results.push(business);
            }
          }

          return results;
        }
        """
    )
    return [_google_maps_lead(result) for result in raw_results if isinstance(result, dict)]


def _deduplicate_new_leads(
    existing_leads: list[dict[str, Any]],
    discovered_leads: list[SheetWritableLead],
) -> list[dict[str, Any]]:
    seen_keys = {_dedupe_key(lead) for lead in existing_leads}
    seen_keys.discard("")

    new_rows: list[dict[str, Any]] = []
    for lead in discovered_leads:
        row = lead.to_sheet_row()
        key = _dedupe_key(row)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        new_rows.append(row)
    return new_rows


def _build_query(target_niche: str, target_city: str) -> str:
    niche = target_niche.strip()
    city = target_city.strip()
    if not niche and not city:
        return "businesses"
    if city and city.lower() not in niche.lower():
        return f"{niche or 'businesses'} near {city}".strip()
    return niche


def _google_maps_lead(raw_result: dict[str, Any]) -> DiscoveryLead:
    return DiscoveryLead(
        name=str(raw_result.get("name", "")).strip(),
        address=str(raw_result.get("address", "")).strip(),
        phone=str(raw_result.get("phone", "")).strip(),
        website=str(raw_result.get("website", "")).strip(),
        email=str(raw_result.get("email", "")).strip(),
        rating=str(raw_result.get("rating", "")).strip(),
        source="Google Maps",
        referenceLink=str(raw_result.get("referenceLink", "")).strip(),
    )


def _dedupe_key(row: dict[str, Any]) -> str:
    name = _row_value(row, "name")
    address = _row_value(row, "address")
    if not name or not address:
        return ""
    return f"{_normalize_key(name)}|{_normalize_key(address)}"


def _row_value(row: dict[str, Any], key: str) -> str:
    for candidate in (key, key.title(), key.upper()):
        if candidate in row:
            return str(row.get(candidate, "") or "")
    return ""


def _normalize_key(value: str) -> str:
    return " ".join(value.lower().split())


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


def _scroll_selectors() -> tuple[str, ...]:
    return (
        '[role="feed"]',
        ".m6QErb.DxyBCb.kA9KIf.dS8AEf.XiKgde.ecceSd",
        '[role="main"]',
        ".section-layout",
        ".section-scrollbox",
        ".scrollable-y",
        '[data-role="region"]',
    )


def _log_failure(message: str) -> None:
    try:
        sheets_client.log_run(message=message, level="ERROR")
    except Exception:
        pass


def _log_info(message: str) -> None:
    try:
        sheets_client.log_run(message=message, level="INFO")
    except Exception:
        pass
