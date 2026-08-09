# Desjardins Auto Quote — Field-by-Field Automation Map

Verified live 2026-08-09 via Playwright MCP. Rater:
`https://clients.desjardinsgeneralinsurance.com/vehicle-quote/init/welcome?cs=au&mca=d&prv=on`
Legal underwriter shown: **Certas Direct Insurance Company**. Quote ref format: e.g. `ECG0BKRW`.

## Interaction gotchas (IMPORTANT)
- **Consent first.** A OneTrust cookie banner + a privacy "We need your consent" dialog appear.
  Dismiss the cookie banner ("Accept all") first, then the consent **Accept** button
  (`data-testid="wizard-next-button"`). Without dismissing the cookie banner the Accept
  click is intercepted and you never leave the consent step.
- **Controlled text inputs** (Last name, One-way commute, DOB Day/Year) sometimes IGNORE
  `.fill()`; commit with `pressSequentially` (real keystrokes).
- **Accessible selects** are readonly `<input class="accessible-select-input">` inside a
  combobox. Open by clicking the input, then click the `[role="option"]`. Options may
  repeat across groups ("Most popular" / "All makes") — click the first match.
- **Next buttons differ by phase:**
  - consent + steps 1–2: `data-testid="wizard-next-button"`
  - steps 3–9:           `data-testid="next-button"`
  - "See your coverage": `data-testid="action-Button-next"`
  - "Report claims manually": `data-testid="noLicenceButton"`
- reCAPTCHA protects the site. Stop as `blocked` if it blocks (never evade).

## Step 0 — Consent
- Cookie banner: button "Accept all" (OneTrust).
- Privacy consent dialog: button **Accept** = `data-testid="wizard-next-button"`.
- Advances URL to `?currentStep=clientInformationStep`.

## Step 1 — clientInformationStep ("Let's get started")
| Field | Selector / interaction | Values (FIXED/VARIABLE) |
|---|---|---|
| First name | `input[id^="datapersondetailsfirstName"]` | VARIABLE |
| Last name | `input[id^="datapersondetailslastName"]` (keystrokes) | VARIABLE |
| Gender | radio, name via label Female/Male | FIXED: Female \| Male |
| DOB Month | `input[id$="monthSelect--accessibleSelectInput"]` | FIXED: January–December |
| DOB Day | `input[id$="dayInput"]` | VARIABLE |
| DOB Year | `input[id$="yearSelect--accessibleSelectInput"]` | VARIABLE |
| Address | `input[id^="datacontactInfoAddressSuggestionValue"]` — type, click resolved option | autocomplete (Canada Post) |

## Step 2 — contactInfoStep ("Step 2 of 16")
| Field | Selector / interaction | Values |
|---|---|---|
| Phone | `input[id^="datapersoncommunicationInfophones0phoneValue"]` (auto-formats) | VARIABLE 10 digits |
| Phone type | select, default "Cell" | FIXED: Cell \| Home \| Work |
| Email | `input[id^="datapersoncommunicationInfoemailemailValue"]` | VARIABLE |
| Marketing consent | radio group, name `ConsentStatus` GRANTED/DENIED | No (data minimization) |
| Effective Month/Day/Year | same `monthSelect`/`dayInput`/`yearSelect` suffixes | e.g. Sept 01 2026 |

## Step 3 — vehicleSelectorStep
| Field | Values |
|---|---|
| Year | select (e.g. 2012) |
| Make | select — **DODGE/RAM** (label; two matches, click first) |
| Model | select — exact trim string, e.g. **RAM 1500 BIG HORN QUAD CAB 4X4** (option id `vehicle-model-277410`) |
| Type of use | radio: Personal \| Personal and business \| Commercial |

## Step 4 — vehicleInformationStep
| Field | Values (FIXED unless noted) |
|---|---|
| Acquisition Month/Year | select (Jan 2019) |
| Condition when acquired | New \| Used \| Demo |
| Vehicle ownership | Purchased and completely paid off \| Purchased and I make payments \| Leased |
| Modified vehicle | Yes \| No |
| Tracking system installed | None \| Domino \| Locate \| Tag System \| Other |
| Winter tires | Yes \| No |
| Parked overnight | Carport \| Private driveway \| Private garage \| Street \| Parking lot \| Underground parking \| Other |
| Kilometres driven yearly | VARIABLE digits (auto-formats, e.g. 15,000) |
| One-way commute | VARIABLE digits (keystrokes) |
| Vehicle used in US | Yes \| No |
| Additional vehicle | No \| Yes, add a vehicle |

## Step 5 — driverIdentificationStep ("Tell us more about you")
| Field | Values |
|---|---|
| Marital status | Single \| Common-law partner \| Married \| Separated \| Divorced \| Widowed |
| Employment status | Employed \| Self-employed \| Business owner \| Retired \| Homemaker \| Student \| Unemployed \| Prefer not to answer |
| Field of work (revealed if Employed) | 15 options incl. "Technology, computer science and multimedia" |
| Licence classes (checkboxes) | G (full) \| G2 \| G1 |
| Licence from elsewhere | Yes \| No |
| Age & month licence obtained | Age select ("N years old"), Month select |
| Current insurer | Allstate \| Aviva \| Belairdirect \| Broker \| CIBC \| Co-operators (Coseco) \| Desjardins \| Intact \| Johnson/RSA \| RBC \| Sonnet \| TD/Meloche \| The Personal \| Wawanesa \| Other/Unknown \| No current insurer |
| Years with current insurer | Less than 1 \| 1–5 \| 6 to 10 \| 11+ |
| Additional driver | No \| Yes, add a driver |

## Step 6 — driverAssignationStep
- Vehicle owner(s): checkbox (driver's full name) / Other
- Age became principal driver: select ("N years old")

## Step 7 — driverConvictionsStep
- Licence suspended: Yes \| No
- Convictions past 3 years (excl. parking/photo radar): Yes \| No

## Step 8 — driverClaimsStep
- "Report claims manually" = `data-testid="noLicenceButton"` (avoids a claims-DB look-up with a
  fabricated licence). Then: "No claims to declare" \| "Yes – add claims".

## Step 9 — savingsDiscountsStep
- Multi-Line (insure home) discount: Yes \| No (renter → No)

## Step 10 — offersStep (premium shown here)
- Ajusto (telematics) interest: Yes \| No (benchmark = no telematics → No).
- **Premium appears** e.g. "$216.42 /month"; "See your coverage" = `data-testid="action-Button-next"`.

## Step 11 — coveragesStep ("Customize your offer")
- Capture premium (regex `\$\s?\d[\d,]*\.?\d*\s*/month`) + coverage rows.
- Default coverage (dummy data): TPL $1,000,000 (needs raising to $2M benchmark), DCPD $0,
  Collision $1,000, Comprehensive $1,000, Accident Benefits Included, Family Protection Included.

## Captured test result (DUMMY data — NOT a real quote)
- Quote ref: ECG0BKRW (manual MCP walk) — premium **$216.42/month** (no telematics).
- This used fake name/DOB; valid only for testing the automation, not as evidence.
