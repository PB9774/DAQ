"""
ui/faultpanel.py — the active-fault list.

Rebuilt only when FaultTracker.revision moves, and even then the rows are a
fixed pool that gets re-labelled rather than re-created.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout

from ui.helpers import (
    badge_style, label, set_mono_width, set_scaled_height, set_ss, set_text,
)
from ui.theme import Color


_ROWS = 8


class _FaultRow(QFrame):
    """Severity, what happened, where. The fault code adds nothing a reader
    of the message does not already know, and the panel is only ~320 px."""

    def __init__(self, parent=None):
        super().__init__(parent)
        set_scaled_height(self, "SMALL", 1.9, 28)
        self._sev = None

        row = QHBoxLayout(self)
        row.setContentsMargins(7, 0, 8, 0)
        row.setSpacing(7)

        self._badge = label("", align=Qt.AlignCenter)
        set_mono_width(self._badge, "WARN", "CAPTION", 26)
        self._message = label("", size="SMALL", weight=700, mono=True)
        self._message.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._where = label("", role="caption", mono=True, align=Qt.AlignRight | Qt.AlignVCenter)
        set_mono_width(self._where, "S7C14", "CAPTION", 4)

        for widget in (self._badge, self._message, self._where):
            row.addWidget(widget)

    def show_fault(self, fault):
        set_text(self._badge, fault.sev.upper())
        set_text(self._message, fault.msg)
        set_text(self._where, fault.loc)
        if fault.sev != self._sev:
            self._sev = fault.sev
            colour = Color.status(fault.sev)
            set_ss(self._badge, badge_style(fault.sev))
            set_ss(self, "QFrame{background:%s;border:none;border-left:3px solid %s;"
                         "border-radius:6px;}" % (Color.tint(fault.sev), colour))
        self.show()

    def restyle(self):
        self._sev = None


class FaultPanel(QFrame):
    """Worst-first list of what is wrong, capped at the rows that fit."""

    def __init__(self, title="ACTIVE FAULTS", rows=_ROWS, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._revision = -1

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(5)

        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(label(title, role="title"))
        head.addStretch()
        self._summary = label("NONE", role="caption", mono=True)
        head.addWidget(self._summary)
        outer.addLayout(head)

        self._rows = []
        for _ in range(rows):
            entry = _FaultRow()
            entry.hide()
            self._rows.append(entry)
            outer.addWidget(entry)

        self._empty = label("NO ACTIVE FAULTS", role="caption",
                            mono=True, align=Qt.AlignCenter)
        outer.addWidget(self._empty)
        outer.addStretch()

    def refresh(self, engine, force=False):
        tracker = engine.faults
        if tracker.revision == self._revision and not force:
            return
        self._revision = tracker.revision

        active = tracker.active
        for index, entry in enumerate(self._rows):
            if index < len(active):
                entry.show_fault(active[index])
            elif not entry.isHidden():
                entry.hide()

        overflow = len(active) - len(self._rows)
        self._empty.setVisible(not active)
        counts = tracker.counts
        set_text(self._summary,
                 "+%d MORE" % overflow if overflow > 0 else
                 ("NONE" if not active else "%dC / %dW / %dI"
                  % (counts["crit"], counts["warn"], counts["info"])))

    def restyle(self):
        self._revision = -1
        for entry in self._rows:
            entry.restyle()
