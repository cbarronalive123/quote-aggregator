"""
desjardins_auto_quote.py
========================
Playwright automation for the Desjardins Insurance (Certas Direct) online auto
quote rater. Ontario PPA focus.

Rater : https://clients.desjardinsgeneralinsurance.com/vehicle-quote/init/welcome?cs=au&mca=d&prv=on
Form kind: QUOTE -- returns a real premium ($/month) + a coverage summary.

CANONICAL INTAKE (aggregator model)
-----------------------------------
All fill values are resolved from a shared per-person params dict via
`params_loader.get_param()`. The same canonical dict drives every carrier script,
so a parent/orchestrator can fill ONE intake and fan it out to all forms. Override
the data source with `--input people/<file>.json`; default is the SQLite personal
profile (`personal_profile.load_profile()`), which returns the same nested shape.

For testing use `--input people/dummy.json` (DUMMY data -- never count a dummy run
as a real quote or evidence).

MAPPED FLOW (verified live 2026-08-09 via Playwright MCP, quote #ECG0BKRW)
-------------------------------------------------------------------------
0. Consent dialog  -> Accept (it is the step's `wizard-next-button`).
1. clientInformationStep : first/last name, gender, DOB (month/day/year),
   address (Canada Post autocomplete).
2. contactInfoStep       : phone (auto-formats), email, marketing consent = No,
   effective date (month/day/year).
   -> creates quote id; URL becomes /{QUOTEID}/gather
3. vehicleSelectorStep   : year -> make (DODGE/RAM) -> model; type of use.
4. vehicleInformationStep: acquisition date, condition, ownership, modified,
   tracking system, winter tires, parked overnight, km, one-way commute,
   US use, additional vehicle.
5. driverIdentificationStep: marital, employment (+ revealed field of work),
   licence classes, licence-elsewhere, current insurer, age & month licence
   obtained, years with insurer, additional driver.
6. driverAssignationStep : vehicle owner checkbox, principal-driver age.
7. driverConvictionsStep : licence suspended, convictions (past 3y).
8. driverClaimsStep      : "Report claims manually" (noLicenceButton) -> no claims.
9. savingsDiscountsStep  : multi-line (home) discount = No.
10. offersStep           : Ajusto (telematics) = No -> "See your coverage".
11. coveragesStep        : CAPTURE premium + coverage summary.

INTERACTION GOTCHAS
-------------------
- Some controlled text inputs (Last name, One-way commute) IGNORE `.fill()`; commit
  with `pressSequentially`. `_type` tries fill then falls back to keystrokes.
- Accessible selects are readonly textboxes inside a combobox; open by clicking the
  textbox, then click the `[role=option]` with the target text. `_select` handles this.
- Next buttons differ per phase:
    wizard-next-button (consent + steps 1-2), next-button (steps 3-9),
    action-Button-next ("See your coverage" on offers step).
- Address autocomplete: click, type address, click the resolved option.
- The site is reCAPTCHA-protected. If a CAPTCHA blocks submission, record status
  `blocked` and stop (per the hackathon safety layer -- never evade).
"""

import argparse
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

from params_loader import get_param, load_params
try:
    from personal_profile import load_profile  # optional: excluded from shared repo (PII)
except Exception:
    def load_profile(*a, **k):
        return None

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME_URL = "https://clients.desjardinsgeneralinsurance.com/vehicle-quote/init/welcome?cs=au&mca=d&prv=on"

