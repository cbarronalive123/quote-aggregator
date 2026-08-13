"""Main application window: hosts the Chat and Settings tabs and wires the
STT -> LLM -> TTS pipeline together, including continuous voice chat."""

from __future__ import annotations

from PyQt6.QtWidgets import QMainWindow, QMessageBox, QTabWidget

from app.chat_widget import ChatWidget
from app.config import SYSTEM_PROMPT
from app.continuous import ContinuousChatWorker
from app.model_manager import ModelManager
from app.settings_widget import SettingsWidget
from app.textutil import clean_reply
from app.worker import run_in_thread


class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.setWindowTitle("Voice AI Chatbot")
        self.resize(860, 640)

        self.config = config
        self.models = ModelManager(config)
        self._worker = None

        self.tabs = QTabWidget()
        self.chat = ChatWidget(config)
        self.settings = SettingsWidget(
            config, self.models, refresh_callback=self.chat.rebuild_voices
        )

        self.tabs.addTab(self.chat, "Chat")
        self.tabs.addTab(self.settings, "Settings")
        self.setCentralWidget(self.tabs)

        # Text send path (non-voice)
        self.chat.send_text.connect(self._on_user_text)

        # Continuous voice chat
        self.chat.mic.toggled.connect(self._on_mic_toggled)
        self.chat.stop_requested.connect(self._on_stop_requested)

        self.statusBar().showMessage("Starting...")
        run_in_thread(self._check_llm, on_done=self._llm_check_done)
        run_in_thread(self.models.warm_up)

    # ---------- LLM availability ----------
    def _check_llm(self):
        return self.models.llm_running()

    def _llm_check_done(self, running: bool):
        if running:
            self.statusBar().showMessage(f"Ollama ready — model: {self.models.llm.model}")
        else:
            self.statusBar().showMessage(
                "Ollama not running. Start the Ollama app to enable AI replies."
            )
            self.chat.append_status(
                "Ollama is not running. Install/start Ollama and pull a model "
                "(e.g. qwen3:4b)."
            )

    # ---------- Continuous voice chat ----------
    def _on_mic_toggled(self, checked: bool):
        if checked:
            self._start_continuous()
        else:
            self._stop_continuous()

    def _start_continuous(self):
        if self._worker is not None:
            return
        worker = ContinuousChatWorker(self.models, self.chat.current_voice)
        worker.user_text.connect(self.chat.append_user)
        worker.ai_text.connect(self.chat.append_ai)
        worker.status.connect(self.chat.append_status)
        worker.level.connect(self.chat.mic.set_level)
        worker.speech_started.connect(self.chat.show_stop)
        worker.speech_finished.connect(self.chat.hide_stop)
        worker.finished.connect(lambda: self._on_worker_finished(worker))
        self._worker = worker
        self.chat.append_status("Continuous voice chat started. Speak now.")
        worker.start()

    def _stop_continuous(self):
        if self._worker is not None:
            self._worker.stop()
            self.chat.mic.reset_level()
            self.chat.hide_stop()
        self.chat.mic.setChecked(False)

    def _on_stop_requested(self):
        if self._worker is not None:
            self._worker.interrupt_speech()
            self.chat.hide_stop()

    def _on_worker_finished(self, worker):
        if self._worker is worker:
            self._worker = None
            self.chat.mic.setChecked(False)
            self.chat.mic.reset_level()
            self.chat.hide_stop()

    # ---------- Text in -> LLM -> voice out ----------
    def _on_user_text(self, text: str):
        voice = self.chat.current_voice()
        self.chat.append_status("Thinking...")
        run_in_thread(
            lambda: self.models.llm.generate(text, system=SYSTEM_PROMPT),
            on_done=lambda reply: self._on_reply(reply, voice),
            on_error=self._on_pipeline_error,
        )

    def _on_reply(self, reply: str, voice: str):
        reply = clean_reply(reply)
        if not reply:
            self.chat.append_status("(empty reply)")
            return
        self.chat.append_ai(reply)
        self.chat.append_status("Speaking...")
        run_in_thread(
            lambda: self.models.synthesize(reply, voice_id=voice),
            on_done=lambda result: self.chat.play_audio(*result),
            on_error=self._on_pipeline_error,
        )

    # ---------- Error handling ----------
    def _on_pipeline_error(self, msg: str):
        self.chat.append_status(f"Error: {msg}")
        QMessageBox.warning(self, "Error", msg)
