"""
canadainsuranceplan_life_quote.py
=================================
Playwright automation for Canada Insurance Plan - Life insurance quote request.

Form URL : https://canadainsuranceplan.ca/  (homepage "Start your custom quote" form)
DB link  : form_scripts table in insurance_websites.db
Form kind: lead_gen  (collects name/email/mobile/DOB/gender/smoker/province/quote_for,
           submits, and shows a "Quote Submitted!" dialog: "We will contact you
           shortly." No $ premium is computed on-page.)

Fields (verified one at a time):
  name, email (#email), mobile (#mobile), dob month (#dob_month) / day / year,
  gender (Male/Female label), smoker (Smoker/Non-smoker label), province (#province),
  quote_for (#quote_for select), Get a quote button.

Note: the gender/smoker choices are label toggles (click by text). Submission shows
a success dialog with an "OK" button.

Usage
-----
Headed:  python canadainsuranceplan_life_quote.py --headed
Headless: python canadainsuranceplan_life_quote.py --headless   (default)
Result persisted to canadainsuranceplan_life_quote_result.json + quote_results.jsonl.
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORM_URL = "https://canadainsuranceplan.ca/"

DOLLAR_RE = re.compile(r"\$\s?\d[\d,.]*")


def _fill(page, sel, value, by_id=True):
    return page.evaluate(
        """(arg) => {
            let el = null;
            if (arg.byId) el = document.getElementById(arg.sel);
            else el = Array.from(document.querySelectorAll('input')).find(i=>i.name===arg.sel || i.getAttribute('aria-label')===arg.sel);
            if (!el) return false;
            const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
            s.call(el, arg.value);
            el.dispatchEvent(new Event('input',{bubbles:true}));
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return el.value;
        }""", {"sel": sel, "value": value, "byId": by_id}
    )


def _select(page, sel, value):
    return page.evaluate(
        """(arg) => {
            const el = document.getElementById(arg.sel);
            if (!el) return false;
            for (let i=0;i<el.options.length;i++){
                if (el.options[i].text === arg.value || el.options[i].value === arg.value){ el.selectedIndex=i; break; }
            }
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return el.options[el.selectedIndex].text;
        }""", {"sel": sel, "value": value}
    )


def run(headless: bool, params: dict | None = None) -> dict:
    result = {"submitted": False, "quote_value": None, "submission_dialog": None, "error": None}
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
            _fill(page, "name", get_param(params, "person.first_name", "John") + " " + get_param(params, "person.last_name", "Doe"), by_id=False)
            _fill(page, "email", get_param(params, "person.email", ""))
            _fill(page, "mobile", get_param(params, "person.phone", "9056889170"))

            # DOB
            dob = get_param(params, "person.date_of_birth", "1990/03/15")
            try:
                y, m, d = dob.split("/")
                months = ["January","February","March","April","May","June","July",
                          "August","September","October","November","December"]
                _select(page, "dob_month", months[int(m)-1])
                _fill(page, "dob_day", str(int(d)))
                _fill(page, "dob_year", str(int(y)))
            except Exception:
                pass

            # Gender = Male, Smoker = Non-smoker (label toggles)
            page.locator('label').filter(has_text="Male").first.click()
            page.locator('label').filter(has_text="Non-smoker").click()

            # Province + Quote For
            _select(page, "province", get_param(params, "person.province", "Ontario"))
            _select(page, "quote_for", "Life Insurance")

            # Submit
            page.get_by_role("button", name="Get a quote").click()
            page.wait_for_timeout(2000)

            # Detect the success dialog
            dialog = page.locator('[role="dialog"], .modal, [class*="dialog"]').filter(has_text="Quote Submitted").first
            if dialog.count():
                result["submitted"] = True
                text = dialog.inner_text(timeout=3000)
                result["submission_dialog"] = text.strip()
                result["result_note"] = "success dialog: 'Quote Submitted!' - broker will contact."
                # dismiss
                ok = dialog.get_by_role("button", name="OK").first
                if ok.count():
                    ok.click()

            # No dollar value expected; check body anyway.
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
    ap.add_argument("--out", default="canadainsuranceplan_life_quote_result.json")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = ap.parse_args()
    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    res = run(headless=headless, params=load_params(args.input))
    res["carrier"] = "canadainsuranceplan.ca"
    res["form_url"] = FORM_URL
    res["form_kind"] = "lead_gen"

    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, args.out), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    with open(os.path.join(base, "quote_results.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")

    print("\n=== RESULT ===")
    print("  submitted:", res.get("submitted"))
    print("  submission_dialog:", res.get("submission_dialog"))
    print("  quote_value:", res.get("quote_value"))
    print("  note:", res.get("result_note"))
    print("  error:", res.get("error"))


if __name__ == "__main__":
    main()
