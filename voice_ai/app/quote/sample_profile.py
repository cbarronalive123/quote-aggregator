"""A filled example ClientProfile for testing the quote agent.

Realistic data for a sample client, with aliases that cover how a human
insurance agent might phrase each question.
"""

from __future__ import annotations

from app.quote.profile import ClientProfile, ProfileField, ProfileGroup


def build_sample_profile() -> ClientProfile:
    return ClientProfile(
        groups=[
            ProfileGroup(
                name="Identity",
                fields=[
                    ProfileField(
                        key="full_name",
                        label="Full legal name",
                        aliases=["name", "your name", "full name", "what is your name"],
                        value="Jordan Avery Brooks",
                    ),
                    ProfileField(
                        key="dob",
                        label="Date of birth",
                        aliases=[
                            "date of birth",
                            "birthday",
                            "birth date",
                            "when were you born",
                            "date born",
                        ],
                        value="1990-04-12",
                        field_type="date",
                        sensitive=True,
                    ),
                    ProfileField(
                        key="gender",
                        label="Gender",
                        aliases=["sex", "gender"],
                        value="Non-binary",
                    ),
                    ProfileField(
                        key="marital_status",
                        label="Marital status",
                        aliases=["married", "single", "marital status"],
                        value="Married",
                    ),
                ],
            ),
            ProfileGroup(
                name="Contact",
                fields=[
                    ProfileField(
                        key="phone",
                        label="Phone number",
                        aliases=["phone", "phone number", "telephone", "cell number", "number to reach"],
                        value="(555) 012-3456",
                        field_type="phone",
                        sensitive=True,
                    ),
                    ProfileField(
                        key="email",
                        label="Email address",
                        aliases=["email", "email address", "e-mail"],
                        value="jordan.brooks@example.com",
                    ),
                ],
            ),
            ProfileGroup(
                name="Address",
                fields=[
                    ProfileField(
                        key="home_address",
                        label="Home address",
                        aliases=[
                            "address",
                            "home address",
                            "street address",
                            "where do you live",
                            "mailing address",
                        ],
                        value="742 Maple Avenue, Apt 3B, Springfield, IL 62704",
                        field_type="address",
                        sensitive=True,
                    ),
                    ProfileField(
                        key="zip_code",
                        label="ZIP code",
                        aliases=["zip", "zip code", "postal code"],
                        value="62704",
                        sensitive=True,
                    ),
                    ProfileField(
                        key="own_or_rent",
                        label="Own or rent home",
                        aliases=["own or rent", "homeowner", "renter", "own your home"],
                        value="Rent",
                    ),
                ],
            ),
            ProfileGroup(
                name="Vehicle",
                fields=[
                    ProfileField(
                        key="vehicle_make_model",
                        label="Vehicle make and model",
                        aliases=["vehicle", "car", "make and model", "what car", "vehicle type"],
                        value="2021 Toyota Corolla",
                    ),
                    ProfileField(
                        key="vehicle_year",
                        label="Vehicle year",
                        aliases=["year", "model year", "what year"],
                        value="2021",
                        field_type="number",
                    ),
                    ProfileField(
                        key="vin",
                        label="VIN",
                        aliases=["vin", "vehicle identification number", "chassis number"],
                        value="JTDBR32E201234567",
                        sensitive=True,
                    ),
                    ProfileField(
                        key="primary_use",
                        label="Primary vehicle use",
                        aliases=["primary use", "how do you use the car", "commute", "pleasure"],
                        value="Commute to work, ~20 miles round trip",
                    ),
                ],
            ),
            ProfileGroup(
                name="License and Driving",
                fields=[
                    ProfileField(
                        key="license_number",
                        label="Driver's license number",
                        aliases=["license number", "drivers license", "license"],
                        value="D123-4567-8910",
                        sensitive=True,
                    ),
                    ProfileField(
                        key="license_state",
                        label="License state",
                        aliases=["license state", "state", "state of license"],
                        value="Illinois",
                    ),
                    ProfileField(
                        key="driving_record",
                        label="Driving history / accidents",
                        aliases=[
                            "accidents",
                            "tickets",
                            "violations",
                            "driving record",
                            "any accidents in the last 3 years",
                            "any tickets",
                        ],
                        value="No accidents or violations in the last 5 years.",
                    ),
                    ProfileField(
                        key="years_driving",
                        label="Years driving",
                        aliases=["years driving", "how long have you been driving", "experience"],
                        value="12",
                        field_type="number",
                    ),
                ],
            ),
            ProfileGroup(
                name="Current Policy",
                fields=[
                    ProfileField(
                        key="has_current_policy",
                        label="Current auto policy",
                        aliases=["current policy", "do you have insurance", "currently insured", "existing coverage"],
                        value="Yes",
                        field_type="bool",
                    ),
                    ProfileField(
                        key="current_carrier",
                        label="Current carrier",
                        aliases=["current carrier", "current company", "who are you insured with"],
                        value="Geico",
                    ),
                    ProfileField(
                        key="current_policy_expiry",
                        label="Current policy expiry",
                        aliases=["policy expiry", "when does your policy end", "expiration date"],
                        value="2026-09-30",
                        field_type="date",
                    ),
                ],
            ),
            ProfileGroup(
                name="Coverage Preferences",
                fields=[
                    ProfileField(
                        key="coverage_type",
                        label="Coverage type requested",
                        aliases=[
                            "coverage",
                            "what coverage",
                            "full coverage",
                            "liability only",
                            "state minimum",
                            "comprehensive and collision",
                        ],
                        value="Full coverage (comprehensive + collision)",
                    ),
                    ProfileField(
                        key="deductible_pref",
                        label="Preferred deductible",
                        aliases=["deductible", "preferred deductible", "collision deductible"],
                        value="$500",
                        field_type="number",
                    ),
                    ProfileField(
                        key="liability_limits",
                        label="Liability limits preference",
                        aliases=["liability", "liability limits", "bodily injury", "property damage limits"],
                        value="$100,000 / $300,000",
                    ),
                    ProfileField(
                        key="addons",
                        label="Add-ons / roadside / rental",
                        aliases=["roadside assistance", "rental reimbursement", "add-ons", "towing", "extras"],
                        value="Interested in roadside assistance",
                    ),
                ],
            ),
            ProfileGroup(
                name="Payment",
                fields=[
                    ProfileField(
                        key="payment_method",
                        label="Preferred payment method",
                        aliases=["payment method", "how would you like to pay", "pay monthly", "auto-pay"],
                        value="Monthly auto-pay",
                    ),
                    ProfileField(
                        key="down_payment_budget",
                        label="Down payment / budget",
                        aliases=["budget", "how much do you want to pay", "monthly budget", "down payment"],
                        value="Comfortable up to $160/month",
                    ),
                ],
            ),
        ]
    )


SAMPLE_PROFILE = build_sample_profile()
