import { NextResponse } from "next/server";
import { defaultProfile } from "@/lib/data";

export const dynamic = "force-dynamic";

// GET /api/profile — pre-filled intake profiles for the mobile app's "fill from
// saved profile" shortcut. Returns the applicant's saved details (from the intake
// form schema) plus a mock profile for testing the quote flow without typing.
export async function GET() {
  const mockProfile: Record<string, string> = {
    first_name: "Jane",
    last_name: "Smith",
    email: "jane.smith@example.com",
    phone: "416-555-0134",
    date_of_birth: "1992-03-18",
    sex: "F",
    marital_status: "M",
    street_address: "42 Maple Ave",
    unit: "3",
    city: "Toronto",
    province: "Ontario",
    postal_code: "M5V 2T6",
    tenure: "Owning",
    vin: "2G1FC1E34H9100010",
    vehicle_year: "2019",
    vehicle_make: "Honda",
    vehicle_model: "Civic",
    trim: "Touring",
    drive_type: "FWD",
    fuel_type: "Gas",
    owned_leased: "Leased",
    purchase_condition: "Used",
    purchase_month: "August",
    purchase_year: "2020",
    annual_km: "12000",
    commute_days: "4",
    commute_oneway_km: "20",
    business_use: "No",
    winter_tires: "Yes",
    anti_theft: "No",
    licence_class: "G",
    first_licence_year: "2010",
    held_other_classes: "Yes",
    years_with_insurer: "5 years or more",
    prior_insurance: "More than 3 years",
    convictions: "None",
    accidents: "None",
    retired: "No",
    coverage_start_date: "2026-10-01",
    liability: "$2,000,000",
    coverage_type: "All perils",
    deductible: "$1,000",
    cancellation_nonpayment: "No",
  };

  return NextResponse.json({
    profiles: [
      { id: "real", name: "Corey Barron (saved)", values: { ...defaultProfile } },
      { id: "mock", name: "Mock — Jane Smith", values: mockProfile },
    ],
  });
}
