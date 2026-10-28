"""
ui/chrome.py — the persistent frame around the pages: status strip and nav.
"""

import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QProgressBar, QPushButton, QSizePolicy, QWidget,
)

from ui.helpers import (
    bar_style, label, numeral, rule, set_mono_width, set_ss,
    set_scaled_height, set_text, set_value, soc_status, style_numeral,
)
from ui.theme import Color, TM
from ui.widgets import LogoWidget, StatusPill

NAV_TABS = ("OVERVIEW", "SEGMENTS", "TRENDS", "LOGS", "SETUP")

# The strip has room for a tag, not a sentence.
SOURCE_TAG = {"NO SIGNAL": "NO SIG", "SIMULATED": "SIM"}


class StatusStrip(QFrame):
    """One-line live summary carried by every engineer page.

    Every fixed width is derived from the current type scale, so the row still
    fits 1024 px with HUGE text instead of squeezing its neighbours out.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        set_scaled_height(self, "LEAD", 2.6, 52)
        self._soc_status = None
        self._rec_on = None
        self._source = None

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 12, 0)
        row.setSpacing(9)

        row.addWidget(LogoWidget(height=26, max_width=104))
        row.addWidget(rule(vertical=True, length=26))

        self._clock = numeral("--:--:--", "LEAD", Color.TEXT, Qt.AlignLeft | Qt.AlignVCenter)
        set_mono_width(self._clock, "00:00:00", "LEAD")
        row.addWidget(self._clock)
        row.addWidget(rule(vertical=True, length=26))

        row.addWidget(label("SOC", role="title"))
        self._soc = numeral("--%", "LEAD", Color.SOC)
        set_mono_width(self._soc, "100%", "LEAD", 4)
        row.addWidget(self._soc)
        self._soc_bar = QProgressBar()
        self._soc_bar.setRange(0, 1000)
        self._soc_bar.setTextVisible(False)
        self._soc_bar.setFixedHeight(8)
        self._soc_bar.setMinimumWidth(48)
        self._soc_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row.addWidget(self._soc_bar, 1)
        row.addWidget(rule(vertical=True, length=26))

        self._pill = StatusPill()
        row.addWidget(self._pill)

        self._src = label("NO SIGNAL", role="caption")
        set_mono_width(self._src, "CAN ● SIM", "CAPTION", 8)
        row.addWidget(self._src)
        row.addWidget(rule(vertical=True, length=26))

        self._rec = label("○ IDLE", role="caption")
        set_mono_width(self._rec, "● REC 9999s", "CAPTION", 6)
        row.addWidget(self._rec)

        self._hz = label("-- Hz", role="caption")
        set_mono_width(self._hz, "999 Hz", "CAPTION", 6)
        self._hz.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(self._hz)

    def refresh(self, engine, recorder=None):
        set_text(self._clock, datetime.datetime.now().strftime("%H:%M:%S"))
        set_text(self._soc, "%.0f%%" % engine.soc)
        set_value(self._soc_bar, engine.soc * 10)

        status = soc_status(engine.soc)
        if status != self._soc_status:
            self._soc_status = status
            colour = Color.status(status)
            style_numeral(self._soc, "LEAD", colour)
            set_ss(self._soc_bar, bar_style(colour))

        counts = engine.faults.counts
        if counts["crit"]:
            self._pill.set_state("crit", "%d CRIT" % counts["crit"])
        elif counts["warn"]:
            self._pill.set_state("warn", "%d WARN" % counts["warn"])
        elif counts["info"]:
            self._pill.set_state("info", "%d INFO" % counts["info"])
        else:
            self._pill.set_state("ok", "OK")

        source = engine.source_name
        if source != self._source:
            self._source = source
            state = "ok" if engine.can_ok else ("warn" if engine.simulate else "crit")
            set_text(self._src, ("CAN ● " if engine.can_ok else "CAN ✕ ") + SOURCE_TAG.get(source, source))
            set_ss(self._src, "color:%s;font-size:%dpx;font-weight:700;"
                              "background:transparent;border:none;"
                              % (Color.status(state), TM.size("CAPTION")))

        active = bool(recorder and recorder.is_active)
        set_text(self._rec, "● REC %ds" % recorder.duration_s if active else "○ IDLE")
        if active != self._rec_on:
            self._rec_on = active
            set_ss(self._rec, "color:%s;font-size:%dpx;font-weight:700;"
                              "background:transparent;border:none;"
                              % (Color.crit if active else Color.TEXT_3, TM.size("CAPTION")))
        set_text(self._hz, "%.0f Hz" % engine.actual_hz)

    def restyle(self):
        self._soc_status = self._rec_on = self._source = None
        self._pill.restyle()


class SelectorHUD(QFrame):
    """Clean, high-contrast HUD strip displaying the current dashboard location
    and what action will occur if OK (Spacebar/Enter) is pressed.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("selector_hud")
        set_scaled_height(self, "CAPTION", 2.2, 30)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 2, 12, 2)
        row.setSpacing(8)

        lbl_loc = label("⯈ LOCATION:", role="title")
        lbl_loc.setObjectName("hud_title")
        row.addWidget(lbl_loc)

        self._loc = label("OVERVIEW", role="lead")
        self._loc.setObjectName("hud_loc")
        row.addWidget(self._loc)

        row.addSpacing(4)
        div = label("│", role="caption")
        div.setObjectName("hud_div")
        row.addWidget(div)
        row.addSpacing(4)

        lbl_action = label("PRESS OK:", role="title")
        lbl_action.setObjectName("hud_action_title")
        row.addWidget(lbl_action)

        self._action = label("Navigate with arrow keys", role="lead")
        self._action.setObjectName("hud_action")
        row.addWidget(self._action)

        row.addStretch()

        self._hint = label("5-KEY NAV: [↑] [↓] [←] [→]  [OK / Space]", role="caption", mono=True)
        self._hint.setObjectName("hud_hint")
        row.addWidget(self._hint)

    def update_info(self, location, action):
        set_text(self._loc, location)
        set_text(self._action, action)


class NavBar(QWidget):
    page_changed = pyqtSignal(int)
    driver_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("navbar")
        set_scaled_height(self, "CAPTION", 4.0, 56)
        self._buttons = []

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 0, 6, 0)
        row.setSpacing(4)

        driver = QPushButton("◀  DRIVER")
        driver.setObjectName("mode")
        driver.setCursor(Qt.PointingHandCursor)
        driver.clicked.connect(self.driver_requested.emit)
        self.driver_button = driver
        row.addWidget(driver)
        row.addSpacing(6)

        for index, title in enumerate(NAV_TABS):
            button = QPushButton(title)
            button.setObjectName("nav")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _, i=index: self.select(i))
            self._buttons.append(button)
            row.addWidget(button, 1)
        self._buttons[0].setChecked(True)

    def select(self, index):
        self.select_silently(index)
        self.page_changed.emit(index)

    def select_silently(self, index):
        """Sync the tab highlight without re-emitting page_changed."""
        for position, button in enumerate(self._buttons):
            button.setChecked(position == index)

    @property
    def all_buttons(self):
        driver_btn = getattr(self, "driver_button", None)
        return ([driver_btn] if driver_btn else []) + self._buttons
