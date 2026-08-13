# Voice-to-Form Insurance Broker Agent — Plan & Approach

## 1. Vision (hackathon framing)

MyChoice.ca is an insurance aggregator/broker that today requires users to type the same long intake questionnaire (VIN, driver history, postal code, roof year, prior-policy expiry, etc.) into many different carrier portals. We are building a system that lets a consumer say, in plain voice, what they want — "Get me a quote on a 2019 Honda Civic in Mississauga" — and have the data automatically filled across **every** carrier form that applies to that insurance type.

Three delivery surfaces:
1. **Website** — Next.js (frontend + API routes).
2. **Mobile app** — Flutter.
3. **Browser automation tool** — a Playwright-driven headless agent that fills carrier quote forms in parallel across multiple tabs, with a direct-API integration path attempted first whenever a carrier exposes one.

A companion camera/document-scanner extracts data from photos of an existing pink slip or policy PDF to pre-fill the user's profile, removing most of the typing friction.

## 2. High-Level Architecture

```
                         ┌──────────────────────────────────────────────┐
                         │                  USER                         │
                         │  (voice · typed text · document photo)       │
                         └───────────────┬──────────────────────────────┘
                                         │
        ┌────────────────────────────────┼────────────────────────────┐
        │                                │                            │
        ▼                                ▼                            ▼
 ┌─────────────┐                ┌──────────────────┐         ┌────────────────┐
 │  Flutter    │                │  Next.js web app  │         │  Document      │
 │  mobile app │  ← shares API →│  (React + route   │         │  scanner agent │
 │             │   contract     │   handlers)       │         │  (camera/OCR)  │
 └──────┬──────┘                └─────────┬────────┘         └───────┬────────┘
        │                                 │                          │
        └────────────┬────────────────────┘                          │
                     │ unified REST/JSON API (treated identically by both clients)
                     ▼                                                                         │
        ┌──────────────────────────────┐                ┌─────────────────────────────┐│
        │  Broker Orchestration Core   │←── profile ───│  Document extraction service││
        │  (Next.js API routes /       │    data         │  (Vision OCR + LLM to map   ││
        │   long-running workers)      │                 │   scanned text → field IDs) ││
        └──────────┬───────────────────┘                └─────────────────────────────┘┘
                   │
                   ├──► Field Schema Registry (canonical field catalog + per-carrier mapping) ──► SQLite / Postgres
                   │
                   ▼
        ┌──────────────────────────────────────────────────────┐
        │  Carrier Integration Layer (per insurance type)     │
        │                                                      │
        │   ┌───────────────┐         fallback        ┌─────────────────┐
        │   │  Direct API   │  ───────────────────────► │  Playwright      │
        │   │  adapters     │        (if no API)         │  headless agent  │
        │   │  (per carrier)│                            │  (multi-tab)     │
        │   └───────────────┘                            └──────────────────┘
        └──────────────────────────────────────────────────────┘
```

## 3. Insurance-type Taxonomy (drives form selection)

Every carrier form is tagged with one (or more) of these types, mirroring MyChoice's product lines:

### Auto
- `auto_personal` — personal sedans/SUVs/trucks (core)
- `auto_commercial_specialty` — work trucks, vans, motorcycles, RVs, classic cars, boats
- `auto_high_risk` — high-risk driver policies
- `auto_telematics` — pay-as-you-go / telematics
- `auto_multi_vehicle` — multi-vehicle bundle

### Property
- `prop_homeowners` — detached / semi-detached / townhomes (comprehensive + broad)
- `prop_condo` — condo unit improvements, personal property, loss assessment
- `prop_renters` — tenant liability + contents
- `prop_secondary_landlord` — vacation cottages, investment, short-term rental

### Commercial
- `commercial_cgl` — general liability for small business / contractors / sole proprietors
- `commercial_property_fleet` — commercial property + fleet

### Travel & Special Lines
- `travel_medical` — emergency medical travel
- `travel_trip_cancel` — trip cancellation
- `life` — life insurance comparison

A carrier's quote flow can declare which of these types it supports; the orchestrator only fans out to forms whose type matches the user's request.

## 4. Field Schema Registry (the heart of the data model)

Goal: maintain a **complete list of every field each form needs**, and **align** overlapping fields so that a single canonical value (e.g. "first name") auto-populates every form that asks for it.

### 4.1 Layers

