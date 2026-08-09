import { NextResponse } from "next/server";
import { formSections } from "@/lib/formSchema";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json({ sections: formSections });
}
