"""
gpsequipeconseil_life_quote.py
==============================
Playwright automation for GPS Équipe conseil - Life insurance comparison quote.

Form URL : https://gpsequipeconseil.com/  (WinQuote form embedded on the homepage)
Engine   : "Obtenir mon prix!" posts to winquote.net/cgi-bin/compete.pl, which returns
           a ranked Report table of annual premiums from many carriers.
DB link  : form_scripts table in insurance_websites.db
Form kind: QUOTE  -- returns real $ premiums (e.g. Beneva/BMO $360.00/yr for
           $500k / 20-yr term / Male / age 36 / non-smoker / QC / annual), plus a
           quote reference ID.

Fields (verified one at a time; WinQuote field names):
  First Client Name, First Client Phone, First Client Email, month/day/year (DOB),
  First Client Gender (Homme/Femme), fp_smoker (Oui/Non), Province (Quebec),
  First Client Premium Amount ($ 500,000), Payment Schedule (Annuel),
  Product Type (Temporaire 20 ans), Risk option (Regular).

Usage
-----
Headed:  python gpsequipeconseil_life_quote.py --headed
Headless: python gpsequipeconseil_life_quote.py --headless   (default)
Result persisted to gpsequipeconseil_life_quote_result.json + quote_results.jsonl.
"""

import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

from params_loader import load_params, get_param

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORM_URL = "https://gpsequipeconseil.com/"

PREMIUM_RE = re.compile(r"([\d,]+\.\d{2})\s*\$")


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


def _select(page, name, value):
    return page.evaluate(
        """(arg) => {
            const el = document.querySelector(`select[name="${arg.name}"]`);
            if (!el) return false;
            for (let i=0;i<el.options.length;i++){
                if (el.options[i].value === arg.value || el.options[i].text === arg.value){ el.selectedIndex=i; break; }
            }
            el.dispatchEvent(new Event('change',{bubbles:true}));
            return el.options[el.selectedIndex].text;
        }""", {"name": name, "value": value}
    )


def run(headless: bool, params: dict | None = None) -> dict:
    result = {"quote_rankings": [], "lowest_premium": None, "reference": None, "error": None}
    params = params or {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"), viewport={"width":1400,"height":1000})
        try:
            page.goto(FORM_URL, wait_until="domcontentloaded", timeout=40000)
            # don't wait for networkidle (analytics/chat widgets keep it busy)
            page.wait_for_timeout(2500)

            # Contact
            _fill(page, "First Client Name", get_param(params, "person.first_name", "John") + " " + get_param(params, "person.last_name", "Doe"))
            _fill(page, "First Client Phone", get_param(params, "person.phone", "9056889170"))
            _fill(page, "First Client Email", get_param(params, "person.email", ""))

            # DOB
            dob = get_param(params, "person.date_of_birth", "1990/03/15")
            try:
                y, m, d = dob.split("/")
                fr_months = ["Janvier","Février","Mars","Avril","Mai","Juin","Juillet",
                             "Août","Septembre","Octobre","Novembre","Décembre"]
                _select(page, "month", fr_months[int(m)-1])
                _select(page, "day", str(int(d)))
                _select(page, "year", str(int(y)))
            except Exception:
                pass

            # Gender Homme (default), Tobacco Non (default), Province Quebec (default)
            # Coverage $ 500,000, Payment Annuel, Term Temporaire 20 ans, Regular (defaults)
            _select(page, "First Client Premium Amount", "$ 500,000")
            _select(page, "First Client Premium Payment Schedule", "Annuel")
            _select(page, "First Client Product Type", "Temporaire 20 ans")

            # Submit ("Get my prize!*")
            page.locator("button:has-text('prize')").click()
            page.wait_for_load_state("domcontentloaded", timeout=20000)
            page.wait_for_timeout(2000)

            # Parse the ranked Report table: Company / Policy / Prime Annuelles
            rows = page.locator("table tr").all()
            rankings = []
            i = 0
            while i < len(rows) - 1:
                cells = rows[i].locator("td").all_inner_texts()
                cells = [c.strip() for c in cells]
                if len(cells) >= 3 and "Prime" not in cells[0]:
                    premium = cells[2] if cells[2] else ""
                    if premium:
                        rankings.append({
                            "company": cells[0],
                            "policy": cells[1],
                            "annual_premium": premium,
                        })
                i += 1
            result["quote_rankings"] = rankings
            if result["quote_rankings"]:
                clean = [r for r in rankings if r["annual_premium"].startswith("$")]
                if clean:
                    result["lowest_premium"] = min(
                        clean, key=lambda x: float(x["annual_premium"].replace("$","").replace(" ","").replace(",","")))

            # reference
            body = page.locator("body").inner_text(timeout=8000)
            m = re.search(r"quote ID#\s*([\w:.\- ]+)", body, re.I)
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
    ap.add_argument("--out", default="gpsequipeconseil_life_quote_result.json")
    ap.add_argument("--input", default=None,
                    help="Path to a per-person parameters JSON (default: quote_params.json).")
    args = ap.parse_args()
    headless = not args.headed
    print(f"Running in {'HEADED' if not headless else 'HEADLESS'} mode", flush=True)
    res = run(headless=headless, params=load_params(args.input))
    res["carrier"] = "gpsequipeconseil.com"
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
