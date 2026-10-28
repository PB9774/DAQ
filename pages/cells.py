"""Segment-level voltage and temperature detail."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QScrollArea, QScroller, QVBoxLayout, QWidget,
)

from core.config import SERIES_CELLS
from core.faults import CELL_V_WARN_HI, CELL_V_WARN_LO
from ui.cellgrid import CellGrid, SegmentHeader, TempGrid
from ui.helpers import (
    card, dv_status, label, numeral, rule, set_mono_min_width, set_scaled_height,
    set_text, style_numeral,
)
from ui.theme import Color, TM


class SegmentDetailsPage(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self._spread_status = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)
        self.summary_card = self._build_summary()
        self.summary_card.setFocusPolicy(Qt.StrongFocus)
        outer.addWidget(self.summary_card)

        grids = QHBoxLayout()
        grids.setSpacing(6)
        self.grid = CellGrid()
        grids.addWidget(self._build_cell_card(), 1)
        self.temps = TempGrid()
        self._temp_summary = label("", role="caption", mono=True)
        self.temp_card = self._grid_card("TEMPERATURE", self._temp_summary, self.temps)
        self.temp_card.setFocusPolicy(Qt.StrongFocus)
        grids.addWidget(self.temp_card, 1)
        outer.addLayout(grids, 1)

    def _build_cell_card(self):
        frame, column = card(margins=(10, 6, 10, 6), spacing=4)
        column.addWidget(label("CELL VOLTAGE", role="title"))
        column.addWidget(label("98 cells · 7 segments", role="caption"))

        self.cell_scroll = QScrollArea()
        self.cell_scroll.setObjectName("grid_scroll")
        self.cell_scroll.setWidgetResizable(True)
        self.cell_scroll.setFrameShape(QFrame.NoFrame)
        self.cell_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cell_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.cell_scroll.setFocusPolicy(Qt.StrongFocus)
        self.cell_scroll.verticalScrollBar().setSingleStep(self.grid.BASE_ROW_H or 32)
        self.cell_scroll.setWidget(self.grid)

        try:
            QScroller.grabGesture(self.cell_scroll.viewport(), QScroller.LeftMouseButtonGesture)
        except Exception:
            pass

        self.grid_header = SegmentHeader(self.cell_scroll)
        column.addWidget(self.grid_header)
        column.addWidget(self.cell_scroll, 1)
        return frame

    @staticmethod
    def _grid_card(title, summary, grid):
        frame, column = card(margins=(10, 6, 10, 6), spacing=4)
        column.addWidget(label(title, role="title"))
        column.addWidget(label(summary, role="caption") if isinstance(summary, str) else summary)
        column.addWidget(grid, 1)
        return frame

    def _build_summary(self):
        frame, row = card(margins=(12, 6, 12, 6), spacing=10, vertical=False)
        set_scaled_height(frame, "LEAD", 2.5, 50)

        self._readouts = {}
        specs = (
            ("HIGH", "high", Color.ACCENT, "3.951"),
            ("LOW", "low", Color.SPEED, "3.951"),
            ("SPREAD", "spread", Color.TEXT, "800 mV"),
            ("AVG", "avg", Color.TEXT, "3.710 V"),
            ("OFF-BAND", "band", Color.TEXT, "00 cells"),
        )
        for index, (title, key, colour, sample) in enumerate(specs):
            if index:
                row.addWidget(rule(vertical=True, length=24))
            row.addWidget(label(title, role="title"))
            value = numeral("--", "LEAD", colour, Qt.AlignLeft | Qt.AlignVCenter)
            set_mono_min_width(value, sample, "LEAD", 2)
            self._readouts[key] = value
            row.addWidget(value)
        row.addStretch()
        return frame

    def refresh(self, engine, recorder=None):
        readouts = self._readouts
        set_text(readouts["high"], "%.3f" % engine.vmax)
        set_text(readouts["low"], "%.3f" % engine.vmin)
        high_tip = "Highest cell: %s" % engine.vmax_location
        low_tip = "Lowest cell: %s" % engine.vmin_location
        if readouts["high"].toolTip() != high_tip:
            readouts["high"].setToolTip(high_tip)
        if readouts["low"].toolTip() != low_tip:
            readouts["low"].setToolTip(low_tip)
        set_text(readouts["spread"], "%.0f mV" % (engine.delta_v * 1000))
        set_text(readouts["avg"], "%.3f V" % (engine.pack_voltage / SERIES_CELLS))
        set_text(self._temp_summary, "MAX %.0f° · AVG %.0f° · MIN %.0f°"
                 % (engine.tmax, engine.avg_temperature, engine.tmin))
        spread_tip = "Temperature spread: %.1f°C" % (engine.tmax - engine.tmin)
        if self._temp_summary.toolTip() != spread_tip:
            self._temp_summary.setToolTip(spread_tip)

        status = dv_status(engine.delta_v)
        if status != self._spread_status:
            self._spread_status = status
            style_numeral(readouts["spread"], "LEAD", Color.status(status))

        # Only worth scanning the pack when an extreme says a cell can be out.
        outside = 0
        if engine.vmax > CELL_V_WARN_HI or engine.vmin < CELL_V_WARN_LO:
            outside = sum(1 for module in engine.modules for cell in module.cells
                          if cell.voltage > CELL_V_WARN_HI or cell.voltage < CELL_V_WARN_LO)
        set_text(readouts["band"], "%d cells" % outside)
        self.grid.set_data(engine)
        self.temps.set_data(engine)

    def on_theme_changed(self):
        self._spread_status = None
        self.grid.update_geometry()
        self.grid.update()
        if hasattr(self, "grid_header"):
            self.grid_header.update()
        if hasattr(self, "cell_scroll"):
            step = int(round((self.grid.BASE_ROW_H or 50) * TM.font_scale))
            self.cell_scroll.verticalScrollBar().setSingleStep(step)
        self.temps.update_geometry()
        self.temps.update()
