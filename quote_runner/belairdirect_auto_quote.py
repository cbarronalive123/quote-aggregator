"""
belairdirect_auto_quote.py
==========================
Playwright automation for the belairdirect (Intact) online auto quote rater.

Entry   : https://www.belairdirect.com/  (Car button into the online rater)
Legal   : Belair Insurance Company Inc. (Intact group)
Form    : QUOTE -- returns a real premium ($/month) + quote reference.

Verified manually 2026-08-11 via a human browser -> $71.83/month (span
#price_monthly_CAR). The automated path fills the same form step by step.

WORKFLOW (matches the manual click-through):
  1. belairdirect.com -> click the visible "Car" button (adds intcid referral).
  2. Vehicle : Year / Make / Model
  3. Next: Usage
  4. Usage   : commute distance, yearly km, condition (Used), anti-theft (No)
  5. Next: Driver
  6. Driver  : first/last name, gender, DOB, first-licence age, licence class,
              years with current insurer
  7. Blur DOB fields (click a blank area) to clear transient validation
  8. Next: Contact
  9. Contact : phone, email, postal, terms consent (required), marketing (off)
 10. Get your price
 11. Read the premium from the stable element #price_monthly_CAR.

All controls live inside Angular shadow-DOM components, so every field is pinned
to its fixed element id (re-resolved at use-time by walking shadow roots). Text is
typed slowly and radios are checked with trusted Playwright actions so the session
looks less automated to Bel Air's reCAPTCHA / behavioral gate.

Run:
  python belairdirect_auto_quote.py --headed --fresh-fake      # new dummy profile
  python belairdirect_auto_quote.py --headed --input people/dummy.json
  python belairdirect_auto_quote.py --headed --keep-open       # leave browser open
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import datetime as _dt

from playwright.sync_api import sync_playwright

from params_loader import get_param, load_params
try:
    from personal_profile import load_profile  # optional: excluded from shared repo (PII)
except Exception:
    def load_profile(*a, **k):
        return None

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MARKETING_HOME = "https://www.belairdirect.com/"

PARAM_MAP = {
    "vin":            "auto.vin",
    "vehicle_year":   "auto.vehicle_year",
    "vehicle_make":   "auto.vehicle_make",
    "vehicle_model":  "auto.vehicle_model",
    "vehicle_trim":   "auto.trim",
    "vehicle_body_type": "auto.body_type",
    "vehicle_drive_type": "auto.drive_type",
    "annual_km":      "auto.annual_km",
    "commute":        "auto.commute_oneway_km",
    "condition":      "auto.purchase_condition",
    "anti_theft":     "auto.anti_theft",
    "anti_theft_system": "auto.anti_theft_system",
    "first_name":     "person.first_name",
    "last_name":      "person.last_name",
    "gender":         "person.sex",             # M -> Male, F -> Female
    "dob":            "person.date_of_birth",   # YYYY-MM-DD or YYYY/MM/DD
    "lic_age":        "driver.first_licence_age",
    "lic_month":      "driver.first_licence_month",
    "licence_class":  "driver.licence_class",
    "years_insurer":  "driver.years_with_insurer",
    "phone":          "person.phone",
    "email":          "person.email",
    "postal":         "person.postal_code",
}

_MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]

# Pacing: fill slowly so Bel Air's anti-automation gate doesn't fire.
PACE_MS = 800
TYPE_DELAY_MS = 40

# Stealth: mask the Playwright automation fingerprint (webdriver flag, languages)
# that Bel Air's reCAPTCHA would otherwise score as a bot.
STEALTH_INIT = r"""
Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => undefined, configurable: true });
Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true });
Object.defineProperty(Navigator.prototype, 'languages', { get: () => ['en-US','en'], configurable: true });
if (navigator.plugins) {
    Object.defineProperty(Navigator.prototype, 'plugins', { get: () => [1,2,3,4,5], configurable: true });
}
Object.defineProperty(window, 'chrome', { get: () => ({ runtime: {} }), configurable: true });
"""


# ---------------------------------------------------------------------------
# Logging / waits
# ---------------------------------------------------------------------------
def _now():
    return _dt.datetime.now().strftime("%H:%M:%S.%f")[:-3]


def _log(msg):
    print(f"[belair][{_now()}] {msg}", flush=True)


def _set_progress(progress_path, percent, label, attempt=1):
    """Write the current step progress (%) to a small JSON the website polls, so it
    can show a live percentage instead of just 'carrier n of N'."""
    if not progress_path:
        return
    try:
        with open(progress_path, "w", encoding="utf-8") as f:
            json.dump({"percent": int(percent), "label": label, "attempt": int(attempt),
                       "ts": _now()}, f)
    except Exception:
        pass


def _wait(page, ms, note=""):
    if ms <= 0:
        return
    _log(f"WAIT {ms}ms{(' - ' + note) if note else ''}")
    page.wait_for_timeout(ms)


# ---------------------------------------------------------------------------
# Stable shadow-DOM element access
# ---------------------------------------------------------------------------
def _resolve(page, element_id):
    """A Playwright locator that pierces shadow DOM for a fixed element id."""
    return page.locator(f"#{element_id}").first


def _set_value(page, element_id, value):
    """Type a value into a controlled input slowly (real keystrokes)."""
    loc = _resolve(page, element_id)
    _log(f"SET #{element_id} = {value!r}")
    try:
        loc.click()
        page.wait_for_timeout(200)
        loc.press_sequentially(str(value), delay=TYPE_DELAY_MS)
    except Exception:
        try:
            loc.fill(str(value))
        except Exception:
            try:
                loc.evaluate(
                    """(node, v) => {
                        const setter = Object.getOwnPropertyDescriptor(
                          window.HTMLInputElement.prototype, 'value').set;
                        setter.call(node, v);
                        node.dispatchEvent(new Event('input', {bubbles:true}));
                        node.dispatchEvent(new Event('change', {bubbles:true}));
                        node.dispatchEvent(new Event('blur', {bubbles:true}));
                    }""",
                    str(value),
                )
            except Exception:
                pass
    _wait(page, PACE_MS, f"post-fill #{element_id}")


def _select_id(page, element_id, value, by_label=True):
    """Select an option on a native <select> by its fixed id."""
    loc = _resolve(page, element_id)
    _log(f"SELECT #{element_id} = {value!r} (by_label={by_label})")
    try:
        if by_label:
            loc.select_option(label=str(value))
        else:
            loc.select_option(value=str(value))
    except Exception:
        try:
            loc.select_option(str(value))
        except Exception:
            try:
                loc.select_option(value=str(value))
            except Exception:
                pass
    _wait(page, PACE_MS, f"post-select #{element_id}")


def _select_antitheft_system(page, value: str):
    """Fill the 'Select anti-theft system' dropdown that Belair reveals when the
    anti-theft radio is set to Yes (a TRACKING_SYSTEM / anti-theft brand). Without it
    the Usage step never validates and won't advance to the Driver step.

    The control is a native <select> whose options carry ids like
    'antitheft-model-vd.antitheftmodel.TRACKING_SYSTEM-TAG-2', so we target it via
    that pattern (robust to aria-label / surrounding DOM changes)."""
    loc = page.locator(
        'select:has(option[id^="antitheft-model-"]), '
        'select[aria-label="Select anti-theft system"], '
        'select[aria-label*="Select anti-theft system"]'
    ).first
    try:
        loc.wait_for(state="attached", timeout=10000)
    except Exception:
        _log("WARN: anti-theft system dropdown not found (skipping)")
        try:
            _log("    diagnostic selects: " + str([
                (s.get_attribute("id"), s.get_attribute("aria-label"))
                for s in page.locator("select").all()][:20]))
        except Exception:
            pass
        return
    _log(f"SELECT anti-theft system = {value!r}")
    try:
        loc.select_option(value=value)
    except Exception:
        try:
            loc.select_option(label=value)
        except Exception:
            _log("WARN: could not select anti-theft system value " + repr(value))
            return
    _wait(page, PACE_MS, "post-select anti-theft system")


def _radio_id(page, element_id, on=True):
    """Check/click a radio or checkbox by fixed id (trusted action first)."""
    loc = _resolve(page, element_id)
    _log(f"RADIO/CHECK #{element_id} -> {'checked' if on else 'unchecked'}")
    try:
        if on:
            loc.check(force=True)
        else:
            loc.uncheck(force=True)
    except Exception:
        try:
            loc.click(force=True)
        except Exception:
            try:
                loc.evaluate(
                    """(node, on) => {
                        node.checked = !!on;
                        node.dispatchEvent(new Event('change', {bubbles:true}));
                        node.dispatchEvent(new Event('click', {bubbles:true}));
                    }""",
                    on,
                )
            except Exception:
                pass
    _wait(page, PACE_MS, f"post-radio #{element_id}")


def _click_button(page, label, exact=True):
    """Click a button by its visible text (searches light + shadow DOM)."""
    _log(f"CLICK button: {label!r}")
    btn = page.get_by_role("button", name=label, exact=exact).first
    try:
        btn.click()
        return True
    except Exception:
        pass
    try:
        btn.click(force=True)
        return True
    except Exception:
        pass
    try:
        btn.evaluate("(el) => el.click()")
        return True
    except Exception:
        pass
    return False


def _next_driver_to_contact(page, lic_month_val=None):
    """Move from the Driver step to the Contact step. Bel Air sometimes reveals the
    conditional "month first licensed" select (#licence-month-0) only AFTER clicking
    "Next: Contact"; if it's not set the page bounces back instead of advancing. So
    we click, and if we don't land on Contact (#about-phone visible), we set any
    revealed month field, blank-click, and retry (a few times)."""
    for attempt in range(1, 5):
        _click_button(page, "Next: Contact")
        # Give the transition a moment; check if we reached Contact.
        try:
            _resolve(page, "about-phone").wait_for(state="visible", timeout=2500)
            _log("Reached Contact step")
            return True
        except Exception:
            pass
        # Still on Driver: set the conditional month field if it appeared.
        try:
            if page.locator("#licence-month-0").count() > 0 and lic_month_val:
                _log(f"conditional #licence-month-0 appeared; setting to {lic_month_val!r}")
                _select_id(page, "licence-month-0", lic_month_val, by_label=True)
        except Exception:
            pass
        # Blank-click to clear any transient validation, then retry.
        try:
            page.mouse.click(120, 260)
            _wait(page, 900, f"blank-area click (Next: Contact retry #{attempt})")
        except Exception:
            pass
    _log("WARNING: did not reach Contact step after retries")
    return False


def _dismiss_validation(page, lic_month_val=None):
    """Clear Bel Air's transient DOB validation on the Driver step before clicking
    "Next: Contact". Simple approach: (1) fill the conditional "month first
    licensed" select if it is present, (2) click a blank area once or twice so the
    spurious "enter a valid date of birth" error clears, (3) verify the error is
    gone (and click blank again if not)."""
    # The month-first-licensed select (#licence-month-0) appears after entering the
    # licence age; if present it must be set or Next stays blocked.
    try:
        if page.locator("#licence-month-0").count() > 0 and lic_month_val:
            _select_id(page, "licence-month-0", lic_month_val, by_label=True)
    except Exception:
        pass

    for eid in ("dob-day-0", "dob-year-0", "licence-age-input-0"):
        try:
            _resolve(page, eid).evaluate(
                "(node) => { node.dispatchEvent(new Event('blur', {bubbles:true})); }")
        except Exception:
            pass
    _wait(page, 500, "post-blur")

    # Click a blank area, and keep clicking (a couple of times) until the DOB
    # validation error is gone. A single click is sometimes not enough.
    for i in range(1, 4):
        try:
            page.mouse.click(120, 260)
            _wait(page, 900, f"blank-area click #{i}")
        except Exception:
            pass
        err = page.evaluate(
            "() => /valid date of birth|month when driver/i.test(document.body.innerText || '')")
        if not err:
            _log("DOB validation cleared")
            return
        _log(f"DOB validation still present after blank click #{i}; retrying")



# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------
def _map_make(make: str) -> str:
    m = (make or "").upper()
    if "DODGE" in m or "RAM" in m:
        return "DODGE"
    return m or "DODGE"


def _map_model(model: str) -> str:
    m = (model or "").upper()
    if "1500" in m and "BIG HORN" in m and "QUAD" in m:
        return "RAM 1500 BIG HORN QUAD CAB 4WD"
    if "4X4" in m:
        return m.replace("4X4", "4WD")
    return model


# Tokens that add no discriminating value when matching a vehicle to the rater's
# option list. We score option labels by how many real tokens they contain.
_STOP = {"RAM", "1500", "CAB", "4DR", "2DR", "DR", "4X4", "X", "CREWCAB", "QUADCAB"}


def _model_tokens(model_label: str) -> set:
    """Normalize a vehicle label into a set of significant uppercase tokens."""
    import re as _re
    s = _re.sub(r"[^A-Z0-9 ]+", " ", (model_label or "").upper())
    toks = set(_re.split(r"\s+", s.strip()))
    return {t for t in toks if t and t not in _STOP and len(t) > 1}


def _build_model_label(V: dict) -> str:
    """Rebuild Belair's full model label from the profile's split vehicle fields.

    The profile stores vehicle_model='1500', trim='Big Horn', body_type='Quad Cab',
    drive_type='4WD' as separate fields, but Belair's dropdown uses one combined
    label like 'RAM 1500 BIG HORN QUAD CAB 4WD'. Prefer an already-combined model
    when present; otherwise assemble make + model + trim + body + drive.
    """
    model = (V.get("vehicle_model") or "").strip()
    # If the stored model is already the long form (contains a trim word), use it.
    if _re_find_big_horn(model):
        return model
    make = (V.get("vehicle_make") or "").upper()
    parts = [model]
    for k in ("vehicle_trim", "vehicle_body_type", "vehicle_drive_type"):
        val = (V.get(k) or "").strip()
        if val and val.lower() not in ("n/a", "none"):
            parts.append(val)
    label = " ".join(p for p in parts if p).upper()
    # Prefix the make unless the label already starts with it (e.g. RAM 1500 ...).
    if make and not label.startswith(make.split()[0]):
        label = f"{make} {label}".strip()
    return label


def _re_find_big_horn(model: str) -> bool:
    m = (model or "").upper()
    return "1500" in m and ("BIG HORN" in m or "LARAMIE" in m or "SPORT" in m or "SLT" in m)


def _select_model_robust(page, target: str, select_id: str = "select-model"):
    """Select the model whose option label best matches the target, adapting to the
    rater's option list even if labels/trim words change. Exact match wins; otherwise
    the option containing the most significant tokens of the target is chosen."""
    loc = _resolve(page, select_id)
    opts = loc.locator("option")
    try:
        entries = []
        count = opts.count()
        for i in range(count):
            text = (opts.nth(i).text_content() or "").strip()
            value = opts.nth(i).get_attribute("value") or ""
            if not text or text.lower() in ("select...", "select"):
                continue
            entries.append({"text": text, "value": value})
    except Exception:
        entries = []
    if not entries:
        _log(f"    WARN no options found for #{select_id}")
        return
    target_tokens = _model_tokens(target)
    best = None
    best_score = -1
    for e in entries:
        score = len(_model_tokens(e["text"]) & target_tokens)
        # bonus for exact match
        if e["text"].strip().upper() == target.upper():
            score += 1000
        if score > best_score:
            best_score = score
            best = e
    chosen = best["text"] if best else target
    _log(f"    SELECT #{select_id} = {chosen!r} (best match, score={best_score})")
    try:
        loc.select_option(label=chosen)
    except Exception:
        try:
            loc.select_option(value=best["value"])
        except Exception:
            loc.select_option(value=target)
    _wait(page, PACE_MS, f"post-select #{select_id}")


def _years_value(y):
    y = (y or "").lower()
    if "never" in y:
        return "0-NONE"
    if "not currently" in y or "past" in y:
        return "0-OTHER"
    if "between" in y and "3" in y and "5" in y:
        return "3-OTHER"
    if "5" in y:
        return "5-OTHER"
    return "1-OTHER"


def _dob_parts(dob: str):
    dob = (dob or "1985/05/10").strip().replace("-", "/")
    try:
        y, mo, d = dob.split("/")
        return y, _MONTHS[int(mo)], d
    except Exception:
        return "1985", "May", "10"


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------
def _enter_quote(page):
    """Start at belairdirect.com and click the visible Car button into the rater."""
    _log(f"NAVIGATE to {MARKETING_HOME}")
    page.goto(MARKETING_HOME, wait_until="domcontentloaded", timeout=60000)
    _wait(page, 2500, "homepage settle")
    # Remove the exit-intent overlay so it doesn't swallow the Car click.
    try:
        page.evaluate("() => { const ov = document.getElementById('exitIntentOverlay'); if (ov) ov.remove(); }")
    except Exception:
        pass
    btn = page.locator("#carBtn:visible, button[data-btnid='toppageQQAuto']:visible").first
    btn.wait_for(state="visible", timeout=10000)
    _log("CLICK homepage 'Car' button")
    _click_button(page, "Car", exact=True)
    _wait(page, 2500, "rater entry settle")
    page.wait_for_selector("#select-year", timeout=20000)
    _log(f"Entered rater (url={page.url})")


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------
def _extra_args():
    """Container-safe Chrome flags. Chromium's sandbox can't start when running as
    root (e.g. inside a Docker container), so add --no-sandbox / --disable-dev-shm-usage
    only there; harmless to leave off on a normal desktop login."""
    try:
        if os.name == "posix" and os.geteuid() == 0:
            return ["--no-sandbox", "--disable-dev-shm-usage"]
    except Exception:
        pass
    return []


def _shutdown_browser(ctx, page=None):
    """Close all tabs and the persistent context so Chrome exits (needed on server/CI)."""
    _log("CLOSE browser")
    if page is not None:
        try:
            page.close()
        except Exception:
            pass
    try:
        for tab in list(ctx.pages):
            try:
                tab.close()
            except Exception:
                pass
    except Exception:
        pass
    try:
        ctx.close()
    except Exception as e:
        _log(f"WARN ctx.close failed: {e}")


def run(headless: bool, params: dict | None = None, out_dir: str = "evidence",
        keep_open: bool = False, minimized: bool = False, progress_path: str | None = None,
        max_retries: int = 2) -> dict:
    result = {"quote_value": None, "quote_monthly": None, "quote_number": None,
              "coverage": {}, "status": None}
    params = params or {}
    V = {k: get_param(params, p, "") for k, p in PARAM_MAP.items()}
    year, month_name, day = _dob_parts(V["dob"])
    make = _map_make(V["vehicle_make"])
    model = _build_model_label(V)
    try:
        km = int(float((V["annual_km"] or "15000").replace(",", "")))
    except Exception:
        km = 15000
    km_band = "13,001 to 16,000 km per year"
    for low, high, band in [(2001, 4000, "2,001 to 4,000 km per year"),
                            (4001, 6000, "4,001 to 6,000 km per year"),
                            (6001, 8000, "6,001 to 8,000 km per year"),
                            (8001, 10000, "8,001 to 10,000 km per year"),
                            (10001, 13000, "10,001 to 13,000 km per year"),
                            (13001, 16000, "13,001 to 16,000 km per year"),
                            (16001, 20000, "16,001 to 20,000 km per year")]:
        if low <= km <= high:
            km_band = band
            break
    gender_id = "gender-MALE-0" if str(V["gender"]).upper() == "M" else \
                ("gender-FEMALE-0" if str(V["gender"]).upper() == "F" else "gender-X-0")
    # Belair's PARAM_MAP reads driver.licence_class; fall back to auto.licence_class
    # (e.g. the real profile stores it there) so a full-G licence isn't mis-filled as G1.
    lic_value = str(V.get("licence_class") or get_param(params, "auto.licence_class", "") or "G").upper()
    lic_id = "licence-G-0" if lic_value.startswith("G") and not lic_value.startswith("G2") else \
             ("licence-G2-0" if lic_value.startswith("G2") else "licence-G1-0")
    cond_id = "vehicle-acquisition-condition-2-used"
    if str(V["condition"]).lower() == "new":
        cond_id = "vehicle-acquisition-condition-2-new"
    elif str(V["condition"]).lower() == "demo":
        cond_id = "vehicle-acquisition-condition-2-demo"
    anti_id = "antitheft-TRACKING_SYSTEM-2" if str(V["anti_theft"]).lower() == "yes" \
        else "antitheft-NONE-2"

    # The Bel Air rater's promotional/exit modals are intermittent and can swallow
    # button clicks. Since the modal rarely shows twice in a row, retry the ENTIRE
    # flow from scratch (fresh browser) once if the first attempt doesn't produce a
    # quote. Both attempts run with a brand-new temp profile.
    for attempt in range(1, max_retries + 1):
        result = {"quote_value": None, "quote_monthly": None, "quote_number": None,
                  "coverage": {}, "status": None, "error": None}
        _log(f"ATTEMPT {attempt}/{max_retries} of the whole Bel Air flow")
        _set_progress(progress_path, 3, f"starting attempt {attempt}", attempt)
        try:
            profile_dir = tempfile.mkdtemp(prefix="belair_quote_")
        except Exception:
            profile_dir = None
        with sync_playwright() as p:
            _launch_kw = dict(
                channel="chrome",
                headless=headless,
                viewport={"width": 1280, "height": 720},
                locale="en-US",
            )
            if minimized and not headless:
                _launch_kw["args"] = _extra_args() + ["--start-minimized", "--window-position=-32000,-32000"]
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir or tempfile.mkdtemp(prefix="belair_quote_"),
                **_launch_kw,
            )
            ctx.add_init_script(STEALTH_INIT)
            page = ctx.new_page()
            page.set_default_timeout(12000)
            try:
                # 0) Entry
                _enter_quote(page)
                _set_progress(progress_path, 8, "entered quote", attempt)

                # 1) Vehicle
                _log("STEP vehicle")
                _select_id(page, "select-year", V["vehicle_year"], by_label=True)
                _select_id(page, "select-make", make, by_label=True)
                _log("WAIT for #select-model")
                page.wait_for_selector("#select-model", timeout=10000)
                _select_model_robust(page, model)
                _click_button(page, "Next: Usage")
                _set_progress(progress_path, 30, "vehicle", attempt)

                # 2) Usage
                _log("STEP usage")
                page.wait_for_selector("#car-driven-km-update", timeout=15000)
                _set_value(page, "car-driven-km-update", V["commute"] or "15")
                _select_id(page, "car-annual-km", km_band, by_label=True)
                _radio_id(page, cond_id, on=True)
                _radio_id(page, anti_id, on=True)
                if str(V["anti_theft"]).lower() == "yes":
                    # Belair reveals a "Select anti-theft system" dropdown only when
                    # the anti-theft answer is Yes; it must be filled or Usage won't
                    # validate.
                    _select_antitheft_system(page, V.get("anti_theft_system") or "TAG")
                _click_button(page, "Next: Driver")
                _set_progress(progress_path, 45, "usage", attempt)

                # 3) Driver
                _log("STEP driver")
                page.wait_for_selector("#about-firstname-0", timeout=15000)
                _set_value(page, "about-firstname-0", V["first_name"])
                _set_value(page, "about-lastname-0", V["last_name"])
                _radio_id(page, gender_id, on=True)
                _select_id(page, "dob-month-0", month_name, by_label=True)
                _set_value(page, "dob-day-0", day)
                _set_value(page, "dob-year-0", year)
                _set_value(page, "licence-age-input-0",
                           re.sub(r"\D", "", V["lic_age"] or "21") or "21")
                lic_month_val = V["lic_month"] or month_name
                _radio_id(page, lic_id, on=True)
                _select_id(page, "driverInsuredYear-0", _years_value(V["years_insurer"]),
                           by_label=False)
                # Clear transient DOB validation (also sets the conditional month if
                # present), then go to Contact.
                _dismiss_validation(page, lic_month_val=lic_month_val)
                _next_driver_to_contact(page, lic_month_val=lic_month_val)
                _set_progress(progress_path, 65, "driver", attempt)

                # 4) Contact
                _log("STEP contact")
                page.wait_for_selector("#about-phone", timeout=15000)
                _set_value(page, "about-phone", V["phone"])
                _set_value(page, "email", V["email"])
                _set_value(page, "postal-code", V["postal"])
                _radio_id(page, "about-terms-yes", True)
                _radio_id(page, "about-marketing-yes", False)
                _wait(page, 3000, "pause before Get your price")
                _set_progress(progress_path, 85, "contact", attempt)

                # 5) Get your price (quiet single click, then passive wait)
                _log("STEP get your price")
                _click_button(page, "Get your price")
                _wait(page, 12000, "waiting for the quote to generate")
                _set_progress(progress_path, 95, "pricing", attempt)

                # 6) Offer -- price is in stable element #price_monthly_CAR
                _log("STEP offer")
                try:
                    price_loc = page.locator("#price_monthly_CAR").first
                    price_loc.wait_for(state="visible", timeout=12000)
                    t = price_loc.inner_text() or (price_loc.text_content() or "")
                    mm = re.search(r"([\d,]+\.\d{2})", t)
                    if mm:
                        result["quote_value"] = mm.group(1)
                        result["quote_monthly"] = "$" + mm.group(1) + " /month"
                        result["status"] = "quoted_comparable_candidate"
                    else:
                        result["status"] = "unresolved"
                except Exception:
                    result["status"] = "unresolved"
                # Fallback: older "Canadian dollars ... month" text layout.
                if not result.get("quote_value"):
                    try:
                        el = page.get_by_text(re.compile(r"Canadian dollars\s*month", re.I)).first
                        el.wait_for(state="visible", timeout=6000)
                        t = el.inner_text()
                        mm = re.search(r"([\d,]+\.\d{2})", t)
                        if mm:
                            result["quote_value"] = mm.group(1)
                            result["quote_monthly"] = "$" + mm.group(1) + " /month"
                            result["status"] = "quoted_comparable_candidate"
                    except Exception:
                        pass
                try:
                    q = page.get_by_text(re.compile(r"Car quote\s*#", re.I)).first.inner_text()
                    qq = re.search(r"(BA\d{6,})", q)
                    if qq:
                        result["quote_number"] = qq.group(1)
                except Exception:
                    pass

                os.makedirs(out_dir, exist_ok=True)
                shot = os.path.join(out_dir, "belairdirect_offer.png")
                page.screenshot(path=shot, full_page=True)
                result["evidence"] = shot
                _set_progress(progress_path, 100, "offer", attempt)

            except Exception as e:
                result["status"] = "blocked"
                result["error"] = str(e)
                _log("ERROR: " + str(e))

            finally:
                if keep_open and not headless and not minimized and (
                        result.get("quote_value") or attempt == 2):
                    _log("--keep-open: holding browser open; press Ctrl+C to exit")
                    try:
                        while True:
                            page.wait_for_timeout(60000)
                    except Exception:
                        pass
                elif not keep_open and not headless and not minimized:
                    try:
                        page.wait_for_timeout(1500)
                    except Exception:
                        pass
                _shutdown_browser(ctx, page)
        if profile_dir and not keep_open:
            try:
                shutil.rmtree(profile_dir, ignore_errors=True)
            except Exception:
                pass
        if result.get("quote_value"):
            break
        if attempt == 1:
            _log("Bel Air flow failed on attempt 1; retrying the whole process from scratch")
    return result


def generate_fresh_fake():
    """A new randomized dummy profile per run so repeat tests don't reuse the same
    identity (which Bel Air flags). NOT a real person -- never valid evidence."""
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
    year = _random.randint(1975, 1995)
    month = _random.randint(1, 12)
    day = _random.randint(1, 28)
    age = _random.randint(18, 25)
    return {
        "_comment": "Auto-generated FRESH dummy test data. NOT a real person.",
        "person": {
            "first_name": first, "last_name": last,
            "email": email, "phone": phone, "phone_type": "Cell",
            "date_of_birth": f"{year}/{month:02d}/{day:02d}",
            "sex": sex, "marital_status": _random.choice(["Single", "Married"]),
            "street_address": f"{_random.randint(1, 999)} Test St",
            "city": "Toronto", "province": "Ontario", "province_code": "ON",
            "postal_code": "M5V 2T6", "tenure": _random.choice(["renting", "owning"]),
        },
        "auto": {
            "vin": "1HGCM82633A004352", "vehicle_year": "2019",
            "vehicle_make": "HONDA", "vehicle_model": "ACCORD EX 4DR",
            "type_of_use": "Personal", "purchase_month": "January", "purchase_year": "2019",
            "purchase_condition": "Used", "owned_leased": "Purchased and completely paid off",
            "modified": "No", "tracking_system": "None", "winter_tires": "Yes",
            "parking_overnight": "Parking lot", "annual_km": "15000",
            "commute_oneway_km": "15", "used_in_us": "No", "additional_vehicle": "No",
        },
        "driver": {
            "employment_status": "Employed",
            "licence_class": "G (full licence)", "licence_from_elsewhere": "No",
            "licence_suspended": "No", "convictions_3yr": "No",
            "claims_10yr": "No claims to declare", "marketing_consent": "No",
            "first_licence_age": f"{age} years old",
            "first_licence_month": _MONTHS[month],
            "current_insurer": "Broker", "years_with_insurer": "5 years",
            "additional_driver": "No", "owner_self": f"{first} {last}",
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true", default=False)
    ap.add_argument("--headed", action="store_true", default=False)
    ap.add_argument("--input", default=None)
    ap.add_argument("--out", default="belairdirect_auto_quote_result.json")
    ap.add_argument("--fresh-fake", action="store_true", default=False,
                    help="Generate a fresh randomized dummy profile for this run.")
    ap.add_argument("--keep-open", action="store_true", default=False,
                    help="Keep the headed browser open at the end.")
    ap.add_argument("--minimized", action="store_true", default=False,
                    help="Run headed but minimized/off-screen (unattended; needs Xvfb).")
    ap.add_argument("--progress", default=None,
                    help="Path to write live % step progress (website reads this).")
    ap.add_argument("--retries", type=int, default=2,
                    help="How many times to retry the whole flow from scratch if no quote.")
    args = ap.parse_args()

    headless = (not args.headed) and (not args.minimized)
    _log(f"Running {'HEADED' if not headless else 'HEADLESS'} mode")
    if args.fresh_fake:
        profile = generate_fresh_fake()
        _log(f"Fresh fake profile: {profile['person']['first_name']} "
             f"{profile['person']['last_name']} <{profile['person']['email']}>")
    elif not args.input:
        profile = load_profile() or generate_fresh_fake()
        _log("No --input / profile; using a fresh fake profile.")
    else:
        profile = load_params(args.input)
    if not profile:
        profile = generate_fresh_fake()

    res = run(headless=headless, params=profile,
              keep_open=args.keep_open and not args.minimized, minimized=args.minimized,
              progress_path=args.progress, max_retries=args.retries)
    res["carrier"] = "belairdirect.com (Intact)"
    res["form_url"] = MARKETING_HOME
    res["form_kind"] = "quote"
    res["_note"] = ("Mock/dummy data if --input people/*.json or --fresh-fake, else the "
                    "real profile. Not valid evidence when dummy/fake data is used.")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quote_results.jsonl")
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")

    _log("=== RESULT ===")
    _log("  quote_monthly: " + str(res.get("quote_monthly")))
    _log("  quote_number: " + str(res.get("quote_number")))
    _log("  status: " + str(res.get("status")))
    _log("  error: " + str(res.get("error")))
    _log("  saved to: " + str(out_path))


if __name__ == "__main__":
    main()
