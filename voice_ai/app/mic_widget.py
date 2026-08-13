"""Microphone button with a live volume meter.

Toggles continuous voice chat (checkable). While capturing, the mic icon's
capsule fills up with the current input level (0..1) to show that it is
recording/working. Painted manually so the fill reflects live volume.
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton


class MicButton(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(52, 52)
        self._level = 0.0
        self.setToolTip(
            "Click to start / stop continuous voice chat "
            "(talks after ~5s of silence)"
        )

    def set_level(self, value: float):
        value = float(np.clip(value, 0.0, 1.0))
        if abs(value - self._level) > 0.005:
            self._level = value
            self.update()

    def reset_level(self):
        if self._level != 0.0:
            self._level = 0.0
            self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        cx = rect.center().x()
        top = rect.center().y() - 16

        # background circle
        active = self.isChecked()
        bg = QColor(220, 40, 40, 80) if active else QColor(0, 0, 0, 45)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg))
        p.drawEllipse(rect)

        cap_w, cap_h = 16.0, 28.0
        cap = QRectF(cx - cap_w / 2, top, cap_w, cap_h)

        # volume fill (from the bottom of the capsule)
        fill_h = cap_h * self._level
        fill_color = QColor(239, 68, 68) if active else QColor(59, 130, 246)
        if fill_h > 1:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(fill_color))
            p.drawRoundedRect(
                QRectF(cx - cap_w / 2 + 1, top + cap_h - fill_h + 1,
                          cap_w - 2, fill_h - 2), 5, 5)

        # capsule outline
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(70, 70, 70), 2))
        p.drawRoundedRect(cap, 7, 7)

        # stand / arc
        p.setPen(QPen(fill_color if active else QColor(70, 70, 70), 2))
        p.drawArc(QRectF(cx - 9, top + cap_h - 6, 18, 14), 0, 180 * 16)
        p.drawLine(int(cx), int(top + cap_h + 7), int(cx), int(top + cap_h + 12))
        p.drawLine(int(cx - 6), int(top + cap_h + 16), int(cx + 6), int(top + cap_h + 16))
