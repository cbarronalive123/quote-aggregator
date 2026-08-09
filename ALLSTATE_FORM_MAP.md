# Allstate Auto Quote — Field-by-Field Automation Map

Verified live 2026-08-09 via Playwright MCP. Two domains:
- Landing/entry: `https://apps.allstate.ca/quickquote/common/landing.aspx?CID=SEO_hero_home_page_Organic_EN`
- Quote app: `https://purchase.allstate.ca` (postcode → getstarted → summary → quote)

Legal: Allstate Insurance Company of Canada. Quote ref format e.g. `#083193545`.
This is an ASP.NET-entry + Vue/React SPA flow.

## Interaction notes
- Native `<select>` controls (`select[name=...]` / role combobox). Use `selectOption`.
- Many fields are revealed only after answering a prior question (conditionals) —
  the "continue" button stays **disabled** until all revealed fields are answered.
- Date pickers open a modal calendar (Month/Year selects + day buttons).
- Consent: at summary step, a required **privacy consent checkbox** to collect/use/
  disclose info for the quote. A separate marketing-email checkbox is optional
  (leave unchecked for data minimization).

## Step flow
1. **Landing** (apps.allstate.ca/quickquote): Postal code + insurance type (Auto) → **Go**.
   URL becomes `/QuickQuote/ON/getstarted?<base64>`.
2. **Get Started** (getstarted): 1 vehicle, 1 driver, "existing Allstate customer?" = No → **SHOP & BUY**
   (cookie banner "Accept" first).
3. **Summary page** (`purchase.allstate.ca/summary`) — vehicle + driver added via dialogs.

### Vehicle dialogs
**"Tell us about your vehicle"**: Add by Year/Make/Model (or VIN).
- Year select (2012) → Make select (**DODGE/RAM**) → Model select (**RAM 1500 BIG HORN QUAD**).

**"Tell us more about your [vehicle]"**:
- New/Used/Demo → Used
- Owned/Financed/Leased → Owned
- Only registered owner? → Yes
- Ownership within last 30 days? → No
- Purchase price incl tax → 30000
- Coverage start date (date picker) → Sep 1 2026
- Purchase month / Purchase year (`select[name=purchasedMonth]`, `select[name=purchasedYear]`) → Jan / 2019

**"How do you use your [vehicle]"**:
- Vehicle used for (`vehicle-used-for`) → Work / School  (reveals one-way commute)
- One-way commute km → 15
- Annual km band (`one-year-kilometers`) → 12001-16000km
- Ridesharing/commercial → No  (reveals confirm checkbox → check it)

**"Let's see how we can save you more money"**:
- Winter tires Nov-Apr → Yes  (reveals "confirm 4 winter tires" checkbox → check)
- Parking (`vehicle-parking`) → Unsecured Condo/Apt Garage or lot
- Anti-theft tracking added after purchase → No
- ADAS features → none (2012 model)

### Driver dialogs
**"To continue, we just need a few details"**:
- Province licensed → ON (default)
- First name / Last name
- Date of birth (date picker) → May 10 1985
- Gender → Male
- Marital status (`marital-status`) → Single (Married/Common Law | Single | Widowed)
- Other licensed drivers in household → No

**"Tell us about your driving history"**:
- Age first licensed (Use G2 age) → 21
- Graduated licensing? → Yes  (reveals license class)
- License class → G  (reveals "G within past 12 months?" → No)
- Minor violations past 3y (`minor-violation`) → None
- Major/criminal violations past 3y → No
- License suspended last 6y → No

**"Tell us about your insurance history"**:
- Currently insured/prior insurance → Yes
- Policy cancelled by insurer last 3y → No
- Auto claims past 6y → No

### Summary → quote
- Drivewise (telematics) → **No** (benchmark)
- Email address, Phone number
- **Privacy consent checkbox** → check (required)
- Marketing/communications email checkbox → leave unchecked
- **get a quote** → `purchase.allstate.ca/quote`

## Captured test result (DUMMY data — NOT a real quote)
- **$94.80/month** (or $1,123 if paid in full), **Quote #083193545**
- Effective Sep 1, 2026 – Sep 1, 2027
- Coverage defaults: TPL/BIPD **$1,000,000** ($18.32), DCPD Included ($39.93),
  Uninsured Auto Included ($1.18), Accident Benefits (Med $28.36 / Income $5.99),
  Family Protection Included/$1M ($1.01).
- **Collision and Comprehensive NOT included** — must be added for the $2M benchmark
  (this quote is cheaper partly for that reason; not directly comparable yet).
- An info dialog re: Accident Benefits changes July 1, 2026 appears on the quote page.
