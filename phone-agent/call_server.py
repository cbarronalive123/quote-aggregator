"""Headless HTTP trigger for the ADB phone agent.

Lets the website (or any caller) place a call on the connected Android phone over
ADB — routing through the phone's own SIM/carrier minutes. Used as the phone-agent
fallback for carriers whose online quote is gated (e.g. Allstate).

Run with the phone-agent venv:
    .venv\\Scripts\\python call_server.py [--port 8765]

Endpoints:
    GET  /status            -> { ok, device_count, devices, adb }
    POST /call              -> body {"number": "18002557828"}  places + hangs up
    POST /call-and-hold     -> body {"number": "..."}          places but keeps the call up
    POST /hangup            -> end any active call
"""

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.phone import AdbPhone, normalize_number  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    base = AdbPhone()
    # Close the connection after each response (HTTP/1.0) — more reliable through an
    # SSH tunnel than HTTP/1.1 keep-alive.
    protocol_version = "HTTP/1.0"

    def _physical_serial(self) -> str | None:
        """Return the serial of the connected physical cell phone (excludes emulators)
        so calls always go out through the real phone, never the emulator."""
        try:
            for d in AdbPhone().list_devices():
                if not str(d).startswith("emulator-"):
                    return d
        except Exception:
            pass
        return None

    # ---- helpers ----
    def _json(self, code: int, obj: dict):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            return json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return {}

    def log_message(self, fmt, *args):  # quieter
        return

    # ---- routes ----
    def do_GET(self):
        if self.path.split("?")[0] == "/status":
            serial = self._physical_serial()
            self._json(200, {
                "ok": serial is not None,
                "device_count": 1 if serial else 0,
                "devices": [serial] if serial else [],
                "adb": self.base.adb_path,
                "detail": "physical (cell) phone connected" if serial else "no physical phone connected",
            })
            return
        self._json(404, {"ok": False, "detail": "not found"})

    def do_POST(self):
        body = self._read_body()
        path = self.path.split("?")[0]
        number = normalize_number(body.get("number", ""))
        # Require the physical cell phone (never the emulator) so the call goes out
        # through the real phone.
        serial = self._physical_serial()
        if not serial:
            self._json(200, {"ok": False, "detail": "no physical (cell) phone connected"})
            return
        phone = AdbPhone(serial=serial)
        if path in ("/call", "/call-and-hold"):
            if not number:
                self._json(400, {"ok": False, "detail": "number required"})
                return
            res = phone.call(number)
            rec = {"started": False, "detail": None}
            if res.ok:
                # Do NOT hang up automatically — keep the call up so the agent/rep can
                # talk; the caller ends it manually via /hangup (or on the phone).
                # Also auto-record the call.
                rec = start_recording_best_effort(phone)
            self._json(200, {"ok": res.ok, "detail": res.detail, "number": number, "recording": rec})
        elif path == "/hangup":
            res = phone.hangup()
            pulled = None
            if res.ok:
                pull = phone.pull_newest_recording()
                if pull.ok:
                    pulled = pull.detail
            self._json(200, {"ok": res.ok, "detail": res.detail, "recording_path": pulled})
        else:
            self._json(404, {"ok": False, "detail": "not found"})


def start_recording_best_effort(phone: AdbPhone, timeout: int = 25):
    """Start recording the active call (best-effort). Waits for the call to be
    answered (off-hook), then taps the on-screen record button. Returns a dict."""
    try:
        res = phone.start_recording(timeout=timeout)
        return {"started": res.ok, "detail": res.detail}
    except Exception as e:  # noqa: BLE001
        return {"started": False, "detail": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"phone-agent call server on http://{args.host}:{args.port} (adb={Handler.base.adb_path})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
