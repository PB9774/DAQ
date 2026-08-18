"""
pages/analytics.py — 5 live chart tabs (V+A, SOC, Power, Tmax, ΔV).
Split out of the old monolithic pages.py.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QSizePolicy, QButtonGroup,
)
from PyQt5.QtGui import QColor, QFont

from theme import TM, Font
from ev import DataEngine
from widgets import TelemetryStrip

from pages.common import _lbl

try:
    import numpy as np
    import pyqtgraph as pg
    _PG = True
except ImportError:
    _PG = False


class AnalyticsPage(QWidget):
    _TABS = [
        ("V+A", "VOLTAGE  +  CURRENT", "#58A6FF"),
        ("SOC", "STATE OF CHARGE", "#3FB950"),
        ("POWER", "BATTERY POWER (kW)", "#F97316"),
        ("TMAX", "MAX CELL TEMPERATURE", "#F0883E"),
        ("DV", "CELL VOLTAGE IMBALANCE", "#A78BFA"),
    ]
    _RANGES = [("1m", 60), ("5m", 300), ("10m", 600), ("20m", 1200), ("30m", 1800)]

    def __init__(self, engine: DataEngine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._window = 300
        self._cur = 0
        self._strip = TelemetryStrip()
        self._pw_list = []
        self._build()

    def _make_pw(self, bg, fg):
        pw = pg.PlotWidget()
        pw.setBackground(QColor(bg))
        pw.showGrid(x=True, y=True, alpha=0.20)
        pw.setMenuEnabled(False)
        pw.setMouseEnabled(x=False, y=True)
        pw.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tf = QFont("Inter", 11)
        for ax in ("left", "bottom"):
            pw.getAxis(ax).setTextPen(pg.mkPen(fg))
            pw.getAxis(ax).setPen(pg.mkPen(fg))
            pw.getAxis(ax).setStyle(tickFont=tf)
        return pw

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 5, 6, 5)
        root.setSpacing(4)
        root.addWidget(self._strip)

        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(0, 0, 0, 0)
        tab_row.setSpacing(6)
        self._tab_grp = QButtonGroup(self)
        for i, (short, _, _) in enumerate(self._TABS):
            b = QPushButton(short)
            b.setObjectName("btn_pill")
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.setFixedHeight(32)
            b.setFont(QFont("Inter", 12, QFont.Bold))
            b.clicked.connect(lambda _, idx=i: self._switch(idx))
            self._tab_grp.addButton(b, i)
            tab_row.addWidget(b)
        tab_row.addStretch()

        self._rate_lbl = QLabel("● 10 Hz")
        self._rate_lbl.setStyleSheet("color:#22C55E;font-size:14px;font-weight:700;background:transparent;border:none;")
        tab_row.addWidget(self._rate_lbl)
        root.addLayout(tab_row)

        self._chart_title = QLabel(self._TABS[0][1])
        self._chart_title.setAlignment(Qt.AlignCenter)
        self._chart_title.setFont(QFont("Inter", Font.SIZE_LG, QFont.Bold))
        root.addWidget(self._chart_title)

        if _PG:
            P = TM.palette
            bg = P["GRAPH_BG"]
            fg = P["TEXT_SEC"]

            # Chart 0: V+A dual axis
            self._dpw = self._make_pw(bg, fg)
            la = self._dpw.getAxis("left")
            la.setLabel("Pack V", "V", color="#58A6FF")
            la.setTextPen(pg.mkPen("#58A6FF"))
            la.setPen(pg.mkPen("#58A6FF"))
            la.setStyle(tickFont=QFont("Inter", 11))
            self._vb2 = pg.ViewBox()
            self._dpw.scene().addItem(self._vb2)
            ra = pg.AxisItem("right")
            ra.setLabel("Current", "A", color="#F472B6")
            ra.setTextPen(pg.mkPen("#F472B6"))
            ra.setPen(pg.mkPen("#F472B6"))
            ra.setStyle(tickFont=QFont("Inter", 11))
            self._dpw.plotItem.layout.addItem(ra, 2, 3)
            ra.linkToView(self._vb2)
            self._vb2.setXLink(self._dpw.plotItem)
            self._vline = self._dpw.plot([], [], pen=pg.mkPen("#58A6FF", width=3), antialias=True)
            self._iline = pg.PlotDataItem([], [], pen=pg.mkPen("#F472B6", width=2), antialias=True)
            self._vb2.addItem(self._iline)
            self._dpw.plotItem.vb.sigResized.connect(lambda: self._vb2.setGeometry(self._dpw.plotItem.vb.sceneBoundingRect()))
            root.addWidget(self._dpw, 1)

            # Chart 1: SOC
            self._spw = self._make_pw(bg, fg)
            self._spw.getAxis("left").setLabel("SOC", "%", color="#3FB950")
            self._spw.getAxis("left").setTextPen(pg.mkPen("#3FB950"))
            self._spw.getAxis("left").setStyle(tickFont=QFont("Inter", 11))
            self._sline = self._spw.plot([], [], pen=pg.mkPen("#3FB950", width=3), antialias=True)
            root.addWidget(self._spw, 1)

            # Chart 2: Power
            self._ppw = self._make_pw(bg, fg)
            self._ppw.getAxis("left").setLabel("Power", "kW", color="#F97316")
            self._ppw.getAxis("left").setTextPen(pg.mkPen("#F97316"))
            self._ppw.getAxis("left").setStyle(tickFont=QFont("Inter", 11))
            self._pline = self._ppw.plot([], [], pen=pg.mkPen("#F97316", width=3), antialias=True)
            root.addWidget(self._ppw, 1)

            # Chart 3: Tmax
            self._tpw = self._make_pw(bg, fg)
            self._tpw.getAxis("left").setLabel("Tmax", "°C", color="#F0883E")
            self._tpw.getAxis("left").setTextPen(pg.mkPen("#F0883E"))
            self._tpw.getAxis("left").setStyle(tickFont=QFont("Inter", 11))
            self._tline = self._tpw.plot([], [], pen=pg.mkPen("#F0883E", width=3), antialias=True)
            root.addWidget(self._tpw, 1)

            # Chart 4: ΔV
            self._dvpw = self._make_pw(bg, fg)
            self._dvpw.getAxis("left").setLabel("ΔV", "V", color="#A78BFA")
            self._dvpw.getAxis("left").setTextPen(pg.mkPen("#A78BFA"))
            self._dvpw.getAxis("left").setStyle(tickFont=QFont("Inter", 11))
            self._dvline = self._dvpw.plot([], [], pen=pg.mkPen("#A78BFA", width=3), antialias=True)
            root.addWidget(self._dvpw, 1)

            self._pw_list = [self._dpw, self._spw, self._ppw, self._tpw, self._dvpw]
        else:
            no = QLabel("pip install pyqtgraph numpy")
            no.setAlignment(Qt.AlignCenter)
            no.setStyleSheet("color:#D97706;font-size:14px;")
            root.addWidget(no, 1)

        root.addWidget(self._range_bar())
        self._switch(0)

    def _switch(self, idx):
        self._cur = idx
        _, title, col = self._TABS[idx]
        self._chart_title.setText(title)
        self._chart_title.setStyleSheet("color:" + col + ";font-size:" + str(Font.SIZE_LG) + "px;font-weight:700;background:transparent;border:none;letter-spacing:2px;")
        if _PG:
            for i, pw in enumerate(self._pw_list):
                pw.setVisible(i == idx)

    def _range_bar(self):
        f = QFrame()
        f.setObjectName("card")
        f.setFixedHeight(40)
        lay = QHBoxLayout(f)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(6)
        lay.addWidget(_lbl("WINDOW", "title"))
        grp = QButtonGroup(self)
        for label, secs in self._RANGES:
            b = QPushButton(label)
            b.setObjectName("btn_pill")
            b.setCheckable(True)
            b.setFixedHeight(28)
            b.setChecked(secs == 300)
            b.clicked.connect(lambda _, s=secs: setattr(self, "_window", s))
            grp.addButton(b)
            lay.addWidget(b)
        lay.addStretch()
        self._el = QLabel("t=0s")
        self._el.setProperty("role", "dim")
        lay.addWidget(self._el)
        return f

    def update_graph_theme(self):
        if not _PG or not self._pw_list:
            return
        P = TM.palette
        bg = QColor(P["GRAPH_BG"])
        fg = P["TEXT_SEC"]
        for pw in self._pw_list:
            pw.setBackground(bg)
            for ax in ("left", "bottom"):
                pw.getAxis(ax).setTextPen(pg.mkPen(fg))
                pw.getAxis(ax).setPen(pg.mkPen(fg))

    def refresh(self, engine, logger=None):
        self._strip.refresh(engine, logger)
        self._rate_lbl.setText("%.0f Hz" % engine.actual_hz)
        if not _PG:
            return

        times = list(engine.time_h)
        if len(times) < 2:
            return
        self._el.setText("t=%.0fs" % times[-1])

        t = np.array(times)
        tmax_t = t[-1]
        tmin_t = tmax_t - self._window
        mask = t >= tmin_t
        tv = t[mask]
        if len(tv) < 2:
            return

        def _auto(line, hist, pw):
            v = np.array(list(hist))[mask]
            line.setData(tv, v)
            pw.setXRange(tmin_t, tmax_t, padding=0)
            pad = (v.max() - v.min()) * .1 or .5
            pw.setYRange(v.min() - pad, v.max() + pad, padding=0)

        vols = np.array(list(engine.voltage_h))[mask]
        curs = np.array(list(engine.current_h))[mask]
        self._vline.setData(tv, vols)
        self._iline.setData(tv, curs)
        self._dpw.setXRange(tmin_t, tmax_t, padding=0)
        if len(vols):
            p = (vols.max() - vols.min()) * .1 or 1
            self._dpw.setYRange(vols.min() - p, vols.max() + p, padding=0)
        if len(curs):
            p = (curs.max() - curs.min()) * .1 or 5
            self._vb2.setYRange(curs.min() - p, curs.max() + p, padding=0)
        self._vb2.setGeometry(self._dpw.plotItem.vb.sceneBoundingRect())

        _auto(self._sline, engine.soc_h, self._spw)
        _auto(self._pline, engine.power_h, self._ppw)
        _auto(self._tline, engine.tmax_h, self._tpw)
        _auto(self._dvline, engine.dv_h, self._dvpw)
