"""ADB phone controller backend.

Places and controls calls on a connected Android phone by driving the device
directly over ADB, which routes the call through the phone's own SIM / carrier
minutes. Use only to call numbers you have consent to call (personal or
opt-in contacts). Bulk unsolicited auto-dialing violates carrier and
telecommunications rules.
"""

import csv
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LOGFILE = Path(__file__).resolve().parent.parent / "logs" / "dial_log.txt"

# Common install locations for adb.exe when it is not on PATH.
_ADB_CANDIDATES = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe",
    Path(os.environ.get("USERPROFILE", "")) / "platform-tools" / "adb.exe",
    Path("C:/platform-tools/adb.exe"),
    Path("C:/Program Files (x86)/Android/android-sdk/platform-tools/adb.exe"),
    Path("C:/Program Files/Android/android-sdk/platform-tools/adb.exe"),
]

# Local folder where pulled call recordings are saved.
RECORDINGS_DIR = Path(__file__).resolve().parent.parent / "recordings"


def find_adb(explicit: str | None = None) -> str:
    """Return the path to adb to use.

    Prefers an explicit path, then 'adb' on PATH, then known install
    locations. Returns 'adb' as a last resort so subprocess errors surface
    a clear message.
    """
    if explicit:
        return explicit
    for cand in _ADB_CANDIDATES:
        if cand.is_file():
            return str(cand)
    return "adb"


def normalize_number(value: str) -> str:
    """Return a dialable number, keeping an optional leading '+'.

    Strips spaces, dashes, parentheses and stray punctuation.
    """
    value = (value or "").strip()
    match = re.match(r"^(\+?)[^\d]*([\d\s().\-]+)", value)
    if not match:
        return re.sub(r"\D", "", value)
    sign, rest = match.group(1), match.group(2)
    digits = re.sub(r"\D", "", rest)
    return sign + digits


@dataclass
class CallResult:
    ok: bool
    detail: str


