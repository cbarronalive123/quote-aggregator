"""
aviva_home_quote.py
===================
Playwright automation for Aviva Direct - Home (Property) Insurance online rater.

Entry  : https://www.aviva.ca/en/  (open the Direct quote modal, choose Home, postal code)
Rater  : myaviva.avivainsurance.ca/sy/bol/{landing,details,applicant,summary}
DB link: form_scripts table (aviva.ca -> aviva_home_quote.py)
Form kind: QUOTE  -- returns a real premium ($132.17/mo / $1543.32/yr, Quote # Q022754xxx).

The property rater is reached via the homepage Direct modal with the hidden
`product_type` field set to `/property` (not `/auto`). Hitting the rater URL
directly rejects the postal code with "not able to provide a quote online for your
province", so we must launch through the modal.

Flow (4 steps, each field verified via Playwright MCP):
  1. Homepage modal : Home Insurance radio + postal code -> Get a quote
  2. Property address: Search address (autofills City/Province/Street), Street number
     must be within the addressPrefill low/high range, years-lived radio, home-type
     radio (HO3=own home / HO6=condo / ten_ac=rent), coverage start date -> Continue
  3. Property details: roof year, heating, wiring, "none of the above" features -> Continue
  4. Policyholder   : first/last name, DOB, email, phone, phone type, marketing No,
     current home insurance No (+ conditional "insurance last" = Never), claims None,
     mortgage Yes, combined-policy No, credit-check consent, -> "Agree and continue"
  5. Summary        : premium + quote number captured ($/mo + $/yr)

Usage
-----
Headed:  python aviva_home_quote.py --headed
Headless: python aviva_home_quote.py --headless   (default)
Result persisted to aviva_home_quote_result.json + quote_results.jsonl.
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME_URL = "https://www.aviva.ca/en/"


def _fill(page, selector, value):
    return page.evaluate(
        """(arg) => {
            const el = document.querySelector(arg.sel);
            if (!el) return false;
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set ||
                           Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
            setter.call(el, arg.value);
            el.dispatchEvent(new Event('input',{bubbles:true}));
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return el.value;
        }""", {"sel": selector, "value": value}
    )


def _select(page, name_or_label, value):
    return page.evaluate(
        """(arg) => {
            const el = Array.from(document.querySelectorAll('select'))
                .find(s => (s.getAttribute('formcontrolname') === arg.sel)
                    || (s.getAttribute('aria-label') === arg.sel)
                    || (s.id === arg.sel));
            if (!el) return false;
            for (let i=0;i<el.options.length;i++){
                if (el.options[i].text === arg.value){ el.selectedIndex=i; break; }
            }
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return el.options[el.selectedIndex].text;
        }""", {"sel": name_or_label, "value": value}
    )


def _radio(page, radio_id):
    return page.evaluate(
        """(id) => {
            const r = document.getElementById(id);
            if (r) { r.click(); r.dispatchEvent(new Event('change',{bubbles:true})); return r.checked; }
            return null;
        }""", radio_id
    )


def _click_btn(page, text):
    return page.evaluate(
        """(text) => {
            const b = Array.from(document.querySelectorAll('button'))
                .find(b => b.textContent.trim() === text || b.textContent.includes(text));
            if (b) { b.click(); return true; }
            return false;
        }""", text
    )


def run(headless: bool, params: dict | None = None) -> dict:
    result = {"quote_value": None, "quote_per_year": None, "quote_number": None, "error": None}
    params = params or {}

    person = {
        "first": get_param(params, "person.first_name", "John"),
        "last": get_param(params, "person.last_name", "Doe"),
        "email": get_param(params, "person.email", "cormbar@msn.com"),
        "phone": get_param(params, "person.phone", "9056889170"),
        "postal": get_param(params, "person.postal_code", "L2R 1A1"),
        "dob": get_param(params, "person.date_of_birth", "1990/03/15"),
    }
    try:
        _y, _m, _d = person["dob"].split("/")
    except Exception:
        _y, _m, _d = "1990", "03", "15"

    ph = {
        "lived3": get_param(params, "property_home.lived_over_3_years", "yes"),
        "risk": get_param(params, "property_home.risk_type", "HO3"),
        "street_num": get_param(params, "property_home.street_number", "30"),
        "roof": get_param(params, "property_home.roof_last_updated", "2015"),
        "heating": get_param(params, "property_home.heating", "Natural gas - furnace"),
        "wiring": get_param(params, "property_home.wiring", "Copper 100 AMP"),
        "coverage_month": get_param(params, "property_home.coverage_start_month", "August"),
        "coverage_day": get_param(params, "property_home.coverage_start_day", "12"),
        "coverage_year": get_param(params, "property_home.coverage_start_year", "2026"),
        "marketing": get_param(params, "property_home.marketing_consent", "no"),
        "current_ins": get_param(params, "property_home.current_home_insurance", "no"),
        "ins_last": get_param(params, "property_home.insurance_last", "Never"),
        "claims": get_param(params, "property_home.claims_past_5_years", "None"),
        "mortgage": get_param(params, "property_home.mortgage", "yes"),
        "combined": get_param(params, "property_home.combined_policy", "No"),
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"), viewport={"width":1400,"height":1000})
        page = context.new_page()
        try:
            # 1) Homepage -> open Direct modal, remove survey iframe, select Home,
            #    set product_type=/property, postal code, submit.
            page.goto(HOME_URL, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_load_state("networkidle", timeout=15000)
            page.evaluate("""() => {
                document.querySelectorAll('.QSIPopOver, iframe[data-src*="qualtrics"], iframe[src*="qualtrics"]')
                    .forEach(el=>el.remove());
            }""")
            page.evaluate("""() => {
                const a = document.querySelector('a[href="#quote"]');
                if (a) a.click();
            }""")
            page.wait_for_timeout(500)
            page.evaluate("""(arg) => {
                const modal = document.querySelector('.o-modal-quickmodal');
                const form = modal.querySelector('form');
                const pt = form.querySelector('input[name="product_type"]');
                if (pt) pt.value = '/property';
                const hr = form.querySelector('input[value="home-insurance"]');
                if (hr) { hr.checked = true; hr.dispatchEvent(new Event('change',{bubbles:true})); hr.dispatchEvent(new Event('click',{bubbles:true})); }
                const pc = modal.querySelector('input[placeholder="A1A 1A1"]');
                if (pc) {
                    const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                    s.call(pc, arg.postal);
                    pc.dispatchEvent(new Event('input',{bubbles:true}));
                    pc.dispatchEvent(new Event('change',{bubbles:true}));
                }
                const btn = modal.querySelector('button[data-text="Get a quote"]');
                if (btn) { btn.click(); return 'btn-clicked'; }
                form.submit(); return 'form-submitted';
            }""", {"postal": person["postal"]})
            page.wait_for_load_state("domcontentloaded", timeout=40000)
            page.wait_for_timeout(1500)

            # 2) Property address. Fill postal + search address (autofills street), then
            #    a valid street number, radios, coverage date, Continue.
            _fill(page, 'input[placeholder="A1A 1A1"], input[aria-label="Postal code"]', person["postal"])
            _click_btn(page, "Search address")
            page.wait_for_timeout(1200)
            _fill(page, 'input[aria-label="Street number"]', ph["street_num"])
            page.wait_for_timeout(400)
            # years lived > 3 = Yes, home type = HO3
            if ph["lived3"].lower().startswith("y"):
                _radio(page, "years3-yes")
            _radio(page, "yourProperty_rad_" + ph["risk"])
            # coverage start date month/day/year
            if ph["coverage_month"]:
                page.evaluate("""(arg) => {
                    const sel = Array.from(document.querySelectorAll('select')).find(s=>s.options[0].text==='January');
                    if (sel){ for(let i=0;i<sel.options.length;i++){ if(sel.options[i].text===arg.m){ sel.selectedIndex=i; break; } }
                        sel.dispatchEvent(new Event('change',{bubbles:true})); }
                }""", {"m": ph["coverage_month"]})
            _fill(page, 'input[placeholder="DD"]', ph["coverage_day"])
            _fill(page, 'input[placeholder="YYYY"]', ph["coverage_year"])
            page.wait_for_timeout(300)
            _click_btn(page, "Continue")
            page.wait_for_timeout(1500)

            # 3) Property details: roof year, heating, wiring, none-of-the-above checkbox
            _fill(page, 'input[placeholder="Year upgrade"]', ph["roof"])
            page.evaluate("""(arg) => {
                const sel = Array.from(document.querySelectorAll('select'))
                    .find(s => Array.from(s.options).some(o=>o.text===arg.v));
                if (sel){ for(let i=0;i<sel.options.length;i++){ if(sel.options[i].text===arg.v){ sel.selectedIndex=i; break; } }
                    sel.dispatchEvent(new Event('change',{bubbles:true})); }
            }""", {"v": ph["heating"]})
            page.evaluate("""(arg) => {
                const sel = Array.from(document.querySelectorAll('select'))
                    .find(s => Array.from(s.options).some(o=>o.text===arg.v));
                if (sel){ for(let i=0;i<sel.options.length;i++){ if(sel.options[i].text===arg.v){ sel.selectedIndex=i; break; } }
                    sel.dispatchEvent(new Event('change',{bubbles:true})); }
            }""", {"v": ph["wiring"]})
            page.evaluate("""() => {
                const cb = Array.from(document.querySelectorAll('input[type="checkbox"]'))
                    .find(c => (c.closest('label')?.textContent||'').includes('None of the above'));
                if (cb) { cb.click(); cb.dispatchEvent(new Event('change',{bubbles:true})); }
            }""")
            page.wait_for_timeout(300)
            _click_btn(page, "Continue")
            page.wait_for_timeout(1500)

            # 4) Policyholder info
            _fill(page, 'input[aria-label="First name"]', person["first"])
            _fill(page, 'input[aria-label="Last name"]', person["last"])
            _fill(page, 'input[placeholder="MM"]', _m)
            _fill(page, 'input[placeholder="DD"]', _d)
            _fill(page, 'input[placeholder="YYYY"]', _y)
            _fill(page, 'input[placeholder="Please enter your email address"]', person["email"])
            _fill(page, 'input[aria-label="Phone number"]', person["phone"])
            _select(page, "phoneType", "Mobile")
            # radios
            _radio(page, "market-no")
            if ph["current_ins"].lower().startswith("n"):
                _radio(page, "CurrentIns-no")
            # conditional "When did you have insurance last?" = Never
            page.evaluate("""() => {
                const rs = Array.from(document.querySelectorAll('input[type="radio"]'));
                const t = rs.find(x => (x.closest('label')?.textContent||'').trim()==='Never');
                if (t) { t.click(); t.dispatchEvent(new Event('change',{bubbles:true})); }
            }""")
            if ph["claims"] == "None":
                _radio(page, "claims-in-5yr-yes")
            if ph["mortgage"].lower().startswith("y"):
                _radio(page, "mortgage-yes")
            if ph["combined"] == "No":
                _radio(page, "combinedPolicy_No")
            # credit-check consent checkbox
            page.evaluate("""() => {
                const cb = document.getElementById('creditCheck');
                if (cb) { cb.click(); cb.dispatchEvent(new Event('change',{bubbles:true})); }
            }""")
            page.wait_for_timeout(300)
            _click_btn(page, "Agree and continue")
            page.wait_for_timeout(2500)

            # 5) Summary: capture premium + quote number
            body = page.locator("body").inner_text(timeout=10000)
            m = re.search(r"\$\s?\d[\d,.]*\s?(?:/|\s)?(month|mo|yr|year)", body)
            if m:
                result["quote_value"] = m.group(0).strip()
            my = re.search(r"\$\s?\d[\d,.]*\s?/\s?yr", body, re.I)
            if my:
                result["quote_per_year"] = my.group(0).strip()
            q = re.search(r"Quote\s*#?\s*:\s*([\w]+)", body, re.I)
            if q:
                result["quote_number"] = q.group(1).strip()
            result["final_url"] = page.url

            if not result["quote_value"]:
                print("  [debug] final_url:", page.url, flush=True)
                print("  [debug] body head:", body[:600].replace("\\n"," "), flush=True)

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
    ap.add_argument("--out", default="aviva_home_quote_result.json")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = ap.parse_args()
    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    res = run(headless=headless, params=load_params(args.input))
    res["carrier"] = "aviva.ca"
    res["form_url"] = "https://www.aviva.ca/bin/aviva/quoter"
    res["form_kind"] = "quote"

    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, args.out), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    with open(os.path.join(base, "quote_results.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")

    print("\n=== RESULT ===")
    print("  quote_value:", res.get("quote_value"))
    print("  quote_per_year:", res.get("quote_per_year"))
    print("  quote_number:", res.get("quote_number"))
    print("  error:", res.get("error"))


if __name__ == "__main__":
    main()
