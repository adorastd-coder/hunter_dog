from __future__ import annotations

from typing import Any, Mapping

from hunterdog.pipeline import config as pipeline_config
from hunterdog.pipeline import sheets_client


def score_leads() -> list[dict[str, Any]]:
    try:
        runtime_config = pipeline_config.get_config()
        leads = sheets_client.get_leads()
    except Exception as exc:
        _log_failure(f"Scoring failed to initialize: {exc}")
        return []

    updated_rows: list[dict[str, Any]] = []
    failure_messages: list[str] = []
    for lead in leads:
        if _status(lead) != "ENRICHED":
            continue

        try:
            score = calculate_lead_score(lead, runtime_config.TARGET_NICHE)
        except Exception as exc:
            failure_messages.append(f"Scoring failed for {_lead_label(lead)}: {exc}")
            continue

        lead["score"] = score
        lead["bucket"] = _bucket(score)
        lead["status"] = "SCORED"
        updated_rows.append(lead)

    try:
        sheets_client.write_leads_batch(leads)
    except Exception as exc:
        _log_failure(f"Scoring failed to write leads: {exc}")
        return []

    if failure_messages:
        _log_failure("; ".join(failure_messages))

    _log_info(f"Scoring updated {len(updated_rows)} leads.")
    return updated_rows


def run() -> list[dict[str, Any]]:
    return score_leads()


def calculate_lead_score(lead: Mapping[str, Any], industry: str) -> int:
    if _is_out_of_target_market(lead):
        base_score = 20
    else:
        base_score = _weighted_score(
            {
                "data_completeness": _score_data_completeness(lead),
                "business_quality": _score_business_quality(lead),
                "digital_presence": _score_digital_presence(lead),
                "location_value": _score_location(lead),
                "industry_potential": _score_industry_potential(industry),
                "contactability": _score_contactability(lead),
            }
        )

    return _clamp_score(base_score + _bonus_score(lead))


def _weighted_score(factors: Mapping[str, int]) -> int:
    # These weights intentionally follow the finalized Hunter Dog scoring spec.
    weights = {
        "data_completeness": 25,
        "business_quality": 25,
        "digital_presence": 20,
        "location_value": 15,
        "industry_potential": 15,
        "contactability": 10,
    }
    total = sum(factors[key] * weight / 100 for key, weight in weights.items())
    return round(min(total, 100))


def _bonus_score(lead: Mapping[str, Any]) -> int:
    bonus = 0
    page_speed_score = _optional_float(_row_value(lead, "page_speed_score"))
    if page_speed_score is not None and page_speed_score < 60:
        bonus += 10

    if _optional_bool(_row_value(lead, "mobile_friendly")) is False:
        bonus += 10

    if _optional_bool(_row_value(lead, "ads_running")) is False:
        bonus += 15

    return bonus


def _score_data_completeness(lead: Mapping[str, Any]) -> int:
    score = 0
    if _row_value(lead, "name").strip():
        score += 25
    if _row_value(lead, "address").strip():
        score += 20
    if _row_value(lead, "phone").strip():
        score += 25
    website = _row_value(lead, "website").strip()
    if website and website.upper() != "N/A":
        score += 15
    if _optional_float(_row_value(lead, "rating")) is not None:
        score += 10
    if _row_value(lead, "email").strip():
        score += 5
    return min(score, 100)


def _score_business_quality(lead: Mapping[str, Any]) -> int:
    score = 50

    rating = _optional_float(_row_value(lead, "rating"))
    if rating is not None:
        if rating >= 4.5:
            score += 30
        elif rating >= 4.0:
            score += 20
        elif rating >= 3.5:
            score += 10
        elif rating < 3.0:
            score -= 10

    name = _row_value(lead, "name").strip().lower()
    if name:
        if "official" in name or "group" in name or "center" in name:
            score += 10
        if len(name) > 30:
            score -= 5
        if len(name) < 5:
            score -= 10

    address = _row_value(lead, "address").strip().lower()
    if address:
        if (
            "street" in address
            or "ave" in address
            or "blvd" in address
            or "rd" in address
        ):
            score += 5
        if (
            "suite" in address
            or "floor" in address
            or "clinic" in address
            or "centre" in address
        ):
            score += 10

    return _clamp_score(score)


def _score_digital_presence(lead: Mapping[str, Any]) -> int:
    score = 20
    website = _row_value(lead, "website").strip().lower()
    if website and website.upper() != "N/A":
        score += 40
        if ".com" in website or ".co.uk" in website or ".com.au" in website:
            score += 10
        if "instagram" in website or "facebook" in website:
            score += 5
        elif "http" in website:
            score += 15

    description = _row_value(lead, "description").strip().lower()
    if description:
        if "instagram" in description or "facebook" in description:
            score += 10
        if "whatsapp" in description or "wa" in description:
            score += 5

    if _row_value(lead, "phone").strip():
        score += 15

    return min(score, 100)


