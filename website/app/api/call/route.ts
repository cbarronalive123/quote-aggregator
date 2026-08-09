import { NextResponse } from "next/server";
import { answerCall, replyCall, endCall, getCallSession } from "@/lib/callSession";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// POST /api/call — control the in-app simulated call.
//   { action: "answer", job_id }          -> user answers the ringing call
//   { action: "reply",  job_id, text }    -> user's spoken reply (playing the agent)
//   { action: "end",    job_id }          -> user hangs up
export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  const { action, job_id, text } = (body ?? {}) as {
    action?: string;
    job_id?: string;
    text?: string;
  };
  if (!job_id) {
    return NextResponse.json({ error: "Missing 'job_id'" }, { status: 400 });
  }
  if (!getCallSession(job_id)) {
    return NextResponse.json({ error: "Call session not found" }, { status: 404 });
  }

  switch (action) {
    case "answer":
      answerCall(job_id);
      break;
    case "reply":
      replyCall(job_id, text ?? "");
      break;
    case "end":
      endCall(job_id);
      break;
    default:
      return NextResponse.json({ error: "Unknown action" }, { status: 400 });
  }

  return NextResponse.json({ ok: true });
}
