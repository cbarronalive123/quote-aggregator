"""
churchillinsurance_life_quote.py
================================
Playwright automation for Churchill Insurance Canada - Request a Quote (life).

Form URL : https://churchillinsurance.ca/Request-a-Quote.html
Submit   : form POSTs to /scripts/form-b968.php (returns {"success":true})
DB link  : form_scripts table in insurance_websites.db
Form kind: lead_gen  (collects name/email/sex/smoker/DOB/coverage/type/phone and
           emails the request to the broker; NO $ premium is computed on-page.)

Fields (verified one at a time):
  name, email, Sex (Male/Female), Non Smoker (Non Smoker/Smoker), DOB (YYYY-MM-DD),
  Coverage (amount), Coverage Type radio (Term/Universal/Whole/Critical Illness/
  Disability/Travel), phone.

Note: the "Submit" control is an <a href="#"> (nicepage template) that does NOT
submit the form on its own; use form.requestSubmit() to POST to form-b968.php.

Usage
-----
Headed:  python churchillinsurance_life_quote.py --headed
Headless: python churchillinsurance_life_quote.py --headless   (default)
Result persisted to churchillinsurance_life_quote_result.json + quote_results.jsonl.
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORM_URL = "https://churchillinsurance.ca/Request-a-Quote.html"

DOLLAR_RE = re.compile(r"\$\s?\d[\d,.]*")


def _fill(page, name_or_placeholder, value, by_name=True):
    return page.evaluate(
        """(arg) => {
            let el = null;
            if (arg.byName) el = document.querySelector(`input[name="${arg.sel}"]`);
            else el = Array.from(document.querySelectorAll('input')).find(i=>i.placeholder===arg.sel);
            if (!el) return false;
            const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
            s.call(el, arg.value);
            el.dispatchEvent(new Event('input',{bubbles:true}));
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return el.value;
        }""", {"sel": name_or_placeholder, "value": value, "byName": by_name}
    )


def run(headless: bool, params: dict | None = None) -> dict:
    result = {"submitted": False, "quote_value": None, "response": None, "error": None}
    params = params or {}
    responses = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"), viewport={"width":1400,"height":1000})

        def on_response(resp):
            try:
                if "form-b968.php" in resp.url and resp.status == 200:
                    responses.append(resp.text())
            except Exception:
                pass
        page.on("response", on_response)

        try:
            page.goto(FORM_URL, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(2000)

            # Name, email, DOB, coverage, phone
            _fill(page, "name", get_param(params, "person.first_name", "John") + " " + get_param(params, "person.last_name", "Doe"))
            _fill(page, "email", get_param(params, "person.email", ""))
            dob = get_param(params, "person.date_of_birth", "1990/03/15")
            dob_fmt = dob.replace("/", "-")  # YYYY-MM-DD
            _fill(page, "1965-01-16", dob_fmt, by_name=False)
            _fill(page, "Coverage", "500000")
            _fill(page, "phone", get_param(params, "person.phone", "9056889170"))

            # Coverage type radio = Term Life Insurance (first radio)
            page.get_by_role("radio").first.click()
            page.wait_for_timeout(300)

            # Submit via requestSubmit (the <a> Submit link does nothing)
            page.evaluate("() => { document.querySelector('form').requestSubmit(); }")
            page.wait_for_timeout(3000)

            result["submitted"] = True
            for body in responses:
                result["response"] = body
                if '"success":true' in body:
                    result["result_note"] = "submitted successfully (form-b968.php success:true). Lead-gen: broker will respond with a quote."
            if not result["response"]:
                result["result_note"] = "form POSTed (no response body captured). Lead-gen: broker will respond."

            # No dollar value on this lead-gen page; check anyway.
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
    ap.add_argument("--out", default="churchillinsurance_life_quote_result.json")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = ap.parse_args()
    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    res = run(headless=headless, params=load_params(args.input))
    res["carrier"] = "churchillinsurance.ca"
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
