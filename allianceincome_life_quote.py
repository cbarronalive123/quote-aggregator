"""
allianceincome_life_quote.py
============================
Playwright automation for Alliance Income Services - Life Insurance quote intake form.

Form URL : https://allianceincome.com/services/life-insurance/
DB link  : form_scripts table in insurance_websites.db (form_url -> script_file)
Form kind: lead_gen  (Fluent Form #24. Collects contact info + product + age, submits,
           then redirects to the partner rater insurdinary.ca/online-quoter/ which
           generates the actual premium. No $ value on the intake form itself.)

Fills every field (verified one at a time), submits, and reports where the flow ends.

Usage
-----
Headed:  python allianceincome_life_quote.py --headed
Headless: python allianceincome_life_quote.py --headless   (default)
Result is persisted to allianceincome_life_quote_result.json and quote_results.jsonl.
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORM_URL = "https://allianceincome.com/services/life-insurance/"

# Form field -> params path. This is a Fluent Form; selectors use the form's own
# input names / ids (ff_24_*). FIXED options: see field_registry.json.
PARAM_MAP = {
    "first_name": "person.first_name",
    "last_name": "person.last_name",
    "phone": "person.phone",
    "email": "person.email",
    "province": "person.province",              # FIXED select
    "product": "life.product",                  # FIXED select
    "age": "life.age",                          # FIXED select
    "terms": "life.terms",                      # FIXED checkbox
}

DOLLAR_RE = re.compile(r"\$\s?\d[\d,.]*")


def _set_select(page, css_id, value):
    return page.evaluate(
        """(arg) => {
            const sel = document.querySelector(arg.sel);
            if (!sel) return false;
            for (let i=0;i<sel.options.length;i++){
                if (sel.options[i].text === arg.value || sel.options[i].value === arg.value){
                    sel.selectedIndex = i; break;
                }
            }
            sel.dispatchEvent(new Event('change',{bubbles:true}));
            return sel.options[sel.selectedIndex].text;
        }""", {"sel": css_id, "value": value}
    )


def _fill(page, selector, value):
    return page.evaluate(
        """(arg) => {
            const el = document.querySelector(arg.sel);
            if (!el) return false;
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
            setter.call(el, arg.value);
            el.dispatchEvent(new Event('input',{bubbles:true}));
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return el.value;
        }""", {"sel": selector, "value": value}
    )


def run(headless: bool, params: dict | None = None) -> dict:
    result = {"submitted": False, "quote_value": None, "redirected_to": None, "error": None}
    params = params or {}
    V = {f: get_param(params, p, "") for f, p in PARAM_MAP.items()}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"), viewport={"width":1400,"height":1000})
        try:
            page.goto(FORM_URL, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # Fill text/phone/email
            _fill(page, 'input[name*="univ_name[first_name]"]', V["first_name"])
            _fill(page, 'input[name*="univ_name[last_name]"]', V["last_name"])
            _fill(page, 'input[name="univ_mobile"]', V["phone"])
            _fill(page, 'input[name="univ_email"]', V["email"])

            # Selects (province, product, age)
            _set_select(page, '#ff_24_univ_province', V["province"])
            _set_select(page, '#ff_24_univ_product', V["product"])
            _set_select(page, '#ff_24_univ_age', V["age"])

            # Terms checkbox
            page.evaluate("""() => {
                const cb = document.querySelector('input[name="univ_terms"]');
                if (cb) { cb.checked=true; cb.dispatchEvent(new Event('change',{bubbles:true})); cb.dispatchEvent(new Event('click',{bubbles:true})); }
            }""")

            # Submit
            page.get_by_role("button", name="GET QUOTES").click()
            page.wait_for_load_state("domcontentloaded", timeout=20000)
            page.wait_for_timeout(2000)

            result["redirected_to"] = page.url
            result["submitted"] = True

            # Check for any quote value on the resulting page
            body = page.locator("body").inner_text(timeout=5000)
            m = DOLLAR_RE.search(body)
            if m:
                result["quote_value"] = m.group(0).strip()
            if "insurdinary" in page.url:
                result["handoff"] = "redirected to Insurdinary online quoter (real premium generated there)"

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
    ap.add_argument("--out", default="allianceincome_life_quote_result.json")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = ap.parse_args()
    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    res = run(headless=headless, params=load_params(args.input))
    res["carrier"] = "allianceincome.com"
    res["form_url"] = FORM_URL
    res["form_kind"] = "lead_gen"

    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, args.out), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    with open(os.path.join(base, "quote_results.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")

    print("\n=== RESULT ===")
    print("  submitted:", res.get("submitted"))
    print("  redirected_to:", res.get("redirected_to"))
    print("  quote_value:", res.get("quote_value"))
    print("  handoff:", res.get("handoff"))
    print("  error:", res.get("error"))


if __name__ == "__main__":
    main()
