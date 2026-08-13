"""Settings widget: a Models tab (choose/download LLM/STT/TTS) and a Voices tab
(checkbox list of enabled voices, default voice, professional badges)."""

from __future__ import annotations

import io
import os
import uuid
import zipfile
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.voices import VOICE_CATALOG, all_voices, resolve_voice

RVC_MODELS_DIR = Path(__file__).resolve().parent.parent / "models" / "rvc"


class _ProgressEmitter(QObject):
    """Lives on the main thread so progress signals from a worker thread are
    queued to the UI thread automatically."""

    progress = pyqtSignal(int)


def _download_rvc_model(url: str, key: str, on_progress=None):
    """Stream + unzip an RVC model. Returns (pth_path, index_path|None)."""
    import requests

    dest = RVC_MODELS_DIR / key
    dest.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=900) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0)) or 1
        downloaded = 0
        buf = io.BytesIO()
        for chunk in r.iter_content(chunk_size=1 << 16):
            if chunk:
                buf.write(chunk)
                downloaded += len(chunk)
                if on_progress:
                    on_progress(int(downloaded / total * 100))
    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        zf.extractall(dest)
    pth = next((f for f in dest.rglob("*.pth")), None)
    index = next((f for f in dest.rglob("*.index")), None)
    if pth is None:
        raise RuntimeError("Downloaded model contains no .pth file.")
    return str(pth), (str(index) if index is not None else None)

# Best local LLMs for an RTX 3060 (12GB, ~6GB free) conversational/voice use.
# qwen3:4b = best default (fast, quality, VRAM headroom for TTS/STT)
# phi4-mini = best reasoning per VRAM (MIT) · llama3.3:8b = best quality (tight)
KNOWN_LLMS = [
    "qwen3:4b",
    "phi4-mini",
    "llama3.2:3b",
    "gemma3:4b",
    "llama3.3:8b",
    "qwen3:8b",
    "mistral:7b-instruct",
]
KNOWN_STT = ["small", "medium", "large-v3-turbo"]


