"""
allstate_auto_quote_headless.py
===============================
Unattended Allstate Canada auto quote runner (batch / CI / no manual watch).

Mirrors the verified flow in allstate_auto_quote.py (validated end-to-end in a
headed browser -> real premium, e.g. "$149.75 / month"). Runs unattended and
never keeps the browser open.

Why minimized-headed by default?
  Allstate (like Aviva/Bel Air) is served behind a bot gate; true headless Chrome
  is usually blocked. Launching real Chrome minimized off-screen keeps the working
  fingerprint and returns a real premium unattended.

Run:
  python allstate_auto_quote_headless.py
  python allstate_auto_quote_headless.py --input people/dummy.json
  python allstate_auto_quote_headless.py --visible            # show browser (debug)
  python allstate_auto_quote_headless.py --true-headless      # experimental, usually blocked
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

LANDING_URL = "https://apps.allstate.ca/quickquote/common/landing.aspx?CID=SEO_hero_home_page_Organic_EN"
POSTAL = "L2R1A1"  # Allstate rejects a spaced postal code.

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
    return (datetime.now().strftime("%H:%M:%S") + f" (+{time.time() - _START:5.1f}s)")


def log(msg: str):
    print(f"[{_stamp()}] {msg}", flush=True)


# --------------------------------------------------------------------------
# Helpers (identical to allstate_auto_quote.py)
# --------------------------------------------------------------------------
def _type(page, target, text):
    loc = page.locator(target).first if isinstance(target, str) else target.first
    loc.wait_for(state="attached", timeout=10000)
    log(f"    type {loc} <- {text!r}")
    loc.fill("")
    loc.press_sequentially(str(text), delay=20)
    page.wait_for_timeout(120)


def _select(page, label, value):
    log(f"    select {label} = {value!r}")
    page.locator(f'select[aria-label="{label}"], select[name="{label}"]').first.select_option(value)
    page.wait_for_timeout(150)


def _radio(page, group, label):
    g = page.get_by_role("group", name=group, exact=False)
    loc = None
    for exact in (True, False):
        try:
            loc = g.get_by_role("radio", name=label, exact=exact).first
            loc.wait_for(state="attached", timeout=5000)
            break
        except Exception:
            loc = None
    if loc is None:
        # Fallback: find the fieldset/group by its question text (robust to the
        # accessible name using a space vs a hyphen, e.g. "graduated licensing").
        fset = page.locator(f'fieldset:has-text("{group}"), [role="group"]:has-text("{group}")').first
        try:
            loc = fset.get_by_role("radio", name=label, exact=False).first
            loc.wait_for(state="attached", timeout=5000)
        except Exception:
            try:
                fset.get_by_text(label, exact=True).first.click(force=True)
                page.wait_for_timeout(150)
                return
            except Exception:
                raise Exception(f"radio [{group}] {label} not found")
    log(f"    radio [{group}] {label}")
    loc.focus()
    page.keyboard.press("Space")
    page.wait_for_timeout(150)


def _checkbox(page, selector, name):
    loc = page.get_by_role("checkbox", name=name).first
    loc.wait_for(state="attached", timeout=10000)
    log(f"    checkbox {name!r}")
    loc.focus()
    page.keyboard.press("Space")
    page.wait_for_timeout(150)


def _dismiss_cookie_banner(page):
    try:
        loc = page.locator("#onetrust-accept-btn-handler")
        if loc.count():
            loc.first.click(timeout=3000)
            page.wait_for_timeout(500)
            return
    except Exception:
        pass
    try:
        page.locator("#onetrust-consent-sdk button:has-text('Accept')").first.click(timeout=3000)
        page.wait_for_timeout(500)
        return
    except Exception:
        pass
    try:
        page.evaluate(
            "() => { const b = document.querySelector('#onetrust-banner-sdk')"
            " || document.querySelector('#onetrust-consent-sdk'); if (b) b.style.display='none'; }"
        )
        page.wait_for_timeout(300)
    except Exception:
        pass


def _dismiss_modal(page):
    """Dismiss the 'Close' modal that can overlay the quote page once generated."""
    try:
        loc = page.locator('[role="dialog"] svg title:has-text("Close"), '
                           '[role="dialog"] [aria-label*="close" i], '
                           'svg title:has-text("Close")')
        btn = page.locator('[role="dialog"] button:has(svg title:has-text("Close")), '
                           '[role="dialog"] [role="button"]:has(svg title:has-text("Close"))')
        if btn.count():
            btn.first.click(timeout=3000)
            page.wait_for_timeout(600)
            log("    dismissed Close modal")
    except Exception:
        pass


def _button(page, name, exact=True):
    _dismiss_cookie_banner(page)
    loc = page.get_by_role("button", name=name, exact=exact).first
    loc.wait_for(state="visible", timeout=15000)
    log(f"    button {name!r}")
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            if loc.is_enabled():
                break
        except Exception:
            break
        page.wait_for_timeout(250)
    loc.click()
    page.wait_for_timeout(1400)


def _date(page, mmddyyyy):
    loc = page.locator('input[placeholder="mm/dd/yyyy"]').first
    loc.wait_for(state="attached", timeout=8000)
    log(f"    date <- {mmddyyyy}")
    loc.fill(str(mmddyyyy))
    page.wait_for_timeout(150)


# --------------------------------------------------------------------------
# Values + fresh profile
# --------------------------------------------------------------------------
def _prepare_values(params: dict) -> dict:
    P = params or {}
    dob = get_param(P, "person.date_of_birth", "1985/03/15")
    try:
        y, m, d = dob.split("/")
    except Exception:
        y, m, d = "1985", "03", "15"
    postal = get_param(P, "person.postal_code", POSTAL).replace(" ", "")
    return {
        "postal": postal,
        "vehicle_year": get_param(P, "auto.vehicle_year", "2019"),
        "vehicle_make": get_param(P, "auto.vehicle_make", "HONDA"),
        "vehicle_model": get_param(P, "auto.vehicle_model", "ACCORD EX 4DR"),
        "condition": get_param(P, "auto.purchase_condition", "Used"),
        "ownership": get_param(P, "auto.ownership", "Owned"),
        "only_owner": get_param(P, "auto.only_owner", "Yes"),
        "within_30d": get_param(P, "auto.within_30d", "No"),
        "purchase_price": get_param(P, "auto.purchase_price", "25000"),
        "coverage_start": get_param(P, "auto.coverage_start_date", "09/01/2026"),
        "purchase_month": get_param(P, "auto.purchase_month", "March"),
        "purchase_year": get_param(P, "auto.purchase_year", "2020"),
        "vehicle_use": get_param(P, "auto.vehicle_use", "Work / School"),
        "one_way_km": get_param(P, "auto.commute_oneway_km", "10"),
        "annual_km_band": get_param(P, "auto.annual_km_band", "12001-16000km"),
        "winter_tires": get_param(P, "auto.winter_tires", "Yes"),
        "parking": get_param(P, "auto.parking", "Home Driveway"),
        "anti_theft": get_param(P, "auto.anti_theft", "No"),
        "first_name": get_param(P, "person.first_name", "Casey"),
        "last_name": get_param(P, "person.last_name", "Reed"),
        "dob": f"{m}/{d}/{y}",
        "gender": {"M": "Male", "F": "Female", "X": "X"}.get(
            str(get_param(P, "person.sex", "Male")).upper(),
            str(get_param(P, "person.sex", "Male"))),
        "marital": get_param(P, "person.marital_status", "Single"),
        "household": get_param(P, "auto.household_drivers", "No"),
        "first_lic_age": get_param(P, "auto.first_licensed_age", "16"),
        "graduated": get_param(P, "auto.graduated_licensing", "Yes"),
        "license_class": get_param(P, "auto.licence_class", "G"),
        "g_12mo": get_param(P, "auto.g_within_12mo", "No"),
        "minor_viol": get_param(P, "auto.minor_violations", "None"),
        "major_viol": get_param(P, "auto.major_violations", "No"),
        "suspended": get_param(P, "auto.licence_suspended", "No"),
        "insured": get_param(P, "auto.insured", "Yes"),
        "cancelled": get_param(P, "auto.policy_cancelled", "No"),
        "claims_6yr": get_param(P, "auto.claims_6yr", "No"),
        "drivewise": get_param(P, "auto.drivewise", "No"),
        "email": get_param(P, "person.email", "casey.reed1234@example.com"),
        "phone": get_param(P, "person.phone", "9056889170"),
    }


def generate_fresh_profile():
    """A new randomized dummy profile per run (never a real person / evidence)."""
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
    year = _random.randint(1970, 1990)  # valid with the fixed licence dates
    month = _random.randint(1, 12)
    day = _random.randint(1, 28)
    return {
        "_comment": "Auto-generated FRESH dummy test data. NOT a real person.",
        "person": {
            "first_name": first, "last_name": last,
            "email": email, "phone": phone, "sex": sex,
            "date_of_birth": f"{year}/{month:02d}/{day:02d}",
            "marital_status": "Single", "postal_code": POSTAL,
        },
        "auto": {
            "vehicle_year": "2019", "vehicle_make": "HONDA",
            "vehicle_model": "ACCORD EX 4DR",
            "purchase_condition": "Used", "ownership": "Owned",
            "only_owner": "Yes", "within_30d": "No",
            "purchase_price": "25000", "coverage_start_date": "09/01/2026",
            "purchase_month": "March", "purchase_year": "2020",
            "vehicle_use": "Work / School", "commute_oneway_km": "10",
            "annual_km_band": "12001-16000km",
            "winter_tires": "Yes", "parking": "Home Driveway",
            "anti_theft": "No", "household_drivers": "No",
            "first_licensed_age": "16", "graduated_licensing": "Yes",
            "licence_class": "G", "g_within_12mo": "No",
            "minor_violations": "None", "major_violations": "No",
            "licence_suspended": "No", "insured": "Yes",
            "policy_cancelled": "No", "claims_6yr": "No", "drivewise": "No",
        },
    }


# --------------------------------------------------------------------------
# Flow
# --------------------------------------------------------------------------
def fill_quote(page, V: dict, result: dict):
    log("landing")
    page.goto(LANDING_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)
    _dismiss_cookie_banner(page)
    _type(page, 'input[placeholder="Postal Code"]', V["postal"])
    page.get_by_role("link", name="Go", exact=True).click()
    page.wait_for_url(re.compile(r"getstarted"), timeout=20000)
    page.wait_for_timeout(2000)

    log("getstarted")
    _button(page, re.compile(r"SHOP\s*&\s*BUY", re.I), exact=False)
    page.wait_for_timeout(2500)

    log("vehicle dialog")
    _select(page, "year", V["vehicle_year"])
    _select(page, "make", V["vehicle_make"])
    _select(page, "model", V["vehicle_model"])
    _button(page, "continue")

    log("vehicle details dialog")
    _radio(page, "new, used or a dealership demo", V["condition"])
    _radio(page, "owned, financed, or leased", V["ownership"])
    _radio(page, "only registered owner", V["only_owner"])
    _radio(page, "within the last 30 days", V["within_30d"])
    _type(page, page.get_by_role("spinbutton", name="purchase price", exact=False), V["purchase_price"])
    _date(page, V["coverage_start"])
    _select(page, "purchasedMonth", V["purchase_month"])
    _select(page, "purchasedYear", V["purchase_year"])
    _button(page, "continue")

    log("vehicle use dialog")
    _select(page, "vehicle-used-for", V["vehicle_use"])
    page.wait_for_timeout(600)
    _type(page, page.get_by_role("spinbutton", name="How many kilometres", exact=False), V["one_way_km"])
    _select(page, "one-year-kilometers", V["annual_km_band"])
    _radio(page, "commercial-usage", "No")
    _checkbox(page, None, "I confirm that this vehicle")
    _button(page, "continue")

    log("savings dialog")
    _radio(page, "winter-tires", V["winter_tires"])
    page.wait_for_timeout(400)
    _checkbox(page, None, "I confirm that 4 winter tires")
    _select(page, "vehicle-parking", V["parking"])
    _radio(page, "anti-theft-devices", V["anti_theft"])
    _button(page, "continue")

    log("driver details dialog")
    _type(page, page.get_by_role("textbox", name="First name"), V["first_name"])
    _type(page, page.get_by_role("textbox", name="Last name"), V["last_name"])
    _date(page, V["dob"])
    _radio(page, "gender", V["gender"])
    _select(page, "marital-status", V["marital"])
    _radio(page, "household-licensed", V["household"])
    _button(page, "continue")

    log("driving history dialog")
    _type(page, page.get_by_role("textbox", name="How old were you when you were first licensed", exact=False), V["first_lic_age"])
    page.keyboard.press("Tab")   # commit the age so the next question reveals
    page.wait_for_timeout(800)
    _radio(page, "graduated", V["graduated"])
    _radio(page, "license-status", V["license_class"])
    _radio(page, "dt-obtainGlicense", V["g_12mo"])
    _select(page, "minor-violation", V["minor_viol"])
    _radio(page, "criminal-violations", V["major_viol"])
    _radio(page, "license-suspended", V["suspended"])
    _button(page, "continue")

    log("insurance history dialog")
    _radio(page, "prior-insurance", V["insured"])
    _radio(page, "policy-cancelled", V["cancelled"])
    _radio(page, "claims-details", V["claims_6yr"])
    _button(page, "continue")

    log("summary + get a quote")
    _radio(page, "include Drivewise", V["drivewise"])
    _type(page, page.get_by_role("textbox", name="Email address"), V["email"])
    _type(page, page.get_by_role("textbox", name="phone-number"), V["phone"])
    _checkbox(page, None, "Yes, I agree that you may")
    _button(page, "get a quote")

    log("quote page")
    page.wait_for_url(re.compile(r"/quote"), timeout=30000)
    page.wait_for_timeout(5000)
    _dismiss_modal(page)
    _read_offer(page, result)

    os.makedirs("evidence", exist_ok=True)
    try:
        page.screenshot(path=os.path.join("evidence", "allstate_offer.png"), full_page=True)
        result["evidence"] = "evidence/allstate_offer.png"
    except Exception:
        pass


def _read_offer(page, result: dict):
    body = page.locator("body").inner_text(timeout=10000)
    m = re.search(r"\$\s?(\d[\d,]*\.?\d*)\s*/\s*month", body, re.I)
    if m:
        result["quote_value"] = m.group(1)
        result["quote_monthly"] = re.sub(r"\s+", " ", m.group(0)).strip()
    qn = re.search(r"Quote\s*#\s*([A-Z0-9]+)", body, re.I)
    if qn:
        result["quote_number"] = qn.group(1)
    log(f"    captured quote_value={result.get('quote_value')!r} "
        f"quote_number={result.get('quote_number')!r}")
    result["status"] = "quoted_comparable_candidate" if result["quote_value"] else "unresolved"
    if not result["quote_value"]:
        log("WARN: no price found; body:\n" + body[:1200])


def _launch_context(p, *, mode: str):
    profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".allstate_profile")
    os.makedirs(profile_dir, exist_ok=True)
    if mode == "true-headless":
        log("Launch: true headless (experimental)")
        return p.chromium.launch_persistent_context(
            profile_dir, channel="chrome", headless=True,
            viewport={"width": 1400, "height": 1000}, locale="en-US")
    if mode == "visible":
        log("Launch: visible headed (debug)")
        return p.chromium.launch_persistent_context(
            profile_dir, channel="chrome", headless=False,
            viewport={"width": 1400, "height": 1000}, locale="en-US")
    log("Launch: minimized headed (unattended)")
    return p.chromium.launch_persistent_context(
        profile_dir, channel="chrome", headless=False,
        args=["--start-minimized", "--window-position=-32000,-32000"],
        viewport={"width": 1400, "height": 1000}, locale="en-US")


def run_headless(params: dict | None = None, mode: str = "minimized-headed") -> dict:
    result = {"quote_value": None, "quote_monthly": None, "quote_number": None,
              "status": None, "mode": mode}
    V = _prepare_values(params or {})
    with sync_playwright() as p:
        ctx = _launch_context(p, mode=mode)
        ctx.add_init_script(STEALTH_INIT)
        page = ctx.new_page()
        page.set_default_timeout(15000)
        try:
            fill_quote(page, V, result)
        except Exception as e:
            result["status"] = "blocked"
            result["error"] = str(e)
            log("ERROR: " + str(e))
            try:
                os.makedirs("evidence", exist_ok=True)
                page.screenshot(path=os.path.join("evidence", "allstate_error.png"), full_page=True)
            except Exception:
                pass
        finally:
            try:
                ctx.close()
            except Exception:
                pass
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=None)
    ap.add_argument("--out", default="allstate_auto_quote_headless_result.json")
    ap.add_argument("--visible", action="store_true", help="Show the browser (debug)")
    ap.add_argument("--true-headless", action="store_true", help="Experimental true headless")
    args = ap.parse_args()

    mode = "visible" if args.visible else ("true-headless" if args.true_headless else "minimized-headed")
    log(f"Running mode={mode}")

    if args.input:
        profile = load_params(args.input)
        log(f"Using profile from {args.input}")
    else:
        profile = generate_fresh_profile()
        log("Generated a FRESH dummy profile for this run: "
            f"{profile['person']['first_name']} {profile['person']['last_name']} "
            f"<{profile['person']['email']}>")

    res = run_headless(params=profile, mode=mode)
    res["carrier"] = "allstate.ca (Allstate Insurance Company of Canada)"
    res["form_url"] = LANDING_URL
    res["form_kind"] = "quote"
    res["_note"] = "Unattended run via allstate_auto_quote_headless.py."

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "quote_results.jsonl"),
              "a", encoding="utf-8") as f:
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
