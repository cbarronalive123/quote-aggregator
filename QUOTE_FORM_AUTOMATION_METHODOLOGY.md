# Quote Form Automation Methodology (Playwright)

> **Goal:** Given a carrier quote form discovered in `insurance_websites.db`, open it in a real browser, verify which forms actually exist, and methodically fill every field — one at a time, testing each — until the whole form is completed. Then encode exactly what worked into a Playwright automation script and test the script itself.

## Why this approach

Many quote forms found by the scanner are `contact-form-7`/Elementor/portal forms where the "real" fields are only visible after the page renders. Static scanning tells us the field *names* but not how to fill them, whether a field is a dropdown vs. text input, date format, or whether it's even on the page. Manual field-by-field verification via a live browser removes all guesswork.

## Tools used

- **Playwright MCP** — interactive headed browser to inspect and fill the live page.
- **Playwright (Python `sync_api`)** — to turn the verified flow into a repeatable automation script and re-test it.

---

## Step 1 — Find the target form

Query the DB for the first reachable domain that has quote forms:

```sql
SELECT domain, quote_form_count, quote_links_json, homepage_url
FROM form_scan_results
WHERE quote_form_count > 0 AND error IS NULL AND homepage_url IS NOT NULL
ORDER BY domain;
```

Our first hit was `2020insurance.ca` (redirects to **Verge Insurance**), with the auto quote form at:
`https://www.vergeinsurance.com/auto-insurance-quote/`

## Step 2 — Open a headed browser and load the quote link

Use the Playwright MCP navigate tool to open the URL in a headed browser and take an accessibility snapshot. The snapshot reveals the **actual rendered form** and every field (with accessibility refs) plus its real labels.

Example snapshot result — the form was a Contact Form 7 form ("Contact form") with these fields:
First Name, Last Name, Email, Phone Number, Street Address, City, Province (dropdown), Postal Code, Effective Date, "Have you ever been cancelled…" (dropdown), and a **Get My Quote** submit button.

## Step 3 — Verify the form(s) that really exist

- Confirm the page really contains a `<form>` with the expected fields (not just a "contact us" stub).
- Identify whether each field is a `text`/`email`/`tel`/`date` input or a `select` dropdown.
- Note any `date` inputs — these require `YYYY-MM-DD`.

## Step 4 — Fill one field at a time and test before moving on (the core rule)

**NEVER skip a field without confirming the previous one took.** For each field:

1. **Type/select it** with Playwright MCP.
2. **Verify** the value is actually in the field (read it back via `page.evaluate`).
3. Only then move to the next field.

### Selector discovery

When MCP filled a field, it showed the exact locator that worked. Those become the script selectors:

| Field (label)          | Verified locator                              | Type     | Value used        |
|------------------------|-----------------------------------------------|----------|-------------------|
| First Name             | `input[name="first-name"]`                    | text     | John              |
| Last Name              | `input[name="last-name"]`                     | text     | Doe               |
| Email                  | `input[name="your-email"]`                    | email    | john.doe@example.com |
| Phone Number           | `input[name="your-phone"]`                    | tel      | 9056889170        |
| Street Address         | `input[name="street-address"]`                | text     | 123 Main Street   |
| City                   | `input[name="city"]`                          | text     | St. Catharines    |
| Province               | `select[name="province"]` (select by label)   | select   | Ontario           |
| Postal Code            | `input[name="postal-code"]`                   | text     | L2R 1A1           |
| Effective Date         | `input[name="effective-date"]`                | date     | 2026-09-01        |
| Cancelled non-payment? | `select[name="cancellation-nonpayment"]`      | select   | No                |

### Key gotchas learned

- **Dropdowns:** use `select_option(label=...)` on `select[name=...]`, not `.fill()`.
- **Date inputs:** must be `YYYY-MM-DD`.
- **Hidden CF7 fields** (`_wpcf7*`) are auto-populated; ignore them.
- **Verify, don't assume:** always read back `input_value()` / selected option.

## Step 5 — Encode the verified flow into a Playwright script

