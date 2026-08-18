"""
pages/dashboard.py — main at-a-glance dashboard: speed, SOC, pack V/I,
per-segment bars, fault panel. Split out of the old monolithic pages.py.
"""

import datetime

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QProgressBar, QPushButton, QSizePolicy

from theme import TM, Color, Font, MONO
from ev import DataEngine, Logger
from widgets import LogoWidget, SevenSegDisplay

from pages.common import _lbl, _bar_ss, _P, _health_ss, _FaultPanel


class DashboardPage(QWidget):
    def __init__(self, save_cb, logger: Logger, parent=None):
        super().__init__(parent)
        self._save_cb = save_cb
        self._logger = logger
        self._seg_rows = []
        self._blink_state = True

        self._blink_t = QTimer(self)
        self._blink_t.setInterval(600)
        self._blink_t.timeout.connect(self._blink)

        self._build()

        clock_timer = QTimer(self, timeout=self._clk, interval=1000)
        clock_timer.start()
        self._clk()

    # ── layout construction ──────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 5, 6, 5)
        root.setSpacing(5)
        root.addWidget(self._header())

        body = QHBoxLayout()
        body.setSpacing(6)
        body.setContentsMargins(0, 0, 0, 0)
        body.addWidget(self._left(), 24)
        body.addWidget(self._centre(), 50)
        body.addWidget(self._right(), 26)
        root.addLayout(body, 1)

    def _header(self):
        f = QFrame()
        f.setObjectName("card_lit")
        f.setFixedHeight(48)
        lay = QHBoxLayout(f)
        lay.setContentsMargins(10, 0, 12, 0)
        lay.setSpacing(10)

        self.logo_widget = LogoWidget(height=32)
        lay.addWidget(self.logo_widget)
        lay.addWidget(self._vdiv())

        self._clk_lbl = QLabel("--:--:--")
        lay.addWidget(self._clk_lbl)
        lay.addStretch()

        self._can_lbl = QLabel("CAN ✗  NO SIGNAL")
        self._can_lbl.setStyleSheet("color:#EF4444;font-size:14px;font-weight:700;background:transparent;border:none;")
        lay.addWidget(self._can_lbl)
        lay.addWidget(self._vdiv())

        self._sensor_lbl = QLabel("SENSORS OK")
        self._sensor_lbl.setStyleSheet("color:#22C55E;font-size:14px;font-weight:600;background:transparent;border:none;")
        lay.addWidget(self._sensor_lbl)
        lay.addWidget(self._vdiv())

        self._rec_lbl = QLabel("○ IDLE")
        self._rec_lbl.setStyleSheet("color:#404A5C;font-size:14px;font-weight:700;background:transparent;border:none;")
        lay.addWidget(self._rec_lbl)
        lay.addWidget(self._vdiv())

        self._hz_lbl = QLabel("-- Hz")
        self._hz_lbl.setStyleSheet("color:#8A97B0;font-size:14px;font-weight:600;background:transparent;border:none;")
        lay.addWidget(self._hz_lbl)
        return f

    def _vdiv(self):
        d = QFrame()
        d.setFixedSize(1, 26)
        d.setStyleSheet("background:" + Color.BORDER + ";")
        return d

    def _clk(self):
        self._clk_lbl.setText(datetime.datetime.now().strftime("%H:%M:%S"))
        self._clk_lbl.setStyleSheet(
            "color:" + _P("TEXT_PRI") + ";font-family:" + MONO + ";"
            "font-size:" + str(Font.SIZE_LG) + "px;font-weight:700;background:transparent;border:none;"
        )
        if hasattr(self, "logo_widget"):
            self.logo_widget.update()

    def _tile(self, tag, attr, col="#3B82F6", h=54):
        f = QFrame()
        f.setObjectName("card")
        f.setFixedHeight(h)
        lay = QHBoxLayout(f)
        lay.setContentsMargins(10, 0, 10, 0)
        t = QLabel(tag.upper())
        t.setProperty("role", "title")
        t.setFixedWidth(90)
        v = QLabel("---")
        v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        v.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(t)
        lay.addWidget(v)
        setattr(self, "_lbl_" + attr, v)
        return f

    def _dv_tile(self):
        f = QFrame()
        f.setObjectName("card")
        f.setFixedHeight(62)
        lay = QVBoxLayout(f)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(1)

        top = QHBoxLayout()
        top.addWidget(_lbl("DELTA V", "title", "font-size:" + str(Font.SIZE_SM) + "px;"))
        self._lbl_dv = QLabel("---")
        self._lbl_dv.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top.addWidget(self._lbl_dv)
        lay.addLayout(top)

        self._dv_detail = QLabel("MAX: ---   MIN: ---")
        self._dv_detail.setProperty("role", "dim")
        lay.addWidget(self._dv_detail)
        return f

    def _seg_bars(self):
        f = QFrame()
        f.setObjectName("card")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(8, 5, 8, 5)
        lay.setSpacing(3)
        lay.addWidget(_lbl("SEGMENTS", "title"))

        for i in range(DataEngine.NUM_MODULES):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(3)

            badge = QLabel("S%d" % (i + 1))
            badge.setFixedSize(22, 18)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet("background:" + _P("ACCENT") + ";color:#fff;border-radius:2px;font-size:16px;font-weight:700;")

            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setTextVisible(False)
            bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            bar.setFixedHeight(7)

            lv = QLabel("-.--")
            lv.setFixedWidth(38)
            lv.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            lt = QLabel("--C")
            lt.setFixedWidth(34)
            lt.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            hbadge = QLabel("OK")
            hbadge.setFixedSize(32, 16)
            hbadge.setAlignment(Qt.AlignCenter)
            hbadge.setStyleSheet(_health_ss("ok"))

            for w in (badge, bar, lv, lt, hbadge):
                row.addWidget(w)
            self._seg_rows.append((badge, bar, lv, lt, hbadge))
            lay.addLayout(row)

        lay.addStretch()
        return f

    def _left(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(self._tile("PACK V", "pv"))
        lay.addWidget(self._dv_tile())
        lay.addWidget(self._tile("CURRENT", "cur", "#F97316"))
        lay.addWidget(self._tile("T-MAX", "tmax", "#EF4444"))
        lay.addWidget(self._seg_bars(), 1)
        return w

    def _centre(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        sf = QFrame()
        sf.setObjectName("card_lit")
        sl = QVBoxLayout(sf)
        sl.setContentsMargins(6, 4, 6, 4)
        sl.setSpacing(2)
        tag = _lbl("SPEED", "title", "font-size:10px;letter-spacing:3px;font-weight:600;")
        tag.setAlignment(Qt.AlignCenter)
        self._gauge = SevenSegDisplay()
        sl.addWidget(tag)
        sl.addWidget(self._gauge, 1)
        lay.addWidget(sf, 4)

        sf2 = QFrame()
        sf2.setObjectName("card")
        sl2 = QVBoxLayout(sf2)
        sl2.setContentsMargins(10, 5, 10, 5)
        sl2.setSpacing(3)
        top2 = QHBoxLayout()
        top2.addWidget(_lbl("SOC", "title", "font-size:20px;letter-spacing:1px;font-weight:600;"))
        top2.addStretch()
        self._lbl_soc = QLabel("--%")
        self._lbl_soc.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top2.addWidget(self._lbl_soc)
        self._soc_bar = QProgressBar()
        self._soc_bar.setRange(0, 1000)
        self._soc_bar.setTextVisible(False)
        self._soc_bar.setFixedHeight(12)
        sl2.addLayout(top2)
        sl2.addWidget(self._soc_bar)
        lay.addWidget(sf2, 2)
        return w

    def _right(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self._fault_panel = _FaultPanel()
        lay.addWidget(self._fault_panel, 1)

        tm_f = QFrame()
        tm_f.setObjectName("card")
        tm_f.setFixedHeight(54)
        tl = QHBoxLayout(tm_f)
        tl.setContentsMargins(10, 0, 10, 0)
        tl.setSpacing(10)
        self._lbl_tmax2 = QLabel("Tmax: --°C")
        self._lbl_tmax2.setStyleSheet("color:#EF4444;font-size:14px;font-family:" + MONO + ";font-weight:700;background:transparent;border:none;")
        self._lbl_tmin2 = QLabel("Tmin: --°C")
        self._lbl_tmin2.setStyleSheet("color:#22C55E;font-size:14px;font-family:" + MONO + ";font-weight:700;background:transparent;border:none;")
        tl.addWidget(self._lbl_tmax2)
        tl.addStretch()
        tl.addWidget(self._lbl_tmin2)
        lay.addWidget(tm_f)

        btn = QPushButton("💾  Save Snapshot")
        btn.setObjectName("btn_primary")
        btn.setFixedHeight(44)
        btn.clicked.connect(self._save_cb)
        lay.addWidget(btn)
        return w

    def _blink(self):
        self._blink_state = not self._blink_state

    # ── data refresh ──────────────────────────────────────────────────────
    def refresh(self, engine, logger=None):
        P = TM.palette

        self._hz_lbl.setText("%.0f Hz" % engine.actual_hz)

        cc = "#22C55E" if engine.can_ok else "#EF4444"
        self._can_lbl.setText(("CAN ●  " if engine.can_ok else "CAN ✗  ") + engine.can_status_text)
        self._can_lbl.setStyleSheet("color:" + cc + ";font-size:14px;font-weight:700;background:transparent;border:none;")

        sc_lbl = "#22C55E" if engine.sensor_ok else "#EF4444"
        self._sensor_lbl.setText("SENSORS OK" if engine.sensor_ok else "SENSOR ERR")
        self._sensor_lbl.setStyleSheet("color:" + sc_lbl + ";font-size:14px;font-weight:600;background:transparent;border:none;")

        if logger and logger.is_active:
            self._rec_lbl.setText("● REC  %ds  %.1fKB" % (logger.duration_s, logger.file_size_kb))
            rc = "#EF4444" if self._blink_state else "#FF8888"
            self._rec_lbl.setStyleSheet("color:" + rc + ";font-size:14px;font-weight:700;background:transparent;border:none;")
            if not self._blink_t.isActive():
                self._blink_t.start()
        else:
            self._rec_lbl.setText("○ IDLE")
            self._rec_lbl.setStyleSheet("color:#404A5C;font-size:14px;font-weight:700;background:transparent;border:none;")
            self._blink_t.stop()
            self._blink_state = True

        self._lbl_pv.setText("%.1f V" % engine.pack_voltage)
        self._lbl_pv.setStyleSheet("color:" + P["ACCENT"] + ";font-size:" + str(Font.SIZE_XL) + "px;font-family:" + MONO + ";font-weight:800;background:transparent;border:none;")

        dv = engine.delta_v
        dc = "#22C55E" if dv < .03 else ("#F59E0B" if dv < .06 else "#EF4444")
        self._lbl_dv.setText("%.3f V" % dv)
        self._lbl_dv.setStyleSheet("color:" + dc + ";font-size:" + str(Font.SIZE_XL) + "px;font-family:" + MONO + ";font-weight:800;background:transparent;border:none;")

        max_loc, max_v, min_loc, min_v = engine.cell_global_extremes()
        self._dv_detail.setText("▲ %s %.3fV   ▼ %s %.3fV" % (max_loc, max_v, min_loc, min_v))
        self._dv_detail.setStyleSheet("color:" + _P("TEXT_DIM") + ";font-family:" + MONO + ";font-size:" + str(Font.SIZE_XS) + "px;background:transparent;border:none;")

        self._lbl_cur.setText("%.0f A" % engine.current)
        self._lbl_cur.setStyleSheet("color:#F97316;font-size:" + str(Font.SIZE_XL) + "px;font-family:" + MONO + ";font-weight:800;background:transparent;border:none;")

        at = engine.tmax
        tl_ = engine.tmax_location
        tc = "#EF4444" if at >= 50 else ("#F59E0B" if at >= 40 else "#22C55E")
        self._lbl_tmax.setText("%.1f C  %s" % (at, tl_))
        self._lbl_tmax.setStyleSheet("color:" + tc + ";font-size:" + str(Font.SIZE_LG) + "px;font-family:" + MONO + ";font-weight:800;background:transparent;border:none;")

        self._gauge.set_speed(engine.speed)

        soc = engine.soc
        sc = P["SOC_COL"] if soc > 40 else ("#F59E0B" if soc > 20 else "#EF4444")
        self._lbl_soc.setText("%.0f%%" % soc)
        self._lbl_soc.setStyleSheet("color:" + sc + ";font-family:" + MONO + ";font-size:30px;font-weight:900;background:transparent;border:none;")
        self._soc_bar.setValue(int(soc * 10))
        self._soc_bar.setStyleSheet(_bar_ss(sc))

        self._lbl_tmax2.setText("Tmax: %.0f C" % engine.tmax)
        self._lbl_tmin2.setText("Tmin: %.0f C" % engine.tmin)

        for i, (badge, bar, lv, lt, hbadge) in enumerate(self._seg_rows):
            v = engine.mod_avg_v(i)
            t = engine.mod_avg_t(i)
            health = engine.mod_health(i)
            frac = max(0., min(1., (v - 3.2) / (4.1 - 3.2)))
            bar.setValue(int(frac * 1000))
            fc = "#F59E0B" if v < 3.40 else ("#EF4444" if v > 3.90 else "#22C55E")
            bar.setStyleSheet(_bar_ss(fc))
            lv.setText("%.2f" % v)
            lv.setStyleSheet("color:" + fc + ";font-size:" + str(Font.SIZE_XS) + "px;font-family:" + MONO + ";font-weight:600;background:transparent;border:none;")
            lt.setText("%.0fC" % t)
            lt.setStyleSheet("color:" + _P("TEXT_DIM") + ";font-size:" + str(Font.SIZE_XS) + "px;background:transparent;border:none;")
            hbadge.setStyleSheet(_health_ss(health))
            hbadge.setText(health.upper())
            badge.setStyleSheet("background:" + _P("ACCENT") + ";color:#fff;border-radius:2px;font-size:13px;font-weight:700;")

        self._fault_panel.refresh(engine.active_faults)
