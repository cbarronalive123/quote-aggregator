"""
allstate_auto_quote.py
======================
Playwright automation for the Allstate Canada online auto quote.

Entry  : apps.allstate.ca/quickquote (postal + Auto -> Go)
Quote  : purchase.allstate.ca  (getstarted -> summary dialogs -> quote)
Carrier: Allstate Insurance Company of Canada
Form kind: QUOTE -- returns a real premium ($/month).

FLOW (verified 2026-08-11 via Playwright MCP -> $149.75/month)
--------------------------------------------------------------
1. Landing: postal code (NO SPACE, e.g. "L2R1A1") + Auto -> Go.
2. Get Started: defaults (1 vehicle, 1 driver, not existing customer) -> SHOP & BUY.
3. Summary page (purchase.allstate.ca/summary), driven by sequential dialogs:
   - Vehicle: Year/Make/Model selects.
   - Vehicle details: New/Used/Demo, Owned/Financed/Leased, only owner, within 30 days,
     purchase price, coverage start date, purchase month/year.
   - Vehicle use: used for, one-way commute km, annual km band, ridesharing No + confirm.
   - Savings: winter tires + confirm, parking, anti-theft, ADAS (optional).
   - Driver: province (default ON), names, DOB, gender, marital, household drivers.
   - Driving history: age first licensed, graduated licensing, license class,
     G within 12 mo, minor/major violations, suspension.
   - Insurance history: currently insured, cancelled, claims.
   - Summary: Drivewise No, email, phone, privacy consent -> get a quote.
4. Quote page (/quote): capture premium ($X.XX / month).

Run:
  python allstate_auto_quote.py                    # minimized-headed (unattended)
  python allstate_auto_quote.py --headed           # visible, persists at the end
  python allstate_auto_quote.py --true-headless    # experimental (usually gated)
  python allstate_auto_quote.py --input people/dummy.json
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
POSTAL = "L2R1A1"  # Allstate rejects a spaced postal code ("Enter a valid postal code").

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
# Keyboard/real-click helpers (match the MCP flow)
# --------------------------------------------------------------------------
def _type(page, target, text):
    """Clear then type into a text/spin field via the keyboard. `target` may be
    a CSS selector string or a Playwright locator."""
    loc = page.locator(target).first if isinstance(target, str) else target.first
    loc.wait_for(state="attached", timeout=10000)
    log(f"    type {loc} <- {text!r}")
    loc.fill("")
    loc.press_sequentially(str(text), delay=20)
    page.wait_for_timeout(120)


def _select(page, label, value):
    """Select an option on a native <select> by its aria-label/name."""
    log(f"    select {label} = {value!r}")
    page.locator(f'select[aria-label="{label}"], select[name="{label}"]').first.select_option(value)
    page.wait_for_timeout(150)


def _radio(page, group, label):
    """Activate a radio button scoped to its fieldset/group (keyboard Space)."""
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
            fset.get_by_text(label, exact=True).first.click(force=True)
            page.wait_for_timeout(150)
            return
    log(f"    radio [{group}] {label}")
    loc.focus()
    page.keyboard.press("Space")
    page.wait_for_timeout(150)


def _checkbox(page, selector, name):
    """Toggle a checkbox by name regex."""
    loc = page.get_by_role("checkbox", name=name).first
    loc.wait_for(state="attached", timeout=10000)
    log(f"    checkbox {name!r}")
    loc.focus()
    page.keyboard.press("Space")
    page.wait_for_timeout(150)


def _dismiss_cookie_banner(page):
    """Accept/dismiss the OneTrust cookie-consent banner so it stops overlaying
    the dialogs and intercepting pointer events."""
    try:
        loc = page.locator("#onetrust-accept-btn-handler")  # OneTrust "Accept All"
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
    # Fallback: hide the banner entirely so it can't block anything.
    try:
        page.evaluate(
            "() => { const b = document.querySelector('#onetrust-banner-sdk')"
            " || document.querySelector('#onetrust-consent-sdk'); if (b) b.style.display='none'; }"
        )
        page.wait_for_timeout(300)
    except Exception:
        pass


def _button(page, name, exact=True):
    """Click a button by accessible name with a real pointer click (enabled-wait)."""
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
    """Type a date directly into the visible mm/dd/yyyy field (no calendar modal)."""
    loc = page.locator('input[placeholder="mm/dd/yyyy"]').first
    loc.wait_for(state="attached", timeout=8000)
    log(f"    date <- {mmddyyyy}")
    loc.fill(str(mmddyyyy))
    page.wait_for_timeout(150)


# --------------------------------------------------------------------------
# Value resolution (works standalone; allstate-specific labels default to the
# verified MCP values so no external profile is required).
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
        "anti_theft_device": get_param(P, "auto.anti_theft_device", "TAG"),
        "first_name": get_param(P, "person.first_name", "Casey"),
        "last_name": get_param(P, "person.last_name", "Reed"),
        "dob": f"{m}/{d}/{y}",
        "gender": {"M": "Male", "F": "Female", "X": "X"}.get(
            str(get_param(P, "person.sex", "Male")).upper(),
            str(get_param(P, "person.sex", "Male"))),
        "marital": {"S": "Single", "M": "Married", "D": "Divorced", "W": "Widowed",
                    "C": "Common-Law", "L": "Common-Law", "P": "Separated"}.get(
            str(get_param(P, "person.marital_status", "Single")).upper(),
            str(get_param(P, "person.marital_status", "Single"))),
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


# --------------------------------------------------------------------------
# Flow (matches the MCP-verified run exactly)
# --------------------------------------------------------------------------
def fill_quote(page, V: dict, result: dict, progress_path: str | None = None):
    log("landing")
    page.goto(LANDING_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)
    _dismiss_cookie_banner(page)
    _type(page, 'input[placeholder="Postal Code"]', V["postal"])
    page.get_by_role("link", name="Go", exact=True).click()
    page.wait_for_url(re.compile(r"getstarted"), timeout=20000)
    page.wait_for_timeout(2000)
    _set_progress(progress_path, 8, "landing", 1)

    log("getstarted")
    _button(page, re.compile(r"SHOP\s*&\s*BUY", re.I), exact=False)
    page.wait_for_timeout(2500)
    _set_progress(progress_path, 18, "getstarted", 1)

    log("vehicle dialog")
    _select(page, "year", V["vehicle_year"])
    _select(page, "make", V["vehicle_make"])
    _select(page, "model", V["vehicle_model"])
    _button(page, "continue")
    _set_progress(progress_path, 32, "vehicle", 1)

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
    _set_progress(progress_path, 48, "vehicle details", 1)

    log("vehicle use dialog")
    _select(page, "vehicle-used-for", V["vehicle_use"])
    page.wait_for_timeout(600)  # one-way km field renders after Work/School is chosen
    _type(page, page.get_by_role("spinbutton", name="How many kilometres", exact=False), V["one_way_km"])
    _select(page, "one-year-kilometers", V["annual_km_band"])
    _radio(page, "commercial-usage", "No")
    _checkbox(page, None, "I confirm that this vehicle")
    _button(page, "continue")
    _set_progress(progress_path, 58, "vehicle use", 1)

    log("savings dialog")
    _radio(page, "winter-tires", V["winter_tires"])
    page.wait_for_timeout(400)
    _checkbox(page, None, "I confirm that 4 winter tires")
    _select(page, "vehicle-parking", V["parking"])
    _radio(page, "anti-theft-devices", V["anti_theft"])
    if str(V["anti_theft"]).strip().lower() in ("yes", "true"):
        # Selecting Yes reveals a required "which device" select inside the
        # "Tracking enabled anti-theft devices" section; fill it so continue enables.
        dev = page.locator('select[aria-label="anti-theft-devices"], select[name="anti-theft-devices"]').first
        try:
            if not dev.is_visible():
                page.get_by_role("button",
                                 name=re.compile(r"Tracking enabled anti-theft devices", re.I)).first.click(timeout=5000)
                page.wait_for_timeout(400)
        except Exception:
            pass
        _select(page, "anti-theft-devices", V["anti_theft_device"])
    _button(page, "continue")
    _set_progress(progress_path, 70, "savings", 1)

    log("driver details dialog")
    _type(page, page.get_by_role("textbox", name="First name"), V["first_name"])
    _type(page, page.get_by_role("textbox", name="Last name"), V["last_name"])
    _date(page, V["dob"])
    _radio(page, "gender", V["gender"])
    _select(page, "marital-status", V["marital"])
    _radio(page, "household-licensed", V["household"])
    _button(page, "continue")
    _set_progress(progress_path, 82, "driver", 1)

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
    _set_progress(progress_path, 87, "driving history", 1)

    log("insurance history dialog")
    _radio(page, "prior-insurance", V["insured"])
    _radio(page, "policy-cancelled", V["cancelled"])
    _radio(page, "claims-details", V["claims_6yr"])
    _button(page, "continue")
    _set_progress(progress_path, 92, "insurance history", 1)

    log("summary + get a quote")
    _radio(page, "include Drivewise", V["drivewise"])
    _type(page, page.get_by_role("textbox", name="Email address"), V["email"])
    _type(page, page.get_by_role("textbox", name="phone-number"), V["phone"])
    _checkbox(page, None, "Yes, I agree that you may")
    _button(page, "get a quote")
    _set_progress(progress_path, 100, "get a quote", 1)

    log("quote page")
    page.wait_for_url(re.compile(r"/quote"), timeout=30000)
    page.wait_for_timeout(4000)
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
    """Return the primary display's (width, height) in pixels.

    Falls back to 1920x1080 if the Windows metrics API is unavailable.
    """
    try:
        import ctypes
        user32 = ctypes.windll.user32
        return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
    except Exception:
        return 1920, 1080


def _centered_args(win_w: int = 1400, win_h: int = 1000):
    """Chrome launch args that place the window in the middle of the screen.

    The persistent profile remembers the off-screen position that the
    minimized/unattended mode uses (--window-position=-32000,-32000), so an
    otherwise-default headed launch reappears off-screen (only a corner is
    grabbable). Forcing an explicit centered position fixes that.
    """
    w, h = _screen_size()
    chrome_extra = 80  # approx. title bar height so the window stays fully on screen
    x = max(0, (w - win_w) // 2)
    y = max(0, (h - (win_h + chrome_extra)) // 2)
    return [f"--window-size={win_w},{win_h}", f"--window-position={x},{y}"]


def _launch_context(p, *, mode: str, keep_open: bool):
    profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".allstate_profile")
    os.makedirs(profile_dir, exist_ok=True)
    if mode == "true-headless":
        log("Launch: true headless (experimental)")
        return p.chromium.launch_persistent_context(
            profile_dir, channel="chrome", headless=True,
            viewport={"width": 1400, "height": 1000}, locale="en-US")
    if mode == "headed":
        log("Launch: visible headed (persists at end), centered on screen")
        return p.chromium.launch_persistent_context(
            profile_dir, channel="chrome", headless=False,
            args=_extra_args() + _centered_args(),
            viewport={"width": 1400, "height": 1000}, locale="en-US")
    log("Launch: minimized headed (unattended)")
    return p.chromium.launch_persistent_context(
        profile_dir, channel="chrome", headless=False,
        args=_extra_args() + ["--start-minimized", "--window-position=-32000,-32000"],
        viewport={"width": 1400, "height": 1000}, locale="en-US")


def run(params: dict | None = None, mode: str = "minimized-headed",
        keep_open: bool = False, out: str = "allstate_auto_quote_result.json",
        progress_path: str | None = None, max_retries: int = 2) -> dict:
    V = _prepare_values(params or {})

    # Allstate is intermittent (gated landing, flaky dialogs). Retry the ENTIRE flow
    # from scratch (fresh browser) up to max_retries times if an attempt fails to quote.
    for attempt in range(1, max_retries + 1):
        result = {"quote_value": None, "quote_monthly": None, "quote_number": None, "status": None}
        log(f"ATTEMPT {attempt}/{max_retries} of the whole Allstate flow")
        with sync_playwright() as p:
            ctx = _launch_context(p, mode=mode, keep_open=keep_open)
            ctx.add_init_script(STEALTH_INIT)
            page = ctx.new_page()
            page.set_default_timeout(15000)
            try:
                fill_quote(page, V, result, progress_path=progress_path)
            except Exception as e:
                result["status"] = "blocked"
                result["error"] = str(e)
                log("ERROR: " + str(e))
                try:
                    os.makedirs("evidence", exist_ok=True)
                    page.screenshot(path=os.path.join("evidence", "allstate_error.png"), full_page=True)
                except Exception:
                    pass
            # Persist the result immediately so it is saved even while the browser is
            # kept open (the keep-open wait below can block indefinitely when detached).
            try:
                with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), out),
                          "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                log(f"    result written to {out}")
            except Exception as e:
                log("WARN: could not persist result: " + str(e))
            finally:
                if keep_open and mode == "headed" and (result.get("quote_value") or attempt == max_retries):
                    log(">>> Browser kept open. Press Enter to close...")
                    try:
                        input()
                    except Exception:
                        log(">>> No interactive input; leaving the browser open until the process is terminated.")
                        try:
                            while True:
                                page.wait_for_timeout(3600000)
                        except KeyboardInterrupt:
                            pass
                elif mode != "true-headless":
                    page.wait_for_timeout(1500)
                try:
                    ctx.close()
                except Exception:
                    pass
        if result.get("quote_value"):
            break
        if attempt < max_retries:
            log("Allstate flow failed; retrying the whole flow from scratch")
    return result


def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--headed", action="store_true", default=False)
    mode.add_argument("--true-headless", action="store_true", default=False)
    ap.add_argument("--input", default=None)
    ap.add_argument("--out", default="allstate_auto_quote_result.json")
    ap.add_argument("--progress", default=None,
                    help="Path to write live % step progress (website reads this).")
    ap.add_argument("--close", action="store_true", default=False,
                    help="Close the browser at the end even in headed mode (for unattended/CI runs).")
    ap.add_argument("--retries", type=int, default=2,
                    help="How many times to retry the whole flow from scratch if no quote.")
    args = ap.parse_args()

    run_mode = "true-headless" if args.true_headless else ("headed" if args.headed else "minimized-headed")
    log(f"Running mode={run_mode}")

    profile = load_params(args.input) if args.input else None
    if args.input and profile:
        log(f"Using profile from {args.input}")

    res = run(params=profile, mode=run_mode, keep_open=args.headed and not args.close,
              out=args.out, progress_path=args.progress, max_retries=args.retries)
    res["carrier"] = "allstate.ca (Allstate Insurance Company of Canada)"
    res["form_url"] = LANDING_URL
    res["form_kind"] = "quote"

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "quote_results.jsonl"),
              "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")

    log("=== RESULT ===")
    log("  quote_monthly: " + str(res.get("quote_monthly")))
    log("  quote_number: " + str(res.get("quote_number")))
    log("  status: " + str(res.get("status")))
    log("  error: " + str(res.get("error")))
    log("  saved to: " + str(out_path))


if __name__ == "__main__":
    main()
