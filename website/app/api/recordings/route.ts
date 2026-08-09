import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// POST /api/recordings — the phone agent uploads the finished call recording here
// so it is stored ON the website server (served from public/recordings) instead of
// only living in the phone agent's own ./recordings dir. Body is the raw audio
// bytes; the original filename is passed via the x-filename header.
export async function POST(req: Request) {
  try {
    const buf = Buffer.from(await req.arrayBuffer());
    if (buf.length === 0) {
      return NextResponse.json({ ok: false, error: "Empty body" }, { status: 400 });
    }

    const header = (req.headers.get("x-filename") || "").trim();
    // Allow only safe basenames; otherwise generate a random one.
    let name = header ? path.basename(header) : "";
    if (!/^[A-Za-z0-9._-]+$/.test(name) || !/\.(wav|mp3|ogg|flac)$/i.test(name)) {
      name = `rec-${crypto.randomBytes(8).toString("hex")}.mp3`;
    }

    const dir = path.join(process.cwd(), "public", "recordings");
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, name), buf);

    return NextResponse.json({ ok: true, path: `/recordings/${name}` });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("recordings POST failed:", msg);
    return NextResponse.json({ ok: false, error: msg }, { status: 500 });
  }
}
