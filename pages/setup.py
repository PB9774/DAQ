"""
pages/setup.py — display preferences, data source, mode, and system actions.

Every control writes straight into the persisted Prefs and emits one signal;
the window owns the consequences (restyle, mode switch, restart).
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QMessageBox, QPushButton, QSlider,
    QVBoxLayout, QWidget,
)

from core import backlight
from core.config import APP_NAME, APP_VERSION, SEGMENTS, CELLS_TOTAL, TELEMETRY_PORT
from ui.helpers import card, label, set_text
from ui.theme import DRIVER, ENGINEER, TM
from ui.tokens import FAMILIES

SCALES = (("SM", 0.9), ("MD", 1.0), ("LG", 1.15), ("XL", 1.3))


class SetupPage(QWidget):
    theme_changed = pyqtSignal()
    brightness_changed = pyqtSignal(float)
    mode_changed = pyqtSignal(str)
    restart_requested = pyqtSignal()

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._ip = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self._build_display(), 1)
        row.addWidget(self._build_source(), 1)
        outer.addLayout(row, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        bottom.addWidget(self._build_about(), 1)
        bottom.addWidget(self._build_actions(), 0)
        outer.addLayout(bottom, 0)

    # ── display ────────────────────────────────────────────────────────────
    def _build_display(self):
        frame, column = card(name="display_card", margins=(12, 10, 12, 10), spacing=8)
        column.addWidget(label("DISPLAY PREFERENCES", role="title", weight=800))

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnStretch(1, 1)

        grid.addWidget(label("THEME", role="caption", weight=700), 0, 0)
        self._theme_button = QPushButton()
        self._theme_button.setObjectName("pill")
        self._theme_button.setCursor(Qt.PointingHandCursor)
        self._theme_button.clicked.connect(self._toggle_theme)
        grid.addWidget(self._theme_button, 0, 1)

        grid.addWidget(label("TEXT SIZE", role="caption", weight=700), 1, 0)
        holder = QFrame()
        holder.setObjectName("scale_box")
        sizes = QHBoxLayout(holder)
        sizes.setContentsMargins(4, 4, 4, 4)
        sizes.setSpacing(6)
        self._scale_buttons = []
        for text, value in SCALES:
            button = QPushButton(text)
            button.setObjectName("scale_pill")
            button.setCheckable(True)
            button.setChecked(abs(TM.font_scale - value) < 0.01)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _, v=value: self._set_scale(v))
            self._scale_buttons.append((button, value))
            sizes.addWidget(button)
        grid.addWidget(holder, 1, 1)

        grid.addWidget(label("TYPEFACE", role="caption", weight=700), 2, 0)
        family = QComboBox()
        family.addItems(sorted(FAMILIES))
        family.setCurrentText(TM.font_family if TM.font_family in FAMILIES else "Inter")
        family.currentTextChanged.connect(self._set_family)
        grid.addWidget(family, 2, 1)

        grid.addWidget(label("BRIGHTNESS", role="caption", weight=700), 3, 0)
        self._brightness = QSlider(Qt.Horizontal)
        self._brightness.setRange(35, 100)
        self._brightness.setValue(int(TM.brightness * 100))
        self._brightness.valueChanged.connect(self._set_brightness)
        grid.addWidget(self._brightness, 3, 1)

        column.addLayout(grid)
        self._panel_note = label("", role="caption")
        column.addWidget(self._panel_note)
        column.addStretch()
        self._sync_labels()
        return frame

    def _build_source(self):
        frame, column = card(name="source_card", margins=(12, 10, 12, 10), spacing=8)
        column.addWidget(label("DATA SOURCE", role="title"))

        self._source_state = label("", size="LEAD", weight=700, mono=True)
        column.addWidget(self._source_state)
        column.addWidget(label("Simulation drives synthetic pack telemetry for bench testing.",
                               role="caption", wrap=True))

        self._sim_button = QPushButton()
        self._sim_button.setObjectName("ghost")
        self._sim_button.setCursor(Qt.PointingHandCursor)
        self._sim_button.clicked.connect(self._toggle_simulation)
        column.addWidget(self._sim_button)

        column.addWidget(label("STARTUP MODE", role="title"))
        modes = QHBoxLayout()
        modes.setSpacing(6)
        self._mode_buttons = []
        for text, value in (("DRIVER", DRIVER), ("ENGINEER", ENGINEER)):
            button = QPushButton(text)
            button.setObjectName("pill")
            button.setCheckable(True)
            button.setChecked(TM.mode == value)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _, v=value: self._set_mode(v))
            self._mode_buttons.append((button, value))
            modes.addWidget(button)
        modes.addStretch()
        column.addLayout(modes)
        column.addStretch()
        return frame

    def _build_about(self):
        frame, column = card(margins=(12, 10, 12, 10), spacing=4)
        column.addWidget(label("SYSTEM", role="title"))
        self._about = label("", role="caption", mono=True)
        column.addWidget(self._about)
        column.addStretch()
        return frame

    def _build_actions(self):
        frame, column = card(margins=(12, 10, 12, 10), spacing=8)
        frame.setMinimumWidth(240)
        column.addWidget(label("ACTIONS", role="title"))

        restart = QPushButton("RESTART APP")
        restart.setObjectName("ghost")
        restart.setCursor(Qt.PointingHandCursor)
        restart.clicked.connect(self._confirm_restart)
        column.addWidget(restart)

        driver = QPushButton("GO TO DRIVER VIEW")
        driver.setObjectName("primary")
        driver.setCursor(Qt.PointingHandCursor)
        driver.clicked.connect(lambda: self.mode_changed.emit(DRIVER))
        column.addWidget(driver)
        return frame

    # ── handlers ───────────────────────────────────────────────────────────
    def _toggle_theme(self):
        TM.toggle_theme()
        self.theme_changed.emit()

    def _set_scale(self, value):
        for button, candidate in self._scale_buttons:
            button.setChecked(candidate == value)
        if abs(TM.font_scale - value) > 0.001:
            TM.font_scale = value
            TM.save()
            self.theme_changed.emit()

    def _set_family(self, name):
        if name != TM.font_family:
            TM.font_family = name
            TM.save()
            self.theme_changed.emit()

    def _set_brightness(self, percent):
        TM.brightness = percent / 100.0
        TM.save()
        self.brightness_changed.emit(TM.brightness)
        self._sync_labels()

    def _set_mode(self, mode):
        for button, candidate in self._mode_buttons:
            button.setChecked(candidate == mode)
        if TM.mode != mode:
            TM.mode = mode
            TM.save()
        self.mode_changed.emit(mode)

    def _toggle_simulation(self):
        self._engine.set_simulate(not self._engine.simulate)

    def _confirm_restart(self):
        answer = QMessageBox.question(
            self, "Restart", "Restart the dashboard now?\n"
            "Any active recording is flushed and closed first.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.restart_requested.emit()

    def _sync_labels(self):
        set_text(self._theme_button, "DARK  ·  SWITCH" if TM.is_dark
                 else "LIGHT  ·  SWITCH")
        set_text(self._panel_note,
                 "PANEL BACKLIGHT %d%%" % round(TM.brightness * 100) if backlight.available()
                 else "WINDOW DIMMING ACTIVE")

    # ── per-tick ───────────────────────────────────────────────────────────
    def refresh(self, engine, recorder=None):
        simulating = engine.simulate
        set_text(self._source_state,
                 ("● SIMULATION" if simulating else "○ %s" % engine.source_name.upper())
                 + "   %.0f Hz" % engine.actual_hz)
        set_text(self._sim_button, "STOP SIMULATION" if simulating else "START SIMULATION")

        live = engine.stream.is_active
        if live and self._ip is None:
            self._ip = engine.local_ip()      # one UDP probe, then cached
        elif not live:
            self._ip = None

        minutes, seconds = divmod(int(engine.elapsed), 60)
        set_text(self._about, "\n".join((
            "%s  %s" % (APP_NAME, APP_VERSION),
            "PACK      %d segments  ·  %d cells" % (SEGMENTS, CELLS_TOTAL),
            "LOOP      %.0f Hz measured" % engine.actual_hz,
            "FEED      %s  ·  tcp %s:%d" % ("LIVE" if live else "OFF",
                                            self._ip or "—", TELEMETRY_PORT),
            "UPTIME    %d min %02d s" % (minutes, seconds),
        )))

    def on_theme_changed(self):
        self._sync_labels()