1. **Canonical field catalog** — the union of every concept we ever need to collect. Each canonical field has:
   - `canonical_id` (stable slug, e.g. `driver_first_name`)
   - `label` ("Driver first name")
   - `data_type` (`string`, `date`, `enum`, `postal_code`, `vin`, `currency`, `boolean`, `phone`, `email`)
   - `insurance_types` — which insurance type(s) this field is relevant to (`auto_personal`, `prop_homeowners`, …)
   - `validation` regex / enum values / min-max
   - ` pii` flag (driver license, DOB — handle with care)
   - `source_weight` — order of preference for where to pull a value from (`document_scan > user_voice > user_profile_lookup > inference`)

2. **Per-carrier form schema** — for every carrier form we discover, we store:
   - `form_id` (slug)
   - `carrier` → links to a row in the carrier table (derived from the websites DB)
   - `website` (the actual quote URL)
   - `insurance_type` (one of the types above)
   - `integration_method` (`api` | `playwright`)
   - `flow_steps[]` — ordered list of steps/pages (login → vehicle → driver → coverage → review)
   - `fields[]` — list of `{ form_field_label, form_field_locator, canonical_id, required, default, options_source }` entries
   - `api_endpoint` / `api_auth_method` — populated when `integration_method = api`
   - `playwright_selectors` — name/id/xpath per field when `integration_method = playwright`

3. **User profile** — a per-user record keyed by `canonical_id` so that anything they've ever told us (or that the scanner extracted) is reusable across all future forms and all insurance types.

### 4.2 Field alignment (the "first name everywhere" behaviour)

