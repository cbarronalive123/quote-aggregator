"""
aviva_auto_quote_headless.py
============================
Unattended Aviva Direct auto quote runner (batch / CI / no manual browser watch).

Mirrors the verified flow in aviva_auto_quote.py (which was validated end-to-end
in a headed browser and captures a real price like "$222.60 / Month"). It runs
unattended and never keeps the browser open.

The flow, helpers, modal handling and the quote-capture routine are identical to
the headed script so behaviour matches exactly.

Why minimized-headed by default instead of true headless?
  Aviva's Akamai gate returns "Access Denied" for true headless Chrome, the same
  as Bel Air. Launching real Chrome minimized off-screen keeps the working
  fingerprint and returns a real premium unattended.

Run:
  python aviva_auto_quote_headless.py
  python aviva_auto_quote_headless.py --input people/fake_jordan.json
  python aviva_auto_quote_headless.py --visible            # show browser (debug)
  python aviva_auto_quote_headless.py --true-headless      # experimental, usually blocked
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

from params_loader import get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

QUOTE_URL = "https://myaviva.avivainsurance.ca/avivaquoter/bol/auto"
POSTAL = "L2R 1A1"

# "Yes, that's correct" uses a curly apostrophe (U+2019) on the page.
YES_CORRECT = "Yes, that\u2019s correct"

# Stealth: mask the Playwright automation fingerprint (webdriver flag, languages)
# that Aviva's bot gate would otherwise score. Use the browser's REAL user-agent
# (no override) with a persistent profile so the vehicle-lookup API accepts us.
STEALTH_INIT = r"""
Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => undefined, configurable: true });
Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true });
Object.defineProperty(Navigator.prototype, 'languages', { get: () => ['en-US','en'], configurable: true });
if (navigator.plugins) {
    Object.defineProperty(Navigator.prototype, 'plugins', { get: () => [1,2,3,4,5], configurable: true });
}
Object.defineProperty(window, 'chrome', { get: () => ({ runtime: {} }), configurable: true });
"""

_START = time.time()


def _stamp() -> str:
    """Return a wall-clock timestamp plus seconds-since-start for a log line."""
    return (datetime.now().strftime("%H:%M:%S")
            + f" (+{time.time() - _START:5.1f}s)")


def log(msg: str):
    print(f"[{_stamp()}] {msg}", flush=True)


# --------------------------------------------------------------------------
# Helpers -- identical to aviva_auto_quote.py so the headless run matches the
# verified headed run exactly.
# --------------------------------------------------------------------------
def _type(page, selector, text):
    """Clear then type into a (possibly masked) text field via the keyboard."""
    loc = page.locator(selector).first
    loc.wait_for(state="attached", timeout=15000)
    log(f"    type {selector} <- {text!r}")
    loc.fill("")
    loc.press_sequentially(str(text), delay=25)
    page.wait_for_timeout(120)


def _select(page, selector, value):
    """Select an option in a native <select> by value."""
    log(f"    select {selector} = {value!r}")
    page.locator(selector).first.select_option(value)
    page.wait_for_timeout(150)


def _select_label(page, selector, label):
    """Select an option in a native <select> by its visible label."""
    log(f"    select {selector} = {label!r} (by label)")
    page.locator(selector).first.select_option(label=label)
    page.wait_for_timeout(150)


def _radio(page, testid):
    """Activate a radio button with the keyboard (focus + Space).

    Aviva's radios are native <input type=radio> that are visually hidden and
    tabindex=-1. A focused radio selects on Space (native behaviour), which fires
    the change event the form listens to.
    """
    loc = page.get_by_test_id(testid).first
    loc.wait_for(state="attached", timeout=15000)
    log(f"    radio {testid}")
    loc.focus()
    page.keyboard.press("Space")
    page.wait_for_timeout(150)


def _checkbox(page, selector):
    """Toggle a checkbox with the keyboard (focus + Space)."""
    loc = page.locator(selector).first
    loc.wait_for(state="attached", timeout=15000)
    log(f"    checkbox {selector}")
    loc.focus()
    page.keyboard.press("Space")
    page.wait_for_timeout(150)


def _button(page, name, exact=False, scope=None):
    """Click a button by its accessible name using a real pointer click.

    Waits for the button to become ENABLED (Aviva disables Continue until the
    form is valid), then clicks it -- exactly what the verified MCP flow does.
    """
    if scope is not None:
        loc = scope.get_by_role("button", name=name, exact=exact).first
    else:
        loc = page.get_by_role("button", name=name, exact=exact).first
    loc.wait_for(state="visible", timeout=20000)
    log(f"    button {name!r}")
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            if loc.is_enabled():
                break
        except Exception:
            break
        page.wait_for_timeout(250)
    loc.click()
    page.wait_for_timeout(1500)


def _dismiss_error_modal(page, keep_open: bool = False) -> bool:
    """Close the 'Sorry, something went wrong' modal if present.

    Aviva can pop an error modal ("We couldn't process your request") -- usually
    with a Close/X button -- right around quote generation. If we don't dismiss it
    the page is blocked and no price is visible.
    """
    for _ in range(3):
        try:
            has_err = page.evaluate(
                "() => /something went wrong|couldn'?t process your request|"
                "try again later|please try again/i.test(document.body.innerText || '')"
            )
        except Exception:
            return False
        if not has_err:
            return False
        if keep_open:
            log(">>> ERROR MODAL PRESENT. Browser kept open for inspection.")
            log(">>> Press Enter here to have the script try to continue...")
            try:
                input()
            except Exception:
                pass
            try:
                if not page.evaluate(
                    "() => /something went wrong|couldn'?t process your request|"
                    "try again later|please try again/i.test(document.body.innerText || '')"
                ):
                    return False
            except Exception:
                pass
            continue
        clicked = False
        try:
            # Strategy 0 (targeted, real pointer click): Aviva's error modal close
            # control is <span role="button" class="close" aria-label="...MVR.close">Close X</span>.
            close_loc = page.locator(
                '[role="button"].close, [class~="close"][role="button"], '
                '[aria-label*="MVR.close"]'
            ).first
            close_loc.wait_for(state="attached", timeout=4000)
            close_loc.click(force=True)
            clicked = True
        except Exception:
            pass
        if not clicked:
            try:
                # Strategy 1: any element whose aria-label/title/text mentions close.
                clicked = page.evaluate(
                    "() => {"
                    " const els = Array.from(document.querySelectorAll('button, a, [role=button], [aria-label]'));"
                    " const b = els.find(x => /close|dismiss/i.test("
                    "  ((x.getAttribute('aria-label') || '') + ' ' + (x.getAttribute('title') || '')"
                    "  + ' ' + (x.textContent || '')).trim()));"
                    " if (!b) return false; b.click(); return true; }"
                )
            except Exception:
                pass
        if not clicked:
            try:
                # Strategy 2: an 'X' / '×' icon button (common close control).
                clicked = page.evaluate(
                    "() => { const els = Array.from(document.querySelectorAll('button, a'));"
                    " const b = els.find(x => /^\\s*[×X]\\s*$/.test(x.textContent || ''));"
                    " if (b) { b.click(); return true; } return false; }"
                )
            except Exception:
                pass
        if not clicked:
            try:
                page.get_by_role("button", name="Close", exact=False).first.click(force=True)
                clicked = True
            except Exception:
                pass
        if not clicked:
            try:
                btns = page.evaluate(
                    "() => Array.from(document.querySelectorAll('button')).map(b =>"
                    " ({t:(b.textContent||'').trim(), a:b.getAttribute('aria-label'), c:b.className})"
                    " ).slice(0, 20)"
                )
                log("    error modal buttons: " + str(btns))
            except Exception:
                pass
        log("    dismissed error modal" if clicked else "    error modal present (no close btn)")
        page.wait_for_timeout(1500)
        if clicked:
            return True
    return False


def _read_offer(page, result: dict, keep_open: bool = False):
    """Reveal the Optional coverage tab and capture the premium + quote number."""
    page.wait_for_timeout(4000)
    _dismiss_error_modal(page, keep_open=keep_open)
    try:
        tab = page.get_by_text("Optional coverage", exact=True).first
        tab.wait_for(state="visible", timeout=10000)
        log("    tab 'Optional coverage'")
        tab.click(force=True)
        page.wait_for_timeout(3000)
    except Exception:
        log("WARN: optional-coverage tab not found; parsing current body")

    body = ""
    for _ in range(25):
        try:
            _dismiss_error_modal(page, keep_open=keep_open)
        except Exception:
            pass
        body = page.locator("body").inner_text(timeout=8000)
        if re.search(r"\$\s?\d[\d,]*\.\d{2}\s*/\s*(Month|Year)", body) or \
           re.search(r"\$\s?\d[\d,]*\.\d{2}", body):
            break
        page.wait_for_timeout(1500)

    if not re.search(r"\$\s?\d[\d,]*\.\d{2}", body):
        log("WARN: no price found on customization page; body follows:")
        log(body[:1500])

    m = re.search(r"\$\s?(\d[\d,]*\.\d{2})\s*/\s*(Month|Year)", body)
    if m:
        result["quote_value"] = "$" + m.group(1) + " / " + m.group(2)
        result["quote_monthly"] = "$" + m.group(1) + " / month"
    else:
        m2 = re.search(r"\$\s?(\d[\d,]*\.\d{2})", body)
        if m2:
            result["quote_value"] = "$" + m2.group(1)
            result["quote_monthly"] = "$" + m2.group(1) + " / month"
    qn = re.search(r"Q\s?([\d ]{6,})", body)
    if qn:
        result["quote_number"] = "Q " + re.sub(r"\s+", "", qn.group(1))
    log(f"    captured quote_value={result.get('quote_value')!r} "
        f"quote_number={result.get('quote_number')!r}")


# --------------------------------------------------------------------------
# Flow -- identical to aviva_auto_quote.py
# --------------------------------------------------------------------------
def fill_quote(page, V: dict, result: dict, out_dir: str = "evidence",
               keep_open: bool = False):
    log("STEP entry (postal code)")
    page.goto(QUOTE_URL, wait_until="domcontentloaded", timeout=60000)
    dialog = page.get_by_role("dialog")
    dialog.wait_for(state="visible", timeout=30000)
    dialog.locator('input[data-testid="postalcode"]').wait_for(state="visible", timeout=30000)
    _type(page, 'input[data-testid="postalcode"]', V["postal"])
    _button(page, "Continue", scope=dialog)

    log("STEP vehicle")
    _select(page, 'select[data-testid="vehicleYear"]', V["vehicle_year"])
    _select(page, 'select[data-testid="vehicleMake"]', V["vehicle_make"])
    _select(page, 'select[data-testid="vehicleModel"]', V["vehicle_model"])
    _select_label(page, 'select[data-testid="purchaseDate_month"]', V["purchase_month"])
    _select(page, 'select[data-testid="purchaseDate_year"]', V["purchase_year"])
    _radio(page, "purchaseCondition-new_AC")
    _radio(page, "winterTires-yes")
    _radio(page, "hasAntiTheftDevice-no")
    _button(page, "Continue")

    log("STEP car use")
    _type(page, 'input[name="annualMileage"]', V["annual_km"])
    _select(page, 'select[data-testid="commutePerWeek"]', V["commute_days"])
    _type(page, 'input[name="commutingMiles"]', V["commute_oneway_km"])
    _type(page, 'input[placeholder="MM/DD/YYYY"]', V["coverage_start_date"])
    _button(page, "Continue")

    log("STEP driver")
    _type(page, '[data-testid="driverFirstName"]', V["first_name"])
    _type(page, '[data-testid="driverLastName"]', V["last_name"])
    _type(page, '[data-testid="dateOfBirth-month"]', V["dob_month"])
    _type(page, '[data-testid="dateOfBirth-day"]', V["dob_day"])
    _type(page, '[data-testid="dateOfBirth-year"]', V["dob_year"])
    _radio(page, "gender-M" if str(V["sex"]).upper() == "M"
            else ("gender-F" if str(V["sex"]).upper() == "F" else "gender-X"))
    _select(page, 'select[data-testid="driverMaritalStatus"]', V["marital_status"])
    _radio(page, "combinedPolicyDiscount-NO")
    _radio(page, "telusHealth-no")
    _radio(page, "hadPriorInsurance-greatthan3years")
    _button(page, "Continue")

    log("STEP licence")
    _radio(page, "licenseClass-G")
    _select_label(page, 'select[data-testid="firstLicenceDate_month"]', V["lic_month"])
    _select(page, 'select[data-testid="firstLicenceDate_year"]', V["lic_year"])
    _button(page, "Continue")

    log("STEP licence history")
    _select_label(page, 'select[data-testid="graduateLicenseDate_month"]', V["g2_month"])
    _select(page, 'select[data-testid="graduateLicenseDate_year"]', V["g2_year"])
    _button(page, "Continue")

    log("STEP driving experience")
    _button(page, "Continue")

    log("STEP double-check")
    _button(page, YES_CORRECT, exact=True)

    log("STEP Aviva journey")
    _radio(page, "driver1-No")
    _button(page, "Continue")

    log("STEP contact")
    _type(page, '[data-testid="userPhoneNumber"]', V["phone"])
    _select(page, 'select[data-testid="userPhoneNumberType"]', V["phone_type"])
    _type(page, '[data-testid="userEmail"]', V["email"])
    _checkbox(page, 'input[type="checkbox"]')
    _button(page, "Continue")

    log("STEP customization / capture")
    _read_offer(page, result, keep_open=keep_open)

    os.makedirs(out_dir, exist_ok=True)
    shot = os.path.join(out_dir, "aviva_offer_headless.png")
    try:
        page.screenshot(path=shot, full_page=True)
        result["evidence"] = shot
    except Exception as e:
        log("WARN screenshot: " + str(e))


def _prepare_values(params: dict) -> dict:
    P = params or {}
    dob = get_param(P, "person.date_of_birth", "1990/03/15")
    try:
        y, m, d = dob.split("/")
    except Exception:
        y, m, d = "1990", "03", "15"
    first_lic = get_param(P, "auto.first_licence_month", "March")
    g2 = get_param(P, "auto.g2_month", "March")
    return {
        "postal": get_param(P, "person.postal_code", POSTAL),
        "vehicle_year": get_param(P, "auto.vehicle_year", "2019"),
        "vehicle_make": get_param(P, "auto.vehicle_make", "HONDA"),
        "vehicle_model": get_param(P, "auto.vehicle_model", "ACCORD EX 4DR"),
        "purchase_month": get_param(P, "auto.purchase_month", "March"),
        "purchase_year": get_param(P, "auto.purchase_year", "2020"),
        "annual_km": get_param(P, "auto.annual_km", "15000"),
        "commute_days": get_param(P, "auto.commute_days", "5"),
        "commute_oneway_km": get_param(P, "auto.commute_oneway_km", "10"),
        "coverage_start_date": get_param(P, "auto.coverage_start_date", "09/01/2026"),
        "first_name": get_param(P, "person.first_name", "John"),
        "last_name": get_param(P, "person.last_name", "Doe"),
        "dob_month": m, "dob_day": d, "dob_year": y,
        "sex": get_param(P, "person.sex", "M"),
        "marital_status": get_param(P, "person.marital_status", "S"),
        "lic_month": first_lic, "lic_year": get_param(P, "auto.first_licence_year", "2008"),
        "g2_month": g2, "g2_year": get_param(P, "auto.g2_year", "2007"),
        "phone": get_param(P, "person.phone", "9056889170"),
        "phone_type": get_param(P, "person.phone_type", "mobile"),
        "email": get_param(P, "person.email", "test@example.com"),
    }


def generate_fresh_profile():
    """A new randomized dummy profile per run so repeat tests never reuse the same
    identity (which Aviva flags). NOT a real person -- never valid evidence."""
    import random as _random
    _random.seed()
    firsts = ["Avery", "Riley", "Casey", "Morgan", "Logan", "Reese", "Parker",
              "Jordan", "Jamie", "Taylor", "Quinn", "Skyler"]
    lasts = ["Walker", "Bennett", "Carter", "Reed", "Hayes", "Doyle", "Grant",
             "Marsh", "Kerr", "Frost", "Blake", "Wells"]
    first = _random.choice(firsts)
    last = _random.choice(lasts)
    sex = _random.choice(["M", "F"])
    email = f"{first.lower()}.{last.lower()}{_random.randint(1000, 9999)}@example.com"
    phone = f"{_random.randint(200, 999)}{_random.randint(100, 999)}{_random.randint(1000, 9999)}"
    # DOB must be <= 1990 so the fixed first-licence (2008) and G2 (2007) dates
    # are >= 16 years old (Aviva validates minimum driver age at first licence).
    year = _random.randint(1970, 1990)
    month = _random.randint(1, 12)
    day = _random.randint(1, 28)
    return {
        "_comment": "Auto-generated FRESH dummy test data. NOT a real person.",
        "person": {
            "first_name": first, "last_name": last,
            "email": email, "phone": phone, "phone_type": "mobile",
            "date_of_birth": f"{year}/{month:02d}/{day:02d}",
            "sex": sex, "marital_status": "S",
            "postal_code": POSTAL,
        },
        "auto": {
            "vehicle_year": "2019", "vehicle_make": "HONDA",
            "vehicle_model": "ACCORD EX 4DR",
            "purchase_month": "March", "purchase_year": "2020",
            "annual_km": "15000", "commute_days": "5", "commute_oneway_km": "10",
            "coverage_start_date": "09/01/2026",
            "first_licence_month": "March", "first_licence_year": "2008",
            "g2_month": "March", "g2_year": "2007",
        },
    }


def _launch_context(p, *, mode: str):
    # Shared persistent profile (same as the headed script) so Aviva treats us as
    # a returning visitor instead of a brand-new flagged identity.
    profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".aviva_profile")
    os.makedirs(profile_dir, exist_ok=True)
    if mode == "minimized-headed":
        log("Launch: minimized headed (unattended fallback)")
        return p.chromium.launch_persistent_context(
            profile_dir, channel="chrome", headless=False,
            args=["--start-minimized", "--window-position=-32000,-32000"],
            viewport={"width": 1400, "height": 1000}, locale="en-US",
        )
    if mode == "visible":
        log("Launch: visible headed (debug)")
        return p.chromium.launch_persistent_context(
            profile_dir, channel="chrome", headless=False,
            viewport={"width": 1400, "height": 1000}, locale="en-US",
        )
    log("Launch: true headless")
    return p.chromium.launch_persistent_context(
        profile_dir, channel="chrome", headless=True,
        viewport={"width": 1400, "height": 1000}, locale="en-US",
    )


def run_headless(params: dict | None = None, out_dir: str = "evidence",
                 mode: str = "minimized-headed") -> dict:
    result = {
        "quote_value": None, "quote_monthly": None, "quote_number": None,
        "status": None, "mode": mode,
    }
    V = _prepare_values(params or {})

    with sync_playwright() as p:
        ctx = _launch_context(p, mode=mode)
        ctx.add_init_script(STEALTH_INIT)
        page = ctx.new_page()
        page.set_default_timeout(20000)
        try:
            fill_quote(page, V, result, out_dir=out_dir)
            result["status"] = "quoted_comparable_candidate" if result["quote_value"] else "unresolved"
        except Exception as e:
            result["status"] = "blocked"
            result["error"] = str(e)
            log("ERROR: " + str(e))
            try:
                os.makedirs("evidence", exist_ok=True)
                page.screenshot(path=os.path.join("evidence", "aviva_headless_error.png"), full_page=True)
                log("Screenshot saved to evidence/aviva_headless_error.png")
            except Exception:
                pass
        finally:
            try:
                ctx.close()
            except Exception:
                pass
    return result


def main():
    ap = argparse.ArgumentParser(
        description="Aviva Direct auto quote - unattended (headless) runner",
    )
    ap.add_argument("--input", default=None)
    ap.add_argument("--out", default="aviva_auto_quote_headless_result.json")
    ap.add_argument("--visible", action="store_true", help="Show the browser window (debug)")
    ap.add_argument("--true-headless", action="store_true",
                    help="Use true headless (experimental -- Akamai usually blocks it with Access Denied)")
    args = ap.parse_args()

    log("Running aviva_auto_quote_headless.py")
    if args.input:
        from params_loader import load_params
        profile = load_params(args.input)
        log(f"Using profile from {args.input}: "
            f"{profile['person']['first_name']} {profile['person']['last_name']}")
    else:
        profile = generate_fresh_profile()
        log("Generated a FRESH dummy profile for this run: "
            f"{profile['person']['first_name']} {profile['person']['last_name']} "
            f"<{profile['person']['email']}>")

    res = run_headless(
        params=profile,
        mode="visible" if args.visible else ("headless" if args.true_headless else "minimized-headed"),
    )
    res["carrier"] = "aviva.ca"
    res["form_url"] = QUOTE_URL
    res["form_kind"] = "quote"
    res["_note"] = "Unattended run via aviva_auto_quote_headless.py (headless)."

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quote_results.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")

    log("=== RESULT ===")
    log("  mode: " + str(res.get("mode")))
    log("  quote_monthly: " + str(res.get("quote_monthly")))
    log("  quote_number: " + str(res.get("quote_number")))
    log("  status: " + str(res.get("status")))
    log("  error: " + str(res.get("error")))
    log("  saved to: " + str(out_path))


if __name__ == "__main__":
    main()
