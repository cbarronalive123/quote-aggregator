import { NextResponse } from "next/server";
import { randomUUID } from "crypto";
import { createAggregation, getAggregation } from "@/lib/aggregate";

export const dynamic = "force-dynamic";

// POST /api/quote — start the aggregation for a submitted form.
// The aggregation always creates ONE in-app call session for the MOBILE APP
// (no broker phone calls) and runs the direct-rate $ auto-quote scripts.
export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const { values } = (body ?? {}) as { values?: Record<string, string> };
  if (!values || typeof values !== "object") {
    return NextResponse.json({ error: "Missing 'values' object" }, { status: 400 });
  }
  const id = randomUUID();
  createAggregation(id, values, false);
  return NextResponse.json(
    { job_id: id, status: "running", progress: 0, total: undefined },
    { status: 202 }
  );
}

// GET /api/quote?id=... — poll the aggregation progress/results.
export async function GET(req: Request) {
  const id = new URL(req.url).searchParams.get("id");
  if (!id) return NextResponse.json({ error: "Missing 'id' param" }, { status: 400 });
  const job = getAggregation(id);
  if (!job) return NextResponse.json({ error: "Job not found" }, { status: 404 });
  return NextResponse.json({
    job_id: job.id,
    status: job.status,
    progress: job.progress,
    total: job.total,
    outcomes: job.outcomes,
    submitted_values: job.submittedValues,
  });
}
