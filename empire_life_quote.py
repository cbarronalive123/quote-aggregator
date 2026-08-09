"""
empire_life_quote.py
====================
Playwright automation for Empire Life - Online Simplified Term Life quote.

Form URL : https://www.empire.ca/insurance/buy-life-insurance/quote-buy
DB link  : form_scripts table in insurance_websites.db
Form kind: QUOTE  -- a live rater that returns a real premium (e.g. $17.33/month)
           as the user fills province, DOB, sex, smoker, product, coverage.

The "Your Quote" value updates live. Verified via Playwright MCP:
  Province -> DOB (day/month/year) -> Sex (M/F) -> Smoker (N/S) -> Product
  (Simplified 10 / 20 Term) -> Existing coverage (No) -> Coverage amount ($250,000)
  -> Payment method (Per Month / Annually). Quote shown next to "Your Quote".

Usage
-----
Headed:  python empire_life_quote.py --headed
Headless: python empire_life_quote.py --headless   (default)
Result persisted to empire_life_quote_result.json + quote_results.jsonl.
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORM_URL = "https://www.empire.ca/insurance/buy-life-insurance/quote-buy"

# Form field -> params path. FIXED options: see field_registry.json.
PARAM_MAP = {
    "province":        "person.province",
    "gender":          "person.sex",          # M / F
    "smoker":          "life.tobacco_use",    # N / S
    "product":         "life.product",        # Simplified 10 / 20
    "existing":        "life.existing_coverage",  # Yes / No
    "coverage_amount": "life.coverage_amount",    # $250,000
    "payment_method":  "life.payment_method",     # Monthly / Annually
}

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
            el.blur();
            return el.value;
        }""", {"name": name, "value": value}
    )


def _click_radio(page, name, value):
    return page.evaluate(
        """(arg) => {
            const r = Array.from(document.querySelectorAll('input[type="radio"]'))
                .find(x => x.name===arg.name && x.value===arg.value);
            if (r) { r.click(); r.dispatchEvent(new Event('change',{bubbles:true})); return true; }
            return false;
        }""", {"name": name, "value": value}
    )


def _click_by_text(page, text):
    page.get_by_text(text, exact=True).first.click()
    page.wait_for_timeout(400)


def run(headless: bool, params: dict | None = None) -> dict:
    result = {"quote_value": None, "quote_valid_for": None, "error": None}
    params = params or {}
    V = {f: get_param(params, p, "") for f, p in PARAM_MAP.items()}
    gender = "M" if V["gender"].upper() in ("M", "MALE", "HOMME") else "F"
    smoker = "N" if V["smoker"].lower() in ("n", "no", "non-smoker", "none, ever", "non") else "S"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"), viewport={"width":1400,"height":1000})
        try:
            page.goto(FORM_URL, wait_until="domcontentloaded", timeout=40000)
            # NOTE: do NOT wait for networkidle — the reCAPTCHA iframe keeps
            # network busy so 'networkidle' never fires. domcontentloaded is enough.
            page.wait_for_timeout(2000)

            # 1) Province
            page.get_by_label("Select Current Province/").select_option(label=V["province"])
            page.wait_for_timeout(500)

            # 2) DOB (day/month/year) from params date_of_birth YYYY/MM/DD
            dob = get_param(params, "person.date_of_birth", "1990/03/15")
            try:
                y, m, d = dob.split("/")
                _fill(page, "day", str(int(d)))
                _fill(page, "month", str(int(m)))
                _fill(page, "year", str(int(y)))
            except Exception:
                pass

            # 3) Sex + Smoker (radios)
            _click_by_text(page, "Male" if gender == "M" else "Female")
            _click_by_text(page, "Non-smoker" if smoker == "N" else "Smoker")

            # 4) Product (Simplified 10 -> T10 / Simplified 20 -> T20) via radio
            product_val = "T10" if "10" in V["product"] else "T20"
            _click_radio(page, "product", product_val)
            page.wait_for_timeout(400)

            # 5) Existing coverage = No (radio value False)
            _click_radio(page, "existing_si", "False")
            page.wait_for_timeout(400)

            # 6) Coverage amount (already default $250,000)
            _fill(page, "coverage_amount", V["coverage_amount"])

            # 7) Payment method (Per Month default; optional Annually)
            if str(V["payment_method"]).lower().startswith("annual"):
                _click_radio(page, "payment_method", "Annually")
                page.wait_for_timeout(300)

            page.wait_for_timeout(800)

            # Capture the "Your Quote" value
            body = page.locator("body").inner_text(timeout=5000)
            m = re.search(r"Your Quote[^\n]*\n(\$\d[\d,.]*)", body)
            if m:
                result["quote_value"] = m.group(1).strip()
            # fallback: any dollar after "Your Quote"
            if not result["quote_value"]:
                idx = body.find("Your Quote")
                seg = body[idx:idx+120]
                dm = DOLLAR_RE.search(seg)
                if dm:
                    result["quote_value"] = dm.group(0).strip()
            if "valid for 48 hours" in body.lower():
                result["quote_valid_for"] = "48 hours"
            result["details"] = {
                "product": V["product"],
                "coverage": V["coverage_amount"],
                "gender": "Male" if gender == "M" else "Female",
                "smoker": "Non-smoker" if smoker == "N" else "Smoker",
                "payment": V["payment_method"],
            }

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
    ap.add_argument("--out", default="empire_life_quote_result.json")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = ap.parse_args()
    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    res = run(headless=headless, params=load_params(args.input))
    res["carrier"] = "empire.ca"
    res["form_url"] = FORM_URL
    res["form_kind"] = "quote"

    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, args.out), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    with open(os.path.join(base, "quote_results.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")

    print("\n=== RESULT ===")
    print("  quote_value:", res.get("quote_value"))
    print("  valid_for:", res.get("quote_valid_for"))
    print("  details:", res.get("details"))
    print("  error:", res.get("error"))


if __name__ == "__main__":
    main()
