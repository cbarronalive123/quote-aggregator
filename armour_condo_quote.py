"""
armour_condo_quote.py
=====================
Playwright automation for Armour Insurance - Condo Quote form (Forminator).

Form URL : https://www.armour-insurance.com/condo-quote/
DB link  : form_scripts table in insurance_websites.db (form_url -> script_file)
Form kind: lead_gen  (Forminator form_id=599; submits via AJAX and returns
           "Thank you for contacting us, we will be in touch shortly." — NO
           dollar value is returned. The broker issues the rate by phone/email.)

Fills every field (one at a time, verified), submits, and watches the AJAX
response. Verifies submission by intercepting the admin-ajax POST to
forminator_submit_form_custom-forms and checking for success.

Usage
-----
Headed (watch it work, for verification) :
    python armour_condo_quote.py --headed
Headless (for batch/automated runs) :
    python armour_condo_quote.py --headless
Default : --headless
"""

import argparse
import json
import re
import sys

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORM_URL = "https://www.armour-insurance.com/condo-quote/"

# --- Forminator field values (loaded from the shared per-person params JSON).
# Custom dropdowns: [one,two] pairs: 'one' = Yes, 'two' = No.
DATA_MAP = {
    "address-1-street_address": "person.street_address",
    "address-1-city":           "person.city",
    "address-1-zip":            "person.postal_code",
    "number-1":                 "property_condo.age",            # age
    "number-2":                 "property_condo.square_feet",   # square feet (max 150!)
    "number-3":                 "property_condo.building_year", # building year (max 150 bug)
    "select-1":                 "property_condo.building_type", # FIXED select "Other"
    "checkbox-1[]":             "property_condo.heating",       # FIXED "two"=Electric
    "select-2":                 "property_condo.has_condo_policy",  # FIXED one=Yes
    "select-8":                 "property_condo.claims",        # FIXED one=No
    "select-3":                 "property_condo.years_lived",   # FIXED two=2
    "select-4":                 "property_condo.betterments_value",  # FIXED "$100,000"
    "select-9":                 "property_condo.contents_value",     # FIXED "$100,000"
    "textarea-1":               "property_condo.unique_features",
    "select-5":                 "property_condo.burglar_alarm", # FIXED one=Yes
    "select-6":                 "property_condo.non_smoker",    # FIXED one=Yes
    "select-10":                "property_condo.has_mortgage",  # FIXED one=Yes
    "select-7":                 "property_condo.retired",       # FIXED one=Yes
}

# A quoted dollar amount (to detect an actual quote result)
DOLLAR_RE = re.compile(r"\$\s?\d[\d,.\s]{2,}")


def _set_select(page, form, name, value):
    """Set a native select (scoped to the quote form) to `value` and sync the UI."""
    sel = form.locator(f'select[name="{name}"]')
    # try value first, then text
    try:
        sel.select_option(value=value, force=True)
    except Exception:
        sel.select_option(label=value, force=True)
    # dispatch change to sync the Forminator custom dropdown
    page.evaluate(
        """(name) => {
            const s = document.querySelector(`select[name="${name}"]`);
            s.dispatchEvent(new Event('change', {bubbles: true}));
        }""", name
    )


