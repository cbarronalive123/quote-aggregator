import { NextResponse } from "next/server";
import { getSetting, setSetting } from "@/lib/repo";

export const dynamic = "force-dynamic";

function readSettings() {
  return {
    vnc_enabled: getSetting("vnc_enabled") === "true",
    max_retries: parseInt(getSetting("max_retries") ?? "", 10) || 2,
    quote_timeout_seconds: parseInt(getSetting("quote_timeout_seconds") ?? "", 10) || 600,
    phone_call_on_blocked: getSetting("phone_call_on_blocked") !== "false",
    phone_agent_url: getSetting("phone_agent_url") || "http://127.0.0.1:8765",
  };
}

export async function GET() {
  return NextResponse.json(readSettings());
}

export async function PUT(req: Request) {
  const body = await req.json().catch(() => ({}));
  if (typeof body.vnc_enabled === "boolean") setSetting("vnc_enabled", String(body.vnc_enabled));
  if (typeof body.max_retries === "number") setSetting("max_retries", String(Math.max(1, Math.min(10, Math.round(body.max_retries)))));
  if (typeof body.quote_timeout_seconds === "number") setSetting("quote_timeout_seconds", String(Math.max(60, Math.min(3600, Math.round(body.quote_timeout_seconds)))));
  if (typeof body.phone_call_on_blocked === "boolean") setSetting("phone_call_on_blocked", String(body.phone_call_on_blocked));
  if (typeof body.phone_agent_url === "string" && body.phone_agent_url.trim()) setSetting("phone_agent_url", body.phone_agent_url.trim());
  return NextResponse.json(readSettings());
}
