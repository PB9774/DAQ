"""
pages/driver.py — the driver HUD.

One screen, no navigation, nothing that needs reading twice: speed in the
middle, charge on the left, the four numbers that decide whether to push or
back off on the right, and one sentence at the bottom saying what the car is
doing. Everything updates by value only; styles move on state changes.
"""

import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from core.config import ENERGY_PER_LAP_KWH, TELEMETRY_PORT
from ui.gauges import BatteryGauge, SpeedGauge
from ui.helpers import (
    card, label, numeral, rule, set_scaled_height, set_scaled_width, set_text,
    soc_status, style_numeral, temp_status,
)
from ui.theme import Color
from ui.widgets import LogoWidget, MetricTile, StatusBanner

class DriverPage(QWidget):
    engineer_requested = pyqtSignal()

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._soc_status = None
        self._feed_active = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(8)
        outer.addWidget(self._build_topbar())

        body = QHBoxLayout()
        body.setSpacing(8)
        body.addWidget(self._build_charge(), 0)
        body.addWidget(self._build_speed(), 1)
        body.addWidget(self._build_numbers(), 0)
        outer.addLayout(body, 1)

        self.banner = StatusBanner()
        outer.addWidget(self.banner)

    # ── construction ───────────────────────────────────────────────────────
    def _build_topbar(self):
        bar = QWidget()
        set_scaled_height(bar, "LEAD", 2.4, 48)
        row = QHBoxLayout(bar)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(12)

        row.addWidget(LogoWidget(height=26, max_width=104))
        row.addWidget(rule(vertical=True, length=24))
        self._clock = label("--:--:--", size="SMALL", weight=700, mono=True)
        row.addWidget(self._clock)
        row.addWidget(rule(vertical=True, length=24))
        self._source = label("NO SIGNAL", role="caption")
        row.addWidget(self._source)
        row.addStretch()

        self._feed_button = QPushButton("START TELEMETRY")
        self._feed_button.setObjectName("driver_feed")
        self._feed_button.setCursor(Qt.PointingHandCursor)
        self._feed_button.setToolTip(
            "Stream telemetry on port %d (closed network only)." % TELEMETRY_PORT)
        self._feed_button.clicked.connect(self._toggle_feed)
        row.addWidget(self._feed_button)

        button = QPushButton("ENGINEER  ▶")
        button.setObjectName("driver_mode")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(self.engineer_requested.emit)
        row.addWidget(button)
        return bar

    def _toggle_feed(self):
        stream = self._engine.stream
        if stream.is_active:
            stream.stop()
        else:
            stream.start()
        self._sync_feed_button(stream.is_active)

    def _sync_feed_button(self, active):
        if active == self._feed_active:
            return
        self._feed_active = active
        self._feed_button.setText("STOP TELEMETRY" if active else "START TELEMETRY")
        self._feed_button.setProperty("active", "true" if active else "false")
        self._feed_button.style().unpolish(self._feed_button)
        self._feed_button.style().polish(self._feed_button)

    def _build_charge(self):
        frame, column = card(margins=(12, 10, 12, 10), spacing=4)
        set_scaled_width(frame, 186)

        head = QHBoxLayout()
        head.setSpacing(6)
        head.addStretch()
        head.addWidget(label("CHARGE", role="title"))
        head.addStretch()
        column.addLayout(head)

        value = QHBoxLayout()
        value.setSpacing(2)
        value.addStretch()
        self._soc = numeral("--", "HERO", Color.SOC, Qt.AlignRight | Qt.AlignVCenter)
        value.addWidget(self._soc)
        value.addWidget(label("%", role="unit", align=Qt.AlignBottom))
        value.addStretch()
        column.addLayout(value)

        row = QHBoxLayout()
        row.setSpacing(10)
        self._battery = BatteryGauge()
        row.addWidget(self._battery, 0)

        side = QVBoxLayout()
        side.setSpacing(2)
        side.addStretch()
        side.addWidget(label("ENERGY", role="title"))
        self._energy = numeral("--", "LEAD", Color.TEXT, Qt.AlignLeft | Qt.AlignVCenter)
        side.addWidget(self._energy)
        side.addWidget(label("kWh", role="unit"))
        side.addSpacing(10)
        side.addWidget(label("RANGE", role="title"))
        self._range = numeral("--", "LEAD", Color.TEXT_2, Qt.AlignLeft | Qt.AlignVCenter)
        side.addWidget(self._range)
        side.addWidget(label("laps", role="unit"))
        side.addStretch()
        row.addLayout(side, 1)
        column.addLayout(row, 1)
        return frame

    def _build_speed(self):
        frame = QFrame()
        frame.setObjectName("card")
        column = QVBoxLayout(frame)
        column.setContentsMargins(8, 6, 8, 6)
        column.setSpacing(2)
        self.speed = SpeedGauge()
        column.addWidget(self.speed, 1)
        return frame

    def _build_numbers(self):
        holder = QWidget()
        set_scaled_width(holder, 214)
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)

        self._pack_v = MetricTile("PACK", "V", size="TITLE", accent=Color.TEXT)
        self._current = MetricTile("CURRENT", "A", size="TITLE", accent=Color.CURRENT)
        self._power = MetricTile("POWER", "kW", size="TITLE", accent=Color.POWER)
        self._temp = MetricTile("MAX TEMP", "°C", size="TITLE", detail=True)
        for tile in (self._pack_v, self._current, self._power, self._temp):
            column.addWidget(tile, 1)
        return holder

    # ── per-tick ───────────────────────────────────────────────────────────
    def refresh(self, engine, recorder=None):
        self._sync_feed_button(engine.stream.is_active)
        self.speed.set_speed(engine.speed)
        self._battery.set_soc(engine.soc)

        set_text(self._soc, "%.0f" % engine.soc)
        status = soc_status(engine.soc)
        if status != self._soc_status:
            self._soc_status = status
            style_numeral(self._soc, "HERO", Color.status(status))

        set_text(self._energy, "%.1f" % engine.energy_kwh)
        set_text(self._range, "%.0f" % (engine.energy_kwh / ENERGY_PER_LAP_KWH))
        set_text(self._clock, datetime.datetime.now().strftime("%H:%M:%S"))
        set_text(self._source, engine.source_name.upper())

        self._pack_v.set_value("%.1f" % engine.pack_voltage)
        self._current.set_value("%+.0f" % engine.current)
        self._power.set_value("%.1f" % engine.power_kw)
        self._temp.set_value("%.0f" % engine.tmax, temp_status(engine.tmax))
        self._temp.set_detail("%s  ·  ΔV %.0f mV"
                              % (engine.tmax_location, engine.delta_v * 1000))

        self.banner.set_state(engine.status, engine.faults.headline)

    def on_theme_changed(self):
        self._soc_status = None
        self.banner.restyle()
        for tile in (self._pack_v, self._current, self._power, self._temp):
            tile.restyle()
        self.speed.update()
        self._battery.update()
