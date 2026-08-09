"""
cheaplifeinsurance_life_quote.py
================================
Playwright automation for Cheap Life Insurance (cheaplifeinsurance.ca) - Life quote request.

Entry  : https://www.cheaplifeinsurance.ca/  -> "Quote Me!" / free-quote.html -> life-insurance-quote.html
Submit : form#quote POSTs to /cgi/quote.cgi
DB link: form_scripts table in insurance_websites.db
Form kind: lead_gen  (submits to CGI; thank-you page gives a reference number + advisor;
           the actual premium is EMAILED within 24h — no $ value shown on the page.)

Fields (verified one at a time via Playwright MCP):
  amount (#amount), term (#term), waiver_of_premium (radio), DOB (#month/#day/#year),
  gender (#gender), height (#height), weight (#weight), tobacco_use (#tobacco_use),
  resident/declined/currently_insured/taking_meds (checkbox),
  first_name, last_name, email, phone (area_code/phone_prefix/phone_suffix + evening *_2),
  postal_code, willing.

Usage
-----
Headed:  python cheaplifeinsurance_life_quote.py --headed
Headless: python cheaplifeinsurance_life_quote.py --headless   (default)
Result persisted to cheaplifeinsurance_life_quote_result.json + quote_results.jsonl.
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME_URL = "https://www.cheaplifeinsurance.ca/"
QUOTE_URL = "https://www.cheaplifeinsurance.ca/quote/life-insurance-quote.html?term"

# Form field -> params path. FIXED options: see field_registry.json.
PARAM_MAP = {
    "amount":           "life.amount",               # FIXED select ($500,000)
    "term":             "life.term",                 # FIXED select (10 Year)
    "waiver":           "life.waiver_of_premium",    # FIXED radio (Yes/No)
    "first_name":       "person.first_name",
    "last_name":        "person.last_name",
    "email":            "person.email",
    "area_code":        "person.phone_area",         # 3-digit area code
    "phone_prefix":     "person.phone_prefix",       # 3-digit exchange
    "phone_suffix":     "person.phone_suffix",       # 4-digit line
    "postal_code":      "person.postal_code",
}


def _fill(page, sel, value):
    return page.evaluate(
        """(arg) => {
            const el = document.querySelector(arg.sel);
            if (!el) return false;
            const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
            s.call(el, arg.value);
            el.dispatchEvent(new Event('input',{bubbles:true}));
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return el.value;
        }""", {"sel": sel, "value": value}
    )


def _select(page, sel, value):
    return page.evaluate(
        """(arg) => {
            const el = document.querySelector(arg.sel);
            if (!el) return false;
            for (let i=0;i<el.options.length;i++){
                if (el.options[i].value === arg.value || el.options[i].text === arg.value){ el.selectedIndex=i; break; }
            }
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return el.options[el.selectedIndex].text;
        }""", {"sel": sel, "value": value}
    )


def run(headless: bool, params: dict | None = None) -> dict:
    result = {"submitted": False, "reference": None, "quote_value": None, "error": None}
    params = params or {}
    V = {f: get_param(params, p, "") for f, p in PARAM_MAP.items()}
    # phone split
    phone = get_param(params, "person.phone", "9056889170")
    area = V["area_code"] or phone[:3]
    pref = V["phone_prefix"] or phone[3:6]
    suff = V["phone_suffix"] or phone[6:10]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"), viewport={"width":1400,"height":1000})
        try:
            page.goto(QUOTE_URL, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # Desired insurance
            _select(page, '#amount', V["amount"])
            _select(page, '#term', V["term"])
            # waiver radio Yes (default)

            # DOB (March 15, 1990 from params date_of_birth)
            dob = get_param(params, "person.date_of_birth", "1990/03/15")
            try:
                y, m, d = dob.split("/")
                months = ["January","February","March","April","May","June","July",
                          "August","September","October","November","December"]
                _select(page, '#month', months[int(m)-1])
                _select(page, '#day', str(int(d)))
            except Exception:
                pass
            _fill(page, '#year', y)

            # Vital stats
            _select(page, '#gender', "Male")
            _select(page, '#height', "5'10''")
            _fill(page, '#weight', "180")
            _select(page, '#tobacco_use', "None, Ever")

            # Checkboxes: for_self/resident/in_canada default checked; ensure
            # include_spouse/declined/currently_insured/taking_meds unchecked.

            # Contact
            _fill(page, '#first_name', V["first_name"])
            _fill(page, '#last_name', V["last_name"])
            _fill(page, '#email', V["email"])
            _fill(page, '#area_code', area)
            _fill(page, '#phone_prefix', pref)
            _fill(page, '#phone_suffix', suff)
            # evening phone (required) same number
            _fill(page, '#area_code2', area)
            _fill(page, '#phone_prefix2', pref)
            _fill(page, '#phone_suffix2', suff)
            _fill(page, '#postal_code', V["postal_code"])

            # Submit via native form submit (triggers validation + POST to CGI).
            # Wait for the actual navigation to the thank-you CGI page.
            try:
                with page.expect_navigation(wait_until="domcontentloaded", timeout=15000):
                    page.evaluate("() => { document.getElementById('quote').requestSubmit(); }")
            except Exception as e:
                result["submit_wait"] = f"no navigation: {e}"
            page.wait_for_timeout(2000)

            result["submitted"] = True
            # Strip select/option labels from the body text so the form's own
            # dollar-amount options (e.g. $50,000) aren't mistaken for a quote.
            body = page.evaluate("""() => {
                const clone = document.body.cloneNode(true);
                clone.querySelectorAll('select, option, script, style').forEach(e => e.remove());
                return clone.innerText;
            }""")
            # --- Capture ALL pertinent details from the result page ---
            m = re.search(r"reference number is ([\w-]+)", body, re.I)
            if m:
                result["reference"] = m.group(1)
            m = re.search(r"(?:your personal advisor|advisor) \(?licensed?[^)]*\)? is ([\w .'-]+)", body, re.I)
            if m:
                result["advisor"] = m.group(1).strip()
            m = re.search(r"([\w.+-]+@[\w.-]+\.\w+)", body)
            if m:
                result["advisor_email"] = m.group(1)
            m = re.search(r"(1[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4})", body)
            if m:
                result["advisor_phone"] = m.group(1)
            m = re.search(r"(Your request for[^\n]+)", body, re.I)
            if m:
                result["confirmation_message"] = m.group(1).strip()

            # Dollar quote value (if any is actually shown)
            dv = re.search(r"\$\s?\d[\d,.]*\s?(per month|/month|monthly)?", body)
            if dv:
                result["quote_value"] = dv.group(0).strip()
            if not result["quote_value"]:
                result["note"] = "no $ value shown; quote will be emailed. Reference: " + str(result.get("reference"))
            result["landed_url"] = page.url

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
    ap.add_argument("--out", default="cheaplifeinsurance_life_quote_result.json")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = ap.parse_args()
    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    res = run(headless=headless, params=load_params(args.input))
    res["carrier"] = "cheaplifeinsurance.ca"
    res["form_url"] = QUOTE_URL
    res["form_kind"] = "lead_gen"

    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, args.out), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    with open(os.path.join(base, "quote_results.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")

    print("\n=== RESULT ===")
    print("  submitted:", res.get("submitted"))
    print("  reference:", res.get("reference"))
    print("  advisor:", res.get("advisor"))
    print("  advisor_phone:", res.get("advisor_phone"))
    print("  advisor_email:", res.get("advisor_email"))
    print("  confirmation:", res.get("confirmation_message"))
    print("  quote_value:", res.get("quote_value"))
    print("  note:", res.get("note"))
    print("  landed_url:", res.get("landed_url"))
    print("  error:", res.get("error"))


if __name__ == "__main__":
    main()
