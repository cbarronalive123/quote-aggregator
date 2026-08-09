"""
bertramandbarry_car_quote.py
============================
Playwright automation for Bertram & Barry Insurance - Car Insurance quote request.

Form URL : https://www.bertramandbarry.ca/quote/car-insurance/
Submit   : Contact Form 7 (#321) -> POST /wp-json/contact-form-7/v1/contact-forms/321/feedback
DB link  : form_scripts table in insurance_websites.db
Form kind: lead_gen  (collects a detailed car-insurance quote request incl. driver,
           vehicle, coverage preferences; emails it to the broker. Response:
           "We've successfully received your claim. A representative will be in
           touch with you." - NO $ premium is computed on-page.)

Fields (verified one at a time; CF7 field names):
  fullname, address, city, province, postalcode, phone, emailaddress,
  age-driver, marital-status (Married/Single), years-licensed,
  addl-gender (Male/Female), certification (Yes/No), convictions (Yes/No),
  conviction-count, business-use (Yes/No), commute (Yes/No),
  vehicle (year make model), liability (select), coverage (select),
  deductible (select), addl-vehicles (Yes/No), policy-years, at-fault-claims,
  years-since-claim, occupation, commute-km, canceled (Yes/No), lapsed,
  property-insurer.

Usage
-----
Headed:  python bertramandbarry_car_quote.py --headed
Headless: python bertramandbarry_car_quote.py --headless   (default)
Result persisted to bertramandbarry_car_quote_result.json + quote_results.jsonl.
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORM_URL = "https://www.bertramandbarry.ca/quote/car-insurance/"

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
                if "contact-forms/321/feedback" in resp.url and resp.status == 200:
                    post_bodies.append(resp.text())
            except Exception:
                pass
        page.on("response", on_response)

        try:
            page.goto(FORM_URL, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # Contact
            _fill(page, "fullname", get_param(params, "person.first_name", "John") + " " + get_param(params, "person.last_name", "Doe"))
            _fill(page, "address", "123 Main St")
            _fill(page, "city", "St. Catharines")
            _fill(page, "province", "Ontario")
            _fill(page, "postalcode", get_param(params, "person.postal_code", "L2R 1A1"))
            _fill(page, "phone", get_param(params, "person.phone", "9056889170"))
            _fill(page, "emailaddress", get_param(params, "person.email", ""))

            # Driver
            _fill(page, "age-driver", "35")
            _select(page, "marital-status", "Single")
            _fill(page, "years-licensed", "18")
            _select(page, "addl-gender", "Male")
            _select(page, "certification", "No")
            _select(page, "convictions", "No")
            _fill(page, "conviction-count", "0")

            # Usage
            _select(page, "business-use", "No")
            _select(page, "commute", "Yes")

            # Vehicle + coverage (defaults $2M / All perils / $500 deductible are fine)
            _fill(page, "vehicle", "2019 Honda Accord")
            _select(page, "addl-vehicles", "No")
            _fill(page, "policy-years", "15")
            _fill(page, "at-fault-claims", "0")
            _fill(page, "years-since-claim", "0")
            _fill(page, "occupation", "Software Developer")
            _fill(page, "commute-km", "10")
            _select(page, "canceled", "No")
            _fill(page, "lapsed", "No")
            _fill(page, "property-insurer", "None")

            # Submit (CF7 AJAX)
            page.get_by_role("button", name="Submit").click()
            page.wait_for_timeout(3000)

            result["submitted"] = True
            for body in post_bodies:
                result["response"] = body[:300]
                if '"status":"mail_sent"' in body:
                    result["result_note"] = "submitted successfully (CF7 mail_sent). Lead-gen: representative will be in touch."
            if not post_bodies:
                result["result_note"] = "form POSTed (no response captured). Lead-gen."

            # No dollar value expected; check body.
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
    ap.add_argument("--out", default="bertramandbarry_car_quote_result.json")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = ap.parse_args()
    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    res = run(headless=headless, params=load_params(args.input))
    res["carrier"] = "bertramandbarry.ca"
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
