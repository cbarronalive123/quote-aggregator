"""
activeinsurance_travel_quote.py
===============================
Playwright automation for Active Insurance - Travel Insurance quote request.

Form URL : https://www.activeinsurance.ca/quote-request/travel-insurance/
Submit   : Contact Form 7 (#632) -> POST /wp-json/contact-form-7/v1/contact-forms/632/feedback
DB link  : form_scripts table in insurance_websites.db
Form kind: lead_gen  (collects a travel quote request incl. departure/return/destination
           + insured details; emails it to the broker. Response: "Thank you. Your
           submission has been received and someone from Active Insurance will be
           in touch." - NO $ premium is computed on-page.)

Fields (verified one at a time; CF7 names):
  your-name, your-address, your-city, your-province, your-postalcode, your-phone,
  your-email, departure-date, return-date, destination,
  insured1-name, insured1-dob, insured1-sex (Male/Female), insured1-health (Yes/No),
  insured1-pre (None/Heart/...), insured1-pre-number (One/Two/...).

Usage
-----
Headed:  python activeinsurance_travel_quote.py --headed
Headless: python activeinsurance_travel_quote.py --headless   (default)
Result persisted to activeinsurance_travel_quote_result.json + quote_results.jsonl.
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORM_URL = "https://www.activeinsurance.ca/quote-request/travel-insurance/"

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
                if "contact-forms/632/feedback" in resp.url and resp.status == 200:
                    post_bodies.append(resp.text())
            except Exception:
                pass
        page.on("response", on_response)

        try:
            page.goto(FORM_URL, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # Contact
            _fill(page, "your-name", get_param(params, "person.first_name", "John") + " " + get_param(params, "person.last_name", "Doe"))
            _fill(page, "your-address", "123 Main St")
            _fill(page, "your-city", "Toronto")
            _fill(page, "your-province", "Ontario")
            _fill(page, "your-postalcode", get_param(params, "person.postal_code", "M5V 2T6"))
            _fill(page, "your-phone", get_param(params, "person.phone", "4164104797"))
            _fill(page, "your-email", get_param(params, "person.email", ""))

            # Travel
            _fill(page, "departure-date", "2026-09-01")
            _fill(page, "return-date", "2026-09-30")
            _fill(page, "destination", "United States")

            # Insured #1
            _fill(page, "insured1-name", get_param(params, "person.first_name", "John") + " " + get_param(params, "person.last_name", "Doe"))
            _fill(page, "insured1-dob", get_param(params, "person.date_of_birth", "1990/03/15").replace("/", "-"))
            # Sex Male (default), Health = No, Pre-existing = None (defaults)
            page.get_by_role("radio", name="No").first.click()
            page.wait_for_timeout(300)

            # Submit (CF7 AJAX)
            page.get_by_role("button", name="Submit", exact=True).click()
            page.wait_for_timeout(3000)

            result["submitted"] = True
            for body in post_bodies:
                result["response"] = body[:300]
                if '"status":"mail_sent"' in body:
                    result["result_note"] = "submitted successfully (CF7 mail_sent). Lead-gen: someone will be in touch."
            if not post_bodies:
                result["result_note"] = "form POSTed (no response captured). Lead-gen."

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
    ap.add_argument("--out", default="activeinsurance_travel_quote_result.json")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = ap.parse_args()
    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    res = run(headless=headless, params=load_params(args.input))
    res["carrier"] = "activeinsurance.ca"
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
