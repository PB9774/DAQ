"""The engineer overview: pack metrics, charge, segment health and faults."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from ui.cellgrid import SegmentHealthBar
from ui.faultpanel import FaultPanel
from ui.gauges import BatteryGauge
from ui.helpers import (
    card, dv_status, label, numeral, set_scaled_width, set_text, soc_status,
    style_numeral, temp_status,
)
from ui.theme import Color
from ui.widgets import MetricTile


class OverviewPage(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self._soc_status = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(self._build_charge(), 0)
        top.addLayout(self._build_tiles(), 1)
        self.faults = FaultPanel(rows=6)
        set_scaled_width(self.faults, 298)
        top.addWidget(self.faults, 0)
        outer.addLayout(top, 1)

        self.segments = SegmentHealthBar()
        outer.addWidget(self.segments)

    def _build_charge(self):
        frame, column = card(margins=(8, 8, 8, 6), spacing=4)
        set_scaled_width(frame, 266)

        row = QHBoxLayout()
        row.setSpacing(10)
        self._battery = BatteryGauge()
        self._battery.setFixedWidth(56)
        row.addWidget(self._battery)

        side = QVBoxLayout()
        side.setSpacing(0)
        side.addStretch()
        side.addWidget(label("CHARGE", role="title"))
        self._soc = numeral("--", "DISPLAY", Color.SOC, Qt.AlignLeft | Qt.AlignVCenter)
        self._soc.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        side.addWidget(self._soc)
        self._energy = label("-- kWh", role="caption", mono=True)
        side.addWidget(self._energy)
        side.addStretch()
        row.addLayout(side, 1)
        column.addLayout(row, 0)
        return frame

    def _build_tiles(self):
        grid = QGridLayout()
        grid.setSpacing(8)
        self._tiles = {
            "pack_v": MetricTile("PACK", "V", size="DISPLAY", accent=Color.TEXT),
            "current": MetricTile("CURRENT", "A", size="DISPLAY", accent=Color.CURRENT),
            "power": MetricTile("POWER", "kW", size="DISPLAY", accent=Color.POWER),
            "delta_v": MetricTile("SPREAD", "mV", size="DISPLAY", detail=True),
            "tmax": MetricTile("HOT SPOT", "°C", size="DISPLAY", detail=True),
            "tavg": MetricTile("AVG TEMP", "°C", size="DISPLAY", accent=Color.TEXT),
        }
        order = ("pack_v", "current", "power", "delta_v", "tmax", "tavg")
        for index, key in enumerate(order):
            grid.addWidget(self._tiles[key], index // 2, index % 2)
        return grid

    def refresh(self, engine, recorder=None):
        self._battery.set_soc(engine.soc)

        set_text(self._soc, "%.0f%%" % engine.soc)
        status = soc_status(engine.soc)
        if status != self._soc_status:
            self._soc_status = status
            style_numeral(self._soc, "DISPLAY", Color.status(status))
        set_text(self._energy, "%.2f kWh LEFT" % engine.energy_kwh)

        tiles = self._tiles
        tiles["pack_v"].set_value("%.1f" % engine.pack_voltage)
        tiles["current"].set_value("%+.0f" % engine.current)
        tiles["power"].set_value("%.1f" % engine.power_kw)
        tiles["delta_v"].set_value("%.0f" % (engine.delta_v * 1000), dv_status(engine.delta_v))
        tiles["delta_v"].set_detail("↑%s ↓%s" % (engine.vmax_location, engine.vmin_location))
        tiles["tmax"].set_value("%.0f" % engine.tmax, temp_status(engine.tmax))
        tiles["tmax"].set_detail("@%s  ↓%.0f°C" % (engine.tmax_location, engine.tmin))
        tiles["tavg"].set_value("%.1f" % engine.avg_temperature)

        self.segments.set_data(engine.stats)
        self.faults.refresh(engine)

    def on_theme_changed(self):
        self._soc_status = None
        for tile in self._tiles.values():
            tile.restyle()
        self.faults.restyle()
        self._battery.update()
        self.segments.update()