- Every per-carrier field row references exactly one `canonical_id`.
- At run time the orchestrator builds a `CanonicalValueSet` by merging, per canonical id, in priority order:
  1. document-scan extraction (highest trust — it came from the user's own pink slip / policy)
  2. utterances from the current voice conversation
  3. values already stored in the user profile
  4. inferred / defaulted values with a "low-confidence" flag
- The form-filler then walks each carrier form's `fields[]` and pulls the value for `canonical_id` from the `CanonicalValueSet`. So `driver_first_name`, whether it appears on Intact, Aviva, or Belairdirect, all resolve to the same value the user voiced a single time.
- A `MAPPING_ALIGNMENT` join table lets us record edge cases where a single canonical field maps to two literal form labels (e.g. one form says "Given name" and another says "First name" — both map to `driver_first_name`).

### 4.3 Storage

- Canonical catalog + per-carrier schemas + aliases live in a relational DB (SQLite for hackathon dev, Postgres for prod). The `insurance_websites.db` produced from the CSVs seeds the carrier table.
- The user profile is stored encrypted at rest; PII canonical fields are tagged `pii` and never logged in plaintext.

## 5. Carrier Integration Layer — "API first, Playwright fallback"

For every carrier form in the registry we attempt, in order:

1. **Direct API** — if the carrier publishes a quoting API (some large carriers and several MGAs do), use it. This is faster, more robust, and avoids TOS issues with scraping. The form registry entry has `integration_method = api` and stores endpoint/auth/request-shape.
2. **Playwright headless automation** — when no API exists, spin up a Playwright browser context, open one tab per carrier form, drive the multi-step flow, and fill from the `CanonicalValueSet`. Each tab is a separate async task so 10+ carriers fill concurrently.

Decision rule, encoded per form in the registry:
- `integration_method` field on the form schema is set during the catalog-building step (manual + a discovery probe that tries OpenAPI/REST discovery on the carrier's domain).
- At runtime we honour that flag; if a form is marked `api` but the API call fails, we **do not** silently fall back to scraping — we record the failure and surface it, so we keep TOS handling explicit.

## 6. Browser Automation Tool (the Playwright agent)

- **Multi-tab**: one context, N tabs, one per carrier. Each tab is an isolated async job.
- **Field filling from the CanonicalValueSet**: the agent looks up the form's pre-recorded selectors for each `canonical_id` and writes the canonical value.
- **Selective re-prompting**: if a canonical field is missing or low-confidence for a given insurance type, the agent pauses that tab and asks the voice/UI layer to collect the missing field, then resumes.
- **Result scrape**: after submission, the agent reads back the quoted premium, deductible, and coverage summary from each carrier and returns them to the orchestrator, which presents a comparison table — exactly the aggregation MyChoice does, minus the manual typing.
- **Anti-bot mitigation**: realistic interaction cadence, waits-for-selector, and per-carrier notes in the registry (some forms need a captcha handoff — flagged as `requires_human`).

## 7. Voice-to-Form AI

- **STT**: streaming transcription on device (Flutter) and in-browser (Web Speech API or a hosted model) → partial transcript sent to the backend.
- **Slot extraction LLM**: a small LLM maps the transcript to the canonical field schema. Intent + entity model:
  - Intent: `request_quote`
  - `insurance_type` (one of §3)
  - per-type fields (VIN, postal code, vehicle year/make/model, roof year, prior carrier expiry, etc.)
- **Aligning on the fly**: every slot the LLM fills is written straight into the `CanonicalValueSet`. If the user repeats something already known, the latest value wins (with a confirmation prompt for PII fields).
- **Conversational follow-up**: when the orchestrator reports a form can't be completed because canonical field X is missing, the voice agent asks the user a targeted question ("What year was your roof last updated?") and the answer slots straight in.
- **Cross-channel**: both the Flutter app and the Next.js web app talk to the same backend voice endpoint so a user can start on the phone in the car and finish on the website at home.

## 8. Document Scanner Camera Agent

- **Capture**: native camera on Flutter (image + PDF); file upload + camera on the web.
- **Extraction**: OCR pass (Vision API / Tesseract on-device), then an LLM pass that maps scanned tokens to canonical fields (`vin`, `driver_license_number`, `prior_policy_number`, `prior_carrier`, `prior_policy_expiry`, `vehicle_year/make/model`, `named_drivers`).
- **Precedence**: scanned values are tagged `source = document_scan` and outrank voice-stated values for the same canonical id, because they came from an authoritative document.
- **UI feedback**: before any scanned value is committed, show the parsed record to the user with the source spans highlighted on the original image; user confirms or edits.

## 9. Repo / Project Structure (proposal)

```
/
├── apps/
│   ├── web/                    # Next.js (app router) - frontend + API routes
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   ├── voice/      # streaming STT + slot extraction
│   │   │   │   ├── quote/      # orchestrate quote fan-out
│   │   │   │   └── scan/       # document upload + extraction
│   │   │   └── (pages)
│   │   └── lib/
│   ├── mobile/                 # Flutter app
│   └── automation/             # Playwright browser agent (Node/TS service)
├── packages/
│   ├── field-registry/         # canonical catalog + per-carrier schemas (shared JSON/SQL)
│   ├── carriers/               # per-carrier API adapters + Playwright selectors
│   └── sdk/                    # typed client the web & mobile apps share
├── data/
│   ├── insurance_websites.db   # carrier seed (produced from the CSVs)
│   └── field_registry.db       # canonical + per-form field schemas (to be built)
└── docs/
    ├── INSURANCE_WEBSITES_REPORT.md
    └── PROJECT_PLAN.md         # this file
```

## 10. Build Order (hackathon milestones)

1. **Seed field registry** — define the canonical catalog (start with `auto_personal` commodities), then walk the top ~20 carrier domains from `insurance_websites.db` and record each one's quote flow + field mapping. (Top carriers cover most of the row volume anyway.)
2. **Next.js API + storage** — wire up the canonical value-set service and a `/quote` orchestrator that reads the registry and emits a fan-out plan.
3. **Playwright agent** — get one carrier form (`auto_personal`) filling end-to-end from the value set, then generalize to a multi-tab runner.
4. **Direct-API probe** — for the carriers in the registry that expose a quoting API, write the adapter and set `integration_method = api`; everything else stays Playwright.
5. **Voice-to-form** — single endpoint consumed by both clients; slot extraction onto the canonical schema.
6. **Flutter app** — voice capture + camera scan + comparison results screen.
7. **Document scanner** — OCR → canonical mapping, integrated as a value source above voice.
8. **Expand insurance types** — repeat the catalog + form-mapping work for `prop_homeowners`, then the rest in priority order.

## 11. Open questions to lock down before coding

- Which carriers (if any) in the registry are we cleared to automate via Playwright per their TOS? (Some explicitly prohibit scraping; those should be API-only or out-of-scope.)
- For the hackathon demo, do we hard-code the comparison presentation to a fixed set of carriers, or present everything `auto_personal` the registry has mapped so far?
- Voice STT: on-device (privacy, offline) vs hosted (accuracy)? Ship both behind a flag.
- Where does PII live at rest — SQLite with field encryption is fine for the hackathon, but Postgres + column encryption for prod.

## 12. Hackathon Execution (Aug 2026) — Ontario PPA Auto Focus

> PIVOT: the "Ontario All-Quote Agent Challenge" brief is scoped to **Ontario
> private-passenger auto only**, personal use, the participant's own profile. The
> earlier multi-line framing (condo / boat / life / home / travel) is **out of
> scope** for this submission. Keep those scripts for technique reuse but do not
> count them as auto results.

### Scope decision
- In scope: Ontario PPA auto quote obtainment + comparison for Corey Barron's own 2012 Ram 1500.
- Out of scope / mark explicitly: property, condo, boat, life, travel, commercial.
- Channels to attempt (per brief): direct writers, broker panels, aggregators, affinity,
  mutuals, specialty, residual market — with lawful access and honest terminal statuses only.

### Data layer (SQLite)
- `personal_profile.db` — participant identity, vehicle (Ram 1500), current insurance
  (Coachman / NFP binder). Loaded via `personal_profile.load_profile()`; scripts read
  `person.*`, `auto.*`, `current_insurance.*`.
- `market_registry.db` — 41 seed rows from the brief's Appendix A (32 groups / ~60 legal
  entities) + aggregator/broker/gap-fill routes. `rate_sources` table with registry_id,
  distribution_type, product_scope, quote_url, phone, status, distinct_rate_source_id.
- `insurance_websites.db` — carrier directory (source for URLs / phone routes).

### Confirmed profile (auto)
- Person: Corey Barron, DOB 1984/10/14 (41), single, M, 10 Tecumseh Cres, Kitchener ON N2B 2T4, renting $1,700/mo 2bdrm.
- Vehicle: 2012 RAM 1500 Big Horn Quad Cab 4WD, VIN 1C6RD7GT9CS103678, owned (used, bought Jan 2019), winter tires YES, anti-theft YES, non-business use.
- Current insurer: Coachman (SGI group), policy BINDER-BARRONCO01 via NFP Canada Corp (expired 30-day binder).
- To confirm: first-licence year (~2019 approx), annual km (15000 default), commute (5 days/15km default).

### Remaining work (prioritized)
1. **Verify + complete profile**: confirm licence year, annual km, commute, purchase price.
2. **Market registry validation** (brief: verify each route during the event):
   - Direct: Aviva (done), **belairdirect (done 2026-08-09 → $71.92/mo, quote #BA13933019)** → Allstate, CAA, Co-operators, Desjardins, RBC, Sonnet, Square One, TD, The Personal. See `RUN_REPORT.md`.
   - Broker aggregators: Rates.ca / LowestRates / Surex.
   - Independent broker verifier: ThinkInsure / Onlia / Scoop (RIBO) for full carrier-list disclosure.
   - Gap-fill: mutuals (Commonwell, Heartland, Peel, Portage), residual (Facility Assoc), non-standard (Echelon/Jevco/Pafco/Coachman), HNW (Chubb/PURE), collector (Hagerty). Mark `ineligible` / `specialty_only` / `affinity_restricted` if they don't fit the 2012 Ram.
   - Set `distinct_rate_source_id` for dedup (e.g. Coachman→SGI; belairdirect→Intact).
3. **Coverage normalization ledger** (brief benchmark): $2M TPL, DCPD included, standard
   mandatory medical/rehab/attendant, $1,000 collision+comp deductibles, OPCF 44R, no
   telematics. Record OPCF 20/27/43/44R + the July 1 2026 optional-benefit changes. Each
   result marked `quoted_comparable` vs `quoted_non_comparable`.
4. **Status enum + evidence store**: adopt the brief's 14 statuses; capture timestamp,
   source URL, quote/reference ID, premium, coverage, and a **redacted** artifact per outcome.
5. **Safety layer** (non-negotiable): redact evidence; no licence/VIN/address in logs, screenshots,
   repo, or prompts; consent before sharing each field + which-route-gets-which-fields disclosure;
   stop at CAPTCHA/anti-bot as `blocked` (record the Aviva headless CDN bot-block as an example);
   no binding/payment; delete data after judging.
6. **One voice/callback handoff**: compliant call (disclose automation, consent to record,
   no misrepresentation) for a `callback_required` route.
7. **Submission artifacts**: GitHub + setup, 3–5 min Loom, machine-readable registry
   (CSV/JSON from `market_registry.db`), redacted run report, architecture & safety note,
   known limitations.
8. **Metrics**: market completion, comparable quote yield, evidence rate, duplicate suppression, freshness.

### Submission minimums (from brief)
- At least one route returns a rate or exact terminal blocker (Aviva already returns a premium).
- At least two outcomes in the common schema with coverage differences shown.
- Registry distinguishes legal underwriter / group / brand / distributor / rate source.
- Every demonstrated outcome has timestamp + redacted evidence.
- No real licence number, full address, payment data, or unredacted call audio in the submission.
