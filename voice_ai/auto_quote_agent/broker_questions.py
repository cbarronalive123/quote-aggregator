"""Broker question set for the auto quote agent (test profile).

A broker asks these live (in any order). Each entry maps to the profile field it
targets (`field`) and the expected answer (`answer`); `answer=None` means the
profile doesn't hold it (the agent must say it doesn't know / needs to be asked).
Extensible - just add more dicts to the list.
"""

from __future__ import annotations

BROKER_QUESTIONS: list[dict] = [
    # ---- Identity ----
    {"q": "May I have your full legal name?", "field": "full_name", "answer": "Test Driver"},
    {"q": "What is your first name?", "field": "first_name", "answer": "Test"},
    {"q": "And your last name?", "field": "last_name", "answer": "Driver"},
    {"q": "What is your date of birth?", "field": "dob", "answer": "May 10th, 1985"},
    {"q": "What is your gender?", "field": "sex", "answer": "M"},
    {"q": "Are you married, single, or something else?", "field": "marital_status", "answer": "S"},

    # ---- Contact ----
    {"q": "What is your email address?", "field": "email", "answer": "test@example.com"},
    {"q": "What is your phone number?", "field": "phone", "answer": "4165550101"},
    {"q": "Can I get your cell number as well?", "field": "phone", "answer": "4165550101"},
    {"q": "Is that your primary contact number?", "field": "phone", "answer": "4165550101"},

    # ---- Address ----
    {"q": "What is your current street address?", "field": "street_address", "answer": "123 Example St"},
    {"q": "What is your unit or apartment number?", "field": None, "answer": None},
    {"q": "What city do you live in?", "field": "city", "answer": "Toronto"},
    {"q": "What province are you in?", "field": "province", "answer": "ON"},
    {"q": "What is your postal code?", "field": "postal_code", "answer": "M5V 2T6"},
    {"q": "Do you own or rent your home?", "field": "tenure", "answer": "rent"},
    {"q": "How much is your monthly rent?", "field": "rent_monthly", "answer": "1500"},
    {"q": "How many years have you lived at this address?", "field": "years_at_address", "answer": None},
    {"q": "How many bedrooms does the home have?", "field": None, "answer": None},

    # ---- Driver's licence ----
    {"q": "What is your driver's licence number?", "field": "licence_number", "answer": "D123-4567-8910"},
    {"q": "What class is your licence?", "field": "licence_class", "answer": "G"},
    {"q": "In what province is your licence issued?", "field": "province", "answer": "ON"},
    {"q": "What year were you first licensed?", "field": "first_licence_year", "answer": "2003"},
    {"q": "Have you held any other licence classes?", "field": "held_other_classes", "answer": "yes"},

    # ---- Vehicle ----
    {"q": "Tell me about the vehicle you'd like to insure.", "field": "vehicle", "answer": "2019 Honda Accord"},
    {"q": "What is the make of the vehicle?", "field": "vehicle_make", "answer": "HONDA"},
    {"q": "What is the model?", "field": "vehicle_model", "answer": "ACCORD EX 4DR"},
    {"q": "What year is the vehicle?", "field": "vehicle_year", "answer": "2019"},
    {"q": "What is the trim level?", "field": "trim", "answer": "EX"},
    {"q": "What is the body type?", "field": "body_type", "answer": "Sedan"},
    {"q": "Is it all-wheel drive or four-wheel drive?", "field": "drive_type", "answer": "FWD"},
    {"q": "Can I get the VIN?", "field": "vin", "answer": "1HGCM82633A004352"},
    {"q": "Do you own the vehicle or lease it?", "field": "owned_leased", "answer": "owned"},
    {"q": "Was it purchased new or used?", "field": None, "answer": None},
    {"q": "What year did you purchase it?", "field": "purchase_year", "answer": "2019"},
    {"q": "Does the vehicle have winter tires?", "field": "winter_tires", "answer": "yes"},
    {"q": "Does it have an anti-theft device?", "field": "anti_theft", "answer": "no"},
    {"q": "How many kilometres do you drive in a year?", "field": "annual_km", "answer": "12000"},
    {"q": "How many days a week do you commute?", "field": "commute_days", "answer": "5"},
    {"q": "What is your one-way commute distance?", "field": "commute_oneway_km", "answer": "10"},
    {"q": "Do you use the vehicle for business purposes?", "field": "business_use", "answer": "no"},

    # ---- Current insurance ----
    {"q": "Are you currently insured?", "field": "insurer", "answer": "Example Broker"},
    {"q": "Who is your current insurer?", "field": "insurer", "answer": "Example Broker"},
    {"q": "What is your current policy number?", "field": "policy_number", "answer": "TEST-POLICY-001"},
    {"q": "Who is your broker?", "field": "broker", "answer": "Sample Brokerage Inc."},
    {"q": "When does your current coverage expire?", "field": "expires", "answer": "2026/09/01"},
    {"q": "How long have you been continuously insured?", "field": "prior_insurance", "answer": "greatthan3years"},
    {"q": "Do you have a claims-free record?", "field": None, "answer": None},
    {"q": "Have you had any accidents in the last three years?", "field": None, "answer": None},

    # ---- Coverage / benchmark ----
    {"q": "What effective date do you need?", "field": "coverage_start_date", "answer": "09/01/2026"},
    {"q": "What third-party liability limits are you looking for?", "field": "liability_limits", "answer": "$2,000,000"},
    {"q": "What liability limits are you looking for?", "field": "liability_limits", "answer": "$2,000,000"},
    {"q": "Do you want DCPD included?", "field": "dcpd", "answer": "Included"},
    {"q": "What accident benefits coverage do you need?", "field": "accident_benefits", "answer": "Standard"},
    {"q": "Do you want income replacement coverage?", "field": "accident_benefits", "answer": "available"},
    {"q": "What deductible do you prefer?", "field": "deductible_pref", "answer": "$1,000"},
    {"q": "Do you want collision and comprehensive?", "field": "coverage_type", "answer": "Full coverage"},
    {"q": "What own-damage coverage do you want (collision and comprehensive)?", "field": "coverage_type", "answer": "Full coverage"},
    {"q": "Are you interested in any optional endorsements?", "field": "endorsements", "answer": "OPCF 44R"},
    {"q": "Do you want OPCF 44R family protection?", "field": "endorsements", "answer": "OPCF 44R"},
    {"q": "How long a term are you looking for?", "field": "term_length", "answer": "12-month"},
    {"q": "Is this a 12-month term?", "field": "term_length", "answer": "12-month"},
    {"q": "Are you interested in roadside assistance or add-ons?", "field": "addons", "answer": None},
    {"q": "Do you want to opt into telematics / usage-based insurance?", "field": "telematics", "answer": "No"},

    # ---- Payment ----
    {"q": "How would you like to pay?", "field": None, "answer": None},
    {"q": "What is your monthly budget for this policy?", "field": None, "answer": None},
    {"q": "Do you want to set up automatic payments?", "field": None, "answer": None},
]

GROUP_HEADERS = {
    "Identity": "May I have your full legal name?",
    "Contact": "What is your email address?",
    "Address": "What is your current street address?",
    "Driver's licence": "What is your driver's licence number?",
    "Vehicle": "Tell me about the vehicle you'd like to insure.",
    "Current insurance": "Are you currently insured?",
    "Coverage": "What effective date do you need?",
    "Payment": "How would you like to pay?",
}


def group_of(q: dict) -> str:
    for name, first_q in GROUP_HEADERS.items():
        if q["q"] == first_q:
            return name
    return ""