class SettingsWidget(QWidget):
    def __init__(self, config, model_manager, refresh_callback=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.models = model_manager
        self.refresh_callback = refresh_callback

        from PyQt6.QtWidgets import QTabWidget

        tabs = QTabWidget()

        tabs.addTab(self._build_models_tab(), "Models")
        tabs.addTab(self._build_voices_tab(), "Voices")
        tabs.addTab(self._build_clone_tab(), "Clone")

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

    # ---------- Models tab ----------
    def _build_models_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.llm_combo = QComboBox()
        self.llm_combo.addItems(KNOWN_LLMS)
        idx = self.llm_combo.findText(self.config.get("llm_model", "llama3.2:3b"))
        if idx >= 0:
            self.llm_combo.setCurrentIndex(idx)
        self.llm_pull_btn = QPushButton("Download / Pull")
        self.llm_pull_btn.clicked.connect(self._pull_llm)
        self.llm_status = QLabel()
        self.llm_status.setWordWrap(True)

        llm_box = QHBoxLayout()
        llm_box.addWidget(self.llm_combo, 1)
        llm_box.addWidget(self.llm_pull_btn)
        form.addRow("LLM:", llm_box)
        form.addRow(self.llm_status)

        self.stt_combo = QComboBox()
        self.stt_combo.addItems(KNOWN_STT)
        idx = self.stt_combo.findText(self.config.get("stt_model", "small"))
        if idx >= 0:
            self.stt_combo.setCurrentIndex(idx)
        form.addRow("STT (speech→text):", self.stt_combo)

        form.addRow(
            "TTS (text→speech):",
            QLabel("Kokoro-82M (built-in, Apache 2.0)"),
        )

        note = QLabel(
            "VRAM budget ≈ 6 GB free. One heavy model is loaded at a time. "
            "LLM = Ollama (needs the Ollama app running). STT/TTS unload after use."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#888;")
        form.addRow(note)

        self.llm_combo.currentTextChanged.connect(self._on_llm_changed)
        self.stt_combo.currentTextChanged.connect(self._on_stt_changed)
        return w

    def _on_llm_changed(self, text: str):
        self.config.set("llm_model", text)
        self.models.llm.model = text

    def _on_stt_changed(self, text: str):
        self.config.set("stt_model", text)
        self.models.stt.model_size = text
        self.models.stt.unload()

    def _pull_llm(self):
        from app.worker import run_in_thread

        model = self.llm_combo.currentText()
        self.llm_status.setText(f"Pulling {model}...")

        def work():
            self.models.llm.pull(model)

        def done(_result):
            self.llm_status.setText(f"Done: {model} ready.")

        def err(msg):
            self.llm_status.setText(f"Error: {msg}")

        run_in_thread(work, on_done=done, on_error=err)

    # ---------- Voices tab ----------
    def _build_voices_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        header = QLabel(
            "Check voices to enable on the chat toolbar. "
            "Professional voices are suited to phone / insurance agents."
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        self.voice_list = QListWidget()
        self._checkboxes = {}
        self._populate_voice_list()
        layout.addWidget(self.voice_list, 1)

        self.default_voice_combo = QComboBox()
        self.refresh_default_voice()
        self.default_voice_combo.currentIndexChanged.connect(self._on_default_changed)

        dl = QHBoxLayout()
        dl.addWidget(QLabel("Default voice:"))
        dl.addWidget(self.default_voice_combo, 1)
        layout.addLayout(dl)

        layout.addWidget(self._build_rvc_group())

        if self.refresh_callback:
            btn = QPushButton("Apply voices to chat")
            btn.clicked.connect(self.refresh_callback)
            layout.addWidget(btn)

        return w

    def _populate_voice_list(self):
        self.voice_list.clear()
        self._checkboxes = {}
        enabled = set(self.config.get("enabled_voices", []))
        for v in all_voices(self.config):
            vid = v["id"]
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, vid)
            self.voice_list.addItem(item)
            cb = QCheckBox(f"{v['label']} — {v['style']}")
            if v.get("professional"):
                cb.setText(f"{v['label']} ★ Professional — {v['style']}")
            cb.setChecked(vid in enabled)
            cb.toggled.connect(self._on_voice_toggled)
            self._checkboxes[vid] = cb
            self.voice_list.setItemWidget(item, cb)

    def _build_rvc_group(self) -> QWidget:
        box = QGroupBox("RVC celebrity voices (Terminator / Robin Williams)")
        form = QFormLayout(box)
        self._rvc_edits = {}
        self._rvc_progress = {}
        self._rvc_emitters = {}
        rvc_models = self.config.get("rvc_models", {})
        for v in VOICE_CATALOG:
            if v.get("kind") != "rvc":
                continue
            key = v["rvc_key"]
            edit = QLineEdit(rvc_models.get(key, ""))
            edit.setPlaceholderText("Path to .pth model file")
            edit.setReadOnly(True)
            browse = QPushButton("Browse…")
            # Bind the current `edit` by value so each row updates its own field.
            browse.clicked.connect(lambda _c=False, e=edit, k=key: self._browse_rvc(k, e))
            dl = QPushButton("Download")
            dl.clicked.connect(
                lambda _c=False, e=edit, k=key, u=v.get("rvc_url", ""):
                self._download_rvc(k, u, e)
            )
            prog = QProgressBar()
            prog.setRange(0, 100)
            prog.setValue(0)
            prog.setTextVisible(False)
            prog.setFixedHeight(8)
            prog.setVisible(False)

            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(dl)
            row.addWidget(browse)

            self._rvc_edits[key] = edit
            self._rvc_progress[key] = prog
            self._rvc_emitters[key] = _ProgressEmitter()

            form.addRow(f"{v['label']}:", row)
            form.addRow("", prog)
        self._rvc_status = QLabel("")
        self._rvc_status.setWordWrap(True)
        form.addRow(self._rvc_status)
        hint = QLabel(
            "Click 'Download' to fetch the model automatically (Arnold from "
            "huggingface.co/yraziel/Schwarzenegger · Robin Williams from "
            "huggingface.co/Coleereer/EGadd). For personal/hobby use only."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888;")
        form.addRow(hint)
        return box

    def _download_rvc(self, key: str, url: str, edit: QLineEdit):
        from app.worker import run_in_thread

        prog = self._rvc_progress[key]
        emitter = self._rvc_emitters[key]
        emitter.progress.connect(prog.setValue)
        prog.setValue(0)
        prog.setVisible(True)
        self._rvc_status.setText(f"Downloading {key}…")

        def work():
            return _download_rvc_model(url, key, on_progress=emitter.progress.emit)

        def done(result):
            pth, index = result
            rvc_models = dict(self.config.get("rvc_models", {}))
            rvc_models[key] = pth
            if index:
                rvc_models[key + "_index"] = index
            self.config.set("rvc_models", rvc_models)
            edit.setText(pth)
            prog.setVisible(False)
            self._rvc_status.setText(f"Ready: {pth}")

        def err(msg):
            prog.setVisible(False)
            self._rvc_status.setText(f"Download error: {msg}")

        run_in_thread(work, on_done=done, on_error=err)

    def _browse_rvc(self, key: str, edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Select RVC model for {key}", "", "RVC model (*.pth);;All files (*)"
        )
        if path:
            edit.setText(path)
            rvc_models = dict(self.config.get("rvc_models", {}))
            rvc_models[key] = path
            self.config.set("rvc_models", rvc_models)

    # ---------- Voice Cloning tab ----------
    def _build_clone_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        intro = QLabel(
            "Clone any voice from a reference audio clip (3–15 s of clean "
            "speech recommended, WAV/MP3). Uses Qwen3-TTS (Apache 2.0 — fully "
            "free, incl. commercial) via the local voice server. "
            "Note: cloning a real person without consent is for personal use only."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()

        self.clone_name = QLineEdit()
        self.clone_name.setPlaceholderText("e.g. My Voice")
        self.clone_ref_edit = QLineEdit()
        self.clone_ref_edit.setPlaceholderText("Reference audio file (.wav/.mp3)")
        self.clone_ref_edit.setReadOnly(True)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_clone_ref)

        ref_row = QHBoxLayout()
        ref_row.addWidget(self.clone_ref_edit, 1)
        ref_row.addWidget(browse)

        form.addRow("Name:", self.clone_name)
        form.addRow("Reference:", ref_row)
        layout.addLayout(form)

        create_btn = QPushButton("Create Clone")
        create_btn.clicked.connect(self._create_clone)
        layout.addWidget(create_btn)

        layout.addWidget(QLabel("Your cloned voices:"))

        self.clone_list = QListWidget()
        self._populate_clone_list()
        layout.addWidget(self.clone_list, 1)

        delete_btn = QPushButton("Delete Selected Clone")
        delete_btn.clicked.connect(self._delete_clone)
        layout.addWidget(delete_btn)

        return w

    def _populate_clone_list(self):
        self.clone_list.clear()
        clones = self.config.get("cloned_voices", {})
        for vid, info in clones.items():
            item = QListWidgetItem(f"{info.get('name', vid)}  ({info.get('reference', '')})")
            item.setData(Qt.ItemDataRole.UserRole, vid)
            self.clone_list.addItem(item)

    def _browse_clone_ref(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select reference audio", "", "Audio (*.wav *.mp3 *.flac);;All files (*)"
        )
        if path:
            self.clone_ref_edit.setText(path)

    def _create_clone(self):
        name = self.clone_name.text().strip()
        ref = self.clone_ref_edit.text().strip()
        if not name or not ref or not os.path.exists(ref):
            QMessageBox.warning(
                self, "Clone", "Provide a name and a valid reference audio file."
            )
            return
        clones = dict(self.config.get("cloned_voices", {}))
        vid = "clone_" + uuid.uuid4().hex[:8]
        clones[vid] = {"name": name, "reference": ref}
        self.config.set("cloned_voices", clones)

        enabled = set(self.config.get("enabled_voices", []))
        enabled.add(vid)
        self.config.set("enabled_voices", sorted(enabled))

        self.clone_name.clear()
        self.clone_ref_edit.clear()
        self._populate_clone_list()
        self._populate_voice_list()
        self._sync_chat_and_default()
        QMessageBox.information(self, "Clone", f"Created clone '{name}'.")

    def _delete_clone(self):
        item = self.clone_list.currentItem()
        if not item:
            return
        vid = item.data(Qt.ItemDataRole.UserRole)
        clones = dict(self.config.get("cloned_voices", {}))
        clones.pop(vid, None)
        self.config.set("cloned_voices", clones)

        enabled = set(self.config.get("enabled_voices", []))
        enabled.discard(vid)
        self.config.set("enabled_voices", sorted(enabled))

        self._populate_clone_list()
        self._populate_voice_list()
        self._sync_chat_and_default()

    def refresh_default_voice(self):
        self.default_voice_combo.blockSignals(True)
        self.default_voice_combo.clear()
        for vid in self.config.get("enabled_voices", []):
            v = resolve_voice(vid, self.config)
            if v:
                self.default_voice_combo.addItem(v["label"], vid)
        idx = self.default_voice_combo.findData(
            self.config.get("default_voice", "af_heart")
        )
        if idx >= 0:
            self.default_voice_combo.setCurrentIndex(idx)
        self.default_voice_combo.blockSignals(False)

    def _sync_chat_and_default(self):
        if self.refresh_callback:
            self.refresh_callback()
        self.refresh_default_voice()

    def _on_voice_toggled(self, checked: bool):
        cb = self.sender()
        for vid, box in self._checkboxes.items():
            if box is cb:
                enabled = set(self.config.get("enabled_voices", []))
                if checked:
                    enabled.add(vid)
                else:
                    enabled.discard(vid)
                self.config.set("enabled_voices", sorted(enabled))
                self.refresh_default_voice()
                return

    def _on_default_changed(self):
        data = self.default_voice_combo.currentData()
        if data:
            self.config.set("default_voice", data)
