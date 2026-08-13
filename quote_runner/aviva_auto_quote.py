"""
aviva_auto_quote.py
===================
Playwright automation for Aviva Direct - Auto Insurance online rater.

Entry  : myaviva.avivainsurance.ca/avivaquoter/bol/auto (direct rater; it pops a
          postal-code dialog). The old aviva.ca homepage quick-modal no longer
          appears, so we skip the homepage entirely.
Form kind: QUOTE  -- returns a real premium ($), unlike lead-gen forms.

Driving style: KEYBOARD-CLICK. Text/masked fields are typed (press_sequentially)
so Angular input masks behave correctly; radios/checkbox are activated with
focus + Space; buttons with focus + Enter. Selects are set natively.

Flow (verified end-to-end in a headed browser):
   1. Postal dialog : postal code -> Continue
   2. Car Details   : year/make/model, purchase date, condition, winter tires,
                      anti-theft
   3. Car Use       : annual km, commute days + one-way km, business use,
                      coverage start
   4. Driver        : first/last name, DOB, sex, marital, combined policy,
                      TELUS, continuous insurance
   5. Licence       : class G, first licence date
   6. Licence hist  : G2 date
   7. Experience    : (No default)
   8. Double-check  : "Yes, that's correct"
   9. Aviva Journey : include app? -> No
  10. Contact       : phone, phone type, email, consent checkbox
  11. Customization : optional coverage tab -> premium + quote number captured

Usage
-----
Headed:  python aviva_auto_quote.py --headed
Headless: python aviva_auto_quote.py --headless   (default)
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

from params_loader import get_param, load_params

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

QUOTE_URL = "https://myaviva.avivainsurance.ca/avivaquoter/bol/auto"
POSTAL = "L2R 1A1"
QUOTE_EMAIL = "test@example.com"   # where the final quote is emailed (default; override via --input)

# Stealth: mask the Playwright automation fingerprint (webdriver flag, languages)
# that Aviva's bot gate would otherwise score. Use the browser's REAL user-agent
# (no override) with a persistent profile so the vehicle-lookup API accepts the
# session.
STEALTH_INIT = r"""
Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => undefined, configurable: true });
Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true });
Object.defineProperty(Navigator.prototype, 'languages', { get: () => ['en-US','en'], configurable: true });
if (navigator.plugins) {
    Object.defineProperty(Navigator.prototype, 'plugins', { get: () => [1,2,3,4,5], configurable: true });
}
Object.defineProperty(window, 'chrome', { get: () => ({ runtime: {} }), configurable: true });
"""

# "Yes, that's correct" uses a curly apostrophe (U+2019) on the page.
YES_CORRECT = "Yes, that\u2019s correct"

# Form field name -> params path. Values are loaded from the shared per-person
# JSON (quote_params.json or --input), or a fresh generated profile.
PARAM_MAP = {
    # vehicle
    "vehicleYear":          "auto.vehicle_year",
    "vehicleMake":          "auto.vehicle_make",
    "vehicleModel":         "auto.vehicle_model",
    "purchaseDate_month":   "auto.purchase_month",
    "purchaseDate_year":    "auto.purchase_year",
    "purchaseCondition":    "auto.purchase_condition",
    "winterTires":          "auto.winter_tires",
    "hasAntiTheftDevice":   "auto.anti_theft",
    # car use
    "annualMileage":        "auto.annual_km",
    "commutePerWeek":       "auto.commute_days",
    "commutingMiles":       "auto.commute_oneway_km",
    "coverageStartDate":    "auto.coverage_start_date",   # MM/DD/YYYY
    # driver
    "driverFirstName":      "person.first_name",
    "driverLastName":       "person.last_name",
    "driverDOB_m":          "person.date_of_birth",       # split into m/d/y below
    "sex":                  "person.sex",
    "maritalStatus":        "person.marital_status",
    "combinedPolicyDiscount": "auto.combined_policy",     # NO
    "telusHealth":          "auto.telus_health",
    "hadPriorInsurance":    "auto.prior_insurance",
    # licence
    "licenseClass":         "auto.licence_class",
    "firstLicenceDate_month": "auto.first_licence_month",
    "firstLicenceDate_year":  "auto.first_licence_year",
    "graduateLicenseDate_month": "auto.g2_month",
    "graduateLicenseDate_year":  "auto.g2_year",
    # contact
    "phone":                "person.phone",
    "phoneType":            "person.phone_type",
    "email":                "person.email",
}

_START = time.time()


def log(msg: str):
    stamp = (datetime.now().strftime("%H:%M:%S") + f" (+{time.time() - _START:5.1f}s)")
    print(f"[{stamp}] {msg}", flush=True)


def _set_progress(progress_path, percent, label, attempt=1):
    """Write the current step progress (%) to a small JSON the website polls."""
    if not progress_path:
        return
    try:
        with open(progress_path, "w", encoding="utf-8") as f:
            json.dump({"percent": int(percent), "label": label, "attempt": int(attempt),
                       "ts": datetime.now().isoformat(timespec="seconds")}, f)
    except Exception:
        pass


# --------------------------------------------------------------------------
# Keyboard-driven helpers.  Text = real keystrokes (mask-friendly); controls =
# focus + a key press (no pointer clicks).
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
    """Activate a radio button with the keyboard (focus + Space)."""
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
    """Activate a button by its accessible name using the keyboard (focus + Enter).

    Waits for the button to become ENABLED (Aviva disables Continue until the
    form is valid), then clicks it with a real pointer click -- exactly what the
    verified MCP flow does.
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
            "purchase_condition": "new", "winter_tires": "yes", "anti_theft": "no",
            "annual_km": "15000", "commute_days": "5", "commute_oneway_km": "10",
            "coverage_start_date": "09/01/2026",
            "combined_policy": "NO", "telus_health": "no",
            "prior_insurance": "greatthan3years", "licence_class": "G",
            "first_licence_month": "March", "first_licence_year": "2008",
            "g2_month": "March", "g2_year": "2007",
        },
    }


