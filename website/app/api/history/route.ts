import { NextResponse } from "next/server";
import { getQuoteHistory } from "@/lib/repo";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json({ runs: getQuoteHistory() });
}
