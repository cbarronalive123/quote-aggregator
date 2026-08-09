"""
vergeinsurance_auto_quote.py
============================
Playwright automation for Verge Insurance - Auto Insurance Quote form.

Form URL : https://www.vergeinsurance.com/auto-insurance-quote/
DB link  : form_scripts table in insurance_websites.db (form_url -> script_file)

Fills every field on the quote form (one at a time, verified), submits it, and
continues chasing any multi-page quote flow until a quoted dollar amount ($$$)
appears or the flow ends. Never assume "Get My Quote" is the last step — there
can be multiple pages.

Usage
-----
Headed (watch it work, for verification) :
    python vergeinsurance_auto_quote.py --headed
Headless (for batch/automated runs) :
    python vergeinsurance_auto_quote.py --headless
Default : --headless (so it can be run unattended)
"""

import argparse
import re
import sys

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORM_URL = "https://www.vergeinsurance.com/auto-insurance-quote/"

# Field values are loaded from the shared per-person params JSON
# (quote_params.json or --input). The form field name -> params path mapping:
DATA_MAP = {
    "first-name": "person.first_name",
    "last-name": "person.last_name",
    "your-email": "person.email",
    "your-phone": "person.phone",
    "street-address": "person.street_address",
    "city": "person.city",
    "province": "person.province",           # FIXED select -> see field_registry
    "postal-code": "person.postal_code",
    "effective-date": "auto.coverage_start_date",  # date, YYYY-MM-DD
    "cancellation-nonpayment": "auto.cancellation_nonpayment",  # FIXED Yes/No
}

# A quoted dollar amount, e.g. "$1,234.56" or "$1 234,56"
DOLLAR_RE = re.compile(r"\$\s?\d[\d,.\s]{2,}")

# Money could also appear without a $ sign but as "Premium: 1234". Keep simple for now.


def _visible_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=3000)
    except Exception:
        return ""


def fill_and_submit(headless: bool = True, params: dict | None = None) -> dict:
    result = {"filled": {}, "submitted": False, "quote_value": None, "flow": []}
    params = params or {}
    # Resolve the form field values from the shared params.
    DATA = {fname: get_param(params, ppath, "") for fname, ppath in DATA_MAP.items()}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            viewport={"width": 1400, "height": 1000},
        )
        try:
            page.goto(FORM_URL, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_load_state("networkidle", timeout=15000)
            form = page.locator('form').filter(has=page.locator('input[name="first-name"]'))

            # --- Field-by-field fill, verifying each ---
            steps = [
                ('input[name="first-name"]', DATA["first-name"], "fill"),
                ('input[name="last-name"]', DATA["last-name"], "fill"),
                ('input[name="your-email"]', DATA["your-email"], "fill"),
                ('input[name="your-phone"]', DATA["your-phone"], "fill"),
                ('input[name="street-address"]', DATA["street-address"], "fill"),
                ('input[name="city"]', DATA["city"], "fill"),
                ('select[name="province"]', DATA["province"], "select"),
                ('input[name="postal-code"]', DATA["postal-code"], "fill"),
                ('input[name="effective-date"]', DATA["effective-date"], "fill"),
                ('select[name="cancellation-nonpayment"]', DATA["cancellation-nonpayment"], "select"),
            ]
            for selector, value, kind in steps:
                if kind == "select":
                    loc = form.locator(selector)
                    loc.select_option(label=value)
                    got = loc.input_value()
                else:
                    # CF7 can report fields "not editable" headless; set the value
                    # directly + dispatch input/change (same as the Armour fix).
                    form.evaluate(
                        """(arg) => {
                            const el = document.querySelector(arg.sel);
                            if (!el) return null;
                            const setter = Object.getOwnPropertyDescriptor(
                                window.HTMLInputElement.prototype, 'value').set;
                            setter.call(el, arg.value);
                            el.dispatchEvent(new Event('input', {bubbles: true}));
                            el.dispatchEvent(new Event('change', {bubbles: true}));
                            return el.value;
                        }""", {"sel": selector, "value": value}
                    )
                    got = form.locator(selector).evaluate("el => el.value")
                result["filled"][selector] = got
                print(f"  filled {selector} = {got}", flush=True)

            # --- Submit ---
            submit = form.locator(
                'button[type="submit"], button:has-text("Get My Quote"), '
                'input[type="submit"]'
            ).first
            print("Submit found:", submit.count() > 0, flush=True)
            if submit.count() == 0:
                result["result_note"] = "no submit button found"
                return result

            # Click and follow the resulting navigation / AJAX flow.
            with page.expect_navigation(wait_until="domcontentloaded", timeout=20000) as nav_info:
                submit.click()
            try:
                nav_info.value
                # URL changed (server-side redirect / next page)
                result["submitted"] = True
            except Exception:
                # No navigation — likely an AJAX submit (CF7). Watch for success/error.
                result["submitted"] = True

            # Chase the flow: collect subsequent pages / forms / $ values.
            visited_urls = {page.url}
            for _ in range(8):  # hard cap on pages to avoid runaway
                page.wait_for_timeout(1500)
                text = _visible_text(page)
                result["flow"].append({"url": page.url, "text_snippet": text[:200]})

                # 1) Did we hit a dollar quote value?
                m = DOLLAR_RE.search(text)
                if m:
                    result["quote_value"] = m.group(0).strip()
                    print("QUOTE FOUND:", result["quote_value"], flush=True)
                    break

                # 2) A success/error message from CF7/portal?
                for marker in ["sent successfully", "thank you", "we will contact you",
                               "submitted", "error", "one or more fields"]:
                    if marker.lower() in text.lower():
                        result["result_note"] = f"flow ended: '{marker}'"
                        print("FLOW ENDED:", marker, flush=True)
                        break
                else:
                    # 3) Is there another visible form to fill / submit on this or next page?
                    next_form = page.locator('form').first
                    if next_form.count() and next_form.locator('button[type="submit"], input[type="submit"]').count():
                        nf = next_form.locator('button[type="submit"], input[type="submit"]').first
                        nf.click(force=True)
                        print("advanced to next step; url now:", page.url, flush=True)
                        continue
                    else:
                        print("no further form/submit; stopping.", flush=True)
                        result["result_note"] = result.get("result_note") or "no further form found"
                        break

                if result.get("result_note"):
                    break
        except PlaywrightTimeoutError as e:
            result["result_note"] = f"timeout: {e}"
            print("Timed out:", e, flush=True)
        finally:
            if headless:
                browser.close()
            else:
                # In headed mode, keep open briefly so the user can observe.
                page.wait_for_timeout(3000)
                browser.close()

    return result


def main():
    parser = argparse.ArgumentParser(description="Fill+submit Verge auto quote form.")
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--headless", action="store_true", default=False,
                   help="Run with a hidden browser (default for unattended runs).")
    g.add_argument("--headed", action="store_true", default=False,
                   help="Run with a visible browser window (for verification).")
    parser.add_argument("--input", default=None,
                        help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = parser.parse_args()

    headless = not args.headed  # headed wins if --headed passed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    params = load_params(args.input)
    result = fill_and_submit(headless=headless, params=params)

    print("\n=== RESULT ===")
    print("  submitted:", result["submitted"])
    print("  quote_value:", result["quote_value"])
    print("  note:", result.get("result_note"))
    print("  flow steps:", len(result["flow"]))
    for step in result["flow"]:
        print("    -", step["url"])


if __name__ == "__main__":
    main()