# Form field name -> canonical params path. Fill values come from the shared intake.
# FIXED options (the bounded lists) are documented inline so the parent script knows
# the valid choices; VARIABLE fields are free text.
PARAM_MAP = {
    # ---- Step 1: clientInformationStep ----
    "first_name":      "person.first_name",                 # VARIABLE
    "last_name":       "person.last_name",                  # VARIABLE
    "gender":          "person.sex",                        # FIXED: M -> Male, F -> Female
    "dob_month":       "person.date_of_birth",              # YYYY/MM/DD -> month
    "dob_day":         "person.date_of_birth",
    "dob_year":        "person.date_of_birth",
    "address":         "person.address_search",             # "street, city" for autocomplete
    # ---- Step 2: contactInfoStep ----
    "phone":           "person.phone",                      # VARIABLE (10 digits)
    "phone_type":      "person.phone_type",                 # FIXED: Cell | Home | Work (default Cell)
    "email":           "person.email",                      # VARIABLE
    "marketing_consent": "driver.marketing_consent",        # FIXED: No (data minimization)
    "eff_date_month":  "auto.coverage_start_month",         # FIXED: January..December
    "eff_date_day":    "auto.coverage_start_day",           # VARIABLE
    "eff_date_year":   "auto.coverage_start_year",          # FIXED: 2026 | 2027
    # ---- Step 3: vehicleSelectorStep ----
    "vehicle_year":    "auto.vehicle_year",                 # FIXED: 2009..current
    "vehicle_make":    "auto.vehicle_make",                 # FIXED: DODGE/RAM etc.
    "vehicle_model":   "auto.vehicle_model",                # FIXED: exact trim string
    "type_of_use":     "auto.type_of_use",                  # FIXED: Personal | Personal and business | Commercial
    # ---- Step 4: vehicleInformationStep ----
    "acq_month":       "auto.purchase_month",               # FIXED
    "acq_year":        "auto.purchase_year",                # FIXED
    "condition":       "auto.purchase_condition",           # FIXED: New | Used | Demo
    "ownership":       "auto.owned_leased",                 # FIXED: Purchased and completely paid off | ... | Leased
    "modified":        "auto.modified",                     # FIXED: Yes | No
    "tracking":        "auto.tracking_system",              # FIXED: None | Domino | Locate | Tag System | Other
    "winter_tires":    "auto.winter_tires",                 # FIXED: Yes | No
    "parking":         "auto.parking_overnight",            # FIXED: Private driveway|garage|Street|Parking lot|Underground|Other|Carport
    "annual_km":       "auto.annual_km",                    # VARIABLE (digits, no comma)
    "commute":         "auto.commute_oneway_km",            # VARIABLE (digits)
    "used_in_us":      "auto.used_in_us",                   # FIXED: Yes | No
    "add_vehicle":     "auto.additional_vehicle",           # FIXED: No | Yes, add a vehicle
    # ---- Step 5: driverIdentificationStep ----
    "marital":         "person.marital_status",             # FIXED: Single | Married | Common-law partner | Separated | Divorced | Widowed
    "employment":      "driver.employment_status",          # FIXED: Employed | Self-employed | ... | Prefer not to answer
    "field_of_work":   "driver.field_of_work",              # FIXED: 15 options (e.g. Technology, computer science and multimedia)
    "licence_class":   "driver.licence_class",              # FIXED checkbox: G (full licence) | G2 | G1
    "licence_elsewhere": "driver.licence_from_elsewhere",   # FIXED: No | Yes
    "current_insurer": "driver.current_insurer",            # FIXED: Allstate|Aviva|Belairdirect|Broker|...|No current insurer
    "lic_age":         "driver.first_licence_age",          # FIXED: "N years old"
    "lic_month":       "driver.first_licence_month",        # FIXED: January..December
    "years_insurer":   "driver.years_with_insurer",         # FIXED: Less than 1 year | 1..5 years | 6 to 10 years | 11+
    "add_driver":      "driver.additional_driver",          # FIXED: No | Yes, add a driver
    # ---- Step 6: driverAssignationStep ----
    "owner_self":      "driver.owner_self",                 # FIXED checkbox (driver is owner)
    "principal_age":   "driver.principal_driver_age",       # FIXED: "N years old"
    # ---- Step 7: driverConvictionsStep ----
    "suspended":       "driver.licence_suspended",          # FIXED: No | Yes
    "convictions":     "driver.convictions_3yr",            # FIXED: No | Yes
    # ---- Step 9: savingsDiscountsStep ----
    "home_insured":    "driver.home_insured_here",          # FIXED: No | Yes
    # ---- Step 10: offersStep ----
    "ajusto":          "driver.ajusto",                     # FIXED: No (telematics) | Yes
}


def _type(page, locator, value):
    """Fill a text input; fall back to keystrokes for controlled React inputs."""
    if not value:
        return
    try:
        locator.fill(str(value))
    except Exception:
        pass
    try:
        if not locator.input_value():
            locator.press_sequentially(str(value))
            page.wait_for_timeout(150)
    except Exception:
        try:
            locator.press_sequentially(str(value))
        except Exception:
            pass


def _select(page, textbox, option_text):
    """Open an accessible select and choose an option by its accessible name."""
    textbox.click()
    page.wait_for_timeout(300)
    opt = page.get_by_role("option", name=option_text, exact=True).first
    try:
        opt.wait_for(state="visible", timeout=3000)
    except Exception:
        # dropdown may not have opened on first click -- retry open
        textbox.click()
        page.wait_for_timeout(300)
        opt = page.get_by_role("option", name=option_text, exact=True).first
        opt.wait_for(state="visible", timeout=3000)
    opt.click()
    page.wait_for_timeout(150)


def _pick(page, group_regex, label):
    """Click a radio/checkbox. Group-scoped label first (for duplicate No/Yes),
    then page-level role (for unique radios like Gender)."""
    try:
        page.get_by_role("group", name=group_regex).get_by_label(label, exact=True).first.click()
        page.wait_for_timeout(100)
        return
    except Exception:
        pass
    try:
        page.get_by_role("radio", name=label, exact=True).first.click()
        page.wait_for_timeout(100)
        return
    except Exception:
        pass
    page.get_by_role("checkbox", name=label, exact=True).first.click()
    page.wait_for_timeout(100)


