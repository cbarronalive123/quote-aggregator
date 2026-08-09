# Web Quote Form — Coverage Notes

The intake form (`components/QuoteForm.tsx`, schema in `lib/formSchema.ts`) is the **"one
intake"** from the hackathon brief: it collects the union of every field any carrier auto
form needs, so a single submission can populate **any** carrier form — filled online by
browser automation, or over the phone by the phone agent when the carrier doesn't quote
online.

## Why it's built this way

Each carrier form in `field_registry.json` and the per-carrier auto scripts
(`aviva_auto_quote.py`, `belairdirect`, `eriemutual_auto_quote.py`,
`bertramandbarry_car_quote.py`, `vergeinsurance_auto_quote.py`, `aprilmarine_boat_quote.py`)
asks for slightly different fields. The web form collects the **superset** so nothing is
re-asked. It maps 1:1 to the repo's canonical profile (`personal_profile.db` → `person`,
`auto`, `current_insurance`).

## Sections and what they feed

| Section | Fields | Fills these carrier forms |
|---|---|---|
| Your information | name, email, phone, DOB, gender, marital | belairdirect, Aviva, Erie, Bertram & Barry, Verge, APRIL |
| Garaging address | street, unit, city, province, postal, tenure | Verge, Bertram & Barry, Erie, all raters (territory rating) |
| Your vehicle | VIN, year, make, model, trim, drive, fuel, owned/leased, new/used, purchase date | belairdirect (VIN lookup), Aviva, Erie, Bertram & Barry |
| How you use it | annual km, commute days/km, business use, winter tires, anti-theft | belairdirect, Aviva, Erie, Bertram & Barry |
| Driver's licence | licence class, first-licensed year, graduated, years with insurer, prior insurance, convictions, accidents, retired | belairdirect, Aviva, Erie, Bertram & Barry |
| Coverage & policy | start date, liability, own-damage, deductible, non-payment | belairdirect, Aviva, Verge, Bertram & Barry, the benchmark package |

## Belairdirect-specific fields covered

From `RUN_REPORT.md`, belairdirect's rater (`webquote.app.belairdirect.com`) needs:
province/language, **VIN** (or manual model/trim), commute one-way km, annual-km bracket,
purchase condition (new/used), anti-theft + type, driver name/gender/DOB, **first-licence
age**, licence class, **years-with-current-insurer**, phone/email/postal, and consent.
All of these are collected in the form (VIN, commute km, annual km, condition, anti-theft,
DOB, licence class, years with insurer, contact, postal, effective date).

## Where the collected data goes

- The form serializes to the `/quotes` route as query params.
- The results page renders the vehicle + postal code from those params.
- The same field values are what the operator pipes into a carrier script
  (`--input`) or hands to the phone agent (`/api/call`) for phone-only carriers.

## Note on completeness vs. the brief

The form currently collects the **auto (PPA)** superset — the only in-scope line for this
hackathon. Property/boat/life/travel fields exist in `field_registry.json` but are out of
scope for the submission; they are intentionally not surfaced on the public quote form so
the site reads as a normal auto-insurance broker. (See `PROJECT_PLAN.md §12` scope pivot.)
