import { getCallSession, registerStream, unregisterStream, push } from "@/lib/callSession";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// GET /api/call/sse?job_id=... — server pushes the in-app call to the mobile app
// over a Server-Sent Events stream. Events (JSON in `data:`):
//   { type: "ringing" }            -> show the incoming-call screen
//   { type: "start" }              -> user answered
//   { type: "agent", text, index } -> the AI requester line (speak it)
//   { type: "outcome", outcome }   -> extracted quote details
//   { type: "end" }                -> call finished
export async function GET(req: Request) {
  const jobId = new URL(req.url).searchParams.get("job_id") || "";
  const session = getCallSession(jobId);
  if (!session) {
    return new Response("call session not found", { status: 404 });
  }

  let controller: ReadableStreamDefaultController<Uint8Array> | undefined;
  const stream = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c;
      registerStream(jobId, c);
      // Always send the "ringing" state first; it repeats harmlessly if the app
      // reconnects. If the user already answered, replay the "start" state too.
      push(session, { type: "ringing" });
      if (session.answered) {
        push(session, { type: "start" });
      }
    },
    cancel() {
      if (controller) unregisterStream(jobId, controller);
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
