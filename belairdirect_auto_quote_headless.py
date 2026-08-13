"""
belairdirect_auto_quote_headless.py
===================================
Unattended Bel Air auto quote runner (batch / CI / no manual browser watch).

Uses the same form-fill flow as belairdirect_auto_quote.py but launches Chrome
minimized off-screen instead of true Playwright headless mode.

Why not true headless?
  Bel Air's Akamai gate blocks default Playwright headless on the homepage, and
  overriding the user-agent (needed to pass that gate) breaks the quote API.
  Minimized headed Chrome matches the working --headed script fingerprint and
  returns a real premium unattended.

Run:
  python belairdirect_auto_quote_headless.py --fresh-fake
  python belairdirect_auto_quote_headless.py --input people/fake_jordan.json
  python belairdirect_auto_quote_headless.py --visible --fresh-fake   # show browser
  python belairdirect_auto_quote_headless.py --true-headless --fresh-fake  # likely blocked
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile

from playwright.sync_api import sync_playwright

from params_loader import get_param, load_params
import belairdirect_auto_quote as bq

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Only needed for --true-headless (homepage Akamai gate); breaks quote API if used
# for the whole session — do NOT set this on the default minimized-headed path.
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _prepare_values(params: dict) -> dict:
    V = {k: get_param(params, p, "") for k, p in bq.PARAM_MAP.items()}
    year, month_name, day = bq._dob_parts(V["dob"])
    make = bq._map_make(V["vehicle_make"])
    model = bq._map_model(V["vehicle_model"])
    try:
        km = int(float((V["annual_km"] or "15000").replace(",", "")))
    except Exception:
        km = 15000
    km_band = "13,001 to 16,000 km per year"
    for low, high, band in [
        (2001, 4000, "2,001 to 4,000 km per year"),
        (4001, 6000, "4,001 to 6,000 km per year"),
        (6001, 8000, "6,001 to 8,000 km per year"),
        (8001, 10000, "8,001 to 10,000 km per year"),
        (10001, 13000, "10,001 to 13,000 km per year"),
        (13001, 16000, "13,001 to 16,000 km per year"),
        (16001, 20000, "16,001 to 20,000 km per year"),
    ]:
        if low <= km <= high:
            km_band = band
            break
    gender_id = (
        "gender-MALE-0" if str(V["gender"]).upper() == "M"
        else ("gender-FEMALE-0" if str(V["gender"]).upper() == "F" else "gender-X-0")
    )
    lic_cls = str(V["licence_class"]).upper()
    if lic_cls.startswith("G") and not lic_cls.startswith("G2"):
        lic_id = "licence-G-0"
    elif lic_cls.startswith("G2"):
        lic_id = "licence-G2-0"
    else:
        lic_id = "licence-G1-0"
    cond_id = "vehicle-acquisition-condition-2-used"
    if str(V["condition"]).lower() == "new":
        cond_id = "vehicle-acquisition-condition-2-new"
    elif str(V["condition"]).lower() == "demo":
        cond_id = "vehicle-acquisition-condition-2-demo"
    anti_id = (
        "antitheft-TRACKING_SYSTEM-2" if str(V["anti_theft"]).lower() == "yes"
        else "antitheft-NONE-2"
    )
    return {
        "V": V, "year": year, "month_name": month_name, "day": day,
        "make": make, "model": model, "km_band": km_band,
        "gender_id": gender_id, "lic_id": lic_id, "cond_id": cond_id, "anti_id": anti_id,
        "lic_month_val": V["lic_month"] or month_name,
    }


def _read_offer(page, result: dict):
    blocked = page.evaluate(
        "() => /working on it|temporarily unavailable|confirm you are human/i.test("
        "document.body.innerText || '')"
    )
    if blocked:
        result["status"] = "blocked"
        result["error"] = (
            "Bel Air rejected this session at quote generation "
            "(maintenance/unavailable or bot gate)."
        )
        bq._log("ERROR: " + result["error"])
        return
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


def fill_quote(page, vals: dict, result: dict, out_dir: str = "evidence"):
    V = vals["V"]
    bq._enter_quote(page)

    bq._log("STEP vehicle")
    bq._select_id(page, "select-year", V["vehicle_year"], by_label=True)
    bq._select_id(page, "select-make", vals["make"], by_label=True)
    page.wait_for_selector("#select-model", timeout=10000)
    bq._select_id(page, "select-model", vals["model"], by_label=True)
    bq._click_button(page, "Next: Usage")

    bq._log("STEP usage")
    page.wait_for_selector("#car-driven-km-update", timeout=15000)
    bq._set_value(page, "car-driven-km-update", V["commute"] or "15")
    bq._select_id(page, "car-annual-km", vals["km_band"], by_label=True)
    bq._radio_id(page, vals["cond_id"], on=True)
    bq._radio_id(page, vals["anti_id"], on=True)
    bq._click_button(page, "Next: Driver")

    bq._log("STEP driver")
    page.wait_for_selector("#about-firstname-0", timeout=15000)
    bq._set_value(page, "about-firstname-0", V["first_name"])
    bq._set_value(page, "about-lastname-0", V["last_name"])
    bq._radio_id(page, vals["gender_id"], on=True)
    bq._select_id(page, "dob-month-0", vals["month_name"], by_label=True)
    bq._set_value(page, "dob-day-0", vals["day"])
    bq._set_value(page, "dob-year-0", vals["year"])
    bq._set_value(page, "licence-age-input-0",
                   re.sub(r"\D", "", V["lic_age"] or "21") or "21")
    bq._radio_id(page, vals["lic_id"], on=True)
    bq._select_id(page, "driverInsuredYear-0", bq._years_value(V["years_insurer"]),
                   by_label=False)
    bq._dismiss_validation(page, lic_month_val=vals["lic_month_val"])
    bq._next_driver_to_contact(page, lic_month_val=vals["lic_month_val"])

    bq._log("STEP contact")
    page.wait_for_selector("#about-phone", timeout=15000)
    bq._set_value(page, "about-phone", V["phone"])
    bq._set_value(page, "email", V["email"])
    bq._set_value(page, "postal-code", V["postal"])
    bq._radio_id(page, "about-terms-yes", True)
    bq._radio_id(page, "about-marketing-yes", False)
    bq._wait(page, 3000, "pause before Get your price")

    bq._log("STEP get your price")
    bq._click_button(page, "Get your price")
    bq._wait(page, 12000, "waiting for the quote to generate")

    bq._log("STEP offer")
    _read_offer(page, result)

    os.makedirs(out_dir, exist_ok=True)
    shot = os.path.join(out_dir, "belairdirect_offer_headless.png")
    page.screenshot(path=shot, full_page=True)
    result["evidence"] = shot


def _launch_context(p, profile_dir: str, *, true_headless: bool, visible: bool):
    """Build browser context — default is minimized headed (works); true headless is experimental."""
    if true_headless:
        bq._log("Launch: true headless + UA (experimental; quote API often blocks)")
        return p.chromium.launch_persistent_context(
            profile_dir,
            channel="chrome",
            headless=True,
            user_agent=CHROME_UA,
            args=bq._extra_args(),
            viewport={"width": 1280, "height": 720},
            locale="en-US",
        )
    launch_args = list(bq._extra_args())
    if not visible:
        launch_args += ["--start-minimized", "--window-position=-32000,-32000"]
        bq._log("Launch: minimized headed (unattended)")
    else:
        bq._log("Launch: visible headed")
    return p.chromium.launch_persistent_context(
        profile_dir,
        channel="chrome",
        headless=False,
        args=launch_args,
        viewport={"width": 1280, "height": 720},
        locale="en-US",
    )


def run_headless(params: dict | None = None, out_dir: str = "evidence",
                 true_headless: bool = False, visible: bool = False) -> dict:
    result = {
        "quote_value": None, "quote_monthly": None, "quote_number": None,
        "coverage": {}, "status": None,
        "mode": "true_headless" if true_headless else "minimized_headed",
    }
    vals = _prepare_values(params or {})
    profile_dir = tempfile.mkdtemp(prefix="belair_headless_")

    with sync_playwright() as p:
        ctx = _launch_context(p, profile_dir, true_headless=true_headless, visible=visible)
        ctx.add_init_script(bq.STEALTH_INIT)
        page = ctx.new_page()
        page.set_default_timeout(12000)
        try:
            fill_quote(page, vals, result, out_dir=out_dir)
        except Exception as e:
            result["status"] = "blocked"
            result["error"] = str(e)
            bq._log("ERROR: " + str(e))
        finally:
            bq._shutdown_browser(ctx, page)

    shutil.rmtree(profile_dir, ignore_errors=True)
    return result


def main():
    ap = argparse.ArgumentParser(
        description="Bel Air auto quote — unattended (minimized headed) runner",
    )
    ap.add_argument("--input", default=None)
    ap.add_argument("--out", default="belairdirect_auto_quote_headless_result.json")
    ap.add_argument("--fresh-fake", action="store_true", default=False)
    ap.add_argument("--visible", action="store_true",
                    help="Show the browser window (debug)")
    ap.add_argument("--true-headless", action="store_true",
                    help="Use Playwright headless+UA (experimental; quote often blocked)")
    args = ap.parse_args()

    bq._log("Running belairdirect_auto_quote_headless.py")
    if args.fresh_fake:
        profile = bq.generate_fresh_fake()
        bq._log(f"Fresh fake profile: {profile['person']['first_name']} "
                f"{profile['person']['last_name']} <{profile['person']['email']}>")
    elif args.input:
        profile = load_params(args.input)
    else:
        try:
            from personal_profile import load_profile
        except Exception:
            def load_profile():
                return None
        profile = load_profile() or bq.generate_fresh_fake()
        bq._log("No --input / profile; using a fresh fake profile.")
    if not profile:
        profile = bq.generate_fresh_fake()

    res = run_headless(
        params=profile,
        true_headless=args.true_headless,
        visible=args.visible,
    )
    res["carrier"] = "belairdirect.com (Intact)"
    res["form_url"] = bq.MARKETING_HOME
    res["form_kind"] = "quote"
    res["_note"] = (
        "Unattended run via belairdirect_auto_quote_headless.py "
        f"(mode={res['mode']})."
    )

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quote_results.jsonl")
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")

    bq._log("=== RESULT ===")
    bq._log("  mode: " + str(res.get("mode")))
    bq._log("  quote_monthly: " + str(res.get("quote_monthly")))
    bq._log("  quote_number: " + str(res.get("quote_number")))
    bq._log("  status: " + str(res.get("status")))
    bq._log("  error: " + str(res.get("error")))
    bq._log("  saved to: " + str(out_path))


if __name__ == "__main__":
    main()
