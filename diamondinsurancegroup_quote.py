"""
diamondinsurancegroup_quote.py
==============================
Playwright automation for Diamond Insurance Group - Multi-product quote request.

Form URL : https://diamondinsurancegroup.ca/get-a-quote/
Submit   : Bricks form (AJAX). Success: "Message successfully sent. We will get back
           to you as soon as possible."
DB link  : form_scripts table in insurance_websites.db
Form kind: lead_gen  (collects contact + coverage selection (Auto/Home/Business/...);
           the broker provides a tailored quote. NO $ premium is computed on-page.)

Fields (verified one at a time; Bricks form-field names):
  form-field-quote-first-name/last-name/email/tel/street/city/province/postal,
  form-field-quote-coverage[] (checkbox), form-field-sub-*-insurance[] (checkboxes),
  referral, info.

Usage
-----
Headed:  python diamondinsurancegroup_quote.py --headed
Headless: python diamondinsurancegroup_quote.py --headless   (default)
Result persisted to diamondinsurancegroup_quote_result.json + quote_results.jsonl.
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORM_URL = "https://diamondinsurancegroup.ca/get-a-quote/"

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


def _check(page, name, value):
    return page.evaluate(
        """(arg) => {
            const el = document.querySelector(`input[name="${arg.name}"][value="${arg.value}"]`);
            if (el) { el.checked = true; el.dispatchEvent(new Event('change',{bubbles:true})); return true; }
            return false;
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
            page.wait_for_load_state("networkidle", timeout=15000)

            # Contact
            _fill(page, "form-field-quote-first-name", get_param(params, "person.first_name", "John"))
            _fill(page, "form-field-quote-last-name", get_param(params, "person.last_name", "Doe"))
            _fill(page, "form-field-quote-email", get_param(params, "person.email", ""))
            _fill(page, "form-field-quote-tel", get_param(params, "person.phone", "9059510029"))
            _fill(page, "form-field-quote-street", "123 Main St")
            _fill(page, "form-field-quote-city", "Mississauga")
            _fill(page, "form-field-quote-province", "Ontario")
            _fill(page, "form-field-quote-postal", get_param(params, "person.postal_code", "L5B 1B5"))

            # Coverage selection: Auto Insurance (main + sub-auto)
            _check(page, "form-field-quote-coverage[]", "Auto Insurance")
            _check(page, "form-field-sub-auto-insurance[]", "Auto Insurance")

            # Submit (main quote form's Submit button; use .first to avoid the
            # newsletter form's button)
            page.locator('form button[type="submit"]').first.click()
            page.wait_for_timeout(3000)

            body = page.locator("body").inner_text(timeout=5000)
            if "Message successfully sent" in body:
                result["submitted"] = True
                result["success_message"] = "Message successfully sent. We will get back to you as soon as possible."
                result["result_note"] = "submitted successfully. Lead-gen: broker will provide a tailored quote."

            m = DOLLAR_RE.search(body)
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
    ap.add_argument("--out", default="diamondinsurancegroup_quote_result.json")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = ap.parse_args()
    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    res = run(headless=headless, params=load_params(args.input))
    res["carrier"] = "diamondinsurancegroup.ca"
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