Write a Python script (`fill_verge_auto_quote.py`) using `playwright.sync_api` that reproduces the exact MCP-verified locators and order. Fill each field, read it back, and compare against the expected value.

## Step 6 — Test the script itself

Run the script headless. It should print the filled fields and confirm `All 10 fields filled and verified`. This proves the automation works without manual MCP interaction.

Result of the test run:

```
[OK] All 10 fields filled and verified.
```

---

## Step 7 — Name and label the script per-form

Name each script `{carrier}_{insurance_type}_quote.py` so the filename is self-describing and maps 1:1 to a form.

Example: **`vergeinsurance_auto_quote.py`** drives the auto quote form at
`https://www.vergeinsurance.com/auto-insurance-quote/`.

The docstring at the top of every script must record the form URL and its DB link.

## Step 8 — Register the script in the DB

The `form_scripts` table maps each quote-form URL → the script that fills it. This is
how the registry answers "which file drives this form?".

```sql
CREATE TABLE form_scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    form_url TEXT NOT NULL,
    domain TEXT,
    insurance_type TEXT,          -- auto / property / business / life / travel / unknown
    script_file TEXT,             -- e.g. vergeinsurance_auto_quote.py
    status TEXT DEFAULT 'registered',  -- registered | fill_verified | submitted | needs_work
    result_note TEXT,
    form_kind TEXT DEFAULT 'unknown',  -- lead_gen | quote | unknown   <-- IMPORTANT
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT,
    UNIQUE(form_url)
);
```

### ⭐ Distinguish **lead-gen** vs **actual quote** forms

Not every "quote" form actually returns a price. Classify each form into one of two kinds:

| `form_kind` | Meaning | How you detect it |
|---|---|---|
| `quote` | A **real quoting form** — you get a dollar value. | After submit (or on a later page in the flow) a **`$` amount / premium** appears. This is what we want for rate comparison. |
| `lead_gen` | A **lead-capture / contact form** — collects your details and a broker contacts you. **No dollar value.** | After submit it ends at a "thank you" / "we will contact you" page with **no `$`**. The actual rate is given later by phone/email. |
| `unknown` | Not yet classified. | — |

The Verge auto form is a confirmed **`lead_gen`**: it fills 10 fields, submits, and redirects to
`https://www.vergeinsurance.com/thank-you-auto-insurance-quote/` with a "thank you" message and
**no dollar value**. Record it as such so it is never mistaken for a rate-bearing form.

Register/update via `register_form_script.py` (idempotent; creates the table if missing):

```bash
# create + register (note --kind)
python register_form_script.py --form "https://www.vergeinsurance.com/auto-insurance-quote/" \
    --domain vergeinsurance.com --type auto --script vergeinsurance_auto_quote.py \
    --kind lead_gen

# bump status/note/kind as you verify and submit
python register_form_script.py --form "..." --status submitted --kind lead_gen --note "..."
```

Update `status`/`result_note`/`form_kind` as you progress through verification and submission.

## Step 9 — Headed / headless toggle

Every script takes a CLI mode so you can watch it work (headed, for verification) or run
it unattended (headless, for batch). Default to headless.

```bash
python vergeinsurance_auto_quote.py --headed     # visible browser, verify manually
python vergeinsurance_auto_quote.py --headless   # hidden browser, unattended (default)
```

A mutually-exclusive `--headless` / `--headed` argparse group controls this; headed wins.

## Step 10 — Submit and chase the multi-page flow (do not trust the first button)

**Never assume "Get My Quote" is the last step.** Quote flows frequently span multiple
pages: the submit can redirect to another page, load an AJAX result, or open a rater
portal. The script must:

1. Click submit and wait for navigation **or** AJAX completion.
2. Loop over the resulting page(s):
   - **Stop** when a quoted dollar amount is found via a `$` regex (e.g. `$1,234.56`).
   - **Stop** when a terminal message appears ("thank you", "submitted", "we will contact you").
   - Otherwise **click the next visible form's submit** and continue (up to a page cap).
3. Record every visited URL and the final outcome.

### Real-world result for Verge auto

