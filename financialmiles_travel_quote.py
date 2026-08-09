"""
financialmiles_travel_quote.py
==============================
Playwright automation for Financial Miles - Travel Insurance quote request.

Form URL : https://www.financialmiles.com/travel-insurance-quote
DB link  : form_scripts table in insurance_websites.db
Form kind: lead_gen  ("Fill out, get personalized quotes delivered to your inbox" -
           quotes are emailed, not shown on-page. Submission shows "Thank you!
           Your submission has been received!")

Fields (verified one at a time; input names use 'TIQ - ' prefix):
  first name (TIQ---First-Name), last name (TIQ---Last-Name),
  email (TIQ---Email), phone (TIQ---Phone), DOB (TIQ - DOB, type=date YYYY-MM-DD),
  visa type (TIQ---Visa-Type radio Super Visa/Visitor Visa),
  pre-existing (TIQ---Medical-Conditions radio Yes/No),
  coverage start (TIQ - Coverage Start, date), coverage end (TIQ - Coverage End, date),
  landing province (TIQ---Landing-Province select), Submit.

Usage
-----
Headed:  python financialmiles_travel_quote.py --headed
Headless: python financialmiles_travel_quote.py --headless   (default)
Result persisted to financialmiles_travel_quote_result.json + quote_results.jsonl.
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORM_URL = "https://www.financialmiles.com/travel-insurance-quote"

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
    result = {"submitted": False, "quote_value": None, "success_message": None, "error": None}
    params = params or {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"), viewport={"width":1400,"height":1000})
        try:
            page.goto(FORM_URL, wait_until="domcontentloaded", timeout=40000)
            # NOTE: do NOT wait for networkidle (ads/analytics keep it busy).
            page.wait_for_timeout(2000)

            _fill(page, "TIQ---First-Name", get_param(params, "person.first_name", "John"))
            _fill(page, "TIQ---Last-Name", get_param(params, "person.last_name", "Doe"))
            _fill(page, "TIQ---Email", get_param(params, "person.email", ""))
            _fill(page, "TIQ---Phone", get_param(params, "person.phone", "9056889170"))
            dob = get_param(params, "person.date_of_birth", "1990/03/15")
            _fill(page, "TIQ - DOB", dob.replace("/", "-"))

            # Visa type = Super Visa; Pre-existing = No (radios)
            page.get_by_role("radio", name="Super Visa").click()
            page.get_by_role("radio", name="No").click()

            # Coverage start/end (dates)
            _fill(page, "TIQ - Coverage Start", "2026-09-01")
            _fill(page, "TIQ - Coverage End", "2026-09-30")

            # Landing province
            page.get_by_label("Landing Province in Canada *").select_option(
                get_param(params, "person.province", "Ontario"))

            # Submit
            page.get_by_role("button", name="Submit").click()
            page.wait_for_timeout(2000)

            # Detect success region
            region = page.locator('[role="region"]').filter(has_text="Thank you").first
            if region.count():
                result["submitted"] = True
                result["success_message"] = region.inner_text(timeout=3000).strip()
                result["result_note"] = "success: 'Thank you! Your submission has been received!' Lead-gen: quotes delivered to inbox."

            body_text = page.locator("body").inner_text(timeout=5000)
            m = DOLLAR_RE.search(body_text)
            if m:
                result["quote_value"] = m.group(0).strip()

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
    ap.add_argument("--out", default="financialmiles_travel_quote_result.json")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = ap.parse_args()
    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    res = run(headless=headless, params=load_params(args.input))
    res["carrier"] = "financialmiles.com"
    res["form_url"] = FORM_URL
    res["form_kind"] = "lead_gen"

    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, args.out), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    with open(os.path.join(base, "quote_results.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")

    print("\n=== RESULT ===")
    print("  submitted:", res.get("submitted"))
    print("  success_message:", res.get("success_message"))
    print("  quote_value:", res.get("quote_value"))
    print("  note:", res.get("result_note"))
    print("  error:", res.get("error"))


if __name__ == "__main__":
    main()
