// Server-only profile store. The "my profile" (real applicant) is persisted in the
// website's SQLite DB (quotedrive.db) so it isn't hardcoded in the client bundle.
// "Fake profile" values are generated fresh on every request (never stored) so repeat
// test submissions are always unique and don't trip a carrier's rate limiter.
//
// Only import this from server components / route handlers — never from a client component.

import { all, get, run } from "./db";
import { defaultProfile } from "./data";
import { formSections, type FieldDef } from "./formSchema";

const TABLE = "intake_profiles";

// All form keys, so generated/loaded profiles always cover every field the form asks.
const formKeys: string[] = formSections.flatMap((s) => s.fields.map((f) => f.key));

function ensureTable() {
  run(
    `CREATE TABLE IF NOT EXISTS ${TABLE} (
      profile_key TEXT PRIMARY KEY,
      kind TEXT,
      name TEXT,
      data TEXT
    )`
  );
}

function buildSavedValues(): Record<string, string> {
  const src = defaultProfile as Record<string, string>;
  const v: Record<string, string> = {};
  for (const k of formKeys) v[k] = src[k] ?? "";
  return v;
}

// Ensure the "my profile" row exists (seeded from the canonical source), so reads
// always return a complete profile even on a fresh server / empty DB.
export function ensureSavedProfile() {
  ensureTable();
  const row = get<{ profile_key: string }>(`SELECT profile_key FROM ${TABLE} WHERE profile_key = 'my'`);
  if (row) return;
  run(
    `INSERT OR REPLACE INTO ${TABLE} (profile_key, kind, name, data) VALUES (?,?,?,?)`,
    "my",
    "saved",
    "Saved profile (test data)",
    JSON.stringify(buildSavedValues())
  );
}

export function getSavedProfile(): { name: string; values: Record<string, string> } {
  ensureSavedProfile();
  const row = get<{ name: string; data: string }>(`SELECT name, data FROM ${TABLE} WHERE profile_key = 'my'`);
  const values: Record<string, string> = {};
  try {
    Object.assign(values, row?.data ? JSON.parse(row.data) : {});
  } catch {
    // ignore malformed row and fall back to canonical
  }
  // Guarantee every form key is present (fill any gaps from the canonical source).
  const src = buildSavedValues();
  for (const k of formKeys) if (!(k in values)) values[k] = src[k] ?? "";
  return { name: row?.name ?? "Saved profile", values };
}

export function listProfiles(): Array<{ profile_key: string; kind: string; name: string }> {
  ensureTable();
  return all<{ profile_key: string; kind: string; name: string }>(
    `SELECT profile_key, kind, name FROM ${TABLE} ORDER BY kind, name`
  );
}

// ---------------------------------------------------------------------------
// Fresh fake profile generation (never persisted).
// ---------------------------------------------------------------------------

