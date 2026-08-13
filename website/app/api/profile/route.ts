import { NextResponse } from "next/server";
import { getSavedProfile, generateFakeProfile, listProfiles } from "@/lib/profileStore";

export const dynamic = "force-dynamic";

// GET /api/profile — pre-filled intake profiles for the mobile app's "fill from
// saved profile" shortcut. Returns the real applicant (Corey Barron) from the DB
// plus a freshly generated, unique fake profile for testing the quote flow.
export async function GET() {
  const saved = getSavedProfile();
  const fake = generateFakeProfile();
  return NextResponse.json({
    profiles: [
      { id: "real", name: saved.name, values: saved.values },
      { id: "fake", name: `${fake.name} (fresh)`, values: fake.values },
    ],
    stored: listProfiles(),
  });
}