def _dismiss_error_modal(page, keep_open: bool = False) -> bool:
    """Close the 'Sorry, something went wrong' modal if present.

    Aviva can pop an error modal ("We couldn't process your request") — usually
    with a Close/X button — right around quote generation. If we don't dismiss it
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
        # When --keep-open is set, pause so the user can inspect/close the modal
        # manually instead of auto-dismissing it.
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
            # A trusted pointer click is needed for Angular's handler, not JS .click().
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
                # Strategy 3: a Close button via role.
                page.get_by_role("button", name="Close", exact=False).first.click(force=True)
                clicked = True
            except Exception:
                pass
        if not clicked:
            # Diagnostic: dump buttons present so we can pinpoint the control.
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
    # The price line ("$175.58 / Month") is revealed on the Optional coverage tab.
    # Try keyboard activation first; fall back to a real click so the price shows.
    # Give the quote API time to finish generating before reading the price.
    page.wait_for_timeout(5000)
    _dismiss_error_modal(page, keep_open=keep_open)
    # Activate the tab that reveals the price. The label has varied ("Optional
    # coverage", "Coverage", "Rates"), so try a few and accept whichever appears.
    tabs = ["Optional coverage", "Coverage", "Rates", "Quote details"]
    clicked = False
    for tname in tabs:
        try:
            tab = page.get_by_text(tname, exact=True).first
            tab.wait_for(state="visible", timeout=4000)
            log(f"    tab '{tname}'")
            tab.click(force=True)
            clicked = True
            page.wait_for_timeout(2500)
            break
        except Exception:
            continue
    if not clicked:
        log("WARN: no coverage tab found; parsing current body")

    # Poll for the price to render. The quote API can take a while and the error
    # modal can reappear and needs re-dismissing, so allow up to ~60s.
    body = ""
    price_hits = []
    for _ in range(35):
        try:
            _dismiss_error_modal(page, keep_open=keep_open)
        except Exception:
            pass
        try:
            body = page.locator("body").inner_text(timeout=8000)
        except Exception:
            body = ""
        # Also harvest any price-looking elements (resilient to layout changes).
        try:
            price_hits = page.locator(
                '[class*="price" i], [class*="amount" i], [class*="premium" i], '
                '[data-testid*="price" i]').all_inner_texts()
        except Exception:
            price_hits = []
        joined = body + "\n" + "\n".join(price_hits)
        if re.search(r"\$\s?\d[\d,]*\.\d{2}\s*/\s*(Month|Year)", joined) or \
           re.search(r"\$\s?\d[\d,]*\.\d{2}", joined):
            break
        page.wait_for_timeout(1500)

    joined = body + "\n" + "\n".join(price_hits)
    if not re.search(r"\$\s?\d[\d,]*\.\d{2}", joined):
        log("WARN: no price found on customization page; body follows:")
        log((body or "")[:1500])

    m = re.search(r"\$\s?(\d[\d,]*\.\d{2})\s*/\s*(Month|Year)", joined)
    if m:
        result["quote_value"] = "$" + m.group(1) + " / " + m.group(2)
        result["quote_monthly"] = "$" + m.group(1) + " / month"
    else:
        m2 = re.search(r"\$\s?(\d[\d,]*\.\d{2})", joined)
        if m2:
            result["quote_value"] = "$" + m2.group(1)
            result["quote_monthly"] = "$" + m2.group(1) + " / month"
    qn = re.search(r"Q\s?([\d ]{6,})", body)
    if qn:
        result["quote_number"] = "Q " + re.sub(r"\s+", "", qn.group(1))
    log(f"    captured quote_value={result.get('quote_value')!r} "
        f"quote_number={result.get('quote_number')!r}")


def _extra_args():
    """Container-safe Chrome flags. Chromium's sandbox can't start when running as
    root (e.g. inside a Docker container), so add --no-sandbox / --disable-dev-shm-usage
    only there; harmless to leave off on a normal desktop login."""
    try:
        if os.name == "posix" and os.geteuid() == 0:
            return ["--no-sandbox", "--disable-dev-shm-usage", "--remote-debugging-port=9222", "--remote-debugging-address=0.0.0.0"]
    except Exception:
        pass
    return []


def _screen_size():
    """Return the primary display's (width, height) in pixels."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
    except Exception:
        return 1920, 1080


