"""Entry point for the Voice AI Chatbot app.

Run:  .venv\\Scripts\\python.exe main.py

No build/compile step is needed in development. main.py also auto-starts the
local voice server (rvc-env: RVC celebrity voices + Qwen3-TTS cloning) as a
background process if it isn't already running, so a single `python main.py`
launches everything.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication

from app.config import Config
from app.window import MainWindow

BASE_DIR = Path(__file__).resolve().parent
RVC_ENV_PYTHONW = BASE_DIR / "rvc-env" / "Scripts" / "pythonw.exe"
RVC_ENV_PYTHON = BASE_DIR / "rvc-env" / "Scripts" / "python.exe"


def _server_alive(url: str) -> bool:
    try:
        import requests

        return requests.get(url + "/health", timeout=2).status_code == 200
    except Exception:
        return False


def _start_voice_server(url: str):
    """Launch the isolated RVC/clone voice server if it isn't already running.

    Fire-and-forget: the server takes ~10-20s to cold-start (imports torch +
    fairseq + qwen-tts), so the app launches immediately and the server becomes
    ready in the background. It's only needed for RVC/clone voices, which are
    used lazily.
    """
    if _server_alive(url):
        return None
    exe = RVC_ENV_PYTHONW if RVC_ENV_PYTHONW.exists() else RVC_ENV_PYTHON
    if not exe.exists():
        return None
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    return subprocess.Popen(
        [str(exe), str(BASE_DIR / "rvc_server.py")],
        cwd=str(BASE_DIR),
        creationflags=flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def main():
    config = Config()
    server_proc = _start_voice_server(config.get("rvc_server_url", "http://127.0.0.1:8123"))

    app = QApplication(sys.argv)
    app.setApplicationName("Voice AI Chatbot")
    window = MainWindow(config)
    # Ensure the window opens on a visible screen (it can otherwise land
    # off-screen on multi-monitor / removed-monitor setups).
    screen = QGuiApplication.primaryScreen()
    if screen is not None:
        area = screen.availableGeometry()
        window.move(area.center() - window.rect().center())
    window.show()
    rc = app.exec()

    if server_proc is not None and server_proc.poll() is None:
        try:
            server_proc.terminate()
            server_proc.wait(timeout=3)
        except Exception:
            pass
    sys.exit(rc)


if __name__ == "__main__":
    main()