This specific form is a **lead-capture (Contact Form 7) form** — not a live rater. After
submitting it redirects to `https://www.vergeinsurance.com/thank-you-auto-insurance-quote/`
("thank you"). No `$` value appears because the broker issues the actual rate by email/phone.
That is correct behavior: the flow-chaser detects the terminal "thank you" and stops, and we
record it as **`form_kind = lead_gen`** so it is never mistaken for a rate-bearing form. For
carriers with a true online rater (e.g. the Applied Systems WebRater portals), the same loop
will instead catch a `$` premium on a later page and be recorded as **`form_kind = quote`**.

## The reusable pattern (for every carrier form)

```
1. Pull the quote URL + field list from the DB.
2. Open headed, snapshot to get real rendered fields + labels.
3. Classify each field: input subtype (text/email/tel/date) or select (+ options).
4. Fill field #1 -> verify -> fill #2 -> verify -> ... -> last field.
5. Record each verified selector.
6. Write the script ({carrier}_{type}_quote.py) with the headed/headless toggle.
7. Run it headless to confirm every field fills; run headed to watch.
8. Register the script in form_scripts (form_url -> script_file); bump status.
9. Extend the script to submit and chase multi-page flow until a $ value or
   terminal message appears. Update result_note.
10. Classify the form: if a $ value was returned -> form_kind='quote';
    if it ended on a thank-you/contact page with no $ -> form_kind='lead_gen'.
    Record it. (These are DIFFERENT: only 'quote' forms give a price to compare.)
11. The script now stands as that carrier's form-filler (feeds the field-registry alignment).
```

## Output files

- `vergeinsurance_auto_quote.py` — the working Playwright script (Verge auto quote): fills all
  10 fields, submits, follows the redirect, detects the terminal "thank you" page. Has
  `--headed`/`--headless` modes. **Classified as `lead_gen`.**
- `insurance_websites.db` → `form_scripts` — maps each form URL to its script + status +
  `form_kind` (lead_gen vs quote).
- This file — the methodology to replicate for the remaining 253 carrier forms.

## Forminator-specific techniques (learned from Armour condo quote)

Not all quote forms are CF7. **Forminator** (used by armour-insurance.com) has quirks
that need handling in the automation script:

1. **Fields can report "not visible"** to Playwright even though they are interactive
   (the framework wraps inputs). Workaround: set values via `page.evaluate` and
   dispatch `input` + `change` events, or use `force=True` on fills.
2. **Custom dropdowns** are a visible widget backed by a native `<select>`. Set the
   native select (scoped to the quote form) and dispatch `change` so the widget syncs.
   For `[one,two]` option pairs, `one` = Yes and `two` = No (confirmed by reading the
   visible text back). The quote form's select fields are `select-1,2,3,4,5,6,7,8,9,10`.
3. **Checkboxes** are visually hidden — the real `<input>` is what must be set. Set
   `el.checked = true` + dispatch `change`.
4. **The submit button lives OUTSIDE the `<form>` element**, so scope its lookup to the
   page, not the form.
5. **AJAX submission** goes to `wp-admin/admin-ajax.php` with action
   `forminator_submit_form_custom-forms`. Detect success by capturing the response
   (contains `"success": true`) or by reading the `.forminator-response-message` element.
   This is how you distinguish a submitted lead-gen form from a failed one.
6. **Dollar-value detection**: a form's own `<select>`/dropdown option labels contain
   `$` figures (e.g. `$100,000`) that are NOT quote results. Strip `select/option` and
   the custom-select widget from the text before matching a `$` premium.
7. **Form bugs**: the Armour form caps BOTH square-feet and building-year at 150
   (the year field wrongly inherits the sq-ft max). Note such quirks in the script so
   the values you enter pass validation.

## A genuine QUOTE form: Aviva Direct auto rater (confirmed `$` value)

Aviva is the first confirmed **`form_kind = quote`** form — it returns a real premium
(unlike Verge/Armour which are `lead_gen`). It is a **multi-page Angular rater** at
`myaviva.avivainsurance.ca/avivaquoter/bol/auto/{step}`.