def _centered_args(win_w: int = 1400, win_h: int = 1000):
    """Chrome launch args that center the window on the screen. Aviva uses a
    persistent profile that remembers a prior off-screen/minimized position, so an
    otherwise-default headed launch would reappear off-screen; force a centered,
    visible position (add ~80px for the title bar)."""
    w, h = _screen_size()
    x = max(0, (w - win_w) // 2)
    y = max(0, (h - (win_h + 80)) // 2)
    return [f"--window-size={win_w},{win_h}", f"--window-position={x},{y}"]


def run(headless: bool, params: dict | None = None, keep_open: bool = False,
        minimized: bool = False, progress_path: str | None = None,
        max_retries: int = 2) -> dict:
    result = {"quote_value": None, "quote_number": None, "emailed": False}
    params = params or {}
    V = {f: get_param(params, p, "") for f, p in PARAM_MAP.items()}
    dob = get_param(params, "person.date_of_birth", "1990/03/15")
    try:
        _y, _m, _d = dob.split("/")
    except Exception:
        _y, _m, _d = "1990", "03", "15"

    # Persistent browser profile (kept across runs) so Aviva treats us as a
    # returning visitor instead of a brand-new flagged identity. Only the person
    # DATA is fresh per run (generate_fresh_profile).
    profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".aviva_profile")
    os.makedirs(profile_dir, exist_ok=True)
    # Aviva's rater is intermittent and can stall mid-flow (gated steps, slow dialogs).
    # Retry the ENTIRE flow from scratch (fresh browser) up to max_retries times if an
    # attempt doesn't produce a quote. The persistent profile is reused for identity.
    for attempt in range(1, max_retries + 1):
        result = {"quote_value": None, "quote_number": None, "emailed": False}
        log(f"ATTEMPT {attempt}/{max_retries} of the whole Aviva flow")
        with sync_playwright() as p:
            # Real installed Chrome, persistent profile, real UA (no override), and
            # stealth init — so Aviva's bot gate lets the vehicle lookup succeed.
            _launch_kw = dict(
                channel="chrome", headless=headless,
                viewport={"width": 1400, "height": 1000},
                locale="en-US",
            )
            if minimized and not headless:
                _launch_kw["args"] = _extra_args() + ["--start-minimized", "--window-position=-32000,-32000"]
            elif not headless:
                # Headed (non-minimized): force a centered, visible window so the run is
                # watchable (the persistent profile otherwise restores an off-screen spot).
                _launch_kw["args"] = _extra_args() + _centered_args()
            ctx = p.chromium.launch_persistent_context(
                profile_dir, **_launch_kw,
            )
            ctx.add_init_script(STEALTH_INIT)
            page = ctx.new_page()
            page.set_default_timeout(20000)
            try:
                log("STEP entry (postal code)")
                page.goto(QUOTE_URL, wait_until="domcontentloaded", timeout=60000)
                dialog = page.get_by_role("dialog")
                dialog.wait_for(state="visible", timeout=30000)
                dialog.locator('input[data-testid="postalcode"]').wait_for(state="visible", timeout=30000)
                _type(page, 'input[data-testid="postalcode"]', get_param(params, "person.postal_code", POSTAL))
                _button(page, "Continue", scope=dialog)
                _set_progress(progress_path, 8, "entry", attempt)

                log("STEP vehicle")
                _select(page, 'select[data-testid="vehicleYear"]', V["vehicleYear"])
                _select(page, 'select[data-testid="vehicleMake"]', V["vehicleMake"])
                _select(page, 'select[data-testid="vehicleModel"]', V["vehicleModel"])
                _select_label(page, 'select[data-testid="purchaseDate_month"]', V["purchaseDate_month"])
                _select(page, 'select[data-testid="purchaseDate_year"]', V["purchaseDate_year"])
                _radio(page, "purchaseCondition-new_AC")
                _radio(page, "winterTires-yes")
                _radio(page, "hasAntiTheftDevice-no")
                _button(page, "Continue")
                _set_progress(progress_path, 22, "vehicle", attempt)

                log("STEP car use")
                _type(page, 'input[name="annualMileage"]', V["annualMileage"])
                _select(page, 'select[data-testid="commutePerWeek"]', V["commutePerWeek"])
                _type(page, 'input[name="commutingMiles"]', V["commutingMiles"])
                _type(page, 'input[placeholder="MM/DD/YYYY"]', V["coverageStartDate"])
                _button(page, "Continue")
                _set_progress(progress_path, 35, "car use", attempt)

                log("STEP driver")
                _type(page, '[data-testid="driverFirstName"]', V["driverFirstName"])
                _type(page, '[data-testid="driverLastName"]', V["driverLastName"])
                _type(page, '[data-testid="dateOfBirth-month"]', _m)
                _type(page, '[data-testid="dateOfBirth-day"]', _d)
                _type(page, '[data-testid="dateOfBirth-year"]', _y)
                _radio(page, "gender-M" if str(V["sex"]).upper() == "M"
                        else ("gender-F" if str(V["sex"]).upper() == "F" else "gender-X"))
                _select(page, 'select[data-testid="driverMaritalStatus"]', V["maritalStatus"])
                _radio(page, "combinedPolicyDiscount-NO")
                _radio(page, "telusHealth-no")
                _radio(page, "hadPriorInsurance-greatthan3years")
                _button(page, "Continue")
                _set_progress(progress_path, 50, "driver", attempt)

                log("STEP licence")
                _radio(page, "licenseClass-G")
                _select_label(page, 'select[data-testid="firstLicenceDate_month"]', V["firstLicenceDate_month"])
                _select(page, 'select[data-testid="firstLicenceDate_year"]', V["firstLicenceDate_year"])
                _button(page, "Continue")
                _set_progress(progress_path, 62, "licence", attempt)

                log("STEP licence history")
                _select_label(page, 'select[data-testid="graduateLicenseDate_month"]', V["graduateLicenseDate_month"])
                _select(page, 'select[data-testid="graduateLicenseDate_year"]', V["graduateLicenseDate_year"])
                # When the driver has held other Ontario licence classes, Aviva adds
                # required G1-date and accelerated-licence questions on this same step.
                # Fill them if they appear so Continue becomes enabled.
                try:
                    g1m = page.locator('select[data-testid="firstGraduatedLicenseDate_month"]').first
                    if g1m.is_visible():
                        try:
                            g1y = str(max(2000, int(V["graduateLicenseDate_year"]) - 1))
                        except Exception:
                            g1y = "2000"
                        _select_label(page, 'select[data-testid="firstGraduatedLicenseDate_month"]', V["graduateLicenseDate_month"])
                        _select(page, 'select[data-testid="firstGraduatedLicenseDate_year"]', g1y)
                except Exception:
                    pass
                try:
                    acc = page.locator('[data-testid="completedAcceleratedLicense-no"]').first
                    if acc.is_visible():
                        _radio(page, "completedAcceleratedLicense-no")
                except Exception:
                    pass
                _button(page, "Continue")
                _set_progress(progress_path, 72, "licence history", attempt)

                log("STEP driving experience")
                _button(page, "Continue")
                _set_progress(progress_path, 78, "driving experience", attempt)

                log("STEP double-check")
                _button(page, YES_CORRECT, exact=True)
                _set_progress(progress_path, 84, "double-check", attempt)

                log("STEP Aviva journey")
                _radio(page, "driver1-No")
                _button(page, "Continue")
                _set_progress(progress_path, 88, "journey", attempt)

                log("STEP contact")
                _type(page, '[data-testid="userPhoneNumber"]', V["phone"])
                _select(page, 'select[data-testid="userPhoneNumberType"]', V["phoneType"])
                _type(page, '[data-testid="userEmail"]', V["email"])
                _checkbox(page, 'input[type="checkbox"]')
                _button(page, "Continue")
                _set_progress(progress_path, 93, "contact", attempt)

                log("STEP customization / capture")
                _set_progress(progress_path, 96, "capturing quote", attempt)
                _read_offer(page, result, keep_open=keep_open)
                _set_progress(progress_path, 100, "captured", attempt)

            except Exception as e:
                result["error"] = str(e)
                log("ERROR: " + str(e))
                try:
                    os.makedirs("evidence", exist_ok=True)
                    page.screenshot(path=os.path.join("evidence", "aviva_error.png"), full_page=True)
                    log("Screenshot saved to evidence/aviva_error.png")
                    body = page.locator("body").inner_text(timeout=5000)[:1500]
                    log("BODY TEXT:\n" + body)
                except Exception as se:
                    log("WARN could not capture error state: " + str(se))
            finally:
                if keep_open and not headless and (result.get("quote_value") or attempt == max_retries):
                    log(">>> Browser kept open for inspection. Press Enter to close it...")
                    try:
                        input()
                    except Exception:
                        page.wait_for_timeout(60000)
                if not headless and not keep_open:
                    page.wait_for_timeout(2000)
                try:
                    ctx.close()
                except Exception:
                    pass
        if result.get("quote_value"):
            break
        if attempt < max_retries:
            log("Aviva flow failed; retrying the whole flow from scratch")
    # Note: .aviva_profile is intentionally kept (persistent cookies/session).
    return result


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--headless", action="store_true", default=False)
    g.add_argument("--headed", action="store_true", default=False)
    ap.add_argument("--out", default="aviva_auto_quote_result.json",
                    help="JSON file to persist the captured result (default: aviva_auto_quote_result.json)")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON. If omitted, a FRESH dummy profile is generated.")
    ap.add_argument("--keep-open", action="store_true", default=False,
                    help="Keep the headed browser open at the end (and pause when the error modal appears) for inspection.")
    ap.add_argument("--close", action="store_true", default=False,
                    help="Close the browser at the end even in headed mode (for unattended/CI runs). "
                         "Headed mode KEEPS the browser open by default so you can inspect it.")
    ap.add_argument("--minimized", action="store_true", default=False,
                    help="Run headed but minimized/off-screen (unattended; needs Xvfb).")
    ap.add_argument("--progress", default=None,
                    help="Path to write live % step progress (website reads this).")
    ap.add_argument("--retries", type=int, default=2,
                    help="How many times to retry the whole flow from scratch if no quote.")
    args = ap.parse_args()
    headless = (not args.headed) and (not args.minimized)
    # Headed mode persists the browser at the end by default; only close it if
    # --close is passed (or we're in headless/minimized mode).
    keep_open = (not headless) and (not args.close) and (not args.minimized)
    log(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode "
        f"(browser {'KEPT OPEN at end' if keep_open else 'closed at end'})")

    if args.input:
        profile = load_params(args.input)
        log(f"Using profile from {args.input}: "
            f"{profile['person']['first_name']} {profile['person']['last_name']}")
    else:
        profile = generate_fresh_profile()
        log("Generated a FRESH dummy profile for this run: "
            f"{profile['person']['first_name']} {profile['person']['last_name']} "
            f"<{profile['person']['email']}>")

    res = run(headless=headless, params=profile, keep_open=keep_open, minimized=args.minimized,
              progress_path=args.progress, max_retries=args.retries)
    res["carrier"] = "aviva.ca"
    res["form_url"] = QUOTE_URL
    res["form_kind"] = "quote"

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quote_results.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")

    log("=== RESULT ===")
    log("  quote_value: " + str(res.get("quote_value")))
    log("  quote_number: " + str(res.get("quote_number")))
    log("  emailed: " + str(res.get("emailed")))
    log("  error: " + str(res.get("error")))
    log(f"  saved to: {out_path} and appended to {log_path}")


if __name__ == "__main__":
    main()
