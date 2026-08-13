// Web intake form schema. This is the "one intake" — it must collect the superset
// of every field any carrier form needs so a single submission can fill any of them.
// Derived from the field_registry.json + personal_profile.db auto fields + the
// per-carrier auto quote scripts (belairdirect, Aviva, Erie Mutual, Bertram & Barry,
// Verge, APRIL) and the OAF-1 canonical schema from the hackathon brief.

export interface FieldDef {
  key: string;
  label: string;
  type: "text" | "email" | "tel" | "number" | "date" | "select" | "radio";
  options?: string[];
  required?: boolean;
  placeholder?: string;
  // Which carrier forms (in the repo) this field feeds — for the coverage note.
  feeds?: string[];
}

export interface Section {
  id: string;
  title: string;
  description: string;
  fields: FieldDef[];
}

export const formSections: Section[] = [
  {
    id: "contact",
    title: "Your information",
    description: "Who you are — fills the applicant/contact step on every carrier form.",
    fields: [
      { key: "first_name", label: "First name", type: "text", required: true, feeds: ["belairdirect", "Aviva", "Erie", "Bertram & Barry", "Verge"] },
      { key: "last_name", label: "Last name", type: "text", required: true, feeds: ["belairdirect", "Aviva", "Erie", "Bertram & Barry", "Verge"] },
      { key: "email", label: "Email", type: "email", required: true, feeds: ["belairdirect", "Aviva", "Erie", "Bertram & Barry", "Verge"] },
      { key: "phone", label: "Phone number", type: "tel", required: true, feeds: ["belairdirect", "Aviva", "Erie", "Bertram & Barry", "Verge"] },
      { key: "phone_type", label: "Phone type", type: "select", options: ["Mobile", "Home", "Work"], required: true, feeds: ["belairdirect", "Aviva"] },
      { key: "date_of_birth", label: "Date of birth", type: "date", required: true, feeds: ["belairdirect", "Aviva", "Erie", "Bertram & Barry", "Verge", "APRIL"] },
      { key: "sex", label: "Gender", type: "select", options: ["M", "F", "X"], required: true, feeds: ["belairdirect", "Aviva", "Erie", "Bertram & Barry", "APRIL"] },
      { key: "marital_status", label: "Marital status", type: "select", options: ["S", "M", "C", "P", "D", "W"], required: true, feeds: ["Aviva", "Bertram & Barry"] },
      { key: "privacy_consent", label: "Consent to quote (privacy)", type: "select", options: ["Yes", "No"], required: true, feeds: ["belairdirect", "Aviva", "Allstate"] },
      { key: "marketing_consent", label: "Marketing / communications consent", type: "select", options: ["No", "Yes"], required: true, feeds: ["belairdirect", "Aviva", "Allstate"] },
    ],
  },
  {
    id: "address",
    title: "Garaging address",
    description: "Where the vehicle is parked — feeds postal code, province and the insurer's territory rating.",
    fields: [
      { key: "street_address", label: "Street address", type: "text", required: true, feeds: ["Verge", "Bertram & Barry", "Erie"] },
      { key: "unit", label: "Unit (optional)", type: "text", feeds: ["personal_profile"] },
      { key: "city", label: "City", type: "text", required: true, feeds: ["Verge", "Bertram & Barry"] },
      { key: "province", label: "Province", type: "select", options: ["Ontario", "Alberta", "British Columbia", "Manitoba", "New Brunswick", "Newfoundland and Labrador", "Nova Scotia", "Northwest Territories", "Nunavut", "Prince Edward Island", "Quebec", "Saskatchewan", "Yukon"], required: true, feeds: ["all"] },
      { key: "postal_code", label: "Postal code", type: "text", required: true, feeds: ["belairdirect", "Aviva", "Erie", "Verge", "Bertram & Barry"] },
      { key: "tenure", label: "Residence type", type: "select", options: ["Renting", "Owning"], required: true, feeds: ["personal_profile", "some raters"] },
    ],
  },
  {
    id: "vehicle",
    title: "Your vehicle",
    description: "The car being insured — supports both VIN lookup and manual year/make/model.",
    fields: [
      { key: "vin", label: "VIN (optional — fastest)", type: "text", feeds: ["belairdirect", "Aviva", "most raters"] },
      { key: "vehicle_year", label: "Year", type: "number", required: true, feeds: ["belairdirect", "Aviva", "Erie", "Bertram & Barry"] },
      { key: "vehicle_make", label: "Make", type: "text", required: true, feeds: ["belairdirect", "Aviva", "Erie", "Bertram & Barry"] },
      { key: "vehicle_model", label: "Model", type: "text", required: true, feeds: ["belairdirect", "Aviva", "Erie", "Bertram & Barry"] },
      { key: "trim", label: "Trim / body type", type: "text", feeds: ["belairdirect", "personal_profile"] },
      { key: "drive_type", label: "Drive type", type: "select", options: ["4WD", "AWD", "FWD", "RWD"], feeds: ["personal_profile"] },
      { key: "fuel_type", label: "Fuel type", type: "select", options: ["Gas", "Diesel", "Hybrid", "Electric"], feeds: ["personal_profile"] },
      { key: "owned_leased", label: "Owned, financed or leased", type: "select", options: ["Owned", "Financed", "Leased"], required: true, feeds: ["Aviva", "Allstate", "personal_profile"] },
      { key: "only_registered_owner", label: "Are you the only registered owner?", type: "select", options: ["Yes", "No"], required: true, feeds: ["Allstate"] },
      { key: "ownership_within_30_days", label: "Took ownership within the last 30 days?", type: "select", options: ["No", "Yes"], required: true, feeds: ["Allstate"] },
      { key: "purchase_price", label: "Purchase price (incl. tax)", type: "number", placeholder: "e.g. 25000", feeds: ["Allstate"] },
      { key: "purchase_condition", label: "New or used", type: "select", options: ["New", "Used", "Demo"], required: true, feeds: ["Aviva", "belairdirect"] },
      { key: "purchase_month", label: "Purchase month", type: "select", options: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], feeds: ["Aviva"] },
      { key: "purchase_year", label: "Purchase year", type: "number", feeds: ["Aviva"] },
    ],
  },
  {
    id: "usage",
    title: "How you use it",
    description: "Driving habits — commute, mileage, discounts and safety features.",
    fields: [
      { key: "annual_km", label: "Annual kilometres", type: "number", required: true, feeds: ["belairdirect", "Aviva", "Erie"] },
      { key: "commute_days", label: "Days commuting / week", type: "select", options: ["0", "1", "2", "3", "4", "5", "6", "7"], required: true, feeds: ["belairdirect", "Aviva", "Bertram & Barry"] },
      { key: "commute_oneway_km", label: "One-way commute (km)", type: "number", feeds: ["belairdirect", "Aviva", "Erie"] },
      { key: "business_use", label: "Business use?", type: "select", options: ["No", "Yes"], required: true, feeds: ["Aviva", "Bertram & Barry", "Erie"] },
      { key: "winter_tires", label: "Winter tires", type: "select", options: ["Yes", "No"], required: true, feeds: ["Aviva", "belairdirect"] },
      { key: "anti_theft", label: "Anti-theft device", type: "select", options: ["No", "Yes"], required: true, feeds: ["Aviva", "belairdirect"] },
      { key: "parking", label: "Where do you park most of the time?", type: "select", options: ["Home Garage", "Home Driveway", "Home Carport", "Secured Condo/Apt Garage", "Unsecured Condo/Apt Garage or lot", "Street", "Location other than my residence"], required: true, feeds: ["Allstate"] },
      { key: "adas_features", label: "ADAS safety features", type: "select", options: ["None", "Forward Collision Mitigation", "Lane Departure Mitigation", "Selectable (restricted) Driver Mode", "Driver Monitor", "Forward/Rear Collision/Lane Departure Warning", "Parking Assist Sensor and/or Camera"], required: true, feeds: ["Allstate"] },
    ],
  },
  {
    id: "driver",
    title: "Driver's licence",
    description: "Licensing history and driving record.",
    fields: [
      { key: "licence_class", label: "Licence class", type: "select", options: ["G", "G2", "Other"], required: true, feeds: ["belairdirect", "Aviva"] },
      { key: "age_first_licensed", label: "Age when you first got your driver's licence", type: "number", feeds: ["belairdirect", "Allstate"] },
      { key: "first_licence_month", label: "First licensed — month", type: "select", options: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], feeds: ["Aviva"] },
      { key: "first_licence_year", label: "First licensed (year)", type: "number", required: true, feeds: ["belairdirect", "Aviva", "Bertram & Barry"] },
      { key: "held_other_classes", label: "Held a graduated licence (G2/G1)?", type: "select", options: ["Yes", "No"], feeds: ["Aviva", "Allstate"] },
      { key: "g2_month", label: "Got your G2 — month", type: "select", options: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], feeds: ["Aviva"] },
      { key: "g2_year", label: "Got your G2 — year", type: "number", feeds: ["Aviva"] },
      { key: "g_within_12_months", label: "Got your G licence within the last 12 months?", type: "select", options: ["No", "Yes"], feeds: ["Allstate"] },
      { key: "years_with_insurer", label: "Years with current insurer", type: "select", options: ["Less than 1 year", "1–2 years", "2–3 years", "3–5 years", "5 years or more"], feeds: ["belairdirect"] },
      { key: "prior_insurance", label: "Prior insurance history", type: "select", options: ["More than 3 years", "Less than 3 years"], feeds: ["Aviva", "Allstate"] },
      { key: "combined_policy", label: "Combined policy discount (bundle)", type: "select", options: ["No", "I do", "My partner does"], feeds: ["Aviva"] },
      { key: "telus_health", label: "TELUS Health customer?", type: "select", options: ["No", "Yes"], feeds: ["Aviva"] },
      { key: "convictions", label: "Minor driving violations", type: "select", options: ["None", "1", "2", "More than 2"], feeds: ["Erie", "Bertram & Barry", "Allstate"] },
      { key: "major_violations", label: "Major / criminal violations (3 yrs)?", type: "select", options: ["No", "Yes"], feeds: ["Allstate"] },
      { key: "accidents", label: "Accidents (6 years)", type: "select", options: ["None", "1", "2", "3", "4", "5"], feeds: ["Erie", "Bertram & Barry"] },
      { key: "license_suspended", label: "Licence suspended in the last 6 years?", type: "select", options: ["No", "Yes"], feeds: ["Allstate"] },
      { key: "other_household_drivers", label: "Other licensed drivers in household?", type: "select", options: ["No", "Yes"], feeds: ["Allstate"] },
      { key: "retired", label: "Retired?", type: "select", options: ["No", "Yes"], feeds: ["Aviva"] },
    ],
  },
  {
    id: "coverage",
    title: "Coverage & policy",
    description: "The benchmark package every carrier should be asked to match.",
    fields: [
      { key: "coverage_start_date", label: "Coverage start date", type: "date", required: true, feeds: ["belairdirect", "Aviva", "Erie", "Verge"] },
      { key: "liability", label: "Liability limit", type: "select", options: ["$2,000,000", "$1,000,000", "$5,000,000"], required: true, feeds: ["Bertram & Barry", "benchmark"] },
      { key: "coverage_type", label: "Own-damage coverage", type: "select", options: ["All perils", "Collision", "Comprehensive", "Specific perils"], feeds: ["Bertram & Barry"] },
      { key: "deductible", label: "Deductible", type: "select", options: ["$1,000", "$500", "$250"], required: true, feeds: ["Bertram & Barry", "benchmark"] },
      { key: "cancellation_nonpayment", label: "Cancelled for non-payment?", type: "select", options: ["No", "Yes"], feeds: ["Verge"] },
    ],
  },
];

// Flatten all keys for the default-profile initializer.
export const allFieldKeys = formSections.flatMap((s) => s.fields.map((f) => f.key));