const FIRST = ["Adam","Beth","Carlo","Diana","Ethan","Fiona","Gavin","Hana","Ivan","Julia","Kai","Lena","Miles","Nora","Owen","Priya","Quinn","Rosa","Sam","Tara","Uma","Victor","Wendy","Xander","Yara","Zach"];
const LAST = ["Adams","Brooks","Carter","Diaz","Evans","Foster","Grant","Hughes","Irving","James","Kim","Lopez","Martin","Nguyen","Owens","Patel","Quinn","Reed","Singh","Turner","Upton","Vega","Ward","Xu","Young","Zimmer"];
const CITIES = ["Toronto","Kitchener","Hamilton","London","Ottawa","Mississauga","Waterloo","Guelph","Barrie","Oshawa"];
const STREETS = ["Maple","Cedar","Oak","Birch","Pine","Elm","Willow","Cherry","Crescent","Meadow"];
const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
// Valid make/model pairs so the raters actually accept the vehicle (make and model
// must be chosen together, not independently, or we'd emit impossible combos like a
// "CHEVROLET Sentra" that no rater lists).
const VEHICLE_PAIRS: Array<[string, string]> = [
  ["HONDA", "ACCORD EX 4DR"],
  ["HONDA", "CIVIC LX 4DR"],
  ["TOYOTA", "COROLLA LE 4DR"],
  ["TOYOTA", "CAMRY LE 4DR"],
  ["MAZDA", "3 GS 4DR"],
  ["NISSAN", "SENTRA S 4DR"],
  ["HYUNDAI", "ELANTRA LE 4DR"],
  ["KIA", "FORTE LX 4DR"],
];
const TRIMS = ["LX", "EX", "Sport", "Touring", "Base", "SE"];
// Curated list of REAL Ontario postal codes (valid FSA + local delivery unit), so a
// fake profile never gets rejected for an invalid postal code. All are Ontario
// (first letter K/L/M/N/P). Generate only from this list — never assemble random codes.
const ONTARIO_POSTAL_CODES = [
  // Toronto (M)
  "M5V 2T6", "M5V 1M6", "M5J 1A1", "M5H 1T1", "M5H 2N2",
  "M4W 3E2", "M4S 1A1", "M4P 1E8", "M5R 1A1", "M5R 2A5",
  "M5S 1A1", "M5T 1R4", "M5G 1A1", "M6K 1A1", "M6P 1C5",
  "M1B 1K1", "M1L 1A1", "M1P 1A1", "M2N 1A1", "M2P 1A1",
  "M3H 1A1", "M4A 1A1", "M4H 1A1", "M5A 1A1", "M5C 1A1",
  "M5E 1A1", "M6A 1A1", "M7A 1A1",
  // Ottawa (K)
  "K1A 0A9", "K1A 0A6", "K1A 0A8", "K1N 9J4", "K1S 5B6",
  "K1P 1A1", "K1P 5G4", "K2P 1A1", "K1R 1A1", "K1V 1A1",
  "K1Z 1A1", "K2A 1A1", "K2B 1A1", "K2C 1A1", "K2G 1A1",
  "K2H 1A1", "K2J 1A1", "K2K 1A1", "K2L 1A1", "K2M 1A1",
  "K2S 1A1", "K2T 1A1", "K4A 1A1", "K7A 1A1", "K7M 1A1",
  "K9A 1A1", "K9H 1A1", "K9J 1A1", "K8A 1A1", "K8N 1A1", "K0A 1A1",
  // Niagara / St. Catharines (L2)
  "L2R 1A1", "L2R 3N5", "L2S 1A1", "L2M 1A1", "L2N 1A1",
  "L2P 1A1", "L2T 1A1", "L2E 1A1", "L2G 1A1", "L2H 1A1",
  "L2J 1A1", "L2V 1A1", "L2W 1A1",
  // Hamilton (L8/L9)
  "L8N 1A1", "L8P 1A1", "L8S 1A1", "L8L 1A1", "L9A 1A1",
  "L9C 1A1", "L9H 1A1", "L9K 1A1",
  // GTA west — Mississauga/Brampton/Oakville (L4/L5/L6/L7)
  "L4W 4Z5", "L5B 1B5", "L5M 1A1", "L6H 1A1", "L6L 1A1",
  "L6M 1A1", "L6T 1A1", "L7A 1A1", "L7E 1A1", "L7G 1A1",
  "L7L 1A1", "L7R 1A1",
  // Kitchener/Waterloo/Guelph/Windsor (N)
  "N2B 1A1", "N2G 1A1", "N2J 1A1", "N2L 1A1", "N1G 1A1",
  "N1H 1A1", "N9A 1A1", "N5A 1A1",
];

