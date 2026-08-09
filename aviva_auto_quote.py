"""
aviva_auto_quote.py
===================
Playwright automation for Aviva Direct - Auto Insurance online rater.

Entry  : https://www.aviva.ca/en/  (open the Direct quote modal, enter postal code)
Rater  : myaviva.avivainsurance.ca/avivaquoter/bol/auto/{step}
DB link: form_scripts table (aviva.ca -> aviva_auto_quote.py)
Form kind: QUOTE  -- returns a real premium ($), unlike lead-gen forms.

Flow (multi-step, each field verified via Playwright MCP):
  1. Quote modal : postal code  -> Get a quote
  2. Car Details : year/make/model, purchase date, condition, winter tires, anti-theft
  3. Car Use     : annual mileage, commute days + one-way km, business use, start date
  4. Driver      : first/last name, DOB, sex, marital, retired, combined policy, TELUS,
                   continuous insurance
  5. Licence     : class, first licence date, G2 date, other classes, out-of-province,
                   international
  6. Experience  : convictions/at-fault/cancellations
  7. Double-check: assumptions -> "Yes, that's correct"
  8. Aviva Journey: include app? -> No
  9. Contact     : phone, phone type, email (user's), consent checkbox
 10. Customization: coverage defaults -> premium shown -> "Email my quote" -> submit

Usage
-----
Headed:  python aviva_auto_quote.py --headed
Headless: python aviva_auto_quote.py --headless   (default)
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import get_param, load_params
from personal_profile import load_profile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME_URL = "https://www.aviva.ca/en/"
QUOTE_EMAIL = "cormbar@msn.com"   # where the final quote is emailed (default)

# Form field name -> params path. Values are loaded from the shared per-person
# JSON (quote_params.json or --input). FIXED fields: see field_registry.json.
PARAM_MAP = {
    # vehicle
    "vehicleYear":          "auto.vehicle_year",
    "vehicleMake":          "auto.vehicle_make",
    "vehicleModel":         "auto.vehicle_model",
    "purchaseDate_month":   "auto.purchase_month",
    "purchaseDate_year":    "auto.purchase_year",
    "purchaseCondition":    "auto.purchase_condition",
    "winterTires":          "auto.winter_tires",
    "hasAntiTheftDevice":   "auto.anti_theft",
    # car use
    "annualMileage":        "auto.annual_km",
    "commutePerWeek":       "auto.commute_days",
    "commutingMiles":       "auto.commute_oneway_km",
    "businessUse":          "auto.business_use",
    "coverageStartDate":    "auto.coverage_start_date",   # MM/DD/YYYY
    # driver
    "driverFirstName":      "person.first_name",
    "driverLastName":       "person.last_name",
    "driverDOB_m":          "person.date_of_birth",       # split into m/d/y below
    "sex":                  "person.sex",
    "maritalStatus":        "person.marital_status",
    "retired":              "auto.retired",
    "combinedPolicyDiscount": "auto.combined_policy",     # NO/ME/PARTNER
    "telusHealth":          "auto.telus_health",
    "hadPriorInsurance":    "auto.prior_insurance",
    # licence
    "licenseClass":         "auto.licence_class",
    "firstLicenceDate_month": "auto.first_licence_month",
    "firstLicenceDate_year":  "auto.first_licence_year",
    "isGraduatedLicense":   "auto.held_other_classes",
    "graduateLicenseDate_month": "auto.g2_month",
    "graduateLicenseDate_year":  "auto.g2_year",
    "hasOutOfProvinceLicense": "auto.out_of_province_continuous",
    "internationalLicenseClass": "auto.international_continuous",
    # contact
    "phone":                "person.phone",
    "phoneType":            "person.phone_type",
    "email":                "person.email",
}


def _set_radio(page, name_prefix, value):
    return page.evaluate(
        """(arg) => {
            const r = Array.from(document.querySelectorAll('input[type="radio"]'))
                .find(x => x.name.startsWith(arg.prefix) && x.value === arg.value);
            if (r) {
                r.checked = true;
                r.dispatchEvent(new Event('change',{bubbles:true}));
                r.dispatchEvent(new Event('click',{bubbles:true}));
            }
            return !!r;
        }""", {"prefix": name_prefix, "value": value}
    )


def _set_select(page, name_or_testid, value, by_value=True):
    return page.evaluate(
        """(arg) => {
            const sel = document.querySelector(`select[name="${arg.name}"], select[data-testid="${arg.name}"]`);
            if (!sel) return false;
            for (let i=0;i<sel.options.length;i++){
                const o = sel.options[i];
                if (arg.byValue && o.value === arg.value) { sel.selectedIndex = i; break; }
                if (!arg.byValue && o.text === arg.value) { sel.selectedIndex = i; break; }
            }
            sel.dispatchEvent(new Event('change',{bubbles:true}));
            return sel.options[sel.selectedIndex].text;
        }""", {"name": name_or_testid, "value": value, "by_value": by_value}
    )


def _fill(page, selector, value):
    return page.evaluate(
        """(arg) => {
            const el = document.querySelector(arg.sel);
            if (!el) return false;
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set ||
                           Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
            setter.call(el, arg.value);
            el.dispatchEvent(new Event('input',{bubbles:true}));
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return el.value;
        }""", {"sel": selector, "value": value}
    )


def run(headless: bool, params: dict | None = None) -> dict:
    result = {"quote_value": None, "quote_number": None, "emailed": False}
    params = params or {}
    # Resolve form field values from the shared per-person params.
    V = {f: get_param(params, p, "") for f, p in PARAM_MAP.items()}
    # DOB is stored as YYYY/MM/DD; split into month/day/year for the form.
    dob = get_param(params, "person.date_of_birth", "1990/03/15")
    try:
        _y, _m, _d = dob.split("/")
    except Exception:
        _y, _m, _d = "1990", "03", "15"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"), viewport={"width":1400,"height":1000})
        try:
            # 1) Quote modal via homepage
            page.goto(HOME_URL, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_load_state("networkidle", timeout=15000)
            # open Direct modal (a "Check our prices" / Get a quote CTA)
            # Fill postal code in the quickmodal
            page.evaluate("""() => {
                const inp = document.querySelector('input[placeholder="A1A 1A1"]');
                if (inp) {
                    const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                    s.call(inp,'M5V 2T6');
                    inp.dispatchEvent(new Event('input',{bubbles:true}));
                    inp.dispatchEvent(new Event('change',{bubbles:true}));
                }
            }""")
            page.wait_for_timeout(500)
            # click Get a quote in the quickmodal
            page.evaluate("""() => {
                const b = document.querySelector('button[data-text="Get a quote"]');
                if (b) b.click();
            }""")
            page.wait_for_timeout(4000)

            # Now on rater. Helper clicks for the current page's Continue/Back.
            def click_continue():
                page.locator('button[name="continueButton"], button:has-text("Continue")').first.click(force=True)
                page.wait_for_timeout(1200)

            # 2) Car Details
            _set_select(page, "vehicleYear", V["vehicleYear"])
            page.wait_for_timeout(300)
            _set_select(page, "vehicleMake", V["vehicleMake"])
            page.wait_for_timeout(300)
            _set_select(page, "vehicleModel", V["vehicleModel"])
            page.wait_for_timeout(300)
            _set_select(page, "purchaseDate_month", V["purchaseDate_month"], by_value=False)
            _set_select(page, "purchaseDate_year", V["purchaseDate_year"])
            _set_radio(page, "purchaseCondition", V["purchaseCondition"])
            _set_radio(page, "winterTires", V["winterTires"])
            _set_radio(page, "hasAntiTheftDevice", V["hasAntiTheftDevice"])
            click_continue()

            # 3) Car Use
            _fill(page, 'input[name="annualMileage"]', V["annualMileage"])
            _set_select(page, "commutePerWeek", V["commutePerWeek"])
            _fill(page, 'input[name="commutingMiles"]', V["commutingMiles"])
            _fill(page, 'input[placeholder="MM/DD/YYYY"]', V["coverageStartDate"])
            click_continue()

            # 4) Driver
            _fill(page, '[data-testid="driverFirstName"]', V["driverFirstName"])
            _fill(page, '[data-testid="driverLastName"]', V["driverLastName"])
            _fill(page, '[data-testid="dateOfBirth-month"]', _m)
            _fill(page, '[data-testid="dateOfBirth-day"]', _d)
            _fill(page, '[data-testid="dateOfBirth-year"]', _y)
            _set_radio(page, "sex", V["sex"])
            _set_select(page, "maritalStatus", V["maritalStatus"])
            _set_radio(page, "retired", V["retired"])
            _set_radio(page, "combinedPolicyDiscount", V["combinedPolicyDiscount"])
            _set_radio(page, "telusHealth", V["telusHealth"])
            _set_radio(page, "hadPriorInsurance", V["hadPriorInsurance"])
            click_continue()

            # 5) Licence
            _set_radio(page, "licenseClass", V["licenseClass"])
            _set_select(page, "firstLicenceDate_month", V["firstLicenceDate_month"], by_value=False)
            _set_select(page, "firstLicenceDate_year", V["firstLicenceDate_year"])
            _set_radio(page, "isGraduatedLicense", V["isGraduatedLicense"])
            _set_select(page, "graduateLicenseDate_month", V["graduateLicenseDate_month"], by_value=False)
            _set_select(page, "graduateLicenseDate_year", V["graduateLicenseDate_year"])
            _set_radio(page, "hasOutOfProvinceLicense", V["hasOutOfProvinceLicense"])
            click_continue()
            # international licence -> "No" (3rd radio of internationalLicenseClass)
            page.evaluate("""() => {
                const rs = document.querySelectorAll('input[type="radio"][name="internationalLicenseClass"]');
                if (rs.length >= 3) { rs[2].checked=true; rs[2].dispatchEvent(new Event('change',{bubbles:true})); }
            }""")
            click_continue()
            # close any "Let's connect" modal that may interrupt
            page.evaluate("""() => {
                const close = document.querySelector('button[aria-label*="MVR.close"], button[aria-label*="close"]');
                if (close) close.click();
            }""")
            page.wait_for_timeout(500)

            # 6) Experience (No already default) + 7) Double-check
            click_continue()
            page.evaluate("""() => {
                const b = Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes("Yes, that's correct"));
                if (b) b.click();
            }""")
            page.wait_for_timeout(1000)

            # 8) Aviva Journey -> No (driver1 radio)
            page.evaluate("""() => {
                const r = document.querySelector('input[type="radio"][value="No"]');
                if (r) { r.checked=true; r.dispatchEvent(new Event('change',{bubbles:true})); r.dispatchEvent(new Event('click',{bubbles:true})); }
            }""")
            click_continue()

            # 9) Contact
            _fill(page, '[data-testid="userPhoneNumber"]', V["phone"])
            _set_select(page, "phoneType", V["phoneType"])
            _fill(page, '[data-testid="userEmail"]', V["email"])
            page.evaluate("""() => {
                const cb = document.querySelector('input[type="checkbox"][name="marketingConsent"]');
                if (cb) { cb.checked=true; cb.dispatchEvent(new Event('change',{bubbles:true})); cb.dispatchEvent(new Event('click',{bubbles:true})); }
            }""")
            click_continue()

            # 10) Customization -> capture premium -> email my quote
            page.wait_for_timeout(1500)
            body = page.locator("body").inner_text(timeout=5000)
            m = re.search(r"\$\s?\d[\d,.]*\s?per (month|year)", body)
            if m:
                result["quote_value"] = m.group(0).strip()
            mn = re.search(r"Q\s?[\d ]{6,}", body)
            if mn:
                result["quote_number"] = mn.group(0).strip()

            # Email the quote
            page.evaluate("""() => {
                const b = Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Email my quote'));
                if (b) b.click();
            }""")
            page.wait_for_timeout(1200)
            page.evaluate("""() => {
                const b = Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Submit');
                if (b) b.click();
            }""")
            page.wait_for_timeout(1500)
            ok = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('*')).some(e=>e.textContent && e.textContent.includes('has been sent to your email'));
            }""")
            result["emailed"] = bool(ok)

        except Exception as e:
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
    ap.add_argument("--out", default="aviva_auto_quote_result.json",
                    help="JSON file to persist the captured result (default: aviva_auto_quote_result.json)")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = ap.parse_args()
    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    profile = load_profile() if not args.input else load_params(args.input)
    res = run(headless=headless, params=profile)
    res["carrier"] = "aviva.ca"
    res["form_url"] = "https://www.aviva.ca/bin/aviva/quoter"
    res["form_kind"] = "quote"

    # Persist the captured result to disk.
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    # Append to a running results log for batch collection.
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quote_results.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")

    print("\n=== RESULT ===")
    print("  quote_value:", res.get("quote_value"))
    print("  quote_number:", res.get("quote_number"))
    print("  emailed:", res.get("emailed"))
    print("  error:", res.get("error"))
    print(f"  saved to: {out_path} and appended to {log_path}")


if __name__ == "__main__":
    main()
