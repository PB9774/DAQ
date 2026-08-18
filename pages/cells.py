"""
pages/cells.py — per-segment cell voltage/temperature heatmap grid.
Split out of the old monolithic pages.py.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QGridLayout

from ev import DataEngine
from widgets import TelemetryStrip

from pages.common import _SegPanel


class HeatmapPage(QWidget):
    def __init__(self, engine: DataEngine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._panels = []
        self._strip = TelemetryStrip()
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(5, 4, 5, 2)
        tl.setSpacing(3)
        tl.addWidget(self._strip)

        # legend + Tmax/Tmin summary
        meta = QHBoxLayout()
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(16)
        for fg, bg, label in [
            ("#4ade80", "#0a5018", "OK 3.55-3.90V"),
            ("#fcd34d", "#78350f", "LOW <3.35V"),
            ("#fca5a5", "#7f1d1d", "HIGH >3.90V"),
        ]:
            dot = QLabel("■")
            dot.setStyleSheet("color:" + fg + ";font-size:14px;background:" + bg + ";border-radius:2px;padding:0 3px;")
            txt = QLabel(label)
            txt.setStyleSheet("font-size:13px;font-weight:600;background:transparent;border:none;")
            meta.addWidget(dot)
            meta.addWidget(txt)
        meta.addSpacing(14)

        self._tmax_lbl = QLabel("Tmax: --°C")
        self._tmax_lbl.setStyleSheet("color:#EF4444;font-size:14px;font-weight:700;background:transparent;border:none;")
        self._tmin_lbl = QLabel("Tmin: --°C")
        self._tmin_lbl.setStyleSheet("color:#22C55E;font-size:14px;font-weight:700;background:transparent;border:none;")
        meta.addWidget(self._tmax_lbl)
        meta.addWidget(self._tmin_lbl)
        meta.addStretch()
        tl.addLayout(meta)
        outer.addWidget(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("background:transparent;border:none;")

        cont = QWidget()
        grid = QGridLayout(cont)
        grid.setContentsMargins(5, 2, 5, 5)
        grid.setSpacing(6)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        for i in range(DataEngine.NUM_MODULES):
            p = _SegPanel(i)
            self._panels.append(p)
            grid.addWidget(p, i // 2, i % 2)
        scroll.setWidget(cont)
        outer.addWidget(scroll, 1)

    def refresh(self, engine, logger=None):
        self._strip.refresh(engine, logger)
        max_loc, max_v, min_loc, min_v = engine.cell_global_extremes()
        self._tmax_lbl.setText("Tmax: %.0f°C" % engine.tmax)
        self._tmin_lbl.setText("Tmin: %.0f°C" % engine.tmin)
        for i, p in enumerate(self._panels):
            p.refresh(engine.modules[i], max_loc, min_loc)