function rint(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}
function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}
function randDigits(n: number): string {
  let s = "";
  for (let i = 0; i < n; i++) s += rint(0, 9);
  return s;
}
function randPostal(): string {
  // Pick from a curated list of real Ontario postal codes (never synthesized).
  return pick(ONTARIO_POSTAL_CODES);
}
function fmtDate(y: number, m: number, d: number): string {
  return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

export function generateFakeProfile(): { name: string; values: Record<string, string> } {
  const first = pick(FIRST);
  const last = pick(LAST);
  const tag = randDigits(4);
  const by = rint(1975, 1998);
  const bm = rint(1, 12);
  const bd = rint(1, 28);
  const ageFirst = rint(16, 22);
  const vYear = rint(2015, 2024);
  const hasOtherDrivers = Math.random() < 0.15;
  const [make, model] = pick(VEHICLE_PAIRS);
  const values: Record<string, string> = {
    // contact
    first_name: first,
    last_name: last,
    email: `${first.toLowerCase()}.${last.toLowerCase()}${tag}@example.com`,
    phone: `${rint(416, 905)}-555-${randDigits(4)}`,
    phone_type: pick(["Mobile", "Home", "Work"]),
    date_of_birth: fmtDate(by, bm, bd),
    sex: pick(["M", "F", "X"]),
    marital_status: pick(["S", "M", "C", "D", "W"]),
    privacy_consent: "Yes",
    marketing_consent: pick(["No", "No", "No", "Yes"]),
    // address
    street_address: `${rint(10, 999)} ${pick(STREETS)} St`,
    unit: Math.random() < 0.4 ? String(rint(1, 99)) : "",
    city: pick(CITIES),
    province: "Ontario",
    postal_code: randPostal(),
    tenure: pick(["Renting", "Owning"]),
    // vehicle
    vin: `${randDigits(3)}${String.fromCharCode(rint(65, 90))}${String.fromCharCode(rint(65, 90))}${String.fromCharCode(rint(65, 90))}${randDigits(4)}${String.fromCharCode(rint(65, 90))}${randDigits(5)}`,
    vehicle_year: String(vYear),
    vehicle_make: make,
    vehicle_model: model,
    trim: pick(TRIMS),
    drive_type: pick(["FWD", "AWD", "RWD", "4WD"]),
    fuel_type: pick(["Gas", "Gas", "Gas", "Hybrid"]),
    owned_leased: pick(["Owned", "Owned", "Financed", "Leased"]),
    only_registered_owner: pick(["Yes", "Yes", "No"]),
    ownership_within_30_days: pick(["No", "No", "Yes"]),
    purchase_price: Math.random() < 0.8 ? String(rint(15000, 45000)) : "",
    purchase_condition: pick(["Used", "Used", "New"]),
    purchase_month: pick(MONTHS),
    purchase_year: String(Math.max(2018, vYear - 1)),
    // usage
    annual_km: pick(["8000", "12000", "15000", "18000", "22000"]),
    commute_days: pick(["0", "2", "3", "4", "5"]),
    commute_oneway_km: rint(5, 60).toString(),
    business_use: pick(["No", "No", "Yes"]),
    winter_tires: pick(["Yes", "Yes", "No"]),
    anti_theft: pick(["No", "Yes"]),
    parking: pick(["Home Garage", "Home Driveway", "Home Carport", "Secured Condo/Apt Garage", "Unsecured Condo/Apt Garage or lot", "Street"]),
    adas_features: pick(["None", "None", "Forward Collision Mitigation", "Parking Assist Sensor and/or Camera"]),
    // driver
    licence_class: pick(["G", "G", "G", "G2"]),
    age_first_licensed: String(ageFirst),
    first_licence_month: pick(MONTHS),
    first_licence_year: String(by + ageFirst),
    held_other_classes: pick(["Yes", "Yes", "No"]),
    g2_month: pick(MONTHS),
    g2_year: String(Math.max(2000, by + ageFirst - 1)),
    g_within_12_months: pick(["No", "No", "Yes"]),
    years_with_insurer: pick(["Less than 1 year", "1–2 years", "2–3 years", "3–5 years", "5 years or more"]),
    prior_insurance: pick(["More than 3 years", "Less than 3 years"]),
    combined_policy: pick(["No", "No", "I do"]),
    telus_health: pick(["No", "No", "Yes"]),
    convictions: pick(["None", "None", "None", "1", "2"]),
    major_violations: pick(["No", "No", "No", "Yes"]),
    accidents: pick(["None", "None", "None", "1"]),
    license_suspended: pick(["No", "No", "No", "Yes"]),
    other_household_drivers: hasOtherDrivers ? "Yes" : "No",
    retired: "No",
    // coverage
    coverage_start_date: "2026-09-01",
    liability: pick(["$2,000,000", "$1,000,000"]),
    coverage_type: pick(["All perils", "Collision", "Comprehensive"]),
    deductible: pick(["$1,000", "$500", "$250"]),
    cancellation_nonpayment: "No",
  };
  return { name: `${first} ${last}`, values };
}
