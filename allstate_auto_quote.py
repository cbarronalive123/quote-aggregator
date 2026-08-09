"""
allstate_auto_quote.py
======================
Playwright automation for the Allstate Canada online auto quote.

Entry  : https://apps.allstate.ca/quickquote/common/landing.aspx?CID=SEO_hero_home_page_Organic_EN
Quote  : https://purchase.allstate.ca (postcode -> getstarted -> summary -> quote)
Legal  : Allstate Insurance Company of Canada
Form kind: QUOTE -- returns a real premium ($/month) + coverage summary + quote #.

CANONICAL INTAKE (aggregator model)
-----------------------------------
Fill values resolve via `params_loader.get_param()`. Shared canonical fields live in
`person/auto/driver`; Allstate-specific option labels live in the `allstate` section
(the same vehicle/driver, but Allstate uses its own option strings, e.g. the model
label and parking wording). A parent/orchestrator fills one intake and fans it out.

Testing: `python allstate_auto_quote.py --headed --input people/dummy.json`
(DUMMY data -- never treat a dummy run as a real quote or evidence).

FLOW (verified live 2026-08-09 via Playwright MCP, quote #083193545)
-------------------------------------------------------------------
1. Landing: postal code + Auto -> Go.
2. Get Started (getstarted): 1 vehicle, 1 driver, not existing customer -> SHOP & BUY.
3. Summary page (purchase.allstate.ca/summary), via dialogs:
   - Vehicle: Year/Make/Model selects.
   - Vehicle details: New/Used/Demo, Owned/Financed/Leased, only owner, within 30 days,
     purchase price, coverage start date (calendar), purchase month/year.
   - Vehicle use: used for, one-way commute km, annual km band, ridesharing No + confirm.
   - Savings: winter tires + confirm, parking, anti-theft, ADAS.
   - Driver: province, names, DOB (calendar), gender, marital, household drivers.
   - Driving history: age first licensed, graduated licensing, license class,
     G within 12 mo, minor/major violations, suspension.
   - Insurance history: currently insured, cancelled, claims.
   - Summary: Drivewise No, email, phone, privacy consent checkbox -> get a quote.
4. Quote page (/quote): capture premium + quote number + coverage.

GOTCHAS
-------
- Native <select> elements -> use selectOption by label/value.
- Many fields are revealed only after a prior answer; the "continue" button stays
  disabled until every revealed field is answered.
- Date pickers open a modal calendar (Month/Year selects + day buttons).
- Privacy consent is a required checkbox at the summary step; marketing-email checkbox
  should be left unchecked (data minimization).
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

LANDING_URL = "https://apps.allstate.ca/quickquote/common/landing.aspx?CID=SEO_hero_home_page_Organic_EN"

# Form field -> params path (canonical person/auto/driver, plus Allstate-specific labels).
PARAM_MAP = {
    "postal":          "person.postal_code",
    "vehicle_year":    "auto.vehicle_year",
    "vehicle_make":    "auto.vehicle_make",
    "vehicle_model":   "allstate.vehicle_model",
    "condition":       "auto.purchase_condition",
    "ownership":       "allstate.ownership",          # Owned | Financed | Leased
    "only_owner":      "allstate.only_owner",         # Yes
    "within_30d":      "allstate.within_30d",         # No
    "purchase_price":  "allstate.purchase_price",
    "coverage_start":  "allstate.coverage_start",     # mm/dd/yyyy
    "purchase_month":  "allstate.purchase_month",
    "purchase_year":   "allstate.purchase_year",
    "vehicle_use":     "allstate.vehicle_use",        # Work / School | Business | Pleasure
    "one_way_km":      "allstate.one_way_km",
    "annual_km_band":  "allstate.annual_km_band",     # 12001-16000km etc.
    "winter_tires":    "auto.winter_tires",           # Yes | No
    "parking":         "allstate.parking",            # Unsecured Condo/Apt Garage or lot
    "anti_theft":      "auto.tracking_system",        # None -> No
    "first_name":      "person.first_name",
    "last_name":       "person.last_name",
    "dob":             "person.date_of_birth",        # YYYY/MM/DD
    "gender":          "allstate.gender",             # Male | Female | X
    "marital":         "allstate.marital_status",     # Married / Common Law | Single | Widowed
    "household":       "allstate.household_drivers",  # No
    "first_lic_age":   "allstate.first_licensed_age",
    "graduated":       "allstate.graduated_licensing",# Yes
    "license_class":   "allstate.license_class",      # G1 | G2 | G
    "g_12mo":          "allstate.g_within_12mo",      # No
    "minor_viol":      "allstate.minor_violations",   # None | 1 | 2 | More than 2
    "major_viol":      "driver.convictions_3yr",      # No
    "suspended":       "driver.licence_suspended",    # No
    "insured":         "allstate.insured",            # Yes
    "cancelled":       "allstate.cancelled",          # No
    "claims_6yr":      "allstate.claims_6yr",         # No
    "drivewise":       "driver.ajusto",               # No (telematics)
    "email":           "person.email",
    "phone":           "person.phone",
}


def _type(page, locator, value):
    if not value:
        return
    try:
        locator.fill(str(value))
    except Exception:
        pass
    try:
        if not locator.input_value():
            locator.press_sequentially(str(value))
    except Exception:
        try:
            locator.press_sequentially(str(value))
        except Exception:
            pass


def _select(page, label, value):
    page.get_by_label(label, exact=True).select_option(value)
    page.wait_for_timeout(150)


def _pick(page, group_name, label):
    try:
        page.get_by_role("group", name=group_name).get_by_role("radio", name=label, exact=True).first.click()
    except Exception:
        page.get_by_role("radio", name=label, exact=True).first.click()
    page.wait_for_timeout(100)


def _check(page, name_re):
    page.get_by_role("checkbox", name=name_re).first.click()
    page.wait_for_timeout(100)


def _click_continue(page):
    page.get_by_role("button", name="continue", exact=True).click()
    page.wait_for_timeout(900)


def _pick_date(page, target_text):
    """Open a calendar modal (by its 'Open Date Picker' button near a label) and pick a day."""
    # open the nearest date-picker button
    page.get_by_role("button", name="Calendar Open Date Picker").click()
    page.wait_for_timeout(400)
    # the modal lists Month/Year selects + day buttons; pick the target day button.
    page.get_by_role("button", name=target_text, exact=True).click()
    page.wait_for_timeout(300)


def _dob_ymd(params):
    dob = get_param(params, "person.date_of_birth", "1985/05/10")
    try:
        y, m, d = dob.split("/")
        m = int(m)
    except Exception:
        y, m, d = "1985", 5, "10"
    return y, int(m), d


_MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"]


def run(headless: bool, params: dict | None = None, out_dir: str = "evidence") -> dict:
    result = {"quote_value": None, "quote_monthly": None, "quote_number": None,
              "coverage": {}, "status": None}
    params = params or {}
    V = {k: get_param(params, p, "") for k, p in PARAM_MAP.items()}
    y, m, d = _dob_ymd(params)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            viewport={"width": 1400, "height": 1000},
        )
        page = ctx.new_page()
        page.set_default_timeout(7000)
        try:
            # 1) Landing
            page.goto(LANDING_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2500)
            try:
                page.get_by_role("button", name="Accept").click(timeout=2500)
            except Exception:
                pass
            page.get_by_role("textbox", name="Please provide your postal").fill(V["postal"])
            page.get_by_role("link", name="Go", exact=True).click()
            # wait for the getstarted app to load
            try:
                page.wait_for_url(re.compile(r"getstarted"), timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(2500)

            # 2) Get Started -> SHOP & BUY
            for _ in range(3):
                try:
                    page.get_by_role("button", name="Accept").click(timeout=2000)
                except Exception:
                    pass
                try:
                    page.get_by_role("button", name=re.compile(r"SHOP\s*&\s*BUY", re.I)).click(timeout=4000)
                    break
                except Exception:
                    page.wait_for_timeout(1500)
            page.wait_for_timeout(3000)

            # 3) Summary -- vehicle dialog
            _select(page, "year", V["vehicle_year"])
            _select(page, "make", V["vehicle_make"])
            _select(page, "model", V["vehicle_model"])
            _click_continue(page)

            # vehicle details dialog
            _pick(page, "new, used or a dealership demo", V["condition"])
            _pick(page, "owned, financed, or leased", V["ownership"])
            _pick(page, "only registered owner", V["only_owner"])
            _pick(page, "within the last 30 days", V["within_30d"])
            _type(page, page.get_by_role("spinbutton", name="purchase price"), V["purchase_price"])
            _pick_date(page, "1 September 2026")  # coverage start day button
            _select(page, "Purchase month", V["purchase_month"])
            _select(page, "Purchase year", V["purchase_year"])
            _click_continue(page)

            # vehicle use dialog
            _select(page, "vehicle-used-for", V["vehicle_use"])
            _type(page, page.get_by_role("spinbutton", name="one way to work"), V["one_way_km"])
            _select(page, "one-year-kilometers", V["annual_km_band"])
            _pick(page, "ridesharing or commercial usage", "No")
            try:
                page.get_by_role("checkbox", name="I confirm that this vehicle").click()
            except Exception:
                pass
            _click_continue(page)

            # savings dialog
            _pick(page, "winter tires installed", V["winter_tires"])
            try:
                page.get_by_role("checkbox", name="I confirm that 4 winter tires").click()
            except Exception:
                pass
            _select(page, "vehicle-parking", V["parking"])
            _pick(page, "anti-theft tracking", "No")
            _click_continue(page)

            # driver details dialog
            _type(page, page.get_by_role("textbox", name="First name"), V["first_name"])
            _type(page, page.get_by_role("textbox", name="Last name"), V["last_name"])
            _pick_date(page, f"{d} {_MONTH_NAMES[m]} {y}")
            _pick(page, "gender", V["gender"])
            _select(page, "marital-status", V["marital"])
            _pick(page, "household-licensed", V["household"])
            _click_continue(page)

            # driving history dialog
            _type(page, page.get_by_role("textbox", name="first licensed"), V["first_lic_age"])
            _pick(page, "graduated licensing", V["graduated"])
            _pick(page, "class of your current", V["license_class"])
            _pick(page, "within the past 12 months", V["g_12mo"])
            _select(page, "minor-violation", V["minor_viol"])
            _pick(page, "criminal-violations", V["major_viol"])
            _pick(page, "license-suspended", V["suspended"])
            _click_continue(page)

            # insurance history dialog
            _pick(page, "prior-insurance", V["insured"])
            _pick(page, "policy-cancelled", V["cancelled"])
            _pick(page, "claims-details", V["claims_6yr"])
            _click_continue(page)

            # summary -> consent -> get a quote
            _pick(page, "include Drivewise", V["drivewise"])
            _type(page, page.get_by_role("textbox", name="Email address"), V["email"])
            _type(page, page.get_by_role("textbox", name="phone-number"), V["phone"])
            _check(page, "Yes, I agree that you may")  # privacy consent (required)
            page.get_by_role("button", name="get a quote").click()
            page.wait_for_timeout(6000)

            # 4) Quote page
            body = page.locator("body").inner_text(timeout=10000)
            m = re.search(r"\$\s?(\d[\d,]*\.?\d*)\s*/\s*month", body)
            if m:
                result["quote_value"] = m.group(1)
                result["quote_monthly"] = m.group(0).strip()
            qn = re.search(r"Quote\s*#([A-Z0-9]+)", body)
            if qn:
                result["quote_number"] = qn.group(1)
            for cov in ["Bodily Injury/Property Damage", "Direct Compensation Property Damage",
                        "Uninsured Automobile", "Family Protection Endorsement"]:
                cm = re.search(re.escape(cov) + r"[^\n]*", body)
                if cm:
                    result["coverage"][cov] = cm.group(0).strip()
            result["status"] = "quoted_comparable_candidate" if result["quote_value"] else "unresolved"

            os.makedirs(out_dir, exist_ok=True)
            shot = os.path.join(out_dir, "allstate_offer.png")
            page.screenshot(path=shot, full_page=True)
            result["evidence"] = shot

        except Exception as e:
            result["status"] = "blocked"
            result["error"] = str(e)
            print("ERROR:", e, flush=True)
        finally:
            if not headless:
                page.wait_for_timeout(3000)
            browser.close()
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headed", action="store_true", default=False)
    ap.add_argument("--input", default=None)
    ap.add_argument("--out", default="allstate_auto_quote_result.json")
    args = ap.parse_args()

    print(f"Running {'HEADED' if args.headed else 'HEADLESS'} mode", flush=True)
    profile = load_profile() if not args.input else load_params(args.input)
    if not profile:
        print("WARNING: no params source. Use --input people/dummy.json", flush=True)

    res = run(headless=not args.headed, params=profile)
    res["carrier"] = "allstate.ca (Allstate Insurance Company of Canada)"
    res["form_url"] = LANDING_URL
    res["form_kind"] = "quote"
    res["_note"] = ("DUMMY/TEST DATA used if --input people/dummy.json. "
                    "Not a real quote; not valid evidence. Collision/Comprehensive "
                    "are NOT included by default.")

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
