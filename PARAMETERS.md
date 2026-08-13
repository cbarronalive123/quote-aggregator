# Quote Automation Parameter System

Each quote-form script now reads its fill values from a **shared per-person JSON file**,
so different users can apply their own parameters without editing code. This makes the
scripts reusable for many people, not just one.

## How it works

```
quote_params.json        <- per-person input (edit this, or pass --input <file>)
field_registry.json      <- documentation of every field (FIXED vs VARIABLE) + options
params_loader.py         <- shared loader used by all scripts
   +--> vergeinsurance_auto_quote.py  (--input)
   +--> armour_condo_quote.py         (--input)
   +--> aviva_auto_quote.py           (--input)
   +--> aprilmarine_boat_quote.py     (--input)
```

Each script resolves its form fields from the params JSON via a `DATA_MAP` / `PARAM_MAP`
that maps **form field name → params path** (e.g. `"province": "person.province"`).

> **SQLite option (current):** the hackathon now stores the participant profile in
> `personal_profile.db` (tables `person`, `auto`, `current_insurance`) instead of JSON.
> `personal_profile.load_profile()` returns the exact same nested dict shape
> (`person.*`, `auto.*`), so scripts keep using `get_param()`. Pass `--input <json>` to
> override with an old-style JSON file when needed. See `PROJECT_PLAN.md` §12.

### Run a script for a specific person

```bash
python vergeinsurance_auto_quote.py --headless --input quote_params.json
# or point to a different person's file:
python aprilmarine_boat_quote.py --headed --input ./people/alice.json
```

---

## FIXED vs VARIABLE parameters (the key distinction)

Every field falls into one of two categories. This is documented in **`field_registry.json`**
(and as inline comments in each script). **Never guess** an option value — look it up in the
registry; if a fixed option is missing, add it to the registry.

| Category | Meaning | Form control | The user must... |
|---|---|---|---|
| **VARIABLE** | Free-text input the person types | text / textarea / email / tel / date / number | Type any value (e.g. their name, email, address, birthdate) |
| **FIXED** | A bounded set of choices | select / radio / checkbox | Choose one of the documented options (e.g. deductible $500/$1,000/$1,500) |

### Examples

- **VARIABLE:** first name, last name, email, phone, street address, postal code, age,
  square feet, vehicle year, boat value.
- **FIXED:** province (list of provinces), cancellation non-payment (Yes/No), building type
  (Detached/Semi-Detached/Duplex/Triplex/Other), heating (one=Central Gas / two=Electric),
  condo policy (one=Yes/two=No), marital status (S/M/C/P/D/W), licence class (G/G2/other),
  engine type (Outboard/In/Out board/Inboard/Jet/Jet M2/Electric), owned months,
  boat claims (0/1/2/3), deductible ($500/$1,000/$1,500).

---

## quote_params.json structure

```jsonc
{
  "person": {                    // shared identity (used by every form)
    "first_name": "John",
    "last_name": "Doe",
    "email": "cormbar@msn.com",
    "phone": "9056889170",
    "phone_type": "mobile",       // FIXED: mobile | work | home
    "date_of_birth": "1990/03/15",// format varies per form (see registry)
    "sex": "M",                   // FIXED: M | F
    "marital_status": "S",        // FIXED: S | M | C | P | D | W
    "street_address": "123 Main Street",
    "city": "St. Catharines",
    "province": "Ontario",        // FIXED: province list
    "province_code": "ON",
    "postal_code": "L2R 1A1"
  },
  "auto": { /* vehicle + driver + licence params (Aviva) */ },
  "property_condo": { /* Armour condo params */ },
  "boat": { /* APRIL Marine params */ }
}
```

Because `person.*` is shared, one person profile drives the identity fields across all
forms, while the `auto` / `property_condo` / `boat` sections hold the per-insurance-type
values (which can also differ per person).

---

## Field registry (source of truth)

`field_registry.json` documents, per form, each field with:

- `type`: `fixed` or `variable`
- `datatype`: `select` / `radio` / `checkbox` / `text` / `email` / `tel` / `date` / `number` / `textarea`
- `options`: the allowed values (FIXED only) — **this is what you choose from, never guess**
- `param`: the `quote_params.json` path that supplies the value
- `format`: date format where relevant

Example (Armour building type):

```json
"select-1": {
  "type": "fixed",
  "datatype": "select",
  "label": "Building type",
  "options": ["Detached", "Semi-Detached", "Duplex", "Triplex", "Other"],
  "param": "property_condo.building_type"
}
```

---

## Adding a new person

1. Copy `quote_params.json` → `people/<name>.json`.
2. Edit the variable fields to that person's details, and pick valid FIXED options from
   `field_registry.json`.
3. Run: `python <script>.py --headed --input people/<name>.json`

## Validation

`params_loader.validate_fixed()` can check that a FIXED field's value is one of the
registry's options, printing a warning if not. This prevents entering an invalid choice.

## Notes / gotchas per form (see QUOTE_FORM_AUTOMATION_METHODOLOGY.md)

- **Armour (Forminator):** `[one,two]` selects map one=Yes, two=No; square-feet AND
  building-year are both capped at 150.
- **Aviva (Angular):** radio values are case-sensitive (`NO`/`ME`/`PARTNER`,
  `greatthan3years`); DOB is stored as `YYYY/MM/DD` and split for the form.
- **APRIL Marine:** boat value auto-formats (`35000` → `35 000`); renewal date is required.
- **Alliance Income (life):** Fluent Form #24 intake → hands off to partner rater
  `insurdinary.ca/online-quoter/` for the real premium (see the handoff note in the methodology).
  Fields: first/last name, phone, email, province, product (FIXED list), age (FIXED list), terms.
- **Verge (CF7):** text inputs can report "not editable" headless — use headed mode to
  verify, or the manual MCP flow.
