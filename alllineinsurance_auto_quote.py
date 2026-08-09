"""
alllineinsurance_auto_quote.py
==============================
Playwright automation for All Line Insurance Brokers - Auto insurance quote request.

Form URL : https://www.alllineinsurance.ca/start-a-quote/
Submit   : Contact Form 7 (#1219) - response "Your message was sent successfully. Thanks."
DB link  : form_scripts table in insurance_websites.db
Form kind: lead_gen  (simple auto quote request; a representative contacts you to
           schedule an appointment. NO $ premium is computed on-page.)

Fields (verified one at a time; CF7 names):
  fname, lname, email, phone, zipcode, date (effective date, YYYY-MM-DD),
  currently insured (radio Yes/No), insurance type (select Automobile).

Usage
-----
Headed:  python alllineinsurance_auto_quote.py --headed
Headless: python alllineinsurance_auto_quote.py --headless   (default)
Result persisted to alllineinsurance_auto_quote_result.json + quote_results.jsonl.
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORM_URL = "https://www.alllineinsurance.ca/start-a-quote/"

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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"), viewport={"width":1400,"height":1000})
        try:
            page.goto(FORM_URL, wait_until="domcontentloaded", timeout=40000)
            # don't wait for networkidle (analytics keep it busy)
            page.wait_for_timeout(2000)

            _fill(page, "fname", get_param(params, "person.first_name", "John"))
            _fill(page, "lname", get_param(params, "person.last_name", "Doe"))
            _fill(page, "email", get_param(params, "person.email", ""))
            _fill(page, "phone", get_param(params, "person.phone", "5192500269"))
            _fill(page, "zipcode", get_param(params, "person.postal_code", "N9A 1A1"))
            _fill(page, "date", "2026-09-01")  # effective date (future)

            # Currently insured = Yes (first radio); type = Automobile (default)
            page.get_by_role("radio").first.click()
            page.wait_for_timeout(200)

            page.get_by_role("button", name="Request a Quote").click()
            page.wait_for_timeout(3000)

            resp = page.locator('.wpcf7-response-output')
            if resp.count():
                result["response"] = resp.inner_text(timeout=3000).strip()
                if "sent successfully" in result["response"].lower():
                    result["submitted"] = True
                    result["result_note"] = "submitted successfully (CF7). Lead-gen: representative will contact you for the quote."

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
    ap.add_argument("--out", default="alllineinsurance_auto_quote_result.json")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = ap.parse_args()
    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    res = run(headless=headless, params=load_params(args.input))
    res["carrier"] = "alllineinsurance.ca"
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