### Flow (10 steps, each verified field-by-field)
1. **Quote modal** (on aviva.ca/en): postal code → "Get a quote". Entered via a React
   native-value setter + input/change events (the `getByRole` fill didn't stick).
2. **Car Details**: `vehicleYear/Make/Model` (testids), `purchaseDate_month/year`,
   `purchaseCondition` (radio), `winterTires` (radio), `hasAntiTheftDevice` (radio).
3. **Car Use**: `annualMileage`, `commutePerWeek` (testid), `commutingMiles` (one-way,
   appears after commute>0), business-use radio, coverage start date (MM/DD/YYYY).
4. **Driver**: `driverFirstName/LastName`, `dateOfBirth-*`, `sex` (M), `maritalStatus`
   (letter codes S/M/C/P/D/W), `retired`, `combinedPolicyDiscount` (NO/ME/PARTNER),
   `telusHealth`, `hadPriorInsurance` (greatthan3years).
5. **Licence**: `licenseClass` (G/G2), `firstLicenceDate_*`, `isGraduatedLicense`,
   `graduateLicenseDate_*`, `hasOutOfProvinceLicense`, `internationalLicenseClass`
   (No = 3rd radio of the group).
6. **Experience** (convictions/accidents) — defaults to No.
7. **Double-check** assumptions → "Yes, that's correct".
8. **Aviva Journey** (telematics) → No (`driver1` radio, value "No").
9. **Contact**: `userPhoneNumber`, `phoneType` (mobile/work/home), `userEmail`,
   `marketingConsent` checkbox.
10. **Customization** → premium is displayed (`$155.15 per month`) → **"Email my quote"**
    → email dialog pre-filled with the user's address → Submit → "Your quote has been
    sent to your email!"

### Key techniques for Angular raters
- **React/Angular controlled inputs**: use the native value setter +
  `input`/`change` events (e.g. the postal code and date fields), not `.fill()`.
- **Radios** share a name but values are case-sensitive (`NO`/`ME`/`PARTNER`,
  `greatthan3years`, `new_AC`). Read the option values first.
- **Conditional fields appear after prior answers** (e.g. one-way commute km only
  after commute>0; G2 date only after "held other classes = Yes").
- **Human-intervention gates**: some answer combos trigger a "Let's connect" modal
  requiring a phone call. Adjust answers to a standard Canadian profile to avoid it.
- **Validation**: licence year is constrained by DOB (min age rule); pick a year that
  satisfies it.
- **Modals intercept clicks** — dismiss them or click via `page.evaluate` (`el.click()`).
- **Result**: a `$` premium in the page text + quote number are the success signal.
  Use the user's real email (`cormbar@msn.com`) so the emailed quote is delivered.
- **Capturing results**: the script extracts `quote_value`, `quote_number`, and `emailed`
  into a result dict, then `main()` persists them to `aviva_auto_quote_result.json` (via
  `--out`) and appends a line to `quote_results.jsonl` for batch collection. This lets the
  automated run record the premium without manual copy.

## A second QUOTE form: APRIL Marine boat rater (confirmed `$` value)

**APRIL Marine** (`aprilmarine.ca/on-en/quote`) is a second confirmed `form_kind = quote`
form — a real boat-insurance rater at `prime.aprilmarine.ca` that returns a genuine premium.

### Flow (verified field-by-field)
1. Landing `aprilmarine.ca/on-en/quote` → **"Get a Quote"** (boat owner) opens `prime.aprilmarine.ca`
   in a **new tab**. Accept the cookie banner first.
2. Quoter landing: Language = **English**, Province = **Ontario** → **Start**.
3. **Boat type**: Motorboat (options: Fishing boat / PwC / Sailboat / Motorboat).
4. **Motorboat Information**: Make (combobox 0), Model (combobox 1, loads after Make),
   Engine Type (combobox 2), Category (auto-determined, disabled), Year (textbox),
   Value to insure (textbox, auto-formats "35 000").
5. **Your Information**: First/Last name, E-mail, Phone, DOB (`YYYY/MM/DD`), Province (auto "ON").
6. **Driver's record**: ownership duration (`experience` radio), already insured
   (`already_insured_with_us` radio), **renewal date** (`YYYY/MM/DD`, required!), boat claims
   (`claim_number` radio), license suspension (`license_suspension` radio).
7. **Get My Premium** → returns **"Estimated premium for: BAYLINER XP (2020): $504.36 / year"**
   with coverage (All risks, Deductible $500, Liability $3,000,000) and emails the full quote.

### Key techniques / gotchas
- **New-tab flow**: the quoter opens in a new tab — use `context.expect_page()` and drive the
  new page object, not the landing page.
- **Required renewal date**: the form errors "Please enter a renewal date" if the approximate
  renewal date field is left blank — it appears after the "already insured" question.
- **Radios share duplicate values** (e.g. `0/1` appear in both claims and suspension groups):
  select by **radio `name` + value**, not by value alone.
- **Value auto-formats** (35000 → "35 000"); the premium regex must allow spaces: `$[\d,.]*\s*/year`.
- **Emailing**: the result page states "The full quote has been emailed to you" — sent to the
  address entered (`cormbar@msn.com`).
- **Result persistence**: `aprilmarine_boat_quote.py` writes `aprilmarine_boat_quote_result.json`
  and appends to `quote_results.jsonl`, capturing `quote_value`, `details`, and `emailed`.

## The intake → partner-rater handoff (Alliance Income life)

Not every "quote" form generates the premium itself. **Alliance Income** (Fluent Form #24)
collects the contact info + product + age + terms (8 fields), submits, and **redirects to a
partner online rater — `insurdinary.ca/online-quoter/`** — which produces the actual `$` quote.

**How to classify this:** the intake form is **`form_kind = lead_gen`** (it captures the lead
and hands off; no `$` on the intake page itself). But its **outcome** is a handoff to a real
rater. Two sub-cases to record in `result_note`:
- If the form **redirects to a partner rater** → note `handoff = "<rater URL>"`. The real
  premium lives on the partner, which is a *separate* form to automate (often its own multi-step
  underwriting flow: coverage calculator, eligibility assessment, appointment).
- If it just ends on a thank-you → plain `lead_gen`.

**Script**: `allianceincome_life_quote.py` fills the 8 fields (wired to the shared params),
submits, and records where the flow lands (`redirected_to`, `handoff`). This pattern matters
for the test harness: an Alliance Income "quote" is really an entry point into Insurdinary, so
to get the `$` you must also automate the partner rater.

### Insurdinary follow-up (verified: no quote value)

Completing the Insurdinary partner flow (reached from Alliance Income) does **not** yield a `$`:
demographics → coverage calculator → underwriting type → eligibility assessments (A/B/C/1/2/3)
→ "Assumption Life / IA Financial / RBC / CPP application" → Beneficiary → Banking → **"Please
Book a Call"** → **"Your Application Has Been Successfully Submitted."** The premium field shows
only a **`$undefined/month` placeholder** — the value is never computed on-screen (the only `$`
is the user-chosen coverage amount, e.g. a $350,000 slider). This partner route is an
**application/lead funnel**, not a live quote rater; the real premium is quoted by an agent
over a call. So: **classify as `lead_gen` with a handoff, and note no quote value is obtainable
without an actual agent.**

## CGI quote forms with split phone (cheaplifeinsurance.ca)

**Cheap Life Insurance** (`cheaplifeinsurance.ca`) submits its life quote form to a legacy
**CGI endpoint** (`/cgi/quote.cgi`). Verified:
- The quote form uses a **split phone number** across three fields: `area_code` (3-digit),
  `phone_prefix` (3-digit exchange), `phone_suffix` (4-digit line). An **evening phone** (`*_2`
  fields) is also required. Filling them all with the same number is correct; a missing/invalid
  field shows **"Invalid or unlisted phone number."** and blocks submission.
- Native HTML5 validation runs via `form.requestSubmit()` — a plain `.click()` on the submit
  button does not trigger it. Use `requestSubmit()` then wait for navigation.
- On success it lands on `/cgi/quote.cgi` ("Thank you") with a **reference number** (e.g. 608A001)
  and an assigned advisor; the actual premium is **emailed within 24 hours** — **no `$` value on
  the page**. Classify `lead_gen` (with a reference for follow-up). Script:
  `cheaplifeinsurance_life_quote.py`.

## A third QUOTE form on the same site: Aviva HOME/PROPERTY rater (confirmed `$` value)

A dollar-value site can host **more than one** quote kind. Aviva Direct already had the **auto**
rater (`aviva_auto_quote.py`); it also has a genuine **home/property** rater that returns a real
premium — `$132.17/month / $1543.32/year` (Quote #Q022754579). Script: `aviva_home_quote.py`.

### How to launch it (critical) — you canNOT hit the rater URL directly
The property rater is reached through the **homepage Direct modal** by setting the hidden
`product_type` field to `/property` (NOT `/auto`). The quickmodal form's hidden fields are:
`product_type=/auto` (default) → set to `/property`; also `newQuoter=true`, `_path=/content/...`,
`_lang=en`. Hitting `myaviva.avivainsurance.ca/avivaquoter/bol/property/` or
`.../sy/bol/landing` directly returns **"not able to provide a quote online for your province"** —
only the modal launch (which carries the correct `sid`/`uuid` context) works.

### Flow (4 steps, each field verified)
1. **Homepage modal**: select the **Home Insurance** radio, set hidden `product_type=/property`,
   enter postal code, click **Get a quote**. (Remove the Qualtrics survey iframe first; clicking the
   submit via `form.submit()` triggers the CDN bot-block — click the **Get a quote** button instead.)
2. **Property address**: postal → **Search address** auto-fills City/Province/Street. The **street
   number must be within the `addressPrefill` API low/high range** (e.g. `L2R 1A1` → Dunkirk Rd
   26–36); else "Please enter a valid street number". Then radios: years-lived (Yes = `years3-yes`),
   home type (own = `yourProperty_rad_HO3`, condo `HO6`, rent `ten_ac`), coverage start date
   (month/day/year) → **Continue**.
3. **Property details**: roof year, heating (Natural gas - furnace), wiring (Copper 100 AMP),
   "None of the above" features checkbox → **Continue**.
4. **Policyholder**: first/last name, DOB, email, phone, phone type (Mobile); radios `market-no`,
   `CurrentIns-no`, **conditional "When did you have insurance last?" = Never** (appears only after
   selecting No to current insurance), `claims-in-5yr-yes` (None), `mortgage-yes`, `combinedPolicy_No`;
   check the **credit-check consent** checkbox (`#creditCheck`); click **Agree and continue**.
5. **Summary**: captures `$132.17/mo $1543.32/yr` + Quote # Q022754579.

### Key techniques / gotchas (Angular controlled inputs, same as the auto rater)
- **Hidden `product_type`** must be flipped to `/property` in the modal before submit.
- **Radio buttons** are Angular-controlled and often obscured by a label span — set them via
  `page.evaluate` (`el.click()` + dispatch `change`), selecting by the input's **id**
  (`years3-yes`, `yourProperty_rad_HO3`, `market-no`, `mortgage-yes`, etc.).
- **Conditional fields** appear after prior answers (insurance-last appears after "No current
  insurance"). Always fill/select them or "Agree and continue" silently won't advance.
- **Address validation** is strict: the street number must exist in the addressPrefill
  `street[].lowNumber..highNumber` range for the chosen street. Use the `addressPrefill` API
  (`/sy/gi-services/addressPrefill/{postal}`) to learn valid numbers.
- **Submit via button click, not `form.submit()`** — the raw form GET triggers Aviva's CDN
  "Access Denied" bot-block in headless. Even so, **headless runs now hit the CDN bot-block** on the
  rater itself (identical to the current `aviva_auto_quote.py` behaviour); a headed/interactive
  session (Playwright MCP) completes it and returns the premium. Record this anti-bot caveat.
