"""
ui/widgets.py — the reusable pieces: logo, metric tile, status pill, banner.

Every one of these separates "the value moved" from "the state changed".
Values go through set_text(); styles are only touched when the quantised
status actually flips.
"""

import os

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from core.config import ASSET_DIR
from ui.helpers import (
    badge_style, label, numeral, set_mono_min_width, set_mono_width,
    set_scaled_height, set_ss, set_text, style_numeral,
)
from ui.theme import Color, TM
from ui.tokens import MONO, STATUS_LABEL


class LogoWidget(QWidget):
    """Team logo, sized from the asset's own aspect and scaled once per resize.

    The width follows the artwork instead of a guessed multiplier — reserving
    more than the mark needs is what pushed the status strip past 1024 px and
    made everything after it collide.
    """

    def __init__(self, height=32, max_width=None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._source = QPixmap()
        self._scaled = QPixmap()
        for name in ("logo1.png", "logo.png", "logo.jpg"):
            path = os.path.join(ASSET_DIR, name)
            if os.path.isfile(path):
                self._source = QPixmap(path)
                break

        if self._source.isNull() or not self._source.height():
            width = height * 3
        else:
            width = int(round(height * self._source.width() / self._source.height()))
        self.setFixedSize(min(width, max_width or width), height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._scaled = QPixmap()

    def paintEvent(self, _event):
        if self._source.isNull():
            return
        if self._scaled.isNull() or self._scaled.size() != self.size():
            self._scaled = self._source.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter = QPainter(self)
        if not TM.is_dark:
            # The mark is white artwork; on a light theme it needs its own plate.
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(Color.GAUGE_BG))
            painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 5, 5)
        painter.drawPixmap(
            (self.width() - self._scaled.width()) // 2,
            (self.height() - self._scaled.height()) // 2,
            self._scaled,
        )


class MetricTile(QFrame):
    """Title, big monospace value, optional unit and detail line."""

    def __init__(self, title, unit="", size="DISPLAY", detail=False,
                 accent=None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._accent = accent
        self._status = None
        self._size = size
        self.detail = None

        outer = QVBoxLayout(self)
        self._apply_spacing()

        head = QHBoxLayout()
        head.setSpacing(6)
        head.addWidget(label(title.upper(), role="title"))
        head.addStretch()
        if unit:
            head.addWidget(label(unit, role="unit"))
        outer.addLayout(head)

        self.value = numeral("--", size, accent or Color.TEXT)
        self.value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer.addWidget(self.value)

        if detail:
            self.detail = label("", role="caption", mono=True)
            outer.addWidget(self.detail)

    def _apply_spacing(self):
        pad_v = max(3, int(round(7 / TM.font_scale)))
        pad_h = max(8, int(round(12 / TM.font_scale)))
        self.layout().setContentsMargins(pad_h, pad_v, pad_h, pad_v)
        self.layout().setSpacing(max(1, int(round(2 / TM.font_scale))))

    def set_value(self, text, status=None):
        set_text(self.value, text)
        if status != self._status:
            self._status = status
            colour = Color.status(status) if status else (self._accent or Color.TEXT)
            style_numeral(self.value, self._size, colour)

    def set_detail(self, text):
        if self.detail is not None:
            set_text(self.detail, text)

    def restyle(self):
        self._status = None
        self._apply_spacing()


class StatusPill(QLabel):
    """Compact tinted badge — OK / 3 WARN / 2 CRIT."""

    def __init__(self, text="OK", parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        set_mono_min_width(self, "18 WARN", "CAPTION", 16)
        self._status = None
        self.set_state("ok", "OK")

    def set_state(self, status, text):
        set_text(self, text)
        if status != self._status:
            self._status = status
            set_ss(self, badge_style(status))

    def restyle(self):
        self._status = None


class StatusBanner(QFrame):
    """The driver's single most important widget: what is the car doing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        set_scaled_height(self, "TITLE", 2.6, 52)
        self._status = None

        row = QHBoxLayout(self)
        row.setContentsMargins(18, 4, 18, 4)
        row.setSpacing(16)

        self._word = label("READY", align=Qt.AlignCenter, size="TITLE", weight=900, spacing=3)
        set_mono_width(self._word, "CAUTION", "TITLE", 30)
        self._message = label("ALL SYSTEMS NOMINAL", size="LEAD", weight=700, mono=True)
        self._message.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row.addWidget(self._word)
        row.addWidget(self._message, 1)

    def set_state(self, status, message):
        set_text(self._message, message)
        if status == self._status:
            return
        self._status = status
        colour = Color.status(status)
        set_text(self._word, STATUS_LABEL.get(status, "NOTICE"))
        set_ss(self, "QFrame{background:%s;border:2px solid %s;border-radius:%dpx;}"
                     % (Color.tint(status), colour, 10))
        set_ss(self._word, "color:%s;font-size:%dpx;font-weight:900;letter-spacing:3px;"
                           "background:transparent;border:none;" % (colour, TM.size("TITLE")))
        set_ss(self._message, "color:%s;font-family:%s;font-size:%dpx;font-weight:700;"
                              "background:transparent;border:none;"
                              % (Color.TEXT, MONO, TM.size("LEAD")))

    def restyle(self):
        self._status = None
