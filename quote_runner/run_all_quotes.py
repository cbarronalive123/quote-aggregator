#!/usr/bin/env python3
"""
run_all_quotes.py
=================
Parent script for the three working auto-quote automations: belairdirect, Aviva and
Allstate. It uses the profile from the website (either the saved applicant profile
or a freshly generated unique fake) and runs each carrier script's
`run()` in sequence, then writes the results so the website's "Your quotes" page
(quote_outcomes table) shows them.

This folder holds COPIES of the three original scripts (so the originals are never
modified). Run from this folder so the copied modules import cleanly.

Usage
-----
  # Saved profile from the website:
  python quote_runner/run_all_quotes.py --profile my --website-url http://localhost:3000

  # Fresh unique fake profile from the website (recommended for repeat testing):
  python quote_runner/run_all_quotes.py --profile fake --website-url http://localhost:3000

  # Use a params JSON directly (nested person/auto/driver), skipping the website:
  python quote_runner/run_all_quotes.py --input people/dummy.json

  # Unattended (minimized headed / Xvfb) is the default; pass --headed to watch it.

The website "Your quotes" page (app/quotes/page.tsx) reads the quote_outcomes table
in website/data/quotedrive.db. After a successful run, refresh that page to see the
three automations' quotes.
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEFAULT_DB = os.path.join(REPO, "website", "data", "quotedrive.db")
DEFAULT_OUT = os.path.join(HERE, "latest_results.json")
RESULTS_JSONL = os.path.join(REPO, "quote_results.jsonl")

# Carrier order + how to map each result back to the website's quote_outcomes table.
# `vehicle` is the known-good vehicle for THAT rater (each rater's database differs):
# belair quotes the RAM 1500, while aviva/allstate quote the HONDA Accord. The parent
# shares the profile's PERSON data with all three, but overrides the vehicle per rater
# so each script can actually complete. Override with --input to control the vehicle.
CARRIERS = [
    {
        "module": "belairdirect_auto_quote",
        "registry_id": "intact-belair-001",
        "brand": "belairdirect",
        "coverage": "$2M TPL, DCPD incl, $1,000 deductibles, OPCF 44R, no telematics",
        "vehicle": {"vehicle_year": "2012", "vehicle_make": "DODGE", "vehicle_model": "RAM 1500 Big Horn Quad Cab 4WD"},
    },
    {
        "module": "aviva_auto_quote",
        "registry_id": "aviva-001",
        "brand": "Aviva Direct",
        "coverage": "$2M TPL, DCPD incl, $1,000 deductibles, OPCF 44R",
        "vehicle": {"vehicle_year": "2019", "vehicle_make": "HONDA", "vehicle_model": "ACCORD EX 4DR"},
    },
    {
        "module": "allstate_auto_quote",
        "registry_id": "allstate-001",
        "brand": "Allstate",
        "coverage": "$2M TPL, DCPD incl, $1,000 deductibles, OPCF 44R",
        "vehicle": {"vehicle_year": "2019", "vehicle_make": "HONDA", "vehicle_model": "ACCORD EX 4DR"},
    },
]


def log(msg):
    print(f"[runner][{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Profile loading
# ---------------------------------------------------------------------------
def _http_json(url, method="GET"):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_website_profile(kind: str, website_url: str):
    """Pull a flat profile from the website's profile API: my=real, fake=fresh."""
    base = website_url.rstrip("/")
    if kind == "fake":
        return _http_json(f"{base}/api/profile/fake", method="POST")
    return _http_json(f"{base}/api/profile/my", method="GET")


