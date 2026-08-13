"""Chat widget: message history, text input, send button, voice picker,
microphone button, and audio playback."""

from __future__ import annotations

import numpy as np
import sounddevice as sd
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.mic_widget import MicButton
from app.voices import resolve_voice


class ChatWidget(QWidget):
    send_text = pyqtSignal(str)
    stop_requested = pyqtSignal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._history = []  # list of dicts: {"role", "content"}

        self.log = QTextBrowser()
        self.log.setOpenExternalLinks(False)
        self.log.setPlaceholderText("Chat with your AI assistant...")

        self.input = QTextEdit()
        self.input.setPlaceholderText("Type a message... (Enter to send)")
        self.input.setFixedHeight(72)

        self.voice_picker = QComboBox()
        self.voice_picker.setMinimumWidth(200)

        self.mic = MicButton()

        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.setStyleSheet(
            "background:#dc2626; color:white; font-weight:bold; padding:6px 12px;"
        )
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self.stop_requested)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._on_send)

        row = QHBoxLayout()
        row.addWidget(QLabel("Voice:"))
        row.addWidget(self.voice_picker, 1)
        row.addWidget(self.mic)
        row.addWidget(self.stop_btn)
        row.addWidget(self.send_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.log, 1)
        layout.addLayout(row)
        layout.addWidget(self.input)

        self.input.installEventFilter(self)
        self.rebuild_voices()

    def set_speaking(self, speaking: bool):
        """Show the Stop button while the AI is talking; hide otherwise."""
        self.stop_btn.setVisible(speaking)

    def show_stop(self):
        self.set_speaking(True)

    def hide_stop(self):
        self.set_speaking(False)

    def rebuild_voices(self):
        current = self.config.get("default_voice", "af_heart")
        self.voice_picker.blockSignals(True)
        self.voice_picker.clear()
        for vid in self.config.get("enabled_voices", []):
            v = resolve_voice(vid, self.config)
            if v:
                self.voice_picker.addItem(v["label"], vid)
        idx = self.voice_picker.findData(current)
        if idx >= 0:
            self.voice_picker.setCurrentIndex(idx)
        self.voice_picker.blockSignals(False)

    def current_voice(self) -> str:
        return self.voice_picker.currentData() or self.config.get(
            "default_voice", "af_heart"
        )

    def eventFilter(self, obj, event):
        if obj is self.input:
            if (
                event.type() == event.Type.KeyPress
                and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            ):
                self._on_send()
                return True
        return super().eventFilter(obj, event)

    def _on_send(self):
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self.append_user(text)
        self.send_text.emit(text)

    def append_user(self, text: str):
        self._history.append({"role": "user", "content": text})
        self.log.append(
            f'<p style="color:#3b82f6; margin:6px 0;"><b>You:</b><br>{self._esc(text)}</p>'
        )

    def append_ai(self, text: str):
        self._history.append({"role": "assistant", "content": text})
        self.log.append(
            f'<p style="color:#10b981; margin:6px 0;"><b>AI:</b><br>{self._esc(text)}</p>'
        )

    def append_status(self, text: str):
        self.log.append(f'<p style="color:#888; margin:4px 0;">{self._esc(text)}</p>')

    @staticmethod
    def _esc(text: str) -> str:
        return (
            text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

    def play_audio(self, audio: np.ndarray, sample_rate: int):
        if audio is None or len(audio) == 0:
            return
        try:
            sd.stop()
            sd.play(audio, samplerate=sample_rate)
        except Exception as exc:  # noqa: BLE001
            self.append_status(f"Playback error: {exc}")
