"""
pages/trends.py — one reused plot, six selectable channels.

The history only grows once a second, so the chart is redrawn once a second
(and on a channel or window change) rather than ten times a second. The old
page kept five live PlotWidgets and re-set data on all of them every tick.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QButtonGroup, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from ui.helpers import card, label, numeral, set_mono_min_width, set_scaled_height, set_text
from ui.theme import Color
from ui.tokens import MONO_QFONT

try:
    import numpy as np
    import pyqtgraph as pg
    _PG = True
except ImportError:
    _PG = False

# (button, key in engine.history, axis label, unit, palette colour key, format)
CHANNELS = (
    ("PACK", "pack_v", "Pack voltage", "V", "ACCENT", "%.1f"),
    ("CURRENT", "current", "Current", "A", "CURRENT", "%.0f"),
    ("POWER", "power", "Power", "kW", "POWER", "%.2f"),
    ("SOC", "soc", "State of charge", "%", "SOC", "%.1f"),
    ("TEMP", "tmax", "Hottest cell", "°C", "SPEED", "%.1f"),
    ("ΔV", "delta_v", "Cell spread", "V", "TEXT_2", "%.3f"),
)
WINDOWS = (("1m", 60), ("5m", 300), ("10m", 600), ("30m", 1800))


class TrendsPage(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self._channel = 0
        self._window = 300
        self._samples = -1
        self._dirty = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)
        outer.addWidget(self._build_controls())

        if _PG:
            self._plot = self._build_plot()
            outer.addWidget(self._plot, 1)
        else:
            missing = label("pyqtgraph and numpy are not installed",
                            role="caption", align=Qt.AlignCenter)
            outer.addWidget(missing, 1)
        outer.addWidget(self._build_stats())
        self._apply_channel()

    # ── construction ───────────────────────────────────────────────────────
    def _build_controls(self):
        frame, row = card(margins=(10, 5, 10, 5), spacing=6, vertical=False)
        set_scaled_height(frame, "CAPTION", 3.5, 48)

        channels = QButtonGroup(self)
        for index, spec in enumerate(CHANNELS):
            button = QPushButton(spec[0])
            button.setObjectName("pill")
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _, i=index: self._select_channel(i))
            channels.addButton(button)
            row.addWidget(button)
        row.addStretch()

        windows = QButtonGroup(self)
        for text, seconds in WINDOWS:
            button = QPushButton(text)
            button.setObjectName("pill")
            button.setCheckable(True)
            button.setChecked(seconds == self._window)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _, s=seconds: self._select_window(s))
            windows.addButton(button)
            row.addWidget(button)
        return frame

    def _build_plot(self):
        plot = pg.PlotWidget()
        plot.setBackground(QColor(Color.GRAPH_BG))
        plot.showGrid(x=True, y=True, alpha=0.18)
        plot.setMenuEnabled(False)
        plot.setMouseEnabled(x=False, y=False)
        plot.hideButtons()
        plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tick_font = QFont(MONO_QFONT, 9)
        for side in ("left", "bottom"):
            axis = plot.getAxis(side)
            axis.setTextPen(pg.mkPen(Color.TEXT_3))
            axis.setPen(pg.mkPen(Color.LINE_HI))
            axis.setStyle(tickFont=tick_font)
        plot.getAxis("bottom").setLabel("seconds ago", color=Color.TEXT_3)
        self._curve = plot.plot([], [], antialias=True)
        return plot

    def _build_stats(self):
        frame, row = card(margins=(12, 6, 12, 6), spacing=14, vertical=False)
        set_scaled_height(frame, "CAPTION", 3.3, 46)
        self._stats = {}
        for key, title in (("now", "NOW"), ("min", "MIN"),
                           ("max", "MAX"), ("avg", "AVG")):
            row.addWidget(label(title, role="title"))
            value = numeral("--", "LEAD", Color.TEXT, Qt.AlignLeft | Qt.AlignVCenter)
            set_mono_min_width(value, "-000.0", "LEAD", 6)
            self._stats[key] = value
            row.addWidget(value)
        row.addStretch()
        self._span = label("NO DATA", role="caption", mono=True)
        row.addWidget(self._span)
        return frame

    # ── controls ───────────────────────────────────────────────────────────
    def _select_channel(self, index):
        self._channel = index
        self._apply_channel()

    def _select_window(self, seconds):
        self._window = seconds
        self._dirty = True

    def _apply_channel(self):
        self._dirty = True
        if not _PG:
            return
        _, _, title, unit, colour_key, _ = CHANNELS[self._channel]
        colour = getattr(Color, colour_key)
        axis = self._plot.getAxis("left")
        axis.setLabel(title, unit, color=colour)
        axis.setTextPen(pg.mkPen(colour))
        self._curve.setPen(pg.mkPen(colour, width=2))

    # ── per-tick ───────────────────────────────────────────────────────────
    def refresh(self, engine, recorder=None):
        if not _PG:
            return
        samples = len(engine.history["t"])
        if samples == self._samples and not self._dirty:
            return
        self._samples, self._dirty = samples, False
        if samples < 2:
            return

        _, key, _, unit, _, fmt = CHANNELS[self._channel]
        times = np.fromiter(engine.history["t"], dtype=float, count=samples)
        values = np.fromiter(engine.history[key], dtype=float, count=samples)
        latest = times[-1]
        mask = times >= latest - self._window
        times, values = times[mask], values[mask]
        if len(times) < 2:
            return

        # x as seconds-ago: the newest sample sits at 0, history runs negative,
        # so the axis reads the same regardless of how long the car has been on.
        ago = times - latest
        self._curve.setData(ago, values)
        low, high = float(values.min()), float(values.max())
        pad = (high - low) * 0.12 or max(abs(high) * 0.05, 0.5)
        self._plot.setXRange(-self._window, 0, padding=0)
        self._plot.setYRange(low - pad, high + pad, padding=0)

        stats = self._stats
        set_text(stats["now"], (fmt + " %s") % (values[-1], unit))
        set_text(stats["min"], fmt % low)
        set_text(stats["max"], fmt % high)
        set_text(stats["avg"], fmt % float(values.mean()))
        set_text(self._span, "%d SAMPLES" % len(times))

    def on_theme_changed(self):
        if not _PG:
            return
        self._plot.setBackground(QColor(Color.GRAPH_BG))
        for side in ("left", "bottom"):
            self._plot.getAxis(side).setPen(pg.mkPen(Color.LINE_HI))
        self._plot.getAxis("bottom").setTextPen(pg.mkPen(Color.TEXT_3))
        self._apply_channel()
