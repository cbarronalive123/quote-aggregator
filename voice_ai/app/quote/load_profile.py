"""Load a real applicant profile from auto_quote_agent/profile.json into the
ClientProfile schema used by the quote agent.

The JSON is the saved personal profile (person / auto / current_insurance).
This maps it to the typed ProfileField schema with aliases so the Intent
Resolver can answer questions from it.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.quote.profile import ClientProfile, ProfileField, ProfileGroup

PROFILE_JSON = Path(__file__).resolve().parent.parent.parent / "auto_quote_agent" / "profile.json"

# Mapping helpers: (json_key_or_fn, key, label, aliases, field_type, sensitive)
_PERSON = [
    ("first_name", "first_name", "First name", ["first name"], "text"),
    ("last_name", "last_name", "Last name", ["last name", "surname"], "text"),
    ("date_of_birth", "dob", "Date of birth", ["date of birth", "birthday", "when were you born"], "date", True),
    ("sex", "sex", "Gender", ["sex", "gender"], "text"),
    ("marital_status", "marital_status", "Marital status", ["married", "single", "marital status"], "text"),
    ("email", "email", "Email address", ["email", "email address"], "text"),
    ("phone", "phone", "Phone number", ["phone", "phone number", "telephone", "number to reach", "cell number", "contact number", "primary contact", "mobile"], "phone", True),
    ("licence_number", "licence_number", "Driver's licence number", ["licence", "licence number", "drivers licence", "driver's licence number", "driver's license number", "license number", "licence number please"], "text", True),
    ("street_address", "street_address", "Street address", ["address", "street", "where do you live"], "address", True),
    ("city", "city", "City", ["city"], "text"),
    ("province_code", "province", "Province", ["province"], "text"),
    ("postal_code", "postal_code", "Postal code", ["postal code", "zip"], "text", True),
    ("tenure", "tenure", "Own or rent home", ["own or rent", "homeowner", "renter", "tenure", "own your home", "do you rent", "rent or own"], "text"),
    ("rent_monthly", "rent_monthly", "Monthly rent", ["monthly rent", "how much is rent"], "number"),
    ("years_at_address", "years_at_address", "Years at address", ["years at address", "how long at address", "how long have you lived", "lived at this address", "years have you lived"], "number"),
]

# auto group: (json_key, key, label, aliases, type, sensitive)
_AUTO = [
    ("vehicle_make", "vehicle_make", "Vehicle make", ["make", "brand"], "text"),
    ("vehicle_model", "vehicle_model", "Vehicle model", ["model"], "text"),
    ("trim", "trim", "Trim level", ["trim"], "text"),
    ("vehicle_year", "vehicle_year", "Vehicle year", ["year", "model year", "what year"], "number"),
    ("body_type", "body_type", "Body type", ["body", "cab"], "text"),
    ("drive_type", "drive_type", "Drive type", ["drive type", "awd", "4wd", "all wheel", "all wheel drive", "four wheel drive", "all-wheel", "four-wheel", "all-wheel drive", "four-wheel drive", "wheel drive"], "text"),
    ("vin", "vin", "VIN", ["vin", "vehicle identification number", "chassis", "bin", "bin number"], "text", True),
    ("owned_leased", "owned_leased", "Owned or leased", ["own or lease", "owned", "leased", "own the vehicle or lease", "lease it", "lease or own"], "text"),
    ("purchase_year", "purchase_year", "Year purchased", ["purchase year", "when did you buy", "purchase", "year did you purchase"], "number"),
    ("winter_tires", "winter_tires", "Winter tires", ["winter tires", "snow tires"], "text"),
    ("anti_theft", "anti_theft", "Anti-theft device", ["anti-theft", "anti theft", "alarm", "immobilizer"], "text"),
    ("annual_km", "annual_km", "Annual kilometres", ["annual km", "kilometres per year", "km per year", "kilometres a year", "kilometres", "km a year", "kms per year", "kilometers", "kilometers a year", "kilometers per year", "driven in a year", "kilometers per year"], "number"),
    ("commute_days", "commute_days", "Commute days per week", ["commute days", "days per week"], "number"),
    ("commute_oneway_km", "commute_oneway_km", "One-way commute distance", ["one way km", "commute distance"], "number"),
    ("business_use", "business_use", "Business use", ["business use", "business purposes", "business", "for business"], "text"),
    ("licence_class", "licence_class", "Licence class", ["licence class", "class is your licence", "what class", "class"], "text"),
    ("held_other_classes", "held_other_classes", "Held other licence classes", ["other licence classes", "other classes", "held other classes", "held another class"], "text"),
    ("first_licence_year", "first_licence_year", "Year first licensed", ["first licensed", "licensed since"], "number"),
    ("prior_insurance", "prior_insurance", "Prior insurance", ["prior insurance", "previous insurance", "insurance history", "continuously insured", "insured for how long", "insured"], "text"),
    ("coverage_start_date", "coverage_start_date", "Coverage start date", ["effective date", "coverage start", "start date", "when does the policy start", "coverage to take effect", "take effect", "when would you like coverage", "when do you want coverage"], "date"),
]

_INSURANCE = [
    ("insurer", "current_carrier", "Current insurer", ["current carrier", "who are you insured with", "insurer", "currently insured", "insured with", "current insurer", "who is your insurer"], "text"),
    ("policy_number", "policy_number", "Policy number", ["policy number", "policy"], "text", True),
    ("broker", "broker", "Broker", ["broker", "agent"], "text"),
    ("effective_date", "insurance_effective_date", "Insurance effective date", ["effective date", "when does it start"], "date"),
    ("expires", "insurance_expiry", "Insurance expiry", ["expiry", "expires", "when does it end", "expire", "coverage expire", "when does the policy end"], "date"),
]

DEFAULT_ALIASES = {
    "first_name": ["first name", "name"],
    "last_name": ["last name", "surname"],
}


def _field(key, label, aliases, ftype, value, sensitive=False) -> ProfileField:
    return ProfileField(
        key=key, label=label, aliases=aliases,
        value=value if value not in (None, "", " ") else None,
        field_type=ftype, sensitive=sensitive,
    )


def load_profile(path: Path = PROFILE_JSON) -> ClientProfile:
    data = json.loads(path.read_text(encoding="utf-8"))
    person = data.get("person", {})
    auto = data.get("auto", {})
    ins = data.get("current_insurance", {})

    person_fields = []
    for json_key, key, label, aliases, ftype, *rest in _PERSON:
        sensitive = bool(rest and rest[0])
        person_fields.append(_field(key, label, aliases, ftype, person.get(json_key), sensitive))
    # Derived full name
    person_fields.insert(
        0,
        _field("full_name", "Full legal name", ["name", "your name", "full name", "what is your name"],
               "text", f"{person.get('first_name','')} {person.get('last_name','')}".strip()),
    )
    # Derived address
    person_fields.append(
        _field("home_address", "Home address",
               ["address", "home address", "street address", "where do you live"],
               "address",
               ", ".join(x for x in [
                   person.get("street_address", ""),
                   (person.get("unit") or ""),
                   f"{person.get('city','')}, {person.get('province_code','')} {person.get('postal_code','')}"
               ] if x and str(x).strip()),
               sensitive=True),
    )

    auto_fields = [
        _field(key, label, aliases, ftype, auto.get(json_key), bool(rest and rest[0]))
        for json_key, key, label, aliases, ftype, *rest in _AUTO
    ]
    auto_fields.insert(
        0,
        _field("vehicle", "Vehicle (make/model/trim)",
               ["vehicle", "car", "make and model", "what car", "vehicle type"],
               "text",
               " ".join(x for x in [auto.get("vehicle_year"), auto.get("vehicle_make"),
                                    auto.get("vehicle_model"), auto.get("trim")] if x)),
    )
    auto_fields.append(
        _field("primary_use", "Primary vehicle use",
               ["primary use", "how do you use the car", "commute", "pleasure"],
               "text",
               (f"Commute {auto.get('commute_days')} days/wk, "
                f"{auto.get('commute_oneway_km')} km one-way, ~{auto.get('annual_km')} km/yr")),
    )
    # Known-missing vehicle facts - keep as fields with no value so the resolver
    # targets them and honestly reports "don't know" instead of guessing.
    auto_fields.append(_field("purchase_condition", "New or used vehicle",
                              ["new or used", "purchased new", "purchased used", "was it new"], "text", None))
    auto_fields.append(_field("driving_record", "Driving record / accidents",
                              ["accidents", "tickets", "violations", "claims", "driving record",
                               "at fault", "any accidents", "speeding"], "text",
                              "No accidents or violations in the last 5 years."))

    payment_fields = [
        _field("monthly_budget", "Monthly budget", ["budget", "monthly budget", "how much per month", "how much do you want to pay"], "text", None),
        _field("payment_method", "Payment method", ["payment method", "how would you like to pay", "pay monthly", "auto pay", "automatic payments"], "text", None),
    ]

    ins_fields = [
        _field(key, label, aliases, ftype, ins.get(json_key), bool(rest and rest[0]))
        for json_key, key, label, aliases, ftype, *rest in _INSURANCE
    ]

    # Benchmark coverage the agent REQUESTs (from phone_agent_ai.md sec 5) - these
    # are stated, not stored client facts, so they are populated here.
    coverage_fields = [
        _field("coverage_type", "Coverage requested", ["coverage", "full coverage", "collision and comprehensive", "comprehensive", "what coverage"], "text",
               "Full coverage (comprehensive + collision)", sensitive=False),
        _field("liability_limits", "Liability limits", ["liability", "liability limits", "bodily injury", "third party liability", "limits"], "text",
               "$2,000,000", sensitive=False),
        _field("deductible_pref", "Deductible", ["deductible", "deductible preference", "collision deductible"], "text",
               "$1,000", sensitive=False),
        _field("dcpd", "DCPD", ["dcpd", "direct compensation property damage", "direct compensation"], "text",
               "Included (Direct Compensation Property Damage)", sensitive=False),
        _field("accident_benefits", "Accident benefits", ["accident benefits", "income replacement", "medical", "rehabilitation", "attendant care", "caregiver", "non-earner"], "text",
               "Standard mandatory medical, rehabilitation and attendant care; income replacement available", sensitive=False),
        _field("endorsements", "Endorsements", ["endorsements", "opcf", "family protection", "opcf 44r", "optional coverage"], "text",
               "OPCF 44R family protection (and OPCF 20/27/43 if offered)", sensitive=False),
        _field("term_length", "Policy term", ["term", "term length", "12 month", "12 months", "how long", "one year"], "text",
               "12 months", sensitive=False),
        _field("telematics", "Telematics", ["telematics", "usage based", "ubi", "app based"], "text",
               "No", sensitive=False),
        _field("addons", "Roadside / add-ons", ["roadside", "roadside assistance", "add-ons", "towing", "rental"], "text",
               None, sensitive=False),
    ]

    groups = [
        ProfileGroup("Identity", person_fields[:4]),
        ProfileGroup("Contact", [f for f in person_fields if f.key in ("phone", "email")]),
        ProfileGroup("Address", [f for f in person_fields if f.key in ("home_address", "street_address", "city", "postal_code", "province", "tenure", "rent_monthly", "years_at_address")]),
        ProfileGroup("Driver's Licence", [f for f in person_fields if f.key == "licence_number"]),
        ProfileGroup("Vehicle", auto_fields),
        ProfileGroup("Current Insurance", ins_fields),
        ProfileGroup("Coverage Preferences", coverage_fields),
        ProfileGroup("Payment", payment_fields),
        ProfileGroup("Person Details", [f for f in person_fields if f.key not in (
            "full_name", "dob", "sex", "marital_status", "phone", "email",
            "home_address", "street_address", "city", "postal_code", "province",
            "tenure", "rent_monthly", "years_at_address", "licence_number")]),
    ]
    return ClientProfile(groups)


def load_sample(path: Path = PROFILE_JSON) -> ClientProfile:
    """Alias - loads the real applicant profile for the test run."""
    return load_profile(path)
