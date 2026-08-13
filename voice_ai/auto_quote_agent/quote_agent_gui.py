"""Quote Agent GUI - voice-enabled PyQt6 chat interface.

You speak (or type) as the broker; the agent transcribes you, answers from the
applicant profile in natural spoken English, and speaks its
answer back. It opens the call audibly with a greeting, introduces itself as an
AI agent, acknowledges consent, and detects + records any quote the broker
gives (monthly, annual, reference number) into a JSON notes file for future
reference.

Reuses the main app's voice stack: faster-whisper STT, Kokoro TTS, volume mic.

Run:  .venv\\Scripts\\python.exe auto_quote_agent\\quote_agent_gui.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.mic_widget import MicButton  # noqa: E402
from app.stt import STTEngine  # noqa: E402
from app.tts import TTSEngine  # noqa: E402
from app.worker import run_in_thread  # noqa: E402
from app.quote.conversation import QuoteConversation  # noqa: E402
from app.quote.load_profile import load_profile  # noqa: E402
from app.quote.quote_notes import CallNotes, QuoteRecord, write_notes  # noqa: E402
from app.quote.quote_outcome import save_outcome  # noqa: E402
from app.quote.resolver import QuoteAnswerEngine  # noqa: E402
from app.voices import VOICE_CATALOG  # noqa: E402
from auto_quote_agent.broker_questions import BROKER_QUESTIONS  # noqa: E402
from auto_quote_agent.quote_voice_worker import QuoteVoiceWorker  # noqa: E402

APPLICANT = "Test Driver"
PURPOSE = "an Ontario private-passenger auto insurance quote"
DEFAULT_VOICE = "bm_george"  # professional voice for the agent


def _to_float(s: str) -> float | None:
    try:
        return float(s.strip().replace("$", "").replace(",", "")) or None
    except ValueError:
        return None


class QuoteDialog(QDialog):
    """Collect the quote the broker gives (fallback manual entry)."""

    def __init__(self, parent=None, company: str = "Allstate"):
        super().__init__(parent)
        self.setWindowTitle("Record quote from broker")
        self._annual = QLineEdit()
        self._monthly = QLineEdit()
        self._ref = QLineEdit()
        self._company = QLineEdit(company)
        self._valid = QLineEdit()
        self._phone = QLineEdit()
        form = QFormLayout()
        form.addRow("Annual price ($):", self._annual)
        form.addRow("Monthly price ($):", self._monthly)
        form.addRow("Quote / reference number:", self._ref)
        form.addRow("Company:", self._company)
        form.addRow("Valid until:", self._valid)
        form.addRow("Call-back phone:", self._phone)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def quote(self) -> QuoteRecord:
        return QuoteRecord(
            annual=_to_float(self._annual.text()),
            monthly=_to_float(self._monthly.text()),
            reference_number=self._ref.text().strip(),
            company=self._company.text().strip() or "Allstate",
            valid_until=self._valid.text().strip(),
            phone_number=self._phone.text().strip(),
        )


class QuoteAgentWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto Quote Agent — Voice (test profile)")
        self.resize(780, 640)

        self._engine: QuoteAnswerEngine | None = None
        self._conv: QuoteConversation | None = None
        self._profile = None
        self._quote: QuoteRecord | None = None
        self._transcript: list[dict] = []
        self._unknowns: list[str] = []
        self._worker: QuoteVoiceWorker | None = None
        self._last_saved: tuple | None = None

        self.stt = STTEngine()
        self.tts = TTSEngine()

        self.log = QTextBrowser()
        self.log.setPlaceholderText("Press Start Call to begin.")

        self.status = QLabel("Not started.")
        self.status.setStyleSheet("color:#555;")

        self.start_btn = QPushButton("Start Call")
        self.start_btn.clicked.connect(self._start)
        self.ask_all_btn = QPushButton("Ask All Questions")
        self.ask_all_btn.clicked.connect(self._ask_all)
        self.quote_btn = QPushButton("Record Quote")
        self.quote_btn.clicked.connect(self._record_quote)
        self.end_btn = QPushButton("End Call & Save Notes")
        self.end_btn.clicked.connect(self._end_call)

        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.setStyleSheet("background:#dc2626; color:white; font-weight:bold;")
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._on_stop_requested)

        self.voice_picker = QComboBox()
        self.voice_picker.setMinimumWidth(200)
        for v in VOICE_CATALOG:
            if v.get("kind") != "rvc":
                self.voice_picker.addItem(f"{v['label']} — {v['style']}", v["id"])
        idx = self.voice_picker.findData(DEFAULT_VOICE)
        if idx >= 0:
            self.voice_picker.setCurrentIndex(idx)

        self.mic = MicButton()
        self.mic.toggled.connect(self._on_mic_toggled)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Type (or use the mic) as the broker... Enter to send")
        self.input.returnPressed.connect(self._send)
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._send)

        top = QHBoxLayout()
        for b in (self.start_btn, self.ask_all_btn, self.quote_btn, self.end_btn):
            top.addWidget(b)
            b.setEnabled(False)
        self.start_btn.setEnabled(True)

        voice_row = QHBoxLayout()
        voice_row.addWidget(QLabel("Agent voice:"))
        voice_row.addWidget(self.voice_picker, 1)
        voice_row.addWidget(self.stop_btn)

        send_row = QHBoxLayout()
        send_row.addWidget(self.input, 1)
        send_row.addWidget(self.send_btn)
        send_row.addWidget(self.mic)

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addLayout(voice_row)
        layout.addWidget(self.log, 1)
        layout.addLayout(send_row)
        layout.addWidget(self.status)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    # ---- helpers ----
    def _add(self, who: str, text: str, color: str):
        self.log.append(f'<p style="color:{color}; margin:3px 0;"><b>{who}:</b> {_esc(text)}</p>')

    def _broker(self, q: str):
        self._transcript.append({"role": "broker", "text": q})
        self._add("Broker", q, "#3b82f6")

    def _agent(self, a: str):
        self._transcript.append({"role": "agent", "text": a})
        self._add("Agent", a, "#10b981")

    def _speak(self, text: str, voice: str | None = None):
        v = voice or self.current_voice()
        def work():
            audio, sr = self.tts.synthesize(text, voice=v)
            import sounddevice as sd
            sd.play(audio, sr)
        run_in_thread(work, on_error=lambda m: self._add("Note", f"TTS error: {m}", "#888"))

    def _speak_spelled(self, value: str, voice: str | None = None):
        v = voice or self.current_voice()
        def work():
            audio, sr = self.tts.synthesize_spelled(value, voice=v)
            import sounddevice as sd
            sd.play(audio, sr)
        run_in_thread(work, on_error=lambda m: self._add("Note", f"TTS error: {m}", "#888"))

    def _require_ready(self) -> bool:
        if self._conv is None:
            QMessageBox.warning(self, "Not started", "Press Start Call first.")
            return False
        return True

    def current_voice(self) -> str:
        return self.voice_picker.currentData() or DEFAULT_VOICE

    # ---- actions ----
    def _start(self):
        self._profile = load_profile()
        self._engine = QuoteAnswerEngine(self._profile)
        self._conv = QuoteConversation(self._engine, APPLICANT, PURPOSE)
        self._quote = None
        self._transcript = []
        self._unknowns = []
        self._last_saved = None
        self.log.clear()
        self.status.setText("Starting… (loading voice)")
        try:
            self.tts.ensure()
        except Exception as exc:  # noqa: BLE001
            self.status.setText(f"TTS not available: {exc}")
        import sounddevice as sd
        if not sd.query_devices():
            self.status.setText("Warning: no audio output device found.")

        greeting = "Hi, how are you?"
        self._agent(greeting)
        self._speak(greeting)
        self.start_btn.setEnabled(False)
        for b in (self.ask_all_btn, self.quote_btn, self.end_btn, self.send_btn, self.input):
            b.setEnabled(True)
        self.status.setText("Ready — greeted the caller. Respond using the mic or typing.")

    def _send(self):
        if not self._require_ready():
            return
        q = self.input.text().strip()
        if not q:
            return
        self.input.clear()
        self._broker(q)
        res = self._conv.respond(q)
        self._agent(res["text"])
        if res.get("type") == "spell" and res.get("spell"):
            self._speak_spelled(res["spell"])
        else:
            self._speak(res["text"])
        if res.get("quote"):
            self._quote = res["quote"]
            self._maybe_save_notes()
        if res["type"] == "unknown":
            self._unknowns.append(q)

    def _ask_all(self):
        if not self._require_ready():
            return
        for item in BROKER_QUESTIONS:
            q = item["q"]
            self._broker(q)
            a = self._engine.spoken_answer(q)
            self._agent(a)
            if "I don't have that information" in a:
                self._unknowns.append(q)
        self.status.setText(f"Asked {len(BROKER_QUESTIONS)} questions. Record the quote.")

    # ---- voice ----
    def _on_mic_toggled(self, checked: bool):
        if checked:
            self._start_voice()
        else:
            self._stop_voice()

    def _start_voice(self):
        if self._worker is not None or not self._require_ready():
            self.mic.setChecked(False)
            return
        worker = QuoteVoiceWorker(self._conv.respond, self.stt, self.tts, self.current_voice())
        worker.broker_text.connect(self._on_broker_voice)
        worker.agent_text.connect(self._on_agent_voice)
        worker.status.connect(self.status.setText)
        worker.level.connect(self.mic.set_level)
        worker.speech_started.connect(self.stop_btn.show)
        worker.speech_finished.connect(self.stop_btn.hide)
        worker.finished.connect(lambda: self._on_voice_finished(worker))
        self._worker = worker
        self.status.setText("Listening — speak as the broker, then pause ~3s.")
        worker.start()

    def _stop_voice(self):
        if self._worker is not None:
            self._worker.stop()
            self.mic.reset_level()
            self.stop_btn.hide()
        self.mic.setChecked(False)

    def _on_stop_requested(self):
        if self._worker is not None:
            self._worker.interrupt_speech()
            self.stop_btn.hide()

    def _on_broker_voice(self, text: str):
        self._broker(text)

    def _on_agent_voice(self, text: str):
        self._agent(text)
        if self._conv is not None and self._conv.quote is not None:
            self._quote = self._conv.quote
            self._maybe_save_notes()

    def _on_voice_finished(self, worker):
        if self._worker is worker:
            self._worker = None
            self.mic.setChecked(False)
            self.mic.reset_level()
            self.stop_btn.hide()
            self.status.setText("Voice chat ended. Start again with the mic.")

    # ---- quote recording ----
    def _maybe_save_notes(self):
        q = self._quote
        if q is None:
            return
        key = (q.monthly, q.annual, q.reference_number)
        if key == self._last_saved:
            return
        self._last_saved = key
        notes = CallNotes(
            applicant=APPLICANT,
            quote=q,
            questions_asked=len(self._transcript),
            unknowns=list(dict.fromkeys(self._unknowns)),
            outstanding_fields=[f.key for f in self._profile.missing_fields()],
            transcript=self._transcript,
            terminal_status="quoted",
        )
        write_notes(notes)
        # Export the quote result in the exact QuoteOutcome JSON shape, timestamped.
        path = save_outcome(q, profile=self._profile, terminal_status="quoted",
                            confidence="medium", source="phone")
        self.status.setText(f"Quote recorded & saved: {path}")

    def _record_quote(self):
        if not self._require_ready():
            return
        dlg = QuoteDialog(self, company=(self._quote.company if self._quote else "Allstate"))
        if dlg.exec():
            self._quote = dlg.quote()
            msg = (f"Thank you — quote recorded for future reference: "
                   f"{self._quote.company}, {self._quote.monthly or '?'}/mo "
                   f"({self._quote.annual or '?'}/yr), ref {self._quote.reference_number or '—'}.")
            self._agent(msg)
            self._maybe_save_notes()

    def _end_call(self):
        if self._conv is None:
            return
        self._stop_voice()
        closing = self._conv.engine.end_of_call()
        self._agent(closing)
        self._speak(closing)
        notes = CallNotes(
            applicant=APPLICANT,
            quote=self._quote or QuoteRecord(),
            questions_asked=len(self._transcript),
            unknowns=list(dict.fromkeys(self._unknowns)),
            outstanding_fields=[f.key for f in self._profile.missing_fields()],
            transcript=self._transcript,
            terminal_status="quoted" if self._quote else "unresolved",
        )
        path = write_notes(notes)
        self.status.setText(f"Notes saved: {path}")
        QMessageBox.information(self, "Saved", f"Call notes written to:\n{path}")


def _esc(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    app = QApplication(sys.argv)
    win = QuoteAgentWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
