"""Simple background-thread helper for PyQt.

Runs a callable on a daemon thread and marshals results/errors back to the
main (Qt) thread via signals. PyQt queues signal emissions to the main thread
automatically, so the UI never freezes during inference/recording.
"""

from __future__ import annotations

import threading
from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal


class _Signals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)


def run_in_thread(
    fn: Callable,
    on_done: Callable = None,
    on_error: Callable = None,
    on_progress: Callable = None,
    *args,
    **kwargs,
):
    """Run fn(*args, **kwargs) in a background thread.

    - on_done(result)      -> success
    - on_error(str(e))     -> exception
    - on_progress(str)     -> optional status updates
    Returns the signals object (so callers can disconnect if needed).
    """
    sig = _Signals()
    if on_done:
        sig.finished.connect(on_done)
    if on_error:
        sig.error.connect(on_error)
    if on_progress:
        sig.progress.connect(on_progress)

    def target():
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - surface any backend error to UI
            sig.error.emit(f"{type(exc).__name__}: {exc}")
        else:
            sig.finished.emit(result)

    threading.Thread(target=target, daemon=True).start()
    return sig
