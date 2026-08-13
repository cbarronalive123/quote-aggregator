#!/usr/bin/env python3
"""Export market_registry.db to market_registry.json for hackathon submission."""

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "market_registry.db"
OUT = ROOT / "market_registry.json"

VALIDATED = [
    {
        "registry_id": "allstate-001",
        "insurer_group": "Allstate",
        "brand_or_program": "Allstate",
        "legal_underwriter": "Allstate Insurance Company of Canada",
        "distribution_type": "direct",
        "product_scope": "standard_PPA",
        "distinct_rate_source_id": "allstate",
        "quote_url": "https://apps.allstate.ca/quickquote/common/landing.aspx",
        "public_phone_route": "1-800-255-7828",
        "status": "blocked",
        "last_verified_at": "2026-08-12",
    },
    {
        "registry_id": "aviva-001",
        "insurer_group": "Aviva",
        "brand_or_program": "Aviva Direct",
        "legal_underwriter": "S&Y Insurance Company",
        "distribution_type": "direct",
        "product_scope": "standard_PPA",
        "distinct_rate_source_id": "aviva",
        "quote_url": "https://www.aviva.ca/en/direct/",
        "public_phone_route": "1-855-788-9090",
        "status": "quoted_comparable",
        "last_verified_at": "2026-08-12",
    },
    {
        "registry_id": "intact-belair-001",
        "insurer_group": "Intact",
        "brand_or_program": "belairdirect",
        "legal_underwriter": "Belair Insurance Company Inc.",
        "distribution_type": "direct",
        "product_scope": "standard_PPA",
        "distinct_rate_source_id": "intact",
        "quote_url": "https://www.belairdirect.com/",
        "public_phone_route": "1-833-332-7852",
        "status": "quoted_comparable",
        "last_verified_at": "2026-08-12",
    },
    {
        "registry_id": "coachman-001",
        "insurer_group": "SGI",
        "brand_or_program": "Coachman",
        "legal_underwriter": "Coachman Insurance Company",
        "distribution_type": "broker",
        "product_scope": "nonstandard_PPA",
        "distinct_rate_source_id": "sgi-coachman",
        "public_phone_route": "broker route",
        "status": "callback_required",
        "last_verified_at": "2026-08-09",
    },
    {
        "registry_id": "fa-001",
        "insurer_group": "FA",
        "brand_or_program": "Facility Association",
        "legal_underwriter": "Facility Association",
        "distribution_type": "residual",
        "product_scope": "nonstandard_PPA",
        "distinct_rate_source_id": "fa",
        "quote_url": "https://www.facilityassociation.com",
        "status": "unresolved",
        "last_verified_at": None,
    },
]


def main():
    if not DB.exists():
        import market_registry
        market_registry.create_db(str(DB))

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM rate_sources ORDER BY registry_id")]
    conn.close()

    rate_sources = []
    for r in rows:
        rate_sources.append({
            "registry_id": r["registry_id"],
            "insurer_group": r["insurer_group"],
            "legal_entities": r["legal_entities"],
            "brand": r["brand"] or None,
            "distribution_type": r["distribution_type"],
            "product_scope": r["product_scope"],
            "quote_url": r["quote_url"] or None,
            "public_phone_route": r["public_phone_route"] or None,
            "licensed_intermediary": r.get("licensed_intermediary") or None,
            "distinct_rate_source_id": r["distinct_rate_source_id"] or None,
            "status": r["status"],
            "last_verified_at": r["last_verified_at"],
            "source_citation": r["source_citation"],
            "notes": r["notes"],
        })

    payload = {
        "version": 1,
        "description": (
            "Ontario private-passenger auto insurance rate sources. "
            "Seeded from hackathon brief Appendix A (41 groups). "
            "validated_rate_sources holds live-verified demo carriers."
        ),
        "generated_from": "market_registry.py / export_market_registry.py",
        "count": len(rate_sources),
        "rate_sources": rate_sources,
        "validated_rate_sources": VALIDATED,
    }

    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({len(rate_sources)} seed + {len(VALIDATED)} validated)")


if __name__ == "__main__":
    main()
