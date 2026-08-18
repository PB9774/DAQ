"""
pages/settings.py — theme, typography, display, data source, and about.
Split out of the old monolithic pages.py.

v20 additions:
  - "Data Source" card: explicit Idle / Simulated toggle (DataEngine no
    longer generates random data unless this is switched on). Choosing
    Simulated keeps the CAN status red — it's clearly labeled "SIMULATED"
    rather than a real connection, so nobody in the pits mistakes test
    data for a live pack.
  - "System" card: manual "Restart App Now" button, plus a note about the
    systemd auto-restart service installed by install.sh.
  - Version bumped to v20 and the mismatched "v1.9" string is fixed.
"""

import os
import subprocess

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QScrollArea, QButtonGroup, QSlider, QComboBox, QMessageBox,
)

from theme import TM
from ev import DataEngine

from pages.common import _lbl, _P

APP_VERSION = "v20"


class SettingsPage(QWidget):
    theme_changed = pyqtSignal()
    restart_requested = pyqtSignal()

    def __init__(self, engine: DataEngine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._build()

    # ── small builders ──────────────────────────────────────────────────
    def _card(self, title):
        f = QFrame()
        f.setObjectName("card_set")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(12, 9, 12, 11)
        lay.setSpacing(6)
        t = QLabel(title.upper())
        t.setStyleSheet("font-size:10px;font-weight:700;letter-spacing:2px;color:" + _P("TEXT_DIM") + ";background:transparent;border:none;")
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:" + _P("BORDER") + ";")
        lay.addWidget(t)
        lay.addWidget(sep)
        return f, lay

    def _pill_grp(self, opts, cur, cb):
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(5)
        g = QButtonGroup(self)
        for val, label in opts:
            b = QPushButton(label)
            b.setObjectName("btn_pill")
            b.setCheckable(True)
            b.setChecked(val == cur)
            b.setFixedHeight(30)
            b.clicked.connect(lambda _, v=val: cb(v))
            g.addButton(b)
            l.addWidget(b)
        l.addStretch()
        return w

    def _slider(self, lo, hi, val, cb):
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(8)
        lbl = QLabel("%d%%" % int(val * 100))
        lbl.setFixedWidth(42)
        lbl.setStyleSheet("font-weight:600;font-size:14px;background:transparent;border:none;")
        sl = QSlider(Qt.Horizontal)
        sl.setRange(int(lo * 100), int(hi * 100))
        sl.setValue(int(val * 100))
        sl.setFixedWidth(180)

        def _u(v, l=lbl):
            l.setText("%d%%" % v)
            cb(v / 100)

        sl.valueChanged.connect(_u)
        l.addWidget(lbl)
        l.addWidget(sl)
        return w

    # ── layout ───────────────────────────────────────────────────────────
    def _build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cont = QWidget()
        root = QVBoxLayout(cont)
        root.setContentsMargins(14, 9, 14, 11)
        root.setSpacing(9)
        root.addWidget(_lbl("Settings", "", "font-size:20px;font-weight:700;"))

        # -- Theme --
        c0, lay0 = self._card("Theme")
        self._tog = QPushButton()
        self._tog.setObjectName("btn_toggle")
        self._tog.setFixedHeight(42)
        self._tog.setMinimumWidth(200)
        self._update_tog()
        self._tog.clicked.connect(self._do_toggle)
        r = QHBoxLayout()
        r.setContentsMargins(0, 3, 0, 3)
        r.addWidget(self._tog)
        r.addStretch()
        lay0.addLayout(r)
        root.addWidget(c0)

        # -- Typography --
        c2, lay2 = self._card("Typography")
        r2 = QHBoxLayout()
        r2.setSpacing(12)
        r2.addWidget(_lbl("Font size", "", "font-size:15px;background:transparent;border:none;"), 1)
        r2.addWidget(self._pill_grp([(0.85, "S"), (1.0, "M"), (1.15, "L")], TM.font_scale, self._set_fs))
        lay2.addLayout(r2)
        r3 = QHBoxLayout()
        r3.setSpacing(12)
        r3.addWidget(_lbl("Font style", "", "font-size:15px;background:transparent;border:none;"), 1)
        fc = QComboBox()
        fc.addItems(["Inter", "Roboto", "Ubuntu", "Mono"])
        fc.setCurrentText(TM.font_family)
        fc.setFixedHeight(32)
        fc.currentTextChanged.connect(self._set_ff)
        r3.addWidget(fc)
        lay2.addLayout(r3)
        root.addWidget(c2)

        # -- Display --
        c3, lay3 = self._card("Display")
        r4 = QHBoxLayout()
        r4.setSpacing(12)
        r4.addWidget(_lbl("Brightness", "", "font-size:15px;background:transparent;border:none;"), 1)
        r4.addWidget(self._slider(0.3, 1.0, TM.brightness, self._set_bright))
        lay3.addLayout(r4)
        r5 = QHBoxLayout()
        r5.setSpacing(12)
        r5.addWidget(_lbl("Contrast", "", "font-size:15px;background:transparent;border:none;"), 1)
        r5.addWidget(self._slider(0.5, 2.0, TM.contrast, lambda v: (setattr(TM, "contrast", v), TM.save(), self.theme_changed.emit())))
        lay3.addLayout(r5)
        root.addWidget(c3)

        # -- Data Source (v20) --
        c5, lay5 = self._card("Data Source")
        self._data_status = QLabel("")
        self._data_status.setStyleSheet("font-size:14px;font-weight:600;background:transparent;border:none;")
        lay5.addWidget(self._data_status)

        r6 = QHBoxLayout()
        r6.setSpacing(12)
        r6.addWidget(_lbl("Mode", "", "font-size:15px;background:transparent;border:none;"), 1)
        self._sim_group = self._pill_grp(
            [(False, "Idle / No Signal"), (True, "Simulated Data")],
            self._engine.simulate,
            self._set_simulate,
        )
        r6.addWidget(self._sim_group)
        lay5.addLayout(r6)

        warn = _lbl(
            "Simulated data is for UI testing only. CAN status stays red in both "
            "modes until real hardware is wired in — the label just tells you why.",
            "dim", "font-size:12px;"
        )
        warn.setWordWrap(True)
        lay5.addWidget(warn)
        root.addWidget(c5)
        self._update_data_status()

        # -- System (v20) --
        c6, lay6 = self._card("System")
        restart_row = QHBoxLayout()
        restart_row.setSpacing(12)
        restart_row.addWidget(_lbl(
            "Manually restart the dashboard app (does not reboot the Pi).",
            "", "font-size:14px;background:transparent;border:none;"
        ), 1)
        restart_btn = QPushButton("⟲  Restart App Now")
        restart_btn.setObjectName("btn_pill")
        restart_btn.setFixedHeight(34)
        restart_btn.clicked.connect(self._confirm_restart)
        restart_row.addWidget(restart_btn)
        lay6.addLayout(restart_row)

        auto_note = _lbl(
            "Crash auto-restart is handled by the accelerons-bms systemd service "
            "(set up by install.sh) — if the app crashes on the car's Pi, systemd "
            "brings it back automatically. This button is for manual restarts only.",
            "dim", "font-size:12px;"
        )
        auto_note.setWordWrap(True)
        lay6.addWidget(auto_note)
        root.addWidget(c6)

        # -- About --
        c4, lay4 = self._card("About")
        for k, v in [
            ("App", "Accelerons BMS Monitor"),
            ("Version", APP_VERSION),
            ("Team", "Accelerons Electric Racing"),
            ("Dept", "Electrical and Electronics Dept."),
            ("Institution", "SAE NIT KKR"),
        ]:
            rr = QHBoxLayout()
            rr.setContentsMargins(0, 1, 0, 1)
            rr.setSpacing(12)
            lk = QLabel(k)
            lk.setProperty("role", "dim")
            lk.setFixedWidth(90)
            lv = QLabel(v)
            lv.setStyleSheet("font-size:15px;font-weight:500;background:transparent;border:none;")
            rr.addWidget(lk)
            rr.addWidget(lv, 1)
            lay4.addLayout(rr)
        root.addWidget(c4)
        root.addStretch()

        scroll.setWidget(cont)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── theme/typography/display handlers ───────────────────────────────
    def _update_tog(self):
        self._tog.setText("☀️  Switch to Light Mode" if TM.is_dark() else "🌙  Switch to Dark Mode")

    def _do_toggle(self):
        TM.toggle()
        self._update_tog()
        self.theme_changed.emit()

    def _set_fs(self, v):
        TM.font_scale = v
        TM.save()
        self.theme_changed.emit()

    def _set_ff(self, v):
        TM.font_family = v
        TM.save()
        self.theme_changed.emit()

    def _set_bright(self, v):
        TM.brightness = v
        TM.save()
        self.theme_changed.emit()
        _rpi_set_brightness(v)

    # ── data source handlers (v20) ──────────────────────────────────────
    def _set_simulate(self, on: bool):
        self._engine.set_simulate(on)
        self._update_data_status()

    def _update_data_status(self):
        if self._engine.simulate:
            self._data_status.setText("🟠  SIMULATED — generating test data, not a real pack")
            self._data_status.setStyleSheet("color:#D97706;font-size:14px;font-weight:700;background:transparent;border:none;")
        else:
            self._data_status.setText("🔴  NO SIGNAL — no real CAN connection, no data")
            self._data_status.setStyleSheet("color:#EF4444;font-size:14px;font-weight:700;background:transparent;border:none;")

    # ── restart handler (v20) ───────────────────────────────────────────
    def _confirm_restart(self):
        reply = QMessageBox.question(
            self, "Restart App",
            "Restart the dashboard now? Any active recording will be stopped and flushed to disk first.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.restart_requested.emit()

    def refresh(self, engine=None, logger=None):
        # Keeps the Data Source status in sync even if something else
        # (future real-CAN auto-fallback, etc.) changes engine.simulate.
        self._update_data_status()


def _rpi_set_brightness(frac: float):
    """
    Write backlight brightness to RPi sysfs.
    Runs install.sh first to set up the udev rule so no sudo is needed at runtime.
    Silently does nothing on non-RPi systems.
    """
    val = max(20, min(255, int(frac * 255)))
    candidates = [
        "/sys/class/backlight/rpi_backlight/brightness",
        "/sys/class/backlight/10-0045/brightness",
        "/sys/class/backlight/backlight/brightness",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "w") as f:
                    f.write(str(val) + "\n")
                return
            except PermissionError:
                # udev rule not yet active — fall back to sudo (one-time cost)
                try:
                    subprocess.run(
                        ["sudo", "tee", path],
                        input=str(val).encode(),
                        capture_output=True, timeout=2
                    )
                except Exception:
                    pass
            return
