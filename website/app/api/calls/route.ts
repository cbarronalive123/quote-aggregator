import { NextRequest, NextResponse } from "next/server";
import { run } from "@/lib/db";
import crypto from "node:crypto";

export const dynamic = "force-dynamic";

// POST /api/calls — the phone agent posts call results here to persist them in the
// shared quotedrive.db. Body mirrors the phone-agent call record shape.
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const id = body.id || `call-${Date.now()}-${crypto.randomInt(1000)}`;
    const ts = body.timestamp || new Date().toISOString();
    run(
      `INSERT OR REPLACE INTO calls (id, registry_id, brand, direction, status, recording_path, transcript, outcome_notes, timestamp)
       VALUES (?,?,?,?,?,?,?,?,?)`,
      id,
      body.registry_id || null,
      body.brand || null,
      body.direction || "outbound",
      body.status || "callback_required",
      body.recording_path || null,
      body.transcript || null,
      body.outcome_notes || null,
      ts
    );
    return NextResponse.json({ ok: true, id, timestamp: ts });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e.message }, { status: 500 });
  }
}