def _click_next(page, testid="next-button"):
    page.get_by_test_id(testid).click()
    page.wait_for_timeout(900)


def _dob_split(params):
    dob = get_param(params, "person.date_of_birth", "1985/05/10")
    try:
        y, m, d = dob.split("/")
    except Exception:
        y, m, d = "1985", "05", "10"
    return y, m, d


def run(headless: bool, params: dict | None = None, out_dir: str = "evidence") -> dict:
    result = {
        "quote_value": None,
        "quote_monthly": None,
        "quote_number": None,
        "coverage": {},
        "status": None,
        "ajusto_declined": True,
    }
    params = params or {}
    V = {k: get_param(params, p, "") for k, p in PARAM_MAP.items()}
    y, m, d = _dob_split(params)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=headless)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            viewport={"width": 1400, "height": 1000},
        )
        page = ctx.new_page()
        page.set_default_timeout(6000)  # fail locators fast during iteration
        def log(step): print(f"[desjardins] STEP {step}", flush=True)
        try:
            log("load")
            page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)  # consent step renders; avoid networkidle (never settles)

            log("consent")
            # 0) Consent: dismiss any OneTrust cookie banner, then accept privacy consent
            #    (Accept button = name="unifiedConsentAccept" = wizard-next-button).
            try:
                page.get_by_role("button", name="Accept all").click(timeout=2500)
                page.wait_for_timeout(500)
            except Exception:
                pass
            for _ in range(4):
                try:
                    page.locator('button[name="unifiedConsentAccept"]').click(timeout=2500)
                except Exception:
                    try:
                        page.get_by_test_id("wizard-next-button").click(timeout=2500)
                    except Exception:
                        pass
                page.wait_for_timeout(1200)
                # advanced past consent when the First name field is present
                if page.get_by_role("textbox", name="First name").count():
                    break

            log("1 client")
            # 1) clientInformationStep
            _type(page, page.get_by_role("textbox", name="First name"), V["first_name"])
            _type(page, page.get_by_role("textbox", name="Last name"), V["last_name"])
            # Gender (unique radio -> page-level role match)
            page.get_by_role("radio",
                             name="Male" if V["gender"].upper() == "M" else "Female",
                             exact=True).click()
            # DOB month combobox (stable id-suffix selectors)
            _select(page, page.locator('input[id$="monthSelect--accessibleSelectInput"]'),
                    _months[int(m)])
            _type(page, page.locator('input[id$="dayInput"]'), d)
            _type(page, page.locator('input[id$="yearSelect--accessibleSelectInput"]'), y)
            # Address autocomplete
            page.get_by_role("textbox", name="Find your address").click()
            _type(page, page.get_by_role("textbox", name="Find your address"), V["address"])
            page.wait_for_timeout(1200)
            try:
                page.locator('[role="option"]').filter(has_text="Tecumseh").first.click()
            except Exception:
                pass
            _click_next(page, "wizard-next-button")

            log("2 contact")
            # 2) contactInfoStep
            _type(page, page.get_by_role("textbox", name="Number"), V["phone"])
            _type(page, page.get_by_role("textbox", name=re.compile("^Email")), V["email"])
            _pick(page, re.compile("consent|contacted", re.I), "No")
            # effective date (stable id-suffix selectors)
            _select(page, page.locator('input[id$="monthSelect--accessibleSelectInput"]'),
                    V["eff_date_month"])
            _type(page, page.locator('input[id$="dayInput"]'), V["eff_date_day"])
            _select(page, page.locator('input[id$="yearSelect--accessibleSelectInput"]'),
                    V["eff_date_year"])
            _click_next(page, "wizard-next-button")
            page.wait_for_timeout(4000)  # quote id creation + nav

            log("3 vehicle")
            # 3) vehicleSelectorStep
            _select(page, page.get_by_role("textbox", name="Year"), V["vehicle_year"])
            _select(page, page.get_by_role("textbox", name="Make"), V["vehicle_make"])
            _select(page, page.get_by_role("textbox", name="Model"), V["vehicle_model"])
            _pick(page, re.compile("Type of vehicle use"), V["type_of_use"])
            _click_next(page)

            log("4 vehicle info")
            # 4) vehicleInformationStep
            _select(page, page.locator('input[id$="monthSelect--accessibleSelectInput"]'), V["acq_month"])
            _select(page, page.locator('input[id$="yearSelect--accessibleSelectInput"]'), V["acq_year"])
            _pick(page, re.compile("Condition of the vehicle"), V["condition"])
            _pick(page, re.compile("Vehicle ownership"), V["ownership"])
            _pick(page, re.compile("Modified vehicle"), V["modified"])
            _select(page, page.get_by_role("textbox", name="Tracking system"), V["tracking"])
            _pick(page, re.compile("winter tires"), V["winter_tires"])
            _select(page, page.get_by_role("textbox", name="Location where the vehicle"), V["parking"])
            _type(page, page.get_by_role("textbox", name="Kilometres driven yearly"), V["annual_km"])
            _type(page, page.get_by_role("textbox", name="One-way commute"), V["commute"])
            _pick(page, re.compile("Vehicle used in the United States"), V["used_in_us"])
            _pick(page, re.compile("Additional vehicle to insure"), V["add_vehicle"])
            _click_next(page)

            log("5 driver id")
            # 5) driverIdentificationStep
            _pick(page, re.compile("Marital status"), V["marital"])
            _pick(page, re.compile("Employment status"), V["employment"])
            page.get_by_role("checkbox", name=V["licence_class"], exact=True).click()
            _pick(page, re.compile("licence from elsewhere"), V["licence_elsewhere"])
            _select(page, page.get_by_role("textbox", name="Current insurer"), V["current_insurer"])
            _pick(page, re.compile("Additional driver to insure"), V["add_driver"])
            # revealed fields when employed
            if V["field_of_work"]:
                _select(page, page.get_by_role("textbox", name="Field of work"), V["field_of_work"])
            _select(page, page.get_by_role("textbox", name="Age"), V["lic_age"])
            _select(page, page.get_by_role("textbox", name="Month"), V["lic_month"])
            _pick(page, re.compile("Number of complete years"), V["years_insurer"])
            _click_next(page)

            # 6) driverAssignationStep
            _pick(page, re.compile("Vehicle owner"), V["owner_self"])
            _select(page, page.get_by_role("textbox", name=re.compile("became the principal")), V["principal_age"])
            _click_next(page)

            # 7) driverConvictionsStep
            _pick(page, re.compile("licence suspended"), V["suspended"])
            _pick(page, re.compile("Convictions in the past 3 years"), V["convictions"])
            _click_next(page)

            # 8) driverClaimsStep -- manual claims, none
            page.get_by_test_id("noLicenceButton").click()
            page.wait_for_timeout(800)
            _pick(page, re.compile("Claims to declare"), V["claims_10yr"])
            _click_next(page)

            # 9) savingsDiscountsStep
            _pick(page, re.compile("Multi-Line|insure your home"), V["home_insured"])
            _click_next(page)
            page.wait_for_timeout(4000)  # rating engine

            # 10) offersStep -- decline Ajusto, see coverage
            _pick(page, re.compile("Interested in the Ajusto program"), V["ajusto"])
            try:
                page.get_by_test_id("action-Button-next").click()
                page.wait_for_timeout(2500)
            except Exception:
                pass

            # 11) coveragesStep -- capture premium + coverage
            body = page.locator("body").inner_text(timeout=8000)
            m = re.search(r"\$\s?\d[\d,]*\.?\d*\s*/month", body)
            if m:
                result["quote_monthly"] = m.group(0).strip()
                result["quote_value"] = re.search(r"[\d,]+\.?\d*", m.group(0)).group(0)
            mn = re.search(r"Quote number:\s*([A-Z0-9]+)", body)
            if mn:
                result["quote_number"] = mn.group(1)
            # capture headline coverage rows
            for cov in ["Third Party Liability", "Direct Compensation Property Damage",
                        "Collision or Upset", "Comprehensive", "Accident Benefits",
                        "Family Protection Coverage"]:
                cm = re.search(re.escape(cov) + r"[^\n]*", body)
                if cm:
                    result["coverage"][cov] = cm.group(0).strip()
            result["status"] = "quoted_comparable_candidate" if result["quote_value"] else "unresolved"

            # evidence screenshot (redacted later; dummy data run)
            os.makedirs(out_dir, exist_ok=True)
            shot = os.path.join(out_dir, "desjardins_offer.png")
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
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--headless", action="store_true", default=False)
    g.add_argument("--headed", action="store_true", default=False)
    ap.add_argument("--input", default=None,
                    help="Params JSON (e.g. people/dummy.json). Default: personal_profile.db.")
    ap.add_argument("--out", default="desjardins_auto_quote_result.json")
    args = ap.parse_args()

    headless = not args.headed
    print(f"Running {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    profile = load_profile() if not args.input else load_params(args.input)
    if not profile:
        print("WARNING: no params source. Use --input people/dummy.json", flush=True)

    res = run(headless=headless, params=profile)
    res["carrier"] = "desjardins.com (Certas Direct)"
    res["form_url"] = HOME_URL
    res["form_kind"] = "quote"
    res["_note"] = ("DUMMY/TEST DATA used if --input people/dummy.json. "
                    "Not a real quote; not valid evidence.")

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


_months = ["", "January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]

if __name__ == "__main__":
    main()