def _score_location(lead: Mapping[str, Any]) -> int:
    address = _row_value(lead, "address").strip().lower()
    if not address:
        return 50
    if _is_out_of_target_market(lead):
        return 0

    for city, score in _location_economy_scores().items():
        if city != "default" and city in address:
            return score
    return _location_economy_scores()["default"]


def _score_industry_potential(industry: str) -> int:
    normalized_industry = str(industry or "").strip().lower()
    industry_scores = _industry_scores()
    if normalized_industry not in industry_scores:
        return 70

    values = industry_scores[normalized_industry]
    return round((values["potential"] + values["digital_readiness"] + values["urgency"]) / 3)


def _score_contactability(lead: Mapping[str, Any]) -> int:
    if _is_out_of_target_market(lead):
        return 0

    score = 0
    phone = _row_value(lead, "phone").strip()
    if phone:
        score += 50
        if "+1" in phone or "+44" in phone or "+61" in phone or "+971" in phone:
            score += 20

    if _row_value(lead, "email").strip():
        score += 20

    website = _row_value(lead, "website").strip()
    if website and website.upper() != "N/A":
        score += 10

    return min(score, 100)


def _bucket(score: int) -> str:
    # A+/A map to the old HOT opportunity band, B/C/D to WARM, and E to COLD.
    if score >= 85:
        return "A+"
    if score >= 75:
        return "A"
    if score >= 65:
        return "B"
    if score >= 55:
        return "C"
    if score >= 45:
        return "D"
    return "E"


def _is_out_of_target_market(lead: Mapping[str, Any]) -> bool:
    text = " ".join(
        (
            _row_value(lead, "address"),
            _row_value(lead, "phone"),
            _row_value(lead, "website"),
        )
    ).lower()
    phone_digits = "".join(character for character in _row_value(lead, "phone") if character.isdigit() or character == "+")
    target_prefixes = ("1", "44", "61", "971")
    foreign_prefixes = ("92", "91", "880", "62", "63", "234")
    has_foreign_phone = any(
        phone_digits.startswith(f"+{prefix}") or phone_digits.startswith(prefix)
        for prefix in foreign_prefixes
    )
    has_target_phone = any(
        phone_digits.startswith(f"+{prefix}") or phone_digits.startswith(prefix)
        for prefix in target_prefixes
    )
    if has_foreign_phone and not has_target_phone:
        return True

    market_terms = (
        "pakistan",
        "lahore",
        "karachi",
        "islamabad",
        "rawalpindi",
        "india",
        "delhi",
        "mumbai",
        "bangladesh",
        "indonesia",
        "philippines",
        "nigeria",
    )
    return any(term in text for term in market_terms)


def _industry_scores() -> dict[str, dict[str, int]]:
    return {
        "dentist": {"potential": 90, "digital_readiness": 70, "urgency": 85},
        "orthodontist": {"potential": 92, "digital_readiness": 72, "urgency": 88},
        "cosmetic dentist": {"potential": 95, "digital_readiness": 75, "urgency": 90},
        "dental implants": {"potential": 95, "digital_readiness": 70, "urgency": 92},
        "pediatric dentist": {"potential": 88, "digital_readiness": 68, "urgency": 85},
        "emergency dentist": {"potential": 85, "digital_readiness": 65, "urgency": 95},
        "private school": {"potential": 80, "digital_readiness": 72, "urgency": 78},
    }


def _location_economy_scores() -> dict[str, int]:
    return {
        "new york": 98,
        "los angeles": 96,
        "houston": 90,
        "chicago": 92,
        "toronto": 90,
        "vancouver": 88,
        "sydney": 90,
        "melbourne": 88,
        "london": 95,
        "manchester": 82,
        "dubai": 95,
        "abu dhabi": 90,
        "jakarta": 80,
        "default": 72,
    }


def _optional_float(value: Any) -> float | None:
    raw_value = str(value or "").strip()
    if not raw_value:
        return None
    try:
        return float(raw_value)
    except ValueError:
        return None


def _optional_bool(value: Any) -> bool | None:
    raw_value = str(value or "").strip().lower()
    if raw_value in {"true", "yes", "1"}:
        return True
    if raw_value in {"false", "no", "0"}:
        return False
    return None


def _clamp_score(score: int | float) -> int:
    return max(0, min(round(score), 100))


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
