"""
aprilmarine_boat_quote.py
=========================
Playwright automation for APRIL Marine - Boat Insurance online rater.

Entry  : https://aprilmarine.ca/on-en/quote  -> "Get a Quote" opens prime.aprilmarine.ca
Rater  : https://prime.aprilmarine.ca/ (multi-step boat quote)
DB link: form_scripts table (aprilmarine.ca -> aprilmarine_boat_quote.py)
Form kind: QUOTE  -- returns a real premium ($), unlike lead-gen forms.

Flow (verified field-by-field via Playwright MCP):
  1. Landing: Language=English, Province=Ontario -> Start
  2. Boat type: Motorboat
  3. Motorboat Information: Make, Model, Engine Type, Category (auto), Year, Value
  4. Your Information: First/Last Name, E-mail, Phone, DOB, Province (auto ON)
  5. Driver's record: ownership duration, already insured, renewal date,
     boat claims, license suspension
  6. Get My Premium -> returns "Estimated premium for: BAYLINER XP (2020): $504.36/year"
     and emails the full quote (to the provided email).

Usage
-----
Headed:  python aprilmarine_boat_quote.py --headed
Headless: python aprilmarine_boat_quote.py --headless   (default)
Result is persisted to aprilmarine_boat_quote_result.json and quote_results.jsonl.
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LANDING_URL = "https://aprilmarine.ca/on-en/quote"

# Form field -> params path (values loaded from the shared per-person JSON).
# FIXED fields: see field_registry.json. Value auto-formats (35000 -> '35 000').
PARAM_MAP = {
    "boat_type":       "boat.boat_type",
    "make":            "boat.make",
    "model":           "boat.model",
    "engine_type":     "boat.engine_type",
    "category":        "boat.category",
    "boat_year":       "boat.boat_year",
    "boat_value":      "boat.boat_value",
    "first_name":      "person.first_name",
    "last_name":       "person.last_name",
    "email":           "person.email",
    "phone":           "person.phone",
    "dob":             "person.date_of_birth",
    "owned":           "boat.owned_months",
    "already_insured": "boat.already_insured",
    "renewal_date":    "boat.renewal_date",
    "claim_number":    "boat.boat_claims",
    "license_suspension": "boat.licence_suspension",
}

DOLLAR_RE = re.compile(r"\$\s?\d[\d,.]*")
YEARLY_RE = re.compile(r"(\$[\d,.]+\s*/\s*year)")


def _set_select(page, index, value):
    return page.evaluate(
        """(arg) => {
            const sel = document.querySelectorAll('select')[arg.index];
            if (!sel) return false;
            for (let i=0;i<sel.options.length;i++){
                if (sel.options[i].text === arg.value || sel.options[i].value === arg.value){
                    sel.selectedIndex = i; break;
                }
            }
            sel.dispatchEvent(new Event('change',{bubbles:true}));
            return sel.options[sel.selectedIndex].text;
        }""", {"index": index, "value": value}
    )


def _fill_by_selector(page, selector, value):
    return page.evaluate(
        """(arg) => {
            const el = document.querySelector(arg.sel);
            if (!el) return false;
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
            setter.call(el, arg.value);
            el.dispatchEvent(new Event('input',{bubbles:true}));
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return el.value;
        }""", {"sel": selector, "value": value}
    )


def _fill_by_index(page, index, value):
    """Fill the Nth enabled text input (0-based). Order on this form is:
       0=Year, 1=Value, 2=First name, 3=Last name, 4=DOB, 5=renewal date."""
    return page.evaluate(
        """(arg) => {
            const els = Array.from(document.querySelectorAll('input[type="text"]')).filter(i=>!i.disabled);
            const el = els[arg.index];
            if (!el) return false;
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
            setter.call(el, arg.value);
            el.dispatchEvent(new Event('input',{bubbles:true}));
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return el.value;
        }""", {"index": index, "value": value}
    )


def _set_radio_by_name(page, name, value):
    return page.evaluate(
        """(arg) => {
            const r = Array.from(document.querySelectorAll('input[type="radio"]'))
                .find(x => x.name===arg.name && x.value===String(arg.value));
            if (r) { r.checked=true; r.dispatchEvent(new Event('change',{bubbles:true})); r.dispatchEvent(new Event('click',{bubbles:true})); return true; }
            return false;
        }""", {"name": name, "value": value}
    )


def run(headless: bool, params: dict | None = None) -> dict:
    result = {"quote_value": None, "quote_number": None, "emailed": False, "details": {}}
    params = params or {}
    # Resolve form field values from the shared per-person params.
    V = {f: get_param(params, p, "") for f, p in PARAM_MAP.items()}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            viewport={"width":1400,"height":1000})
        page = context.new_page()
        try:
            # 1) Go straight to the quoter (more robust than the new-tab click).
            #    The boat-owner "Get a Quote" on the landing page opens
            #    https://prime.aprilmarine.ca/ in a new tab; navigating directly avoids
            #    the cookie-banner interception in headless mode.
            page.goto("https://prime.aprilmarine.ca/", wait_until="domcontentloaded", timeout=40000)
            page.wait_for_load_state("networkidle", timeout=15000)
            quote = page

            # 2) Select English + Ontario on the quoter landing, then Start
            quote.evaluate("""() => {
                const el = Array.from(document.querySelectorAll('div')).find(d=>d.textContent.trim()==='English');
                if (el) el.click();
            }""")
            quote.wait_for_timeout(300)
            quote.evaluate("""() => {
                const el = Array.from(document.querySelectorAll('div')).find(d=>d.textContent.trim()==='Ontario');
                if (el) el.click();
            }""")
            quote.wait_for_timeout(300)
            quote.get_by_role("button", name="Start").click()
            quote.wait_for_timeout(1000)

            # 3) Boat type = Motorboat (last of the 4 options)
            quote.evaluate("""() => {
                const el = Array.from(document.querySelectorAll('div')).find(d=>d.textContent.trim()==='Motorboat');
                if (el) el.click();
            }""")
            quote.wait_for_timeout(1200)

            # 4) Motorboat Information
            _set_select(quote, 0, V["make"])   # Make
            quote.wait_for_timeout(400)
            _set_select(quote, 1, V["model"])  # Model
            quote.wait_for_timeout(400)
            _set_select(quote, 2, V["engine_type"]) # Engine Type
            quote.wait_for_timeout(400)
            # Year[0] + Value[1]
            _fill_by_index(quote, 0, V["boat_year"])
            quote.wait_for_timeout(300)
            _fill_by_index(quote, 1, V["boat_value"])
            quote.wait_for_timeout(300)

            # 5) Your Information (First[2], Last[3], email, phone, DOB)
            _fill_by_index(quote, 2, V["first_name"])
            _fill_by_index(quote, 3, V["last_name"])
            _fill_by_selector(quote, 'input[type="email"]', V["email"])
            _fill_by_selector(quote, 'input[type="tel"]', V["phone"])
            _fill_by_selector(quote, 'input[placeholder="YYYY/MM/DD"]', V["dob"])

            # 6) Driver's record
            _set_radio_by_name(quote, "experience", V["owned"])
            _set_radio_by_name(quote, "already_insured_with_us", V["already_insured"])
            _fill_by_selector(quote, 'input[placeholder="YYYY/MM/DD"]', V["renewal_date"])
            _set_radio_by_name(quote, "claim_number", V["claim_number"])
            _set_radio_by_name(quote, "license_suspension", V["license_suspension"])

            # 7) Get My Premium
            quote.get_by_role("button", name="Get My Premium").click()
            quote.wait_for_timeout(4000)

            body = quote.locator("body").inner_text(timeout=8000)
            m = YEARLY_RE.search(body)
            if m:
                result["quote_value"] = m.group(1).strip()
            # capture premium + coverage details
            for label in ["Estimated premium", "Deductible", "Liability"]:
                mm = re.search(label + r"[:\s]*([$\d,]+)", body)
                if mm:
                    result["details"][label] = mm.group(1)
            result["emailed"] = "has been emailed" in body or "emailed to you" in body

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
    ap.add_argument("--out", default="aprilmarine_boat_quote_result.json")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = ap.parse_args()
    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    res = run(headless=headless, params=load_params(args.input))
    res["carrier"] = "aprilmarine.ca"
    res["form_url"] = "https://aprilmarine.ca/on-en/quote"
    res["form_kind"] = "quote"

    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, args.out), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    with open(os.path.join(base, "quote_results.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")

    print("\n=== RESULT ===")
    print("  quote_value:", res.get("quote_value"))
    print("  details:", res.get("details"))
    print("  emailed:", res.get("emailed"))
    print("  error:", res.get("error"))


if __name__ == "__main__":
    main()
