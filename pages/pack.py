"""
pages/pack.py — battery pack diagram: 7 segments colored by health,
voltage, or temperature. Split out of the old monolithic pages.py.

v20 fix: v19 looked up each segment's labels positionally via
`sw.findChildren(QLabel)[1]/[2]/[3]` — fragile, since it silently breaks
(wrong label updated, or an IndexError) if the widget tree ever changes.
Each segment tile is now a tiny dataclass-like holder with direct
references to its labels, so there's nothing to accidentally reorder.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
    QPushButton, QButtonGroup, QSizePolicy,
)

from theme import MONO
from ev import DataEngine
from widgets import TelemetryStrip

from pages.common import _P, _health_ss


class _SegTile:
    """Direct references to one segment's widgets — no positional lookup."""
    def __init__(self, frame, v_lbl, t_lbl, h_badge):
        self.frame = frame
        self.v_lbl = v_lbl
        self.t_lbl = t_lbl
        self.h_badge = h_badge


class PackDiagramPage(QWidget):
    def __init__(self, engine: DataEngine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._strip = TelemetryStrip()
        self._mode = "health"  # "health" | "voltage" | "temp"
        self._tiles = []
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 5, 6, 5)
        root.setSpacing(5)
        root.addWidget(self._strip)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        title = QLabel("BATTERY PACK DIAGRAM")
        title.setObjectName("page_header")
        hdr.addWidget(title)
        hdr.addStretch()

        self._mode_grp = QButtonGroup(self)
        for i, (key, label) in enumerate([("health", "HEALTH"), ("voltage", "VOLTAGE"), ("temp", "TEMP")]):
            b = QPushButton(label)
            b.setObjectName("btn_pill")
            b.setCheckable(True)
            b.setChecked(key == "health")
            b.setFixedHeight(30)
            b.clicked.connect(lambda _, k=key: self._set_mode(k))
            self._mode_grp.addButton(b, i)
            hdr.addWidget(b)
        root.addLayout(hdr)

        # 7-segment grid: 2 rows — top row has 4, bottom 3
        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setSpacing(10)
        for i in range(DataEngine.NUM_MODULES):
            tile = self._make_seg_tile(i)
            self._tiles.append(tile)
            row, col = i // 4, i % 4
            grid.addWidget(tile.frame, row, col)
        for col in range(DataEngine.NUM_MODULES % 4, 4):
            grid.addWidget(QWidget(), DataEngine.NUM_MODULES // 4, col)
        root.addWidget(grid_w, 1)

        self._summary = QLabel("Pack status: Initialising...")
        self._summary.setStyleSheet("color:" + _P("TEXT_SEC") + ";font-size:15px;font-weight:600;background:transparent;border:none;")
        self._summary.setAlignment(Qt.AlignCenter)
        root.addWidget(self._summary)

    def _make_seg_tile(self, idx):
        f = QFrame()
        f.setObjectName("card")
        f.setMinimumHeight(120)
        f.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay = QVBoxLayout(f)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        title = QLabel("SEGMENT %d" % (idx + 1))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:15px;font-weight:800;letter-spacing:2px;background:transparent;border:none;")

        v_lbl = QLabel("---")
        v_lbl.setAlignment(Qt.AlignCenter)
        v_lbl.setStyleSheet("font-size:22px;font-family:" + MONO + ";font-weight:900;background:transparent;border:none;")

        t_lbl = QLabel("---")
        t_lbl.setAlignment(Qt.AlignCenter)
        t_lbl.setStyleSheet("font-size:17px;font-family:" + MONO + ";font-weight:700;background:transparent;border:none;")

        h_badge = QLabel("OK")
        h_badge.setAlignment(Qt.AlignCenter)
        h_badge.setFixedHeight(24)
        h_badge.setStyleSheet(_health_ss("ok"))

        lay.addWidget(title)
        lay.addWidget(v_lbl)
        lay.addWidget(t_lbl)
        lay.addWidget(h_badge)
        return _SegTile(f, v_lbl, t_lbl, h_badge)

    def _set_mode(self, mode):
        self._mode = mode

    def refresh(self, engine, logger=None):
        self._strip.refresh(engine, logger)
        n_crit = 0
        n_warn = 0

        for i, tile in enumerate(self._tiles):
            health = engine.mod_health(i)
            avg_v = engine.mod_avg_v(i)
            tmax_s = engine.mod_tmax(i)
            if health == "crit":
                n_crit += 1
            elif health == "warn":
                n_warn += 1

            tile.v_lbl.setText("%.3f V" % avg_v)
            tile.t_lbl.setText("Tmax %.0f°C" % tmax_s)
            tile.h_badge.setText(health.upper())
            tile.h_badge.setStyleSheet(_health_ss(health))

            if self._mode == "health":
                bg = {"ok": "#0A1F10", "warn": "#1F1400", "crit": "#1F0505"}.get(health, "#1A2130")
                border = {"ok": "#22C55E", "warn": "#D97706", "crit": "#EF4444"}.get(health, "#283040")
            elif self._mode == "voltage":
                fc = (avg_v - 3.3) / (3.9 - 3.3)
                r = int(255 * (1 - max(0, min(1, fc))))
                g = int(200 * max(0, min(1, fc)))
                bg = "#%02x%02x05" % (max(10, r // 8), max(8, g // 8))
                border = "#%02x%02x30" % (r // 2, g // 2)
            else:  # temp
                fc = (tmax_s - 30) / (55 - 30)
                r = int(255 * max(0, min(1, fc)))
                g = int(200 * max(0, min(1, 1 - fc)))
                bg = "#%02x%02x05" % (max(10, r // 8), max(8, g // 8))
                border = "#%02x%02x30" % (r // 2, g // 2)

            tile.frame.setStyleSheet("QFrame#card{background:%s;border:2px solid %s;border-radius:8px;}" % (bg, border))

            vc = "#EF4444" if avg_v > 3.90 else ("#F59E0B" if avg_v < 3.40 else "#4ADE80")
            tc2 = "#EF4444" if tmax_s >= 50 else ("#F59E0B" if tmax_s >= 42 else "#22C55E")
            tile.v_lbl.setStyleSheet("color:" + vc + ";font-size:22px;font-family:" + MONO + ";font-weight:900;background:transparent;border:none;")
            tile.t_lbl.setStyleSheet("color:" + tc2 + ";font-size:17px;font-family:" + MONO + ";font-weight:700;background:transparent;border:none;")

        msg = "All segments nominal" if n_crit + n_warn == 0 else ("%d CRITICAL  |  %d WARNING segments" % (n_crit, n_warn))
        sc = "#EF4444" if n_crit else ("#D97706" if n_warn else "#22C55E")
        self._summary.setText(msg)
        self._summary.setStyleSheet("color:" + sc + ";font-size:15px;font-weight:700;background:transparent;border:none;")
