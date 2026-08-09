"""
aldormaninsurance_classic_car_quote.py
=======================================
Playwright automation for Al Dorman Insurance - Classic Car insurance quote request.

Form URL : https://www.aldormaninsurance.com/copy-of-boat-insurance-quote  (Classic Car Quote)
Submit   : Webflow form (posts AJAX; on success the form fields are cleared).
DB link  : form_scripts table in insurance_websites.db
Form kind: lead_gen  (collects classic car quote details incl. vehicle value + VIN;
           forwards to the broker. NO $ premium is computed on-page.)

Fields (verified one at a time; Webflow names):
  full-name, phone, drivers-license number, value-of vehicle,
  home-address & storage address, email, year/make/model, vin. Submit button "Send".

Usage
-----
Headed:  python aldormaninsurance_classic_car_quote.py --headed
Headless: python aldormaninsurance_classic_car_quote.py --headless   (default)
Result persisted to aldormaninsurance_classic_car_quote_result.json + quote_results.jsonl.
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORM_URL = "https://www.aldormaninsurance.com/copy-of-boat-insurance-quote"

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
    result = {"submitted": False, "quote_value": None, "success_banner": None, "error": None}
    params = params or {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"), viewport={"width":1400,"height":1000})
        try:
            page.goto(FORM_URL, wait_until="domcontentloaded", timeout=40000)
            # don't wait for networkidle (Webflow/analytics keep it busy)
            page.wait_for_timeout(2000)

            _fill(page, "full-name", get_param(params, "person.first_name", "John") + " " + get_param(params, "person.last_name", "Doe"))
            _fill(page, "phone", get_param(params, "person.phone", "9057351234"))
            _fill(page, "drivers-license number", "D1234-56789-00000")
            _fill(page, "value-of vehicle", "50000")
            _fill(page, "home-address & storage address", "1003 Niagara St")
            _fill(page, "email", get_param(params, "person.email", ""))
            _fill(page, "year/make/model", "1970 Chevrolet Camaro")
            _fill(page, "vin", "1G1FT22R9L124563")

            # Submit (Send button)
            page.evaluate("""() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Send');
                if (btn) btn.click();
            }""")
            page.wait_for_timeout(3000)

            # Webflow success: form fields are cleared after submit, or a success banner shows
            firstName = page.evaluate("() => document.querySelector('input[name=\"full-name\"]')?.value || ''")
            done = page.evaluate("() => document.querySelector('.w-form-done, .w-form-success')?.innerText || ''")
            if not firstName or done:
                result["submitted"] = True
                result["success_banner"] = done.strip()
                result["result_note"] = "submitted successfully (Webflow form cleared). Lead-gen: broker will contact for the quote."

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
    ap.add_argument("--out", default="aldormaninsurance_classic_car_quote_result.json")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = ap.parse_args()
    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    res = run(headless=headless, params=load_params(args.input))
    res["carrier"] = "aldormaninsurance.com"
    res["form_url"] = FORM_URL
    res["form_kind"] = "lead_gen"

    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, args.out), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    with open(os.path.join(base, "quote_results.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")

    print("\n=== RESULT ===")
    print("  submitted:", res.get("submitted"))
    print("  success_banner:", res.get("success_banner"))
    print("  quote_value:", res.get("quote_value"))
    print("  note:", res.get("result_note"))
    print("  error:", res.get("error"))


if __name__ == "__main__":
    main()
