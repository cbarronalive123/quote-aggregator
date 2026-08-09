"""
belairdirect_auto_quote.py
==========================
Playwright automation for the belairdirect (Intact) online auto quote rater.

Rater  : https://webquote.app.belairdirect.com/?language=en&province=on&f=c
Legal  : Belair Insurance Company Inc. (Intact group)
Form kind: QUOTE -- returns a real premium ($/month) + quote reference.

Mapped live 2026-08-09 via Playwright MCP -> $71.92/mo, quote #BA13935324.
(Previous evidence: #BA13933019.) See RUN_REPORT.md + ALLSTATE/DESJARDINS maps.

CANONICAL INTAKE (aggregator model)
-----------------------------------
Reads every value via params_loader.get_param() from the shared canonical dict
(person/auto/driver). The website's /api/quote orchestrator builds that dict from
WHICHEVER profile the user selected (My profile = real, Fake profile = mock/dummy),
so the SAME script works for both -- the switching happens upstream.
Test locally: `python belairdirect_auto_quote.py --headed --input people/dummy.json`

FLOW (verified via MCP)
-----------------------
0. Rater entry: Year -> Make -> Model native selects (or VIN lookup).
   NOTE: bare / redirects to the marketing homepage -- use the ?language&province&f=c URL.
1. Usage : one-way commute (Angular native setter), Yearly kilometres select,
   Condition radio, Anti-theft radio. Dismiss the "Continue Online" promo overlay.
2. Driver: first/last name, gender radio, DOB (month select + day/year native setter),
   age first licensed, licence-class radio, years-with-insurer select.
3. Contact: phone (auto-formats), email, postal; check the required Terms consent
   (#about-terms-yes); leave marketing consent unchecked. -> Get your price.
4. Offer : capture "$NN.NN" + quote #.

GOTCHAS
-------
- Angular/shadow-DOM inputs (DOB day/year, commute, age) IGNORE .fill(); set via the
  native value setter + input/change/blur events (_native_set).
- Year/Make/Model, Yearly km, birth month, years-with-insurer are NATIVE <select>s.
- Make must be "DODGE" (canonical "DODGE/RAM" or "RAM" -> map to "DODGE").
- DOB arrives as YYYY-MM-DD (form) or YYYY/MM/DD (dummy json) -- handle both.
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import get_param, load_params
try:
    from personal_profile import load_profile  # optional: excluded from shared repo (PII)
except Exception:
    def load_profile(*a, **k):
        return None

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME_URL = "https://webquote.app.belairdirect.com/?language=en&province=on&f=c"

PARAM_MAP = {
    "vin":            "auto.vin",
    "vehicle_year":   "auto.vehicle_year",
    "vehicle_make":   "auto.vehicle_make",
    "vehicle_model":  "auto.vehicle_model",
    "annual_km":      "auto.annual_km",
    "commute":        "auto.commute_oneway_km",
    "condition":      "auto.purchase_condition",
    "first_name":     "person.first_name",
    "last_name":      "person.last_name",
    "gender":         "person.sex",             # M -> Male, F -> Female
    "dob":            "person.date_of_birth",   # YYYY-MM-DD or YYYY/MM/DD
    "lic_age":        "driver.first_licence_age",
    "licence_class":  "driver.licence_class",
    "years_insurer":  "driver.years_with_insurer",
    "phone":          "person.phone",
    "email":          "person.email",
    "postal":         "person.postal_code",
}

_MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]

# Bel Air's make list uses "DODGE" for the 2012 Ram 1500 (not "DODGE/RAM"/"RAM").
def _map_make(make: str) -> str:
    m = (make or "").upper()
    if "DODGE" in m or "RAM" in m:
        return "DODGE"
    return m or "DODGE"

# Normalize any profile's model wording to the exact Bel Air select option.
def _map_model(model: str) -> str:
    m = (model or "").upper()
    if "1500" in m and "BIG HORN" in m and "QUAD" in m:
        return "RAM 1500 BIG HORN QUAD CAB 4WD"
    return model

# Map a profile's "years with insurer" wording to Bel Air's exact option.
def _map_years(y: str) -> str:
    y = (y or "").lower()
    if "never" in y:
        return "Never been insured"
    if "not currently" in y or "in the past" in y or "past" in y:
        return "Not currently insured, but have been in the past"
    if "between" in y and "3" in y and "5" in y:
        return "Between 3 and 5 years"
    if "5" in y:
        return "5 years or more"
    return "3 years or less"


def _dob_parts(dob: str):
    dob = (dob or "1985/05/10").strip()
    dob = dob.replace("-", "/")
    try:
        y, mo, d = dob.split("/")
        return y, _MONTHS[int(mo)], d
    except Exception:
        return "1985", "May", "10"


def _native_set(page, locator, value):
    """Set an Angular/shadow-DOM controlled input via the native value setter + events."""
    el = locator.first
    try:
        el.evaluate(
            """(node, v) => {
                const setter = Object.getOwnPropertyDescriptor(
                  window.HTMLInputElement.prototype, 'value').set;
                setter.call(node, v);
                node.dispatchEvent(new Event('input', {bubbles: true}));
                node.dispatchEvent(new Event('change', {bubbles: true}));
                node.dispatchEvent(new Event('blur', {bubbles: true}));
            }""",
            str(value),
        )
    except Exception:
        try:
            locator.fill(str(value))
        except Exception:
            locator.press_sequentially(str(value))
    page.wait_for_timeout(250)


def _type(page, locator, value):
    try:
        locator.fill(str(value))
    except Exception:
        _native_set(page, locator, str(value))


def _select(page, label, value):
    _remove_overlays(page)
    try:
        page.get_by_label(label, exact=True).select_option(str(value))
    except Exception:
        page.get_by_label(label).first.select_option(str(value))
    page.wait_for_timeout(200)


def _pick(page, name_re, label):
    """Click a radio by accessible name: exact full-name first, then regex, then group."""
    _remove_overlays(page)
    try:
        page.get_by_role("radio", name=name_re, exact=True).click()
    except Exception:
        try:
            page.get_by_role("radio", name=re.compile(name_re), exact=False).first.click()
        except Exception:
            grp = page.get_by_role("group", name=re.compile(name_re))
            grp.get_by_role("radio", name=label, exact=True).first.click()
    page.wait_for_timeout(150)


def _remove_overlays(page):
    try:
        page.evaluate("""() => {
            document.querySelectorAll(
                'feature-exit-intent, [class*=exit-intent], [class*=exitIntent], ' +
                '[class*=modal-backdrop], [class*=modal-overlay]'
            ).forEach(el => el.remove());
        }""")
    except Exception:
        pass


def _click_next(page, label):
    for _ in range(3):
        _remove_overlays(page)
        btn = page.get_by_role("button", name=label, exact=True)
        try:
            btn.click(timeout=4000)
        except Exception:
            pass
        page.wait_for_timeout(1200)
        # stop if the button disappeared (navigation happened)
        if btn.count() == 0:
            break


def run(headless: bool, params: dict | None = None, out_dir: str = "evidence") -> dict:
    result = {"quote_value": None, "quote_monthly": None, "quote_number": None, "coverage": {}, "status": None}
    params = params or {}
    V = {k: get_param(params, p, "") for k, p in PARAM_MAP.items()}
    year, month_name, day = _dob_parts(V["dob"])
    make = _map_make(V["vehicle_make"])
    # Annual km -> Bel Air's Yearly kilometres select option.
    try:
        km = int(float((V["annual_km"] or "15000").replace(",", "")))
    except Exception:
        km = 15000
    km_band = "13,001 to 16,000 km per year"
    for low, high, band in [(2001, 4000, "2,001 to 4,000 km per year"),
                            (4001, 6000, "4,001 to 6,000 km per year"),
                            (6001, 8000, "6,001 to 8,000 km per year"),
                            (8001, 10000, "8,001 to 10,000 km per year"),
                            (10001, 13000, "10,001 to 13,000 km per year"),
                            (13001, 16000, "13,001 to 16,000 km per year"),
                            (16001, 20000, "16,001 to 20,000 km per year")]:
        if low <= km <= high:
            km_band = band
            break

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=headless)
        except Exception:
            browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            viewport={"width": 1400, "height": 1000},
        )
        page = ctx.new_page()
        page.set_default_timeout(9000)
        def log(step): print(f"[belair] STEP {step}", flush=True)
        try:
            log("entry")
            page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            # 0) Vehicle (Year/Make/Model native selects)
            _select(page, "Year", V["vehicle_year"])
            _select(page, "Make", make)
            _select(page, "Model", _map_model(V["vehicle_model"]))
            _click_next(page, "Next: Usage")

            # Promo overlay ("Continue Online") may intercept clicks
            try:
                page.get_by_role("button", name="Continue Online", exact=True).click(timeout=2500)
                page.wait_for_timeout(500)
            except Exception:
                pass

            # 1) Usage
            log("usage")
            _native_set(page, page.get_by_role("spinbutton", name="Enter the distance you drive"), V["commute"] or "15")
            _select(page, "Yearly kilometres", km_band)
            _pick(page, "Condition of the car when you got it Tooltip Demo car Used", "Used")
            _pick(page, "Anti-theft system", "No")
            _click_next(page, "Next: Driver")

            # 2) Driver
            log("driver")
            _type(page, page.get_by_role("textbox", name="First name", exact=True), V["first_name"])
            _type(page, page.get_by_role("textbox", name="Last name", exact=True), V["last_name"])
            _pick(page, f"Gender identity.*{'Male' if V['gender'].upper() == 'M' else 'Female'}", V["gender"].upper())
            _select(page, "Select birth month", month_name)
            _native_set(page, page.get_by_role("textbox", name="Enter birth date"), day)
            _native_set(page, page.get_by_role("textbox", name="Enter birth year"), year)
            _native_set(page, page.get_by_role("spinbutton", name="Age when you got your first"),
                        re.sub(r"\D", "", V["lic_age"] or "21") or "21")
            _pick(page, "Current driver's licence class Tooltip Driver's licence class G", V["licence_class"] or "G")
            _select(page, "Number of years with current", _map_years(V["years_insurer"]))
            _click_next(page, "Next: Contact")

            # 3) Contact
            log("contact")
            try:
                page.get_by_role("textbox", name="Phone number").first.wait_for(state="visible", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(300)
            _type(page, page.get_by_role("textbox", name="Phone number"), V["phone"])
            _type(page, page.get_by_role("textbox", name="Email"), V["email"])
            _type(page, page.get_by_role("textbox", name="Postal code"), V["postal"])
            try:
                page.locator("#about-terms-yes").click(timeout=3000)
                page.wait_for_timeout(300)
            except Exception:
                pass
            _click_next(page, "Get your price")
            page.wait_for_timeout(6000)

            # 4) Offer page (price lives in a shadow-DOM component -> use get_by_text)
            log("offer")
            try:
                el = page.get_by_text(re.compile(r"Canadian dollars\s*month", re.I)).first
                el.wait_for(state="visible", timeout=12000)
                t = el.inner_text()
                mm = re.search(r"([\d,]+\.\d{2})", t)
                if mm:
                    result["quote_value"] = mm.group(1)
                    result["quote_monthly"] = "$" + mm.group(1) + " /month"
            except Exception:
                pass
            try:
                q = page.get_by_text(re.compile(r"Car quote\s*#", re.I)).first.inner_text()
                qq = re.search(r"(BA\d{6,})", q)
                if qq:
                    result["quote_number"] = qq.group(1)
            except Exception:
                pass
            result["status"] = "quoted_comparable_candidate" if result["quote_value"] else "unresolved"

            os.makedirs(out_dir, exist_ok=True)
            shot = os.path.join(out_dir, "belairdirect_offer.png")
            page.screenshot(path=shot, full_page=True)
            result["evidence"] = shot

        except Exception as e:
            result["status"] = "blocked"
            result["error"] = str(e)
            print("ERROR:", e, flush=True)
        finally:
            if not headless:
                page.wait_for_timeout(2000)
            browser.close()
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true", default=False)
    ap.add_argument("--headed", action="store_true", default=False)
    ap.add_argument("--input", default=None)
    ap.add_argument("--out", default="belairdirect_auto_quote_result.json")
    args = ap.parse_args()
    headless = args.headless or not args.headed
    print(f"Running {'HEADED' if args.headed else 'HEADLESS'} mode", flush=True)
    profile = load_profile() if not args.input else load_params(args.input)
    if not profile:
        print("WARNING: no params source. Use --input people/dummy.json", flush=True)
    res = run(headless=not args.headed, params=profile)
    res["carrier"] = "belairdirect.com (Intact)"
    res["form_url"] = HOME_URL
    res["form_kind"] = "quote"
    res["_note"] = ("Mock/dummy data if --input people/dummy.json, else the real profile. "
                    "Not valid evidence when dummy data is used.")
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quote_results.jsonl")
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")
    print("\n=== RESULT ===")
    print("  quote_monthly:", res.get("quote_monthly"))
    print("  quote_number:", res.get("quote_number"))
    print("  status:", res.get("status"))
    print("  coverage:", res.get("coverage"))
    print("  error:", res.get("error"))
    print("  saved to:", out_path)


if __name__ == "__main__":
    main()
