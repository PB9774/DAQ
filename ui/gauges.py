"""
ui/gauges.py — hand-painted instruments (speed arc, battery column).

Painted widgets instead of stacks of styled QLabels: one paintEvent per
frame, no style engine involvement, and update() is skipped entirely when
the value has not moved enough to change a pixel.
"""

import math

from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QSizePolicy, QWidget

from core.config import SPEED_MAX
from ui.helpers import soc_status
from ui.theme import Color
from ui.tokens import MONO_QFONT

_START_ANGLE = 216.0
_SWEEP = 252.0


def _ramp(fraction):
    """Green -> amber -> red across the dial."""
    fraction = max(0.0, min(1.0, fraction))
    if fraction < 0.55:
        a, b, t = QColor("#22C55E"), QColor("#FFB020"), fraction / 0.55
    else:
        a, b, t = QColor("#FFB020"), QColor("#FF4D4F"), (fraction - 0.55) / 0.45
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
    )


class SpeedGauge(QWidget):
    """Sweeping arc with tick marks and a tabular centre readout."""

    def __init__(self, compact=False, parent=None):
        super().__init__(parent)
        self._speed = 0.0
        self._compact = compact
        self.setMinimumHeight(150 if compact else 230)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)

    def set_speed(self, speed):
        speed = max(0.0, min(SPEED_MAX, float(speed)))
        if abs(speed - self._speed) < 0.25:
            return
        self._speed = speed
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        side = min(self.width(), self.height() * 1.55)
        radius = side * 0.40
        centre = QPointF(self.width() / 2.0, self.height() * 0.60)
        box = QRectF(centre.x() - radius, centre.y() - radius, radius * 2, radius * 2)
        thickness = max(9.0, radius * 0.115)
        fraction = self._speed / SPEED_MAX

        painter.setPen(QPen(QColor(Color.GAUGE_TRACK), thickness, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(box, int(_START_ANGLE * 16), int(-_SWEEP * 16))

        if fraction > 0.004:
            painter.setPen(QPen(_ramp(fraction), thickness, Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(box, int(_START_ANGLE * 16), int(-_SWEEP * fraction * 16))

        self._draw_ticks(painter, centre, radius, thickness)
        self._draw_readout(painter, centre, radius, fraction)

    def _draw_ticks(self, painter, centre, radius, thickness):
        """Ticks are scale, not state: the arc carries the colour, they don't.

        Colouring reached ticks made a 40 km/h dial read green-amber-green in
        three places at once, which is noise on a HUD you glance at."""
        inner = radius - thickness * 0.95
        step = 10
        count = int(SPEED_MAX // step)
        tick_font = QFont(MONO_QFONT)
        tick_font.setPixelSize(max(9, int(radius * 0.105)))
        tick_font.setBold(True)

        minor = QColor(Color.TEXT_3)
        minor.setAlpha(120)
        major_colour = QColor(Color.TEXT_2)

        for index in range(count + 1):
            value = index * step
            angle = math.radians(_START_ANGLE - _SWEEP * (value / SPEED_MAX))
            cos_a, sin_a = math.cos(angle), -math.sin(angle)
            major = value % 20 == 0

            length = inner * (0.10 if major else 0.055)
            painter.setPen(QPen(major_colour if major else minor,
                                2.4 if major else 1.4, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(
                QPointF(centre.x() + (inner - length) * cos_a, centre.y() + (inner - length) * sin_a),
                QPointF(centre.x() + inner * cos_a, centre.y() + inner * sin_a),
            )
            if major and not self._compact:
                label_r = inner - length - radius * 0.16
                point = QPointF(centre.x() + label_r * cos_a, centre.y() + label_r * sin_a)
                painter.setFont(tick_font)
                painter.setPen(QPen(QColor(Color.TEXT_3)))
                painter.drawText(QRectF(point.x() - 18, point.y() - 9, 36, 18),
                                 Qt.AlignCenter, str(value))

    def _draw_readout(self, painter, centre, radius, fraction):
        value_font = QFont(MONO_QFONT)
        value_font.setPixelSize(max(40, int(radius * (0.72 if self._compact else 0.86))))
        value_font.setBold(True)
        painter.setFont(value_font)
        # One quantised step, not a continuous ramp: white until the car is
        # near the limiter, then red. Anything else flickers colour mid-corner.
        painter.setPen(QPen(QColor(Color.crit if fraction >= 0.92 else Color.TEXT)))
        box = QRectF(centre.x() - radius, centre.y() - radius * 0.62, radius * 2, radius * 1.0)
        painter.drawText(box, Qt.AlignCenter, "%.0f" % self._speed)

        unit_font = QFont(MONO_QFONT)
        unit_font.setPixelSize(max(11, int(radius * 0.135)))
        unit_font.setBold(True)
        painter.setFont(unit_font)
        painter.setPen(QPen(QColor(Color.TEXT_3)))
        painter.drawText(QRectF(centre.x() - radius, centre.y() + radius * 0.40, radius * 2, radius * 0.3),
                         Qt.AlignCenter, "km / h")


class BatteryGauge(QWidget):
    """Vertical cell-stack battery. 20 chunks, so 5 % of travel per chunk."""

    CHUNKS = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lit = -1
        self._status = soc_status(0.0)
        self.setMinimumWidth(74)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

    def set_soc(self, soc):
        soc = max(0.0, min(100.0, float(soc)))
        lit = int(round(soc / 100.0 * self.CHUNKS))
        status = soc_status(soc)
        if lit == self._lit and status == self._status:
            return
        self._lit, self._status = lit, status
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        colour = QColor(Color.status(self._status))
        width = min(self.width() - 8, 62)
        left = (self.width() - width) / 2.0
        cap_h = max(6.0, self.height() * 0.028)
        body = QRectF(left, cap_h + 3, width, self.height() - cap_h - 8)

        painter.setPen(QPen(QColor(Color.LINE_HI), 2))
        painter.setBrush(QColor(Color.SURFACE))
        painter.drawRoundedRect(QRectF(left + width * 0.30, 1, width * 0.40, cap_h), 2, 2)
        painter.drawRoundedRect(body, 8, 8)

        pad = 5.0
        inner_h = body.height() - pad * 2
        gap = 2.0
        chunk_h = (inner_h - gap * (self.CHUNKS - 1)) / self.CHUNKS
        painter.setPen(Qt.NoPen)
        for index in range(self.CHUNKS):
            top = body.bottom() - pad - (index + 1) * chunk_h - index * gap
            if index < self._lit:
                painter.setBrush(colour)
            else:
                dim = QColor(Color.LINE)
                dim.setAlpha(110)
                painter.setBrush(dim)
            painter.drawRoundedRect(QRectF(body.left() + pad, top, body.width() - pad * 2, chunk_h), 2, 2)
