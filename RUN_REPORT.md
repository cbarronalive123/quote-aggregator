# Run Report — belairdirect (Intact group) — Direct route

Date: 2026-08-09 (live, headed browser via Playwright MCP)
Profile: Corey Barron, 2012 RAM 1500 Big Horn Quad Cab 4WD, VIN 1C6RD7GT9CS103678, Kitchener ON

## Result
- Status: **quoted_comparable_candidate** (coverage differs from Aviva — see normalization note)
- Price: **$71.92 / month** (monthly basis, +1.3% interest on monthly payments)
- Web discount applied; price valid 60 days
- Quote reference: **# BA13933019**
- Evidence: `belairdirect_offer_BA13933019.png`
- Route URL: `https://www.belairdirect.com/` → Car → online rater `webquote.app.belairdirect.com`
- Phone (for callback route): 1 833 842-4457

## Coverage captured (initial estimated price — not guaranteed)
| Cover | Detail |
|---|---|
| Liability (Property damage & injury) | Covered up to **$1,000,000** |
| DCPD (Not-at-fault accident) | Covered, deductible **$0** |
| Family Protection | Covered |
| Accident Benefits (Med/Rehab/Attendant) | Non-catastrophic **$65,000**; catastrophic **$1,000,000** |
| Own-damage (Collision/Comprehensive) | Not shown in summary (default offer) |

## Coverage normalization note (critical for comparison)
belairdirect defaulted to **$1M liability**; the brief's benchmark is **$2M TPL**. Aviva result
may be a different limit/deductible. **Do not rank $71.92 vs Aviva until coverage is normalized**
to the benchmark ($2M TPL, DCPD incl., $1k collision+comp deductible, OPCF 44R, no telematics)
or both marked `quoted_non_comparable`.

## Driver / vehicle inputs used (as submitted)
- Commute one-way 15 km; annual km 13,001–16,000; condition Used; anti-theft Yes (type: Other)
- Name Corey Barron; Gender Male; DOB 10/14/1984
- First licence age **21** (user-corrected; DOB + 21y ≈ 2005)
- Licence class **G**; Years with current insurer: **5 years or more**
- Contact: phone 519-476-0578; email cormbar@msn.com; postal N2B 2T4
- Consent: Terms/Privacy accepted (marketing consent **not** checked)

## Interaction notes (for encoding belairdirect_auto_quote.py)
- Province/language/cookies overlay → click Confirm (ON/EN) first.
- Step 1 (info): click "Find your car with VIN", type VIN, then a model combobox appears → pick the resolved trim.
- Step 2 (usage): commute = numeric spinbutton (set via native value setter + input/change/blur — Angular/shadow DOM);
  yearly-km combobox; Condition radio; Anti-theft Yes radio → reveals "Select anti-theft system" combobox.
- Step 3 (driver): name, gender radio, DOB month combobox + day/year textboxes (native setter + Tab needed),
  first-licence age spinbutton, licence-class radio, years-with-insurer combobox.
- Step 4 (contact): phone (auto-formats 519-476-0578), email, postal; Group member = none.
- Consent checkbox "Yes, I agree" (Terms/Privacy) → "Get your price".
- Offer page shows price + quote ref; "Get a copy of your quote" available.
- A `feature-exit-intent` overlay periodically intercepts clicks — remove it or retry (not a bot-block).

## Profile correction
- Phone updated in `personal_profile.py` to 519-476-0578. **Re-run `python personal_profile.py` to reseed `personal_profile.db`** (shell reseed not completed in this session).
