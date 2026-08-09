"""
canadianterminsurance_life_quote.py
===================================
Playwright automation for Canadian Term Insurance - Term life comparison quote.

Entry  : https://canadianterminsurance.ca/  (full quote form is on the HOMEPAGE)
Engine : Get a Quote posts to winquote.net/compete.pl, which opens Rank Results
         with real annual premiums from many carriers.
DB link: form_scripts table in insurance_websites.db
Form kind: QUOTE  -- returns real $ premiums (e.g. Co-operators Life $245.00/yr
           for $500k/10yr term/M/age36/non-smoker), plus a quote reference ID.

Fields (verified one at a time on the homepage):
  firstname, visitor(email), telephone, birth DOB (#selMonth/#selDay/#selYear),
  Province, First Client Gender (radio 1=M/2=F), fp_smoker_cigarette (100=No/0=Yes),
  Health Risk, Amount of Insurance, Payment Schedule, Product Type, Get a Quote.

Usage
-----
Headed:  python canadianterminsurance_life_quote.py --headed
Headless: python canadianterminsurance_life_quote.py --headless   (default)
Result persisted to canadianterminsurance_life_quote_result.json + quote_results.jsonl.
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORM_URL = "https://canadianterminsurance.ca/"

DOLLAR_RE = re.compile(r"\$\s?\d[\d,.]*")
PREMIUM_RE = re.compile(r"(\$[\d,]+\.\d{2})")


def _fill(page, name, value):
    return page.evaluate(
        """(arg) => {
            const el = document.querySelector(`input[name="${arg.name}"]`);
            if (!el) return false;
            const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
            s.call(el, arg.value);
            el.dispatchEvent(new Event('input',{bubbles:true}));
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return el.value;
        }""", {"name": name, "value": value}
    )


def _select(page, name_or_id, value):
    return page.evaluate(
        """(arg) => {
            const el = document.querySelector(`#${arg.sel}`) ||
                       Array.from(document.querySelectorAll('select')).find(s=>s.name===arg.sel || s.getAttribute('aria-label')===arg.sel);
            if (!el) return false;
            for (let i=0;i<el.options.length;i++){
                if (el.options[i].text === arg.value || el.options[i].value === arg.value){ el.selectedIndex=i; break; }
            }
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return el.options[el.selectedIndex].text;
        }""", {"sel": name_or_id, "value": value}
    )


def _click_radio(page, name, value):
    return page.evaluate(
        """(arg) => {
            const r = Array.from(document.querySelectorAll('input[type="radio"]'))
                .find(x => x.name===arg.name && x.value===String(arg.value));
            if (r) { r.checked=true; r.dispatchEvent(new Event('change',{bubbles:true})); return true; }
            return false;
        }""", {"name": name, "value": value}
    )


def run(headless: bool, params: dict | None = None) -> dict:
    result = {"quote_rankings": [], "lowest_premium": None, "reference": None, "error": None}
    params = params or {}
    V = {
        "firstname": get_param(params, "person.first_name", "John") + " " + get_param(params, "person.last_name", "Doe"),
        "visitor": get_param(params, "person.email", ""),
        "telephone": get_param(params, "person.phone", ""),
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"), viewport={"width":1400,"height":1000})
        page = context.new_page()
        try:
            page.goto(FORM_URL, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(2000)

            # Contact fields
            _fill(page, "firstname", V["firstname"])
            _fill(page, "visitor", V["visitor"])
            _fill(page, "telephone", V["telephone"])

            # DOB
            dob = get_param(params, "person.date_of_birth", "1990/03/15")
            try:
                y, m, d = dob.split("/")
                months = ["January","February","March","April","May","June","July",
                          "August","September","October","November","December"]
                _select(page, "selMonth", months[int(m)-1])
                _select(page, "selDay", str(int(d)))
                _select(page, "selYear", str(int(y)))
            except Exception:
                pass

            # Province
            _select(page, "selProvince", get_param(params, "person.province", "Ontario"))
            # Gender (Male) + Smoker (No) — click the visible toggle text, which is
            # how the form's JS records the selection (native radio set alone isn't
            # enough to trigger the custom toggle handler).
            page.get_by_text("Male", exact=True).click()
            page.get_by_text("No", exact=True).click()
            page.wait_for_timeout(500)

            # Enable + submit the Get a Quote button (it starts disabled; fields above
            # satisfy required validation but the button may not auto-enable on JS fills)
            page.evaluate("""() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Get a Quote'));
                if (btn) { btn.disabled = false; btn.click(); }
            }""")
            # Wait for the WinQuote Rank Results tab to open (opens async in a new tab).
            quotes_tab = None
            try:
                new_pg = context.wait_for_event("page", timeout=15000)
                new_pg.wait_for_load_state("domcontentloaded", timeout=20000)
                quotes_tab = new_pg
            except Exception:
                pass
            if quotes_tab is None:
                for pg in context.pages:
                    if "winquote.net" in pg.url or "Rank Results" in pg.title():
                        quotes_tab = pg
                        break
            if quotes_tab is None:
                quotes_tab = page

            quotes_tab.wait_for_load_state("domcontentloaded", timeout=20000)
            quotes_tab.wait_for_timeout(2000)

            # Parse the ranked premium table: each row has Company / Policy / Annual Premium
            # columns. Extract per-row cells directly from the results table.
            rankings = []
            for table in quotes_tab.locator("table").all():
                header_text = table.locator("tr").first.inner_text(timeout=3000)
                if "Annual Premium" not in header_text and "Company" not in header_text:
                    continue
                rows = table.locator("tr")
                n = rows.count()
                for i in range(n):
                    cells = rows.nth(i).locator("td").all_inner_texts()
                    cells = [c.strip() for c in cells]
                    if len(cells) >= 3 and PREMIUM_RE.match(cells[2]):
                        rankings.append({
                            "company": cells[0],
                            "policy": cells[1],
                            "annual_premium": cells[2],
                        })
            result["quote_rankings"] = rankings

            if result["quote_rankings"]:
                result["lowest_premium"] = min(result["quote_rankings"], key=lambda x: float(x["annual_premium"].replace("$","").replace(",","")))
                result["lowest_premium"]["rank"] = 1

            # reference / quote ID
            body = quotes_tab.locator("body").inner_text(timeout=8000)
            m = re.search(r"quote ID#\s*([\w:.]+)", body, re.I)
            if m:
                result["reference"] = m.group(1).strip()

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
    ap.add_argument("--out", default="canadianterminsurance_life_quote_result.json")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = ap.parse_args()
    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    res = run(headless=headless, params=load_params(args.input))
    res["carrier"] = "canadianterminsurance.ca"
    res["form_url"] = FORM_URL
    res["form_kind"] = "quote"

    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, args.out), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    with open(os.path.join(base, "quote_results.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")

    print("\n=== RESULT ===")
    print("  rankings_count:", len(res.get("quote_rankings", [])))
    print("  lowest_premium:", res.get("lowest_premium"))
    print("  reference:", res.get("reference"))
    print("  error:", res.get("error"))


if __name__ == "__main__":
    main()