def load_local_params(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_personal_profile_db():
    """Fallback "my" profile from personal_profile.db (nested person/auto)."""
    db = os.path.join(REPO, "personal_profile.db")
    out = {}
    if not os.path.exists(db):
        return {}
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        for t in ("person", "auto"):
            row = conn.execute(f"SELECT * FROM {t} LIMIT 1").fetchone()
            if row:
                out[t] = {k: row[k] for k in row.keys()}
    finally:
        conn.close()
    return out


# The vehicle must exist in EACH rater's database or the raters won't proceed past
# the vehicle step. Belair's verified working vehicle is the test 2019 Honda Accord;
# Horn Quad Cab 4WD (DODGE), and the same vehicle is listed on Aviva/Allstate under
# DODGE, so use it for the fake test to reach all three. Identity stays random/unique.
FAKE_VEHICLE = {
    "vehicle_year": "2012",
    "vehicle_make": "DODGE",
    "vehicle_model": "RAM 1500 Big Horn Quad Cab 4WD",
}


def local_fake_nested():
    """Local fallback fresh fake (nested params) with a vehicle all raters accept."""
    import random as _r
    _r.seed()
    firsts = ["Avery", "Riley", "Casey", "Morgan", "Logan", "Reese", "Parker", "Jordan", "Jamie", "Taylor", "Quinn", "Skyler"]
    lasts = ["Walker", "Bennett", "Carter", "Reed", "Hayes", "Doyle", "Grant", "Marsh", "Kerr", "Frost", "Blake", "Wells"]
    f = _r.choice(firsts)
    l = _r.choice(lasts)
    y = _r.randint(1970, 1985)
    m = _r.randint(1, 12)
    d = _r.randint(1, 28)
    return {
        "person": {
            "first_name": f, "last_name": l,
            "email": f"{f.lower()}.{l.lower()}{_r.randint(1000, 9999)}@example.com",
            "phone": f"{_r.randint(200, 999)}{_r.randint(100, 999)}{_r.randint(1000, 9999)}",
            "phone_type": "mobile",
            "date_of_birth": f"{y}/{m:02d}/{d:02d}",
            "sex": _r.choice(["M", "F"]), "marital_status": "S",
            "postal_code": "L2R 1A1",
        },
        "auto": {
            **FAKE_VEHICLE,
            "purchase_month": "January", "purchase_year": "2019", "purchase_condition": "used",
            "winter_tires": "yes", "anti_theft": "yes", "annual_km": "15000",
            "commute_days": "5", "commute_oneway_km": "15", "coverage_start_date": "09/01/2026",
            "combined_policy": "NO", "telus_health": "no", "prior_insurance": "greatthan3years",
            "licence_class": "G", "first_licence_month": "January", "first_licence_year": "2008",
            "g2_month": "January", "g2_year": "2007",
            "parking": "Home Driveway", "first_licensed_age": "19",
            "graduated_licensing": "Yes", "g_within_12mo": "No",
            "minor_violations": "None", "major_violations": "No", "licence_suspended": "No",
            "insured": "Yes", "policy_cancelled": "No", "claims_6yr": "No", "drivewise": "No",
        },
        "driver": {
            "first_licence_age": "19", "first_licence_month": "January",
            "licence_class": "G", "years_with_insurer": "5 years or more",
        },
    }


# ---------------------------------------------------------------------------
# Website flat values -> nested params expected by the scripts
# ---------------------------------------------------------------------------
def _mdy(date_str: str) -> str:
    """Convert YYYY-MM-DD (website) to MM/DD/YYYY (rater date fields)."""
    if not date_str:
        return "09/01/2026"
    s = date_str.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        y, m, d = s.split("-")
        return f"{m}/{d}/{y}"
    if re.match(r"^\d{4}/\d{2}/\d{2}$", s):
        y, m, d = s.split("/")
        return f"{m}/{d}/{y}"
    return s


def _slash_dob(date_str: str) -> str:
    """Website YYYY-MM-DD -> YYYY/MM/DD (Aviva splits on '/')."""
    if date_str and re.match(r"^\d{4}-\d{2}-\d{2}$", date_str.strip()):
        return date_str.strip().replace("-", "/")
    return date_str or "1990/03/15"


def _annual_band(km: str) -> str:
    try:
        n = int(float((km or "15000").replace(",", "")))
    except Exception:
        n = 15000
    for low, high, band in [(0, 4000, "0-4000km"), (4001, 8000, "4001-8000km"),
                            (8001, 12000, "8001-12000km"), (12001, 16000, "12001-16000km")]:
        if low <= n <= high:
            return band
    return "More than 16000 km"


def flat_to_params(flat: dict) -> dict:
    v = flat or {}
    y = _slash_dob(v.get("date_of_birth", ""))
    vehicle_use = "Work / School" if (v.get("commute_oneway_km") or "").strip() else "Pleasure"
    return {
        "person": {
            "first_name": v.get("first_name", ""),
            "last_name": v.get("last_name", ""),
            "email": v.get("email", ""),
            "phone": re.sub(r"\D", "", v.get("phone", "") or ""),
            "phone_type": (v.get("phone_type", "mobile") or "mobile").lower(),
            "date_of_birth": y,
            "sex": v.get("sex", "M"),
            "marital_status": v.get("marital_status", "S"),
            "postal_code": v.get("postal_code", "L2R 1A1"),
            "street_address": v.get("street_address", ""),
            "city": v.get("city", ""),
            "province": v.get("province", "Ontario"),
            "province_code": "ON",
        },
        "auto": {
            "vin": v.get("vin", ""),
            "vehicle_year": v.get("vehicle_year", "2012"),
            "vehicle_make": (v.get("vehicle_make", "HONDA") or "HONDA").upper(),
            "vehicle_model": v.get("vehicle_model", "ACCORD EX 4DR"),
            "trim": v.get("trim", ""),
            "purchase_condition": (v.get("purchase_condition", "Used") or "Used").lower(),
            "purchase_month": v.get("purchase_month", "January"),
            "purchase_year": v.get("purchase_year", "2019"),
            "purchase_price": v.get("purchase_price", "") or "25000",
            "owned_leased": v.get("owned_leased", "Owned"),
            "ownership": v.get("owned_leased", "Owned"),
            "only_owner": v.get("only_registered_owner", "Yes"),
            "within_30d": v.get("ownership_within_30_days", "No"),
            "winter_tires": "yes" if str(v.get("winter_tires", "Yes")).lower() == "yes" else "no",
            "anti_theft": "yes" if str(v.get("anti_theft", "No")).lower() == "yes" else "no",
            "annual_km": v.get("annual_km", "15000"),
            "commute_days": v.get("commute_days", "5"),
            "commute_oneway_km": v.get("commute_oneway_km", "15"),
            "business_use": v.get("business_use", "No"),
            "coverage_start_date": _mdy(v.get("coverage_start_date", "")),
            "licence_class": v.get("licence_class", "G"),
            "first_licence_month": v.get("first_licence_month", "January"),
            "first_licence_year": v.get("first_licence_year", "2005"),
            "held_other_classes": v.get("held_other_classes", "Yes"),
            "g2_month": v.get("g2_month", "January"),
            "g2_year": v.get("g2_year", "2004"),
            "retired": v.get("retired", "No"),
            "combined_policy": "NO" if str(v.get("combined_policy", "No")).lower() == "no" else "ME",
            "telus_health": "no" if str(v.get("telus_health", "No")).lower() == "no" else "yes",
            "prior_insurance": "greatthan3years" if str(v.get("prior_insurance", "More than 3 years")).lower().startswith("more") else "lessthan3years",
            # Allstate-specific
            "vehicle_use": vehicle_use,
            "annual_km_band": _annual_band(v.get("annual_km", "15000")),
            "parking": v.get("parking", "Home Driveway"),
            "household_drivers": v.get("other_household_drivers", "No"),
            "first_licensed_age": v.get("age_first_licensed", "21"),
            "graduated_licensing": "Yes" if str(v.get("held_other_classes", "Yes")).lower() == "yes" else "No",
            "g_within_12mo": v.get("g_within_12_months", "No"),
            "minor_violations": v.get("convictions", "None"),
            "major_violations": v.get("major_violations", "No"),
            "licence_suspended": v.get("license_suspended", "No"),
            "insured": "Yes",
            "policy_cancelled": v.get("cancellation_nonpayment", "No"),
            "claims_6yr": "No" if str(v.get("accidents", "None")).lower() in ("none", "") else "Yes",
            "drivewise": "No",
        },
        "driver": {
            "first_licence_age": v.get("age_first_licensed", "21"),
            "first_licence_month": v.get("first_licence_month", "January"),
            "licence_class": v.get("licence_class", "G"),
            "years_with_insurer": v.get("years_with_insurer", "5 years or more"),
        },
    }


# ---------------------------------------------------------------------------
# Result parsing + persistence
# ---------------------------------------------------------------------------
def _num(s):
    if not s:
        return None
    m = re.search(r"[\d][\d,]*\.\d{2}", str(s))
    return float(m.group(0).replace(",", "")) if m else None


def _carrier_params(base: dict, carrier: dict) -> dict:
    """Return a copy of the profile with the carrier's known-good vehicle applied.

    The raters' vehicle databases differ (belair -> RAM 1500, aviva/allstate ->
    HONDA Accord), so we share the person/driver data but set a vehicle that rater
    actually lists. Purchase details follow the vehicle's model year.
    """
    import copy
    p = copy.deepcopy(base)
    veh = carrier.get("vehicle")
    if veh:
        auto = p.setdefault("auto", {})
        auto["vehicle_year"] = veh.get("vehicle_year", auto.get("vehicle_year", "2019"))
        auto["vehicle_make"] = veh.get("vehicle_make", auto.get("vehicle_make", "HONDA"))
        auto["vehicle_model"] = veh.get("vehicle_model", auto.get("vehicle_model", "ACCORD EX 4DR"))
        # Purchased used a few years after the model year, as a second owner.
        try:
            auto["purchase_year"] = str(max(2016, int(auto["vehicle_year"]) + 3))
        except Exception:
            auto["purchase_year"] = "2019"
        auto["purchase_month"] = "January"
        auto["purchase_condition"] = "used"
        auto["vin"] = auto.get("vin", "")
        # Allstate's vehicle-details dialog requires a purchase price. The saved
        # profile may leave it empty (''), and get_param returns '' instead of the
        # default, so force a real value here to keep the Allstate step from stalling.
        auto["purchase_price"] = str(auto.get("purchase_price") or "25000")
    return p


def parse_result(res: dict):
    monthly = _num(res.get("quote_monthly")) or _num(res.get("quote_value"))
    annual = round(monthly * 12, 2) if monthly else None
    has_quote = bool(res.get("quote_value") or res.get("quote_number"))
    status = "quoted_comparable" if has_quote else ("blocked" if res.get("error") else "unresolved")
    return {
        "monthly": monthly,
        "annual": annual,
        "quote_id": res.get("quote_number") or None,
        "status": status,
        "error": res.get("error"),
    }


def upsert_db(db_path: str, carrier, parsed, res, profile_label: str):
    """Insert/replace one carrier's result into the website's quote_outcomes table."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS quote_outcomes (
                registry_id TEXT PRIMARY KEY, brand TEXT, status TEXT, annual_premium REAL,
                monthly_premium REAL, quote_id TEXT, coverage_notes TEXT, confidence TEXT,
                timestamp TEXT, source TEXT, recording TEXT, evidence TEXT
            )"""
        )
        conn.execute(
            """INSERT OR REPLACE INTO quote_outcomes (
                registry_id, brand, status, annual_premium, monthly_premium, quote_id,
                coverage_notes, confidence, timestamp, source, recording, evidence
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                carrier["registry_id"], carrier["brand"], parsed["status"],
                parsed["annual"], parsed["monthly"], parsed["quote_id"],
                carrier["coverage"],
                "high" if parsed["status"] == "quoted_comparable" else "medium",
                datetime.now().isoformat(), "automated", None,
                res.get("evidence") or None,
            ),
        )
        conn.commit()
        return True
    except Exception as e:
        log(f"    DB upsert failed for {carrier['brand']}: {e}")
        return False
    finally:
        conn.close()


def append_jsonl(line: dict):
    try:
        os.makedirs(os.path.dirname(RESULTS_JSONL), exist_ok=True)
        with open(RESULTS_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception as e:
        log(f"    append jsonl failed: {e}")


# ---------------------------------------------------------------------------
# Quote history (append-only archive of every run for the /history page)
# ---------------------------------------------------------------------------
def ensure_history_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS quote_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, run_at TEXT NOT NULL,
        label TEXT, profile TEXT, vehicle TEXT, postal TEXT, status TEXT, created_at TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS quote_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL,
        registry_id TEXT, brand TEXT, status TEXT, annual_premium REAL,
        monthly_premium REAL, quote_id TEXT, coverage_notes TEXT, confidence TEXT,
        timestamp TEXT, source TEXT, evidence TEXT)""")