def fill_and_submit(headless: bool = True, params: dict | None = None) -> dict:
    result = {"filled": {}, "submitted": False, "quote_value": None, "result_note": None}
    submission_responses = []
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

        # Intercept Forminator's AJAX submit so we can read the success response.
        def on_response(resp):
            try:
                if "admin-ajax.php" in resp.url and resp.status == 200:
                    body = resp.text()
                    # Forminator submission responses contain "success" and the
                    # action/fields; nonce requests (forminator_get_nonce) don't.
                    if "success" in body and "forminator_get_nonce" not in body:
                        submission_responses.append(body)
            except Exception:
                pass
        page.on("response", on_response)

        try:
            page.goto(FORM_URL, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # The Forminator quote form is the one containing the address field.
            form = page.locator('form').filter(has=page.locator('input[name="address-1-street_address"]')).first

            # --- Text/number/textarea fields (force=True: Forminator wrapper
            #     can report fields "not visible" though they are interactive) ---
            for name in ["address-1-street_address", "address-1-city", "address-1-zip",
                         "number-1", "number-2", "number-3"]:
                # Forminator: set value directly and dispatch input/change so the
                # framework registers it (more reliable than Playwright fill here).
                page.evaluate(
                    """(arg) => {
                        const el = document.querySelector(`input[name="${arg.name}"]`);
                        el.value = arg.val;
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    }""", {"name": name, "val": DATA[name]}
                )
                result["filled"][name] = form.locator(f'input[name="{name}"]').evaluate(
                    "el => el.value")
                print(f"  filled {name} = {result['filled'][name]}", flush=True)

            # --- Custom selects (set native + dispatch change) ---
            for name in ["select-1", "select-2", "select-8", "select-3",
                         "select-4", "select-9", "select-5", "select-6",
                         "select-10", "select-7"]:
                _set_select(page, form, name, DATA[name])
                # read back the visible selection text (scoped to the quote form)
                vis = form.locator(f'select[name="{name}"]').evaluate(
                    "el => el.options[el.selectedIndex].text"
                )
                result["filled"][name] = vis
                print(f"  filled {name} = {vis}", flush=True)

            # --- Checkbox (heating = Electric). Forminator hides the real input;
            #     set it directly and dispatch change to sync the UI. ---
            page.evaluate("""() => {
                const el = document.querySelector('input[type="checkbox"][value="two"]');
                el.checked = true;
                el.dispatchEvent(new Event('change', {bubbles: true}));
            }""")
            result["filled"]["checkbox-1[]"] = "two"
            print("  checked checkbox-1[] = two (Electric)", flush=True)

            # --- Textarea ---
            page.evaluate(
                """(val) => {
                    const el = document.querySelector('textarea[name="textarea-1"]');
                    el.value = val;
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                }""", DATA["textarea-1"]
            )
            result["filled"]["textarea-1"] = form.locator(
                'textarea[name="textarea-1"]').evaluate("el => el.value")
            print("  filled textarea-1", flush=True)

            # --- Submit (Forminator renders the button outside the <form>) ---
            submit = page.locator(
                'button:has-text("Request Quote"), button.forminator-button-submit, '
                'input[type="submit"].forminator-button'
            ).first
            print("Submit found:", submit.count() > 0, flush=True)
            if submit.count() == 0:
                result["result_note"] = "no submit button found"
                return result
            # Forminator's submit button is in a wrapper reported "not visible";
            # trigger it with a native click via evaluate (same as a real click).
            submit.evaluate("el => el.click()")
            page.wait_for_timeout(500)

            # Forminator submits via AJAX; wait for either the AJAX success body
            # or the on-page response message element.
            page.wait_for_timeout(2000)
            for body in submission_responses:
                try:
                    data = json.loads(body)
                    if data.get("success"):
                        result["submitted"] = True
                        msg = (data.get("data", {}) or {}).get("message")
                        result["result_note"] = msg or "submitted (AJAX success)"
                        print("SUBMIT SUCCESS:", result["result_note"], flush=True)
                except Exception:
                    continue

            # Fallback: read the on-page Forminator success/error message element.
            if not result["submitted"]:
                resp_el = page.locator(
                    ".forminator-response-message, .forminator-response, "
                    ".forminator-form-response"
                ).first
                if resp_el.count():
                    resp_text = resp_el.inner_text(timeout=3000).strip()
                    if resp_text:
                        result["result_note"] = resp_text
                        print("PAGE RESPONSE:", resp_text, flush=True)
                        if "success" in resp_text.lower() or "thank" in resp_text.lower():
                            result["submitted"] = True

            # Check the visible page text for a dollar value, EXCLUDING the
            # form's own <select> / custom-dropdown labels (which contain $ figures
            # that are not real quotes). A real quote only counts if it appears in
            # visible page text AFTER a successful submission.
            text = page.evaluate("""() => {
                const clone = document.body.cloneNode(true);
                clone.querySelectorAll('select, option, script, style, .forminator-custom-select, .forminator-select2').forEach(e => e.remove());
                return clone.innerText;
            }""")
            m = DOLLAR_RE.search(text)
            if m:
                result["quote_value"] = m.group(0).strip()
                print("QUOTE VALUE FOUND:", result["quote_value"], flush=True)
            if not result["result_note"]:
                result["result_note"] = "no AJAX success captured (lead-gen or no response)"

        except PlaywrightTimeoutError as e:
            result["result_note"] = f"timeout: {e}"
            print("Timed out:", e, flush=True)
        finally:
            page.remove_listener("response", on_response)
            if not headless:
                page.wait_for_timeout(3000)
            browser.close()

    return result


def main():
    parser = argparse.ArgumentParser(description="Fill+submit Armour condo quote form.")
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--headless", action="store_true", default=False)
    g.add_argument("--headed", action="store_true", default=False)
    parser.add_argument("--input", default=None,
                        help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = parser.parse_args()

    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    params = load_params(args.input)
    result = fill_and_submit(headless=headless, params=params)

    print("\n=== RESULT ===")
    print("  submitted:", result["submitted"])
    print("  quote_value:", result["quote_value"])
    print("  note:", result.get("result_note"))
    print("  fields filled:", len(result["filled"]))


if __name__ == "__main__":
    main()