class AdbPhone:
    """Thin wrapper around the `adb` CLI for making/controlling calls."""

    def __init__(self, adb_path: str | None = None, serial: str | None = None):
        self.adb_path = find_adb(adb_path)
        self.serial = serial
        # Cached on-screen Call button coordinates to skip the slow uiautomator
        # dump on repeat calls (they are stable for a given device/orientation).
        self._call_button_center: tuple[int, int] | None = None

    def _cmd(self, args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
        base = [self.adb_path]
        if self.serial:
            base += ["-s", self.serial]
        base += args
        try:
            return subprocess.run(
                base, capture_output=True, text=True, timeout=timeout
            )
        except FileNotFoundError:
            raise RuntimeError(
                "ADB executable not found. Install Android platform-tools and/or "
                "set the adb_path."
            )

    def available(self) -> bool:
        try:
            self._cmd(["version"], timeout=10)
            return True
        except RuntimeError:
            return False

    def list_devices(self) -> list[str]:
        """Return serials of devices currently authorized as 'device'."""
        return [d["serial"] for d in self.list_devices_states() if d["state"] == "device"]

    def list_devices_states(self) -> list[dict]:
        """Return every attached device with its ADB state.

        State is one of: device, unauthorized, offline, or 'unknown'.
        """
        r = self._cmd(["devices"])
        out: list[dict] = []
        for line in r.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                out.append({"serial": parts[0], "state": parts[1]})
        return out

    def _default_dialer(self) -> str | None:
        try:
            r = self._cmd(["shell", "cmd", "telecom", "get-default-dialer"], timeout=15)
            pkg = r.stdout.strip()
            return pkg if pkg else None
        except Exception:  # noqa: BLE001
            return None

    def call_state(self) -> int:
        """Return the busiest telephony call state across all SIM slots:
        0=idle, 1=ringing, 2=active/offhook."""
        try:
            r = self._cmd(["shell", "dumpsys", "telephony.registry"], timeout=20)
            states = [int(s) for s in re.findall(r"mCallState[ =:]+(\d)", r.stdout)]
            return max(states) if states else 0
        except Exception:  # noqa: BLE001
            return 0

    def is_in_call(self) -> bool:
        return self.call_state() in (1, 2)

    def _find_call_button(self) -> tuple[int, int] | None:
        """Locate the on-screen Call button with a single uiautomator dump."""
        try:
            self._cmd(["shell", "uiautomator", "dump", "/sdcard/ui_phone.xml"], timeout=20)
            r = self._cmd(["shell", "cat", "/sdcard/ui_phone.xml"], timeout=20)
        except Exception:  # noqa: BLE001
            return None
        xml = r.stdout
        for regex in (
            r'resource-id="com.samsung.android.dialer:id/dialButton"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
            r'content-desc="Call"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
        ):
            m = re.search(regex, xml)
            if m:
                x1, y1, x2, y2 = map(int, m.groups())
                return ((x1 + x2) // 2, (y1 + y2) // 2)
        return None

    def _tap(self, x: int, y: int) -> None:
        self._cmd(["shell", "input", "tap", str(x), str(y)])

    def call(self, number: str) -> CallResult:
        """Place a call by driving the dialer UI directly.

        Confirmed-working flow on this Samsung: force-stop and reopen the
        dialer with the number pre-filled (ACTION_DIAL + tel:), then tap the
        on-screen Call button. This bypasses the app chooser and the
        unreliable ACTION_CALL/KEYCODE_CALL paths.
        """
        num = normalize_number(number)
        if not num:
            return CallResult(False, "empty number")
        dialer = self._default_dialer() or "com.samsung.android.dialer"

        self._cmd(["shell", "am", "force-stop", dialer])
        time.sleep(0.8)
        self._cmd(
            ["shell", "am", "start", "-a", "android.intent.action.DIAL",
             "-d", f"tel:{num}"]
        )
        time.sleep(1.8)

        call_button = self._call_button_center
        if call_button is None:
            # First call: find and cache the button (slow uiautomator dump).
            call_button = self._find_call_button()
            if call_button:
                self._call_button_center = call_button
        if not call_button:
            return CallResult(False, "could not locate the Call button")
        self._tap(*call_button)
        return CallResult(True, "dialer_tap")

    # -------------------------------------------------------------- recording
    def _dump_ui(self) -> str | None:
        """Dump the current screen's accessibility tree and return the XML."""
        try:
            self._cmd(["shell", "uiautomator", "dump", "/sdcard/ui_rec.xml"], timeout=20)
            r = self._cmd(["shell", "cat", "/sdcard/ui_rec.xml"], timeout=20)
            return r.stdout
        except Exception:  # noqa: BLE001
            return None

    def _find_button_matching(self, keywords: list[str]) -> tuple[int, int] | None:
        """Find the centre of a clickable node whose content-desc or text
        contains any of the keywords (case-insensitive)."""
        xml = self._dump_ui()
        if not xml:
            return None
        for kw in keywords:
            esc = re.escape(kw)
            pat = re.compile(
                r'(?:content-desc|text)="[^"]*' + esc + r'[^"]*"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',
                re.IGNORECASE,
            )
            m = pat.search(xml)
            if m:
                x1, y1, x2, y2 = map(int, m.groups())
                return ((x1 + x2) // 2, (y1 + y2) // 2)
        return None

    def start_recording(self, timeout: int = 45) -> CallResult:
        """Start recording the active call by tapping the in-call record
        button(s). Waits for the call to be answered (off-hook) first.

        On Samsung this is a two-stage tap (record button, then a confirmation)
        and recording takes ~3s to begin - handled here automatically.
        """
        waited = 0
        while waited < timeout:
            if self.call_state() == 2:  # answered / off-hook
                break
            time.sleep(1)
            waited += 1

        time.sleep(1.2)
        # If the button already reads "Stop recording", it is already recording.
        stop = self._find_button_matching(["stop recording"])
        if stop:
            return CallResult(True, "recording already active")

        btn = self._find_button_matching(["record call", "off, record", "record"])
        if not btn:
            return CallResult(False, "record button not found (is a call active?)")
        self._tap(*btn)

        time.sleep(1.5)
        # Some builds show a confirmation dialog ("Start recording" etc.).
        # Avoid generic keywords so we never re-tap the record button and stop it.
        confirm = self._find_button_matching(
            ["start recording", "record now", "start call recording"]
        )
        if confirm:
            self._tap(*confirm)

        time.sleep(3)
        return CallResult(True, "recording started")

    def _find_newest_recording_remote(self) -> str | None:
        """Locate the most recently created call-recording file on the device."""
        dirs = [
            "/storage/emulated/0/Call/CallRecordings",
            "/storage/emulated/0/Music/Call",
            "/storage/emulated/0/Recordings/Call",
            "/storage/emulated/0/Recorder/Call",
            "/storage/emulated/0/Call",
        ]
        exts = (".m4a", ".amr", ".mp3", ".wav", ".mp4")
        newest: str | None = None
        for d in dirs:
            r = self._cmd(["shell", "ls", "-lt", d])
            for line in r.stdout.splitlines():
                parts = line.split(None, 7)
                if len(parts) < 8:
                    continue
                fname = parts[7].strip()
                if fname.lower().endswith(exts):
                    newest = f"{d}/{fname}"
                    break  # ls -lt sorts newest first within this dir
            if newest:
                break
        return newest

    def pull_newest_recording(self, dest_dir: str | os.PathLike = RECORDINGS_DIR) -> CallResult:
        """Pull the newest call recording from the device into dest_dir."""
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        remote = self._find_newest_recording_remote()
        if not remote:
            return CallResult(False, "no recording found on device")
        name = Path(remote).name or f"recording_{int(time.time())}.m4a"
        local = dest_dir / name
        r = self._cmd(["pull", remote, str(local)])
        ok = r.returncode == 0 and "error" not in r.stderr.lower()
        detail = str(local) if ok else (r.stderr.strip() or r.stdout.strip())[:300]
        return CallResult(ok, detail)

    def hangup(self) -> CallResult:
        # KEYCODE_ENDCALL acts as the power button on Samsung when no call is
        # active (it turns the screen off). Poll for an active call first, and
        # only send ENDCALL once one is detected.
        for _ in range(5):
            if self.is_in_call():
                r = self._cmd(["shell", "input", "keyevent", "KEYCODE_ENDCALL"])
                return CallResult(
                    r.returncode == 0,
                    (r.stdout + r.stderr).strip()[:300] or "hung up",
                )
            time.sleep(0.4)
        self._cmd(["shell", "input", "keyevent", "KEYCODE_WAKEUP"])
        return CallResult(False, "no active call detected")

    def answer(self) -> CallResult:
        r = self._cmd(["shell", "input", "keyevent", "KEYCODE_CALL"])
        return CallResult(r.returncode == 0, (r.stdout + r.stderr).strip()[:300] or "answered")

    def pair(self, host_port: str, code: str) -> CallResult:
        """Pair a device over Wi-Fi. host_port is 'ip:port' shown in
        Developer options -> Wireless debugging -> Pair device with code."""
        r = self._cmd(["pair", host_port, code])
        ok = "Successfully paired" in (r.stdout + r.stderr)
        return CallResult(ok, (r.stdout + r.stderr).strip()[:300])

    def connect(self, host_port: str) -> CallResult:
        """Connect to an already-paired wireless device. host_port is the
        'ip:port' under Developer options -> Wireless debugging."""
        r = self._cmd(["connect", host_port])
        ok = "connected" in (r.stdout + r.stderr).lower()
        return CallResult(ok, (r.stdout + r.stderr).strip()[:300])


def load_contacts(path: str | os.PathLike) -> list[dict]:
    """Load contacts from CSV. Expected optional headers: name, number.

    Plain columns (numbers only) are also supported. Rows missing a dialable
    number are skipped.
    """
    path = Path(path)
    if not path.exists():
        return []
    contacts: list[dict] = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        sample = fh.read(2048)
        fh.seek(0)
        has_header = bool(re.search(r"name|number", sample, re.IGNORECASE))
        reader = csv.reader(fh)
        if has_header:
            next(reader, None)
        for row in reader:
            row = [c.strip() for c in row]
            if not row:
                continue
            name = row[0] if row[0] else row[1] if len(row) > 1 else ""
            number = row[1] if len(row) > 1 else row[0]
            num = normalize_number(number)
            if num:
                contacts.append({"name": name or num, "number": num})
    return contacts


def append_log(entry: str, logfile: str | os.PathLike = DEFAULT_LOGFILE) -> None:
    logfile = Path(logfile)
    logfile.parent.mkdir(parents=True, exist_ok=True)
    with open(logfile, "a", encoding="utf-8") as fh:
        fh.write(entry + "\n")


def _parse_log_line(line: str) -> dict | None:
    """Parse one call-log line into a record.

    New CSV format:  <datetime>,<direction>,<number>,<status>
    Legacy format:   [<datetime>] CALL <number> -> <status>
    """
    line = line.strip()
    if not line:
        return None
    parts = line.split(",")
    if len(parts) >= 4 and re.match(r"^\d{4}-\d{2}-\d{2}", parts[0]):
        return {
            "dt": parts[0].strip(),
            "direction": parts[1].strip() or "outbound",
            "number": parts[2].strip(),
            "status": ",".join(parts[3:]).strip(),
        }
    m = re.match(r"^\[([^\]]+)\]\s*CALL\s+(\S+)\s*->\s*(.*)$", line)
    if m:
        return {
            "dt": m.group(1),
            "direction": "outbound",
            "number": m.group(2),
            "status": m.group(3),
        }
    return None


def read_call_log(logfile: str | os.PathLike = DEFAULT_LOGFILE) -> list[dict]:
    """Read and parse the call-log file into records (newest last)."""
    logfile = Path(logfile)
    if not logfile.exists():
        return []
    records: list[dict] = []
    for line in logfile.read_text(encoding="utf-8").splitlines():
        rec = _parse_log_line(line)
        if rec:
            records.append(rec)
    return records


def make_call(number: str, phone: AdbPhone, logfile=DEFAULT_LOGFILE) -> CallResult:
    """Dial a number, wait briefly, hang up, and log the outcome."""
    res = phone.call(number)
    append_log(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] CALL {number} -> {'OK' if res.ok else 'FAIL'} {res.detail}", logfile)
    if res.ok:
        time.sleep(2)
        phone.hangup()
    return res
