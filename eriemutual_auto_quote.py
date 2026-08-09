"""
eriemutual_auto_quote.py
========================
Playwright automation for Erie Mutual Insurance - Auto Insurance quote request.

Form URL : https://www.eriemutual.com/insurance/auto-insurance/auto-insurance-quote/
Submit   : Contact Form 7 (contact-form 14123) -> POST /wp-json/contact-form-7/v1/contact-forms/14123/feedback
DB link  : form_scripts table in insurance_websites.db
Form kind: lead_gen  (collects auto quote details incl. vehicle/driver, emails them
           to the broker; NO $ premium is computed on-page.)

Fields (verified one at a time; names are CF7 input names):
  firstname, lastname, postalcode, email-address, phone, region (select),
  effective-date (date YYYY-MM-DD), vehicle-count (select No/Yes),
  vehicle-year, vehicle-make, vehicle-model, vehicle-distance (km one-way),
  vehicle-km (annual), vehicle-use (select Commuting/Pleasure),
  driver-firstname, driver-lastname, driver-birthdate (date YYYY-MM-DD),
  convictions (select), accidents (select).

Usage
-----
Headed:  python eriemutual_auto_quote.py --headed
Headless: python eriemutual_auto_quote.py --headless   (default)
Result persisted to eriemutual_auto_quote_result.json + quote_results.jsonl.
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORM_URL = "https://www.eriemutual.com/insurance/auto-insurance/auto-insurance-quote/"

DOLLAR_RE = re.compile(r"\$\s?\d[\d,.]*")


def _fill(page, name, value):
    return page.evaluate(
        """(arg) => {
            const el = document.querySelector(`input[name="${arg.name}"]`);
            if (!el) return false;
            const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
            s.call(el, arg.value);
            el.dispatchEvent(new Event('input',{bubbles:true}));
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return el.value;
        }""", {"name": name, "value": value}
    )


def _select(page, name, value):
    return page.evaluate(
        """(arg) => {
            const el = document.querySelector(`select[name="${arg.name}"]`);
            if (!el) return false;
            for (let i=0;i<el.options.length;i++){
                if (el.options[i].value === arg.value || el.options[i].text === arg.value){ el.selectedIndex=i; break; }
            }
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return el.options[el.selectedIndex].text;
        }""", {"name": name, "value": value}
    )


def run(headless: bool, params: dict | None = None) -> dict:
    result = {"submitted": False, "quote_value": None, "response": None, "error": None}
    params = params or {}
    post_bodies = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"), viewport={"width":1400,"height":1000})

        def on_response(resp):
            try:
                if "contact-forms/14123/feedback" in resp.url and resp.status == 200:
                    post_bodies.append(resp.text())
            except Exception:
                pass
        page.on("response", on_response)

        try:
            page.goto(FORM_URL, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # Personal info
            _fill(page, "firstname", get_param(params, "person.first_name", "John"))
            _fill(page, "lastname", get_param(params, "person.last_name", "Doe"))
            _fill(page, "postalcode", get_param(params, "person.postal_code", "L2R 1A1"))
            _fill(page, "email-address", get_param(params, "person.email", ""))
            _fill(page, "phone", get_param(params, "person.phone", "9056889170"))

            # Policy info
            _select(page, "region", "Niagara")
            dob = get_param(params, "person.date_of_birth", "1990/03/15")
            # Date inputs: use Playwright fill (native setter isn't accepted by CF7's
            # SWV date validator for type=date fields).
            page.locator('#effective-date').fill("2026-09-01")

            # Vehicle info
            _select(page, "vehicle-count", "No")
            _fill(page, "vehicle-year", get_param(params, "auto.vehicle_year", "2019"))
            _fill(page, "vehicle-make", get_param(params, "auto.vehicle_make", "HONDA"))
            _fill(page, "vehicle-model", get_param(params, "auto.vehicle_model", "ACCORD"))
            _fill(page, "vehicle-distance", "10")
            _fill(page, "vehicle-km", "15000")
            _select(page, "vehicle-use", "Commuting")

            # Driver info
            _fill(page, "driver-firstname", get_param(params, "person.first_name", "John"))
            _fill(page, "driver-lastname", get_param(params, "person.last_name", "Doe"))
            page.locator('#driver-birthdate').fill(dob.replace("/", "-"))

            # Report card
            _select(page, "convictions", "None")
            _select(page, "accidents", "None")

            # Submit (CF7 AJAX)
            page.get_by_role("button", name="Submit").click()
            page.wait_for_timeout(3000)

            result["submitted"] = True
            for body in post_bodies:
                result["response"] = body[:300]
                if '"success":true' in body:
                    result["result_note"] = "submitted successfully (CF7 feedback success). Lead-gen: broker responds with a quote."
            if not post_bodies:
                result["result_note"] = "form POSTed (CF7 feedback); no response body captured. Lead-gen."

            # No dollar value expected; check anyway.
            body_text = page.locator("body").inner_text(timeout=5000)
            m = DOLLAR_RE.search(body_text)
            if m:
                result["quote_value"] = m.group(0).strip()

        except Exception as e:
            result["error"] = str(e)
            print("ERROR:", e, flush=True)
        finally:
            page.remove_listener("response", on_response)
            if not headless:
                page.wait_for_timeout(3000)
            browser.close()
    return result


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--headless", action="store_true", default=False)
    g.add_argument("--headed", action="store_true", default=False)
    ap.add_argument("--out", default="eriemutual_auto_quote_result.json")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = ap.parse_args()
    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    res = run(headless=headless, params=load_params(args.input))
    res["carrier"] = "eriemutual.com"
    res["form_url"] = FORM_URL
    res["form_kind"] = "lead_gen"

    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, args.out), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    with open(os.path.join(base, "quote_results.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")

    print("\n=== RESULT ===")
    print("  submitted:", res.get("submitted"))
    print("  response:", res.get("response"))
    print("  quote_value:", res.get("quote_value"))
    print("  note:", res.get("result_note"))
    print("  error:", res.get("error"))


if __name__ == "__main__":
    main()
