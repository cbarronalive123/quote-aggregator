"""PyQt6 phone-agent frontend.

A phone-app style UI that connects to your Android device over ADB, lets you
dial from a keypad or your contact list, and logs call attempts. Calls route
through the phone's own SIM/carrier minutes.
"""

import json
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from backend.phone import AdbPhone, CallResult, RECORDINGS_DIR, append_log, read_call_log

ROOT = Path(__file__).resolve().parent
DEFAULT_LOG = ROOT / "logs" / "dial_log.txt"
CONFIG = ROOT / "config.json"


def _load_config() -> dict:
    try:
        if CONFIG.exists():
            return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    return {}


def _save_config(data: dict) -> None:
    try:
        CONFIG.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


class PhoneWorker(QObject):
    """Runs a blocking ADB operation off the GUI thread."""

    finished = pyqtSignal(object)  # CallResult
    error = pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            self.finished.emit(self._fn(*self._args, **self._kwargs))
        except Exception as exc:  # noqa: BLE001 - surface any backend error
            self.error.emit(str(exc))


class PhoneApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Phone Agent - ADB Dialer")
        self.resize(880, 640)

        self.phone = AdbPhone()
        self._worker = None
        self._thread = None
        self._calling = False
        self._recording = False
        self._auto_record = bool(_load_config().get("auto_record", False))
        self._play_index: int | None = None
        self._playing = False
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.8)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.mediaStatusChanged.connect(self._on_media_status)

        self._build_ui()
        self.refresh_devices()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # Dialer + device controls
        left = QWidget()
        left_layout = QVBoxLayout(left)

        # Device selection
        dev_row = QHBoxLayout()
        dev_row.addWidget(QLabel("Device:"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(180)
        dev_row.addWidget(self.device_combo, 1)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_devices)
        dev_row.addWidget(refresh_btn)
        wifi_btn = QPushButton("Wi-Fi")
        wifi_btn.setToolTip("Connect wirelessly (Wireless debugging)")
        wifi_btn.clicked.connect(self._on_wifi_connect)
        dev_row.addWidget(wifi_btn)
        left_layout.addLayout(dev_row)

        # Number display
        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display.setPlaceholderText("Enter a number")
        display_font = self.display.font()
        display_font.setPointSize(20)
        display_font.setBold(True)
        self.display.setFont(display_font)
        left_layout.addWidget(self.display)

        # Dialpad (with phone-keypad letters)
        grid = QGridLayout()
        keys = [
            ("1", ""),     ("2", "ABC"), ("3", "DEF"),
            ("4", "GHI"),  ("5", "JKL"), ("6", "MNO"),
            ("7", "PQRS"), ("8", "TUV"), ("9", "WXYZ"),
            ("*", ""),     ("0", "+"),   ("#", ""),
        ]
        for i, (key, letters) in enumerate(keys):
            btn = self._make_keypad_button(key, letters)
            btn.clicked.connect(lambda _=False, k=key: self._append_key(k))
            grid.addWidget(btn, i // 3, i % 3)
        left_layout.addLayout(grid)

        # Call / clear / hangup (uniform height)
        controls = QHBoxLayout()
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedHeight(48)
        self.clear_btn.clicked.connect(self._clear_display)
        self.call_btn = QPushButton("Call")
        self.call_btn.setStyleSheet(
            "background-color:#2e7d32; color:white; font-weight:bold; padding:10px;"
        )
        self.call_btn.setFixedHeight(48)
        self.call_btn.clicked.connect(self._on_call)
        self.hangup_btn = QPushButton("Hang Up")
        self.hangup_btn.setStyleSheet(
            "background-color:#c62828; color:white; font-weight:bold; padding:10px;"
        )
        self.hangup_btn.setFixedHeight(48)
        self.hangup_btn.clicked.connect(self._on_hangup)
        self.hangup_btn.setEnabled(False)
        controls.addWidget(self.clear_btn)
        controls.addWidget(self.call_btn)
        controls.addWidget(self.hangup_btn)
        left_layout.addLayout(controls)

        # Round red Auto Record button, on its own row.
        record_row = QHBoxLayout()
        record_row.addStretch(1)
        self.record_btn = QPushButton("REC")
        self.record_btn.setCheckable(True)
        self.record_btn.setFixedSize(72, 72)
        self.record_btn.setStyleSheet(
            "QPushButton {"
            "  background-color:#e53935; color:white; font-weight:bold;"
            "  font-size:15px; border-radius:36px; border:3px solid #b71c1c;"
            "}"
            "QPushButton:checked {"
            "  background-color:#ff1744; border:3px solid #ffffff;"
            "}"
            "QPushButton:hover { background-color:#d32f2f; }"
            "QPushButton:disabled { background-color:#6e6e6e; border-color:#555; }"
        )
        self.record_btn.setToolTip(
            "Toggle auto-record. When ON, every call is recorded automatically."
        )
        self.record_btn.setChecked(self._auto_record)
        self.record_btn.clicked.connect(self._on_record)
        record_row.addWidget(self.record_btn)
        record_row.addStretch(1)
        left_layout.addLayout(record_row)
        left_layout.addStretch(1)

        # Right: call log + recordings tabs
        tabs = QTabWidget()
        self.log_list = QListWidget()
        tabs.addTab(self.log_list, "Call Log")

        rec_tab = QWidget()
        rec_layout = QVBoxLayout(rec_tab)
        rec_layout.setContentsMargins(0, 0, 0, 0)
        self.recordings_list = QListWidget()
        self.recordings_list.currentRowChanged.connect(self._on_recording_selected)
        rec_layout.addWidget(self.recordings_list)

        player_row = QHBoxLayout()
        self.prev_btn = QPushButton("⏮ Prev")
        self.prev_btn.clicked.connect(self._on_prev)
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setStyleSheet(
            "background-color:#2e7d32; color:white; font-weight:bold;"
        )
        self.play_btn.clicked.connect(self._on_play_stop)
        self.next_btn = QPushButton("Next ⏭")
        self.next_btn.clicked.connect(self._on_next)
        player_row.addWidget(self.prev_btn)
        player_row.addWidget(self.play_btn)
        player_row.addWidget(self.next_btn)
        rec_layout.addLayout(player_row)
        tabs.addTab(rec_tab, "Recordings")

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(tabs)
        splitter.setSizes([430, 440])
        self.setCentralWidget(splitter)
        self.statusBar().showMessage("Ready")

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.display.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for w in (self.clear_btn, self.call_btn, self.record_btn, self.hangup_btn,
                  refresh_btn, wifi_btn):
            w.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFocus()

        self._load_log()
        self._load_recordings()

    def keyPressEvent(self, event):
        key = event.key()
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            self._append_key(chr(key))
            event.accept()
        elif key == Qt.Key.Key_Asterisk:
            self._append_key("*")
            event.accept()
        elif key == Qt.Key.Key_NumberSign:
            self._append_key("#")
            event.accept()
        elif key == Qt.Key.Key_Plus:
            self._append_key("+")
            event.accept()
        elif key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.display.setText(self.display.text()[:-1])
            event.accept()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_call()
            event.accept()
        elif key == Qt.Key.Key_Escape:
            self._on_hangup()
            event.accept()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------- actions
    def _make_keypad_button(self, key: str, letters: str) -> QPushButton:
        """Build a keypad button showing the number on top and the
        phone-keypad letters beneath it (e.g. 2 / ABC)."""
        btn = QPushButton()
        btn.setFixedSize(72, 58)
        btn.setCursor(btn.cursor().shape())
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        num_label = QLabel(key)
        num_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num_label.setFont(QFont(num_label.font().family(), 15, QFont.Weight.Bold))
        num_label.setStyleSheet("border: none; background: transparent;")

        letters_label = QLabel(letters)
        letters_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        letters_label.setFont(QFont(letters_label.font().family(), 7))
        letters_label.setStyleSheet("border: none; background: transparent;")

        layout = QVBoxLayout(btn)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)
        layout.addWidget(num_label)
        layout.addWidget(letters_label)
        return btn

    def _append_key(self, key: str):
        current = self.display.text()
        if len(current) < 20:
            self.display.setText(current + key)

    def _clear_display(self):
        self.display.clear()

    def _selected_number(self) -> str:
        return self.display.text().strip()

    def _set_busy(self, busy: bool):
        self._calling = busy
        self.call_btn.setEnabled(not busy)
        self.hangup_btn.setEnabled(busy)
        self.device_combo.setEnabled(not busy)

    def _on_call(self):
        number = self._selected_number()
        if not number:
            self.statusBar().showMessage("Enter a number first")
            return
        self._call_number(number)

    def _call_number(self, number: str):
        if self._calling:
            return
        if not self.device_combo.currentText():
            QMessageBox.warning(
                self, "No device", "Connect your Android phone and refresh devices."
            )
            return
        self.phone.serial = self.device_combo.currentText()
        self._last_number = number
        self._set_busy(True)
        self.statusBar().showMessage("Dialing...")
        self._run_worker(lambda: self.phone.call(number), on_done=self._on_call_placed)

    def _on_call_placed(self, result: CallResult):
        if getattr(result, "ok", False):
            method = getattr(result, "detail", "")
            # Stay "in call": Hang Up stays enabled so the user can end it.
            self.statusBar().showMessage(
                f"Call placed ({method}). Talk on your phone; press Hang Up when done."
            )
            append_log(
                f"{_now()},outbound,{self._last_number},placed ({method})",
                DEFAULT_LOG,
            )
            # Automatically start recording if auto-record is toggled ON.
            if self._auto_record:
                self._run_worker(
                    self.phone.start_recording, on_done=self._on_record_started
                )
        else:
            self._set_busy(False)
            self.statusBar().showMessage(f"Failed: {getattr(result, 'detail', '')}")
            append_log(
                f"{_now()},outbound,{self._last_number},FAILED {getattr(result, 'detail', '')}",
                DEFAULT_LOG,
            )
        self._load_log()

    def _on_record(self):
        self._auto_record = self.record_btn.isChecked()
        cfg = _load_config()
        cfg["auto_record"] = self._auto_record
        _save_config(cfg)
        if self._auto_record:
            self.statusBar().showMessage(
                "Auto record ON: every call will be recorded automatically."
            )
        else:
            self.statusBar().showMessage("Auto record OFF.")

    def _on_record_started(self, result: CallResult):
        if getattr(result, "ok", False):
            self._recording = True
            self.statusBar().showMessage(
                f"Recording started. Hang Up to save it to {RECORDINGS_DIR}."
            )
        else:
            self.statusBar().showMessage(f"Recording failed: {getattr(result, 'detail', '')}")

    def _on_hangup(self):
        self._run_worker(self.phone.hangup, on_done=self._on_hung_up)

    def _on_hung_up(self, result: CallResult):
        self._set_busy(False)
        if getattr(result, "ok", False):
            self.statusBar().showMessage("Call ended.")
            append_log(f"{_now()},outbound,{self._last_number},ended", DEFAULT_LOG)
            if self._recording:
                self._recording = False
                self._run_worker(
                    self.phone.pull_newest_recording, on_done=self._on_recording_pulled
                )
        else:
            self.statusBar().showMessage(f"Hang up failed: {getattr(result, 'detail', '')}")
            append_log(
                f"{_now()},outbound,{self._last_number},hangup failed {getattr(result, 'detail', '')}",
                DEFAULT_LOG,
            )
        self._load_log()

    def _on_recording_pulled(self, result: CallResult):
        if getattr(result, "ok", False):
            self.statusBar().showMessage(f"Recording saved: {getattr(result, 'detail', '')}")
            append_log(f"{_now()},outbound,{self._last_number},recording -> {getattr(result, 'detail', '')}", DEFAULT_LOG)
        else:
            self.statusBar().showMessage(
                f"Could not pull recording: {getattr(result, 'detail', '')}"
            )
            append_log(
                f"{_now()},outbound,{self._last_number},recording pull failed {getattr(result, 'detail', '')}",
                DEFAULT_LOG,
            )
        self._load_log()
        self._load_recordings()

    def _on_wifi_connect(self):
        from PyQt6.QtWidgets import QInputDialog, QMessageBox

        ip, ok = QInputDialog.getText(
            self, "Wireless ADB", "Device IP:Port\n(e.g. 192.168.1.50:5555)"
        )
        if not ok or not ip.strip():
            return
        host_port = ip.strip()
        self.statusBar().showMessage(f"Connecting to {host_port}...")
        QApplication.processEvents()

        res = self.phone.connect(host_port)
        if res.ok:
            self.statusBar().showMessage(f"Connected to {host_port}. Refresh to select it.")
        else:
            pair_choice = QMessageBox.question(
                self,
                "Connect failed",
                f"{getattr(res, 'detail', '')}\n\nPair this device first?\n"
                "(Phone: Developer options -> Wireless debugging -> Pair device "
                "with code)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if pair_choice == QMessageBox.StandardButton.Yes:
                code, ok2 = QInputDialog.getText(
                    self, "Pairing code", "Enter the 6-digit code shown on the phone"
                )
                if ok2 and code.strip():
                    self.phone.serial = None
                    pair_res = self.phone.pair(host_port, code.strip())
                    if pair_res.ok:
                        connect_res = self.phone.connect(host_port)
                        self.statusBar().showMessage(
                            "Paired + connected." if connect_res.ok
                            else f"Paired but connect failed: {connect_res.detail}"
                        )
                    else:
                        self.statusBar().showMessage(f"Pair failed: {pair_res.detail}")
        self.refresh_devices()

    # ------------------------------------------------------------- threading
    def _run_worker(self, fn, on_done=None):
        self._thread = QThread(self)
        self._worker = PhoneWorker(fn)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        handler = on_done if on_done else self._on_result
        self._worker.finished.connect(handler)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.error.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_result(self, result: CallResult):
        self._set_busy(False)
        if getattr(result, "ok", False):
            self.statusBar().showMessage("Done.")
        else:
            self.statusBar().showMessage(f"Failed: {getattr(result, 'detail', '')}")

    def _on_error(self, message: str):
        self._set_busy(False)
        self.statusBar().showMessage(f"Error: {message}")
        QMessageBox.critical(self, "Error", message)

    # ---------------------------------------------------------------- data
    def refresh_devices(self):
        try:
            states = self.phone.list_devices_states()
        except Exception as exc:  # noqa: BLE001
            states = []
            self.statusBar().showMessage(f"ADB error: {exc}")
        devices = [d["serial"] for d in states if d["state"] == "device"]
        unauthorized = [d["serial"] for d in states if d["state"] == "unauthorized"]
        self.device_combo.clear()
        self.device_combo.addItems(devices)
        if devices:
            self.statusBar().showMessage(f"{len(devices)} device(s) connected.")
        elif unauthorized:
            self.statusBar().showMessage(
                f"Phone {unauthorized[0]} is connected but UNAUTHORIZED — "
                "accept the 'Allow USB debugging?' prompt on the phone, then Refresh."
            )
        else:
            self.statusBar().showMessage(
                "No device. Enable USB/wireless debugging, connect, then Refresh."
            )

    def _load_log(self):
        from datetime import date, datetime, timedelta

        self.log_list.clear()
        records = read_call_log(DEFAULT_LOG)
        if not records:
            return

        records.sort(key=lambda r: r["dt"], reverse=True)
        today = date.today()
        groups: dict[str, list[dict]] = {}
        for rec in records:
            try:
                d = datetime.strptime(rec["dt"][:10], "%Y-%m-%d").date()
            except (ValueError, IndexError):
                continue
            if d == today:
                header = "Today"
            elif d == today - timedelta(days=1):
                header = "Yesterday"
            else:
                header = d.strftime("%a, %b %d")
            groups.setdefault(header, []).append(rec)

        for header, recs in groups.items():
            hitem = QListWidgetItem(header)
            hitem.setForeground(QColor("#90a4ae"))
            f = hitem.font()
            f.setBold(True)
            hitem.setFont(f)
            hitem.setFlags(hitem.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.log_list.addItem(hitem)
            for rec in recs:
                item = QListWidgetItem()
                self.log_list.addItem(item)
                self.log_list.setItemWidget(item, self._build_log_row(rec))
        self.log_list.scrollToBottom()

    def _build_log_row(self, record: dict) -> QWidget:
        direction = record.get("direction", "outbound")
        outbound = direction == "outbound"
        icon = "↗" if outbound else "↙"
        icon_color = "#4fc3f7" if outbound else "#66bb6a"
        dt = record.get("dt", "")
        time_text = dt[11:16] if len(dt) >= 16 else dt

        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(10)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(f"color:{icon_color}; font-size:16px; font-weight:bold;")
        num_lbl = QLabel(record.get("number", ""))
        num_lbl.setStyleSheet("font-size:14px;")
        time_lbl = QLabel(time_text)
        time_lbl.setStyleSheet("color:#9aa0a6; font-size:12px;")

        lay.addWidget(icon_lbl)
        lay.addWidget(num_lbl)
        lay.addStretch()
        lay.addWidget(time_lbl)
        return row

    def _load_recordings(self):
        from datetime import datetime
        from pathlib import Path

        # Build a lookup of call-log timestamps -> dialed number so we can
        # show which number each recording was to.
        call_times = []
        for rec in read_call_log(DEFAULT_LOG):
            try:
                call_times.append(
                    (datetime.strptime(rec["dt"][:19], "%Y-%m-%d %H:%M:%S"), rec["number"])
                )
            except (ValueError, IndexError):
                pass

        self.recordings_list.clear()
        rec_dir = Path(RECORDINGS_DIR)
        if not rec_dir.exists():
            return
        files = sorted(rec_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in files:
            if not path.is_file():
                continue
            size_kb = path.stat().st_size / 1024
            ts = datetime.fromtimestamp(path.stat().st_mtime)
            time_str = ts.strftime("%b %d, %Y · %I:%M %p")
            number = self._match_call_number(ts, call_times)
            label = time_str
            if number:
                label += f"  →  {number}"
            label += f"   ({size_kb:.0f} KB)"
            item = QListWidgetItem(label)
            item.setToolTip(str(path))
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setForeground(QColor("#e0e0e0"))
            self.recordings_list.addItem(item)
        if self.recordings_list.count() == 0:
            self.recordings_list.addItem("No recordings yet")

    def _match_call_number(self, ts, call_times: list, window: int = 180) -> str | None:
        """Return the dialed number from the call whose timestamp is closest to
        ts (within `window` seconds), else None."""
        best: str | None = None
        best_diff: float | None = None
        for call_dt, number in call_times:
            diff = abs((ts - call_dt).total_seconds())
            if diff <= window and (best_diff is None or diff < best_diff):
                best = number
                best_diff = diff
        return best

    # ---------------------------------------------------------------- player
    def _on_recording_selected(self, row: int):
        self._play_index = row

    def _play_at(self, index: int):
        item = self.recordings_list.item(index)
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole) or ""
        if not path:
            return
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()
        self._set_playing(True)
        self.statusBar().showMessage(f"Playing: {item.text()}")

    def _set_playing(self, playing: bool):
        self._playing = playing
        if playing:
            self.play_btn.setText("■ Stop")
            self.play_btn.setStyleSheet(
                "background-color:#c62828; color:white; font-weight:bold;"
            )
        else:
            self.play_btn.setText("▶ Play")
            self.play_btn.setStyleSheet(
                "background-color:#2e7d32; color:white; font-weight:bold;"
            )

    def _on_play_stop(self):
        if self._playing:
            self.player.stop()
            self._set_playing(False)
            return
        if self.recordings_list.count() == 0:
            self.statusBar().showMessage("No recordings to play.")
            return
        if self._play_index is None:
            self._play_index = 0
            self.recordings_list.setCurrentRow(0)
        self._play_at(self._play_index)

    def _on_prev(self):
        if self.recordings_list.count() == 0:
            return
        idx = (self._play_index if self._play_index is not None else 0) - 1
        if idx < 0:
            idx = self.recordings_list.count() - 1
        self._play_index = idx
        self.recordings_list.setCurrentRow(idx)
        self._play_at(idx)

    def _on_next(self):
        if self.recordings_list.count() == 0:
            return
        idx = (self._play_index if self._play_index is not None else -1) + 1
        if idx >= self.recordings_list.count():
            idx = 0
        self._play_index = idx
        self.recordings_list.setCurrentRow(idx)
        self._play_at(idx)

    def _on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._set_playing(False)


def _now() -> str:
    import time

    return time.strftime("%Y-%m-%d %H:%M:%S")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#101418"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#1b2027"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e8eaed"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e8eaed"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e8eaed"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2e7d32"))
    app.setPalette(palette)

    win = PhoneApp()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
