"""Natural spoken phrasing for profile answers.

Turns a raw field value into something that sounds natural when the agent
speaks it (e.g. province "ON" -> "Ontario", DOB "1984/10/14" -> "October 14th,
1984", tenure "renting" -> "They rent.").
"""

from __future__ import annotations

import re

PROVINCES = {
    "ON": "Ontario", "QC": "Quebec", "NS": "Nova Scotia", "NB": "New Brunswick",
    "MB": "Manitoba", "BC": "British Columbia", "PE": "Prince Edward Island",
    "SK": "Saskatchewan", "AB": "Alberta", "NL": "Newfoundland and Labrador",
    "YT": "Yukon", "NT": "Northwest Territories", "NU": "Nunavut",
}

MONTHS = {i: name for i, name in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _spoken_date(value) -> str:
    """Format a date naturally, e.g. 09/01/2026 -> September 1st, 2026."""
    v = str(value).strip()
    m = re.search(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", v)  # YYYY-MM-DD
    if m:
        year, month, day = m.groups()
        return f"{MONTHS.get(int(month), month)} {_ordinal(int(day))}, {year}"
    m = re.search(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", v)  # MM/DD/YYYY
    if m:
        month, day, year = m.groups()
        return f"{MONTHS.get(int(month), month)} {_ordinal(int(day))}, {year}"
    return v


def _yes_no(value: str, yes: str, no: str) -> str:
    return yes if str(value).strip().lower().startswith("y") else no


def spell_chars(value) -> str:
    """Spell an alphanumeric ID character-by-character so TTS reads it as
    separate letters/numbers (and '0' as 'zero'), e.g. B0672 -> 'B 0 6 7 2'."""
    parts = []
    for ch in str(value):
        if ch.isalnum():
            parts.append("zero" if ch == "0" else ch.upper())
        elif ch in "- ":
            parts.append("hyphen" if ch == "-" else " ")
    return " ".join(p for p in parts if p)


def spell_letters(value) -> str:
    """Letters only, spaced, for spelling names slowly: 'Barron' -> 'B A R R O N'."""
    return " ".join(c.upper() for c in str(value) if c.isalnum())


_TEMPLATES = {
    "full_name": lambda f: f"The full name is {f.value}.",
    "dob": lambda f: f"Date of birth is {_spoken_date(f.value)}.",
    "sex": lambda f: "Male." if str(f.value).upper().startswith("M")
                    else "Female." if str(f.value).upper().startswith("F") else f"{f.value}.",
    "marital_status": lambda f: f"Marital status is {f.value}.",
    "email": lambda f: f"The email is {f.value}.",
    "phone": lambda f: f"The phone number is {f.value}.",
    "street_address": lambda f: f"The address is {f.value}.",
    "city": lambda f: f"{f.value}.",
    "province": lambda f: f"{PROVINCES.get(f.value, f.value)}.",
    "province_code": lambda f: f"{PROVINCES.get(f.value, f.value)}.",
    "postal_code": lambda f: f"{f.value}.",
    "tenure": lambda f: "They rent." if str(f.value).lower().startswith("rent")
                     else f"{f.value}.",
    "rent_monthly": lambda f: f"Rent is {f.value} dollars per month.",
    "licence_number": lambda f: f"The licence number is {spell_chars(f.value)}.",
    "licence_class": lambda f: f"Licence class {f.value}.",
    "first_licence_year": lambda f: f"First licensed in {f.value}.",
    "vehicle": lambda f: f"A {f.value}.",
    "vehicle_year": lambda f: f"{f.value}.",
    "drive_type": lambda f: f"{f.value}.",
    "vin": lambda f: f"The VIN is {spell_chars(f.value)}.",
    "owned_leased": lambda f: f"{str(f.value).title()}.",
    "purchase_year": lambda f: f"Purchased in {f.value}.",
    "winter_tires": lambda f: _yes_no(f.value, "Yes, winter tires are installed.",
                                      "No winter tires."),
    "anti_theft": lambda f: _yes_no(f.value, "Yes, it has an anti-theft device.",
                                    "No anti-theft device."),
    "annual_km": lambda f: f"About {f.value} kilometers per year.",
    "commute_days": lambda f: f"{f.value} days a week.",
    "commute_oneway_km": lambda f: f"{f.value} kilometers one way.",
    "business_use": lambda f: _yes_no(f.value, "Yes, used for business.",
                                      "No, not used for business."),
    "driving_record": lambda f: f"{str(f.value).rstrip('.')}.",
    "current_carrier": lambda f: f"Currently insured with {f.value}.",
    "policy_number": lambda f: f"Policy number {spell_chars(f.value)}.",
    "broker": lambda f: f"The broker is {f.value}.",
    "insurance_expiry": lambda f: f"The policy expires on {_spoken_date(f.value)}.",
    "prior_insurance": lambda f: f"Continuously insured for {f.value}.",
    "coverage_start_date": lambda f: f"Coverage starts on {_spoken_date(f.value)}.",
    "coverage_type": lambda f: f"{f.value}.",
    "liability_limits": lambda f: f"Liability limits of {f.value}.",
    "deductible_pref": lambda f: f"A {f.value} deductible.",
    "dcpd": lambda f: f"DCPD, direct compensation property damage, {f.value}.",
    "accident_benefits": lambda f: f"Standard accident benefits with {f.value}.",
    "endorsements": lambda f: f"{f.value}.",
    "term_length": lambda f: f"A {str(f.value).replace(' months', '-month').replace('months', '-month')} term.",
    "telematics": lambda f: _yes_no(f.value, "No telematics.", f"Telematics {f.value}."),
}


def spoken_answer(field) -> str:
    tpl = _TEMPLATES.get(field.key)
    if tpl:
        return tpl(field)
    value = str(field.value)
    if field.key in ("province", "province_code"):
        value = PROVINCES.get(value, value)
    if field.key == "dob":
        value = _spoken_dob(value)
    return f"{field.label}: {value}"