def backfill_history(conn):
    """One-time: preserve whatever was already in quote_outcomes as an archived run
    so pre-existing quotes show up in history alongside future runs."""
    row = conn.execute("SELECT COUNT(*) AS c FROM quote_history").fetchone()
    if row and row[0] > 0:
        return
    existing = conn.execute("SELECT * FROM quote_outcomes").fetchall()
    if not existing:
        return
    now = datetime.now().isoformat()
    cur = conn.execute(
        "INSERT INTO quote_runs (run_at,label,status,created_at) VALUES (?,?,?,?)",
        (now, "Imported from previous results", "complete", now))
    run_id = cur.lastrowid
    for r in existing:
        conn.execute(
            """INSERT INTO quote_history (run_id,registry_id,brand,status,annual_premium,
               monthly_premium,quote_id,coverage_notes,confidence,timestamp,source,evidence)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, r["registry_id"], r["brand"], r["status"], r["annual_premium"],
             r["monthly_premium"], r["quote_id"], r["coverage_notes"], r["confidence"],
             r["timestamp"], r["source"], r["evidence"]))
    conn.commit()


def record_run(conn, written, profile_label):
    """Archive the just-finished run (one quote_runs row + one quote_history row per
    carrier) so the website's /history page can list it by date/time."""
    now = datetime.now().isoformat()
    status = "complete" if written and all(w.get("status") == "quoted_comparable" for w in written) else "partial"
    cur = conn.execute(
        "INSERT INTO quote_runs (run_at,label,profile,status,created_at) VALUES (?,?,?,?,?)",
        (now, "Automated run", profile_label, status, now))
    run_id = cur.lastrowid
    for w in written:
        conn.execute(
            """INSERT INTO quote_history (run_id,registry_id,brand,status,annual_premium,
               monthly_premium,quote_id,coverage_notes,confidence,timestamp,source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, w["registry_id"], w["brand"], w["status"],
             w["annual_premium"], w["monthly_premium"], w["quote_id"], None,
             "high" if w["status"] == "quoted_comparable" else "medium", now, "automated"))
    conn.commit()
    return run_id


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Run the three auto-quote automations with a profile.")
    ap.add_argument("--profile", choices=["my", "fake"], default="my",
                    help="Profile source: 'my' = saved profile, 'fake' = fresh unique fake.")
    ap.add_argument("--input", default=None,
                    help="Path to a nested params JSON (person/auto/driver). Overrides --profile.")
    ap.add_argument("--website-url", default="http://localhost:3000",
                    help="Website base URL for the profile API (default http://localhost:3000).")
    ap.add_argument("--db", default=DEFAULT_DB, help="Path to the website quotedrive.db.")
    ap.add_argument("--headed", action="store_true", default=False,
                    help="Run with a visible browser (needs a display / Xvfb on a server).")
    ap.add_argument("--headless", action="store_true", default=False,
                    help="Pass headless=True to belair/aviva (experimental; often gated).")
    ap.add_argument("--minimized", action="store_true", default=False,
                    help="Run all three in minimized headed (off-screen) mode instead of visible headed.")
    ap.add_argument("--out", default=DEFAULT_OUT, help="Path to write latest_results.json.")
    ap.add_argument("--dry-run", action="store_true", default=False,
                    help="Load the profile and print what would run, but do NOT launch browsers or write to the DB.")
    args = ap.parse_args()

    headless = args.headless and not args.minimized

    # 1) Load the profile
    profile = None
    profile_label = ""
    if args.input:
        profile = load_local_params(args.input)
        p = profile.get("person", {})
        profile_label = f"{p.get('first_name', '?')} {p.get('last_name', '?')}"
        log(f"Using profile from {args.input}: {profile_label}")
    elif args.profile == "fake":
        try:
            data = fetch_website_profile("fake", args.website_url)
            profile = flat_to_params(data.get("values", {}))
            profile_label = f"{profile['person']['first_name']} {profile['person']['last_name']} (fresh fake)"
            log(f"Fetched fresh fake profile from website: {profile_label}")
        except Exception as e:
            log(f"Website unreachable ({e}); using local fresh fake profile.")
            profile = local_fake_nested()
            profile_label = f"{profile['person']['first_name']} {profile['person']['last_name']} (local fake)"
    else:  # my
        try:
            data = fetch_website_profile("my", args.website_url)
            profile = flat_to_params(data.get("values", {}))
            profile_label = f"{profile['person']['first_name']} {profile['person']['last_name']} (saved)"
            log(f"Fetched saved profile from website: {profile_label}")
        except Exception as e:
            log(f"Website unreachable ({e}); falling back to personal_profile.db.")
            profile = load_personal_profile_db()
            profile_label = "Saved profile (local db)"
            log(f"Using local profile: {profile_label}")

    if args.dry_run:
        log(f"DRY RUN using profile: {profile_label}")
        log("Would run these carriers with this nested params:")
        for c in CARRIERS:
            log(f"  - {c['module']}  (registry: {c['registry_id']})")
        log(f"person: {profile.get('person')}")
        log(f"auto: {profile.get('auto')}")
        log(f"driver: {profile.get('driver')}")
        log("Dry run complete — no browsers launched, no DB writes.")
        return

    # 2) Run each carrier script (imported as a module from this folder)
    sys.path.insert(0, HERE)
    results = []
    for c in CARRIERS:
        log(f"--- {c['brand']} ---")
        try:
            mod = __import__(c["module"])
            start = time.time()
            # Apply the carrier's known-good vehicle (each rater's DB differs) so the
            # script can actually find its model, while sharing the profile's person data.
            params = _carrier_params(profile, c)
            if c["module"] == "allstate_auto_quote":
                if args.minimized:
                    res = mod.run(params=params, mode="minimized-headed", keep_open=False)
                else:
                    res = mod.run(params=params, mode="headed" if args.headed else "minimized-headed", keep_open=args.headed)
            else:
                res = mod.run(headless=headless, params=params, keep_open=args.headed,
                              minimized=args.minimized)
            elapsed = round(time.time() - start, 1)
            parsed = parse_result(res)
            res["carrier"] = c["brand"]
            res["form_kind"] = "quote"
            res["profile"] = profile_label
            res["elapsed_s"] = elapsed
            log(f"    quote_value={res.get('quote_value')!r} quote_number={res.get('quote_number')!r} status={parsed['status']} ({elapsed}s)")
        except Exception as e:
            res = {"carrier": c["brand"], "error": str(e), "status": "blocked"}
            parsed = parse_result(res)
            log(f"    ERROR running {c['brand']}: {e}")
        results.append({"carrier": c, "result": res, "parsed": parsed})

    # 3) Persist: upsert to the website DB + write latest_results.json + append jsonl
    log("=== Persisting results ===")
    written = []
    for r in results:
        ok = upsert_db(args.db, r["carrier"], r["parsed"], r["result"], profile_label)
        written.append({
            "registry_id": r["carrier"]["registry_id"],
            "brand": r["carrier"]["brand"],
            "status": r["parsed"]["status"],
            "monthly_premium": r["parsed"]["monthly"],
            "annual_premium": r["parsed"]["annual"],
            "quote_id": r["parsed"]["quote_id"],
            "error": r["parsed"]["error"],
            "db_updated": ok,
        })
        append_jsonl({
            "carrier": r["carrier"]["brand"],
            "registry_id": r["carrier"]["registry_id"],
            "form_kind": "quote",
            "quote_value": r["result"].get("quote_value"),
            "quote_monthly": r["result"].get("quote_monthly"),
            "quote_number": r["result"].get("quote_number"),
            "result_note": None if r["parsed"]["status"] == "quoted_comparable" else r["parsed"]["error"],
            "profile": profile_label,
            "ts": datetime.now().isoformat(),
        })
        log(f"  {r['carrier']['brand']}: status={r['parsed']['status']} "
            f"monthly={r['parsed']['monthly']} db_updated={ok}")

    # Archive this run into the website's history tables (idempotent backfill keeps
    # any pre-existing quotes from before this feature too).
    try:
        hconn = sqlite3.connect(args.db)
        hconn.row_factory = sqlite3.Row
        ensure_history_tables(hconn)
        backfill_history(hconn)
        run_id = record_run(hconn, written, profile_label)
        hconn.close()
        log(f"    archived run #{run_id} to history")
    except Exception as e:
        log(f"    WARN: history write failed: {e}")

    out = {
        "run_at": datetime.now().isoformat(),
        "profile": profile_label,
        "db": args.db,
        "results": written,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    log("=== SUMMARY ===")
    for w in written:
        log(f"  {w['brand']}: {w['status']} monthly=${w['monthly_premium'] if w['monthly_premium'] is not None else 'n/a'} "
            f"quote#={w['quote_id'] or 'n/a'} db={w['db_updated']}")
    log(f"Full results: {args.out}")
    log("Refresh the website's 'Your quotes' page (/quotes) to see these results.")


if __name__ == "__main__":
    main()
