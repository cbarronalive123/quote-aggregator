"""Quote outcome export for the auto quote agent.

Produces the exact `QuoteOutcome` JSON shape documented in
`auto_quote_agent/quote_result_json.md` (Section 1) and saves it as a
timestamped file under `auto_quote_agent/recordings/`.

Follows the rules: numbers are JSON numbers, timestamps are ISO 8601 UTC (Z),
money is CAD, and only the allowed `status` enum values are used.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

from app.quote.quote_notes import QuoteRecord

RECORDINGS_DIR = Path(__file__).resolve().parent.parent.parent / "auto_quote_agent" / "recordings"

_STATUS_MAP = {
    "quoted": "quoted_comparable",
    "quoted_comparable": "quoted_comparable",
    "quoted_non_comparable": "quoted_non_comparable",
    "estimate": "estimate_only",
    "callback": "callback_required",
    "manual_handoff": "manual_handoff",
    "blocked": "blocked",
    "unreachable": "unreachable",
    "ineligible": "ineligible",
    "unresolved": "unresolved",
}


def _registry_id(brand: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", brand.lower()).strip("-")
    return f"{slug}-001" if slug else "carrier-001"


def _iso_date(value: str) -> str | None:
    if not value:
        return None
    v = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def build_outcome(
    quote: QuoteRecord,
    profile=None,
    terminal_status: str = "quoted",
    confidence: str = "medium",
    source: str = "phone",
) -> dict:
    brand = (quote.company or "Allstate").strip() or "Allstate"
    effective = None
    if profile is not None:
        f = profile.get("coverage_start_date")
        if f is not None and f.has_value():
            effective = _iso_date(f.value)

    expiry = _iso_date(quote.valid_until)
    if expiry is None and effective is not None:
        try:
            expiry = (datetime.fromisoformat(effective) + timedelta(days=365)).date().isoformat()
        except ValueError:
            expiry = None

    discounts = []
    if profile is not None:
        for key, label in (("winter_tires", "winter tires"), ("anti_theft", "anti-theft")):
            f = profile.get(key)
            if f is not None and f.has_value() and str(f.value).strip().lower().startswith("y"):
                discounts.append(label)

    coverage_notes = _coverage_notes(profile)

    return {
        "registry_id": _registry_id(brand),
        "brand": brand,
        "status": _STATUS_MAP.get(terminal_status, "unresolved"),
        "annual_premium": quote.annual,
        "monthly_premium": quote.monthly,
        "quote_id": quote.reference_number or None,
        "effective_date": effective,
        "expiry_date": expiry,
        "coverage_notes": coverage_notes,
        "discounts": discounts,
        "confidence": confidence,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "source": source,
        "evidence": None,
        "recording": None,
    }


def _coverage_notes(profile) -> str:
    if profile is None:
        return ""
    parts = []
    f = profile.get("liability_limits")
    if f and f.has_value():
        parts.append(f"{f.value} TPL")
    f = profile.get("dcpd")
    if f and f.has_value():
        parts.append("DCPD incl")
    f = profile.get("deductible_pref")
    if f and f.has_value():
        parts.append(f"{f.value} deductibles")
    f = profile.get("endorsements")
    if f and f.has_value():
        parts.append("OPCF 44R")
    f = profile.get("telematics")
    if f and f.has_value() and str(f.value).strip().lower().startswith("n"):
        parts.append("no telematics")
    return ", ".join(parts)


def save_outcome(quote: QuoteRecord, profile=None, terminal_status: str = "quoted",
                 confidence: str = "medium", source: str = "phone") -> Path:
    outcome = build_outcome(quote, profile, terminal_status, confidence, source)
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = RECORDINGS_DIR / f"quote_{ts}.json"
    path.write_text(json.dumps(outcome, indent=2), encoding="utf-8")
    return path
