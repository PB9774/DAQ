"""
pages/common.py — shared helpers and widgets used by more than one page.

Pulled out of the old monolithic pages.py (v19) so pages can be split into
one file each without duplicating this code (v20 readability refactor).

Notable v20 change: _FaultPanel used to fully tear down and rebuild every
fault row on every refresh() call (10x/sec). That was fine when the fault
list was capped at 14 rows, but now that DataEngine no longer truncates the
fault list (a real pack-wide event could produce 50+ simultaneous faults),
rebuilding everything every 100ms would get expensive. _FaultPanel now
keeps one persistent row widget per fault code and only adds/removes rows
when the *set* of active codes changes — existing rows just get their text
updated in place, which is cheap.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
    QScrollArea, QWidget, QSizePolicy,
)

from theme import TM, Color, Font, MONO


# ── small style helpers ─────────────────────────────────────────────────────
def _sep():
    """A thin horizontal divider line, themed to match the current palette."""
    s = QFrame()
    s.setFixedHeight(1)
    s.setStyleSheet("background:" + Color.BORDER + ";border:none;")
    return s


def _lbl(text, role="", ss=""):
    """Shorthand for building a QLabel with an optional theme role and/or
    a raw stylesheet override."""
    l = QLabel(text)
    if role:
        l.setProperty("role", role)
    if ss:
        l.setStyleSheet(ss)
    return l


def _bar_ss(fill):
    """Stylesheet for a QProgressBar with the given fill color."""
    P = TM.palette
    return (
        "QProgressBar{background:" + P["BG_PANEL"] + ";border:none;border-radius:3px;}"
        "QProgressBar::chunk{background:" + fill + ";border-radius:3px;}"
    )


def _P(key):
    """Shorthand for looking up a color in the current theme palette."""
    return TM.palette.get(key, "#888")


def _health_ss(health):
    """Stylesheet for a segment/cell health badge (ok / warn / crit)."""
    if health == "crit":
        return "background:#7F1D1D;color:#FCA5A5;border-radius:4px;font-size:13px;font-weight:800;"
    if health == "warn":
        return "background:#78350F;color:#FCD34D;border-radius:4px;font-size:13px;font-weight:800;"
    return "background:#14532D;color:#86EFAC;border-radius:4px;font-size:13px;font-weight:800;"


def _cell_colors(v):
    """Background/foreground color pair for a cell-voltage box, based on
    how close the voltage is to the healthy range."""
    if v > 3.90:
        return "#7f1d1d", "#fca5a5"
    if v < 3.35:
        return "#78350f", "#fcd34d"
    if v < 3.55:
        return "#1c3314", "#86efac"
    frac = (v - 3.55) / (3.90 - 3.55)
    g = int(30 + frac * 60)
    return "#0a%02x18" % g, "#4ade80"


def _ntc_ss(t):
    """Stylesheet for a temperature-sensor box, based on how hot it is."""
    if t > 50:
        return "background:#7f1d1d;color:#fca5a5;"
    if t > 45:
        return "background:#991b1b;color:#fecaca;"
    if t > 40:
        return "background:#78350f;color:#fcd34d;"
    return "background:" + _P("BG_CARD2") + ";color:" + _P("TEXT_DIM") + ";"


# ══════════════════════════════════════════════════════════════════════════
# FAULT PANEL — 3-level: info (blue) · warn (amber) · crit (red)
# v20: incremental rendering, no truncation of the fault list.
# ══════════════════════════════════════════════════════════════════════════
_LEVEL_COLORS = {"crit": ("#2A0A0A", "#EF4444"), "warn": ("#2A1A00", "#D97706"), "info": ("#0A1230", "#3B82F6")}
_LEVEL_ICONS = {"crit": "▮", "warn": "▲", "info": "●"}


class _FaultRow(QFrame):
    """One persistent row in the fault panel. Created once per fault code,
    then just has its text/color updated in place on subsequent ticks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(5)

        self.icon = QLabel("")
        self.code_lbl = QLabel("")
        self.code_lbl.setFixedWidth(36)
        self.msg_lbl = QLabel("")
        self.msg_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.loc_lbl = QLabel("")

        for w in (self.icon, self.code_lbl, self.msg_lbl, self.loc_lbl):
            layout.addWidget(w)

    def update_fault(self, code, msg, sev, loc):
        bg, fc = _LEVEL_COLORS.get(sev, ("#1A1A1A", "#888"))
        self.setStyleSheet("background:" + bg + ";border-radius:4px;border:1px solid " + fc + "44;")
        self.icon.setText(_LEVEL_ICONS.get(sev, "?"))
        self.icon.setStyleSheet("color:" + fc + ";font-size:" + str(Font.SIZE_SM) + "px;background:transparent;border:none;")
        self.code_lbl.setText(code)
        self.code_lbl.setStyleSheet("color:" + fc + ";font-family:" + MONO + ";font-size:" + str(Font.SIZE_SM) + "px;font-weight:700;background:transparent;border:none;")
        self.msg_lbl.setText(msg)
        self.msg_lbl.setStyleSheet("color:" + _P("TEXT_PRI") + ";font-family:" + MONO + ";font-size:" + str(Font.SIZE_SM) + "px;background:transparent;border:none;")
        self.loc_lbl.setText(loc)
        self.loc_lbl.setStyleSheet("color:" + fc + ";font-family:" + MONO + ";font-size:13px;font-weight:700;background:transparent;border:none;")


class _FaultPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card_lit")
        self._rows = {}       # fault code -> _FaultRow
        self._ok_label = None
        self._last_codes = frozenset()

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 7, 8, 7)
        root.setSpacing(4)

        hdr = QHBoxLayout()
        self._title = QLabel("FAULT MONITOR")
        self._badge = QLabel("OK")
        self._badge.setFixedSize(40, 20)
        self._badge.setAlignment(Qt.AlignCenter)
        hdr.addWidget(self._title)
        hdr.addStretch()
        hdr.addWidget(self._badge)
        root.addLayout(hdr)
        root.addWidget(_sep())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:transparent;border:none;")

        self._inner = QWidget()
        self._inner.setStyleSheet("background:transparent;")
        self._flay = QVBoxLayout(self._inner)
        self._flay.setContentsMargins(0, 0, 0, 0)
        self._flay.setSpacing(3)
        scroll.setWidget(self._inner)
        root.addWidget(scroll, 1)

        self._set_ok_state()

    def _set_ok_state(self):
        for row in self._rows.values():
            row.deleteLater()
        self._rows.clear()

        if self._ok_label is None:
            self._ok_label = QLabel("✓  All systems nominal")
            self._flay.addWidget(self._ok_label)
        self._ok_label.setStyleSheet(
            "color:#22C55E;font-size:" + str(Font.SIZE_SM) + "px;font-weight:700;"
            "background:transparent;border:none;padding:2px 0;"
        )
        self._badge.setText("OK")
        self._badge.setStyleSheet("background:#16A34A;color:#fff;border-radius:4px;font-size:13px;font-weight:700;")
        self._title.setStyleSheet(
            "color:" + _P("TEXT_SEC") + ";font-size:" + str(Font.SIZE_SM) + "px;"
            "font-weight:700;letter-spacing:1px;background:transparent;border:none;"
        )

    def refresh(self, faults):
        """faults: list of (code, msg, sev, loc) tuples, already the full
        (untruncated) set from DataEngine.active_faults."""
        if not faults:
            if self._last_codes:  # only touch the UI if we're transitioning to OK
                self._set_ok_state()
            self._last_codes = frozenset()
            return

        # leaving the OK state
        if self._ok_label is not None:
            self._flay.removeWidget(self._ok_label)
            self._ok_label.deleteLater()
            self._ok_label = None

        new_codes = {f[0] for f in faults}

        # remove rows for codes that are no longer active
        for code in list(self._rows.keys()):
            if code not in new_codes:
                row = self._rows.pop(code)
                self._flay.removeWidget(row)
                row.deleteLater()

        # add/update rows, preserving fault order (crit/warn/info as emitted)
        for code, msg, sev, loc in faults:
            row = self._rows.get(code)
            if row is None:
                row = _FaultRow()
                self._rows[code] = row
                self._flay.addWidget(row)
            row.update_fault(code, msg, sev, loc)

        self._last_codes = frozenset(new_codes)

        n_crit = sum(1 for f in faults if f[2] == "crit")
        n_warn = sum(1 for f in faults if f[2] == "warn")
        if n_crit:
            bc, bt, tc = "#EF4444", "%d CRIT" % n_crit, "#EF4444"
        elif n_warn:
            bc, bt, tc = "#D97706", "%d WARN" % n_warn, "#D97706"
        else:
            bc, bt, tc = "#3B82F6", "%d INFO" % len(faults), "#3B82F6"

        self._badge.setText(bt)
        self._badge.setStyleSheet("background:" + bc + ";color:#fff;border-radius:4px;font-size:13px;font-weight:700;min-width:54px;")
        self._title.setStyleSheet(
            "color:" + tc + ";font-size:" + str(Font.SIZE_SM) + "px;"
            "font-weight:700;letter-spacing:1px;background:transparent;border:none;"
        )


# ══════════════════════════════════════════════════════════════════════════
# SEGMENT PANEL — one BMS segment: 14 cell voltage boxes + 7 NTC boxes
# ══════════════════════════════════════════════════════════════════════════
class _SegPanel(QFrame):
    CELL_W = 52
    CELL_H = 44
    NTC_H = 44

    def __init__(self, idx, parent=None):
        super().__init__(parent)
        self._idx = idx
        self._cells = []
        self._ntcs = []
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 5, 5)
        root.setSpacing(3)

        hdr = QHBoxLayout()
        hdr_lbl = QLabel("  SEGMENT %d" % (self._idx + 1))
        hdr_lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        hdr_lbl.setStyleSheet(
            "color:" + _P("ACCENT") + ";font-size:15px;font-weight:800;"
            "letter-spacing:3px;background:" + _P("BG_CARD2") + ";border-radius:3px;padding:2px 6px;"
        )
        self._health_badge = QLabel("OK")
        self._health_badge.setFixedSize(42, 20)
        self._health_badge.setAlignment(Qt.AlignCenter)
        self._health_badge.setStyleSheet(_health_ss("ok"))
        self._tmax_lbl = QLabel("T--°")
        self._tmax_lbl.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        self._tmax_lbl.setStyleSheet("color:#F59E0B;font-size:13px;font-family:" + MONO + ";font-weight:700;background:transparent;border:none;")
        hdr.addWidget(hdr_lbl, 1)
        hdr.addWidget(self._tmax_lbl)
        hdr.addSpacing(4)
        hdr.addWidget(self._health_badge)
        root.addLayout(hdr)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(3)
        for i in range(14):
            lbl = QLabel("C%d\n3.70" % (i + 1))
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedSize(self.CELL_W, self.CELL_H)
            lbl.setStyleSheet("background:#0a5018;color:#4ade80;border-radius:3px;font-family:" + MONO + ";font-size:20px;font-weight:1000;")
            self._cells.append(lbl)
            grid.addWidget(lbl, i // 7, i % 7)
        root.addLayout(grid)

        ntc = QHBoxLayout()
        ntc.setContentsMargins(0, 0, 0, 0)
        ntc.setSpacing(3)
        for i in range(7):
            b = QLabel("T%d" % (i + 1))
            b.setFixedHeight(self.NTC_H)
            b.setMinimumWidth(self.CELL_W)
            b.setAlignment(Qt.AlignCenter)
            b.setStyleSheet(
                "border-radius:3px;font-family:" + MONO + ";font-size:20px;font-weight:1000;"
                "background:" + _P("BG_CARD2") + ";color:" + _P("TEXT_DIM") + ";"
            )
            self._ntcs.append(b)
            ntc.addWidget(b)
        root.addLayout(ntc)

    def refresh(self, module, max_v_loc, min_v_loc):
        all_v = [c.voltage for c in module.cells]
        gmax_v = max(all_v)
        gmin_v = min(all_v)
        tm = max(c.temperature for c in module.cells)

        tc = "#EF4444" if tm >= 50 else ("#F59E0B" if tm >= 42 else "#22C55E")
        self._tmax_lbl.setText("T%.0f°" % tm)
        self._tmax_lbl.setStyleSheet("color:" + tc + ";font-size:13px;font-family:" + MONO + ";font-weight:700;background:transparent;border:none;")

        health = "crit" if tc == "#EF4444" else ("warn" if tc == "#F59E0B" else "ok")
        if gmax_v > 3.90 or gmin_v < 3.35:
            health = "crit" if (gmax_v > 3.95 or gmin_v < 3.15) else "warn"
        self._health_badge.setText(health.upper())
        self._health_badge.setStyleSheet(_health_ss(health))

        mi_label = "S%d" % (self._idx + 1)
        for i, c in enumerate(module.cells):
            bg, fg = _cell_colors(c.voltage)
            cell_loc = "%sC%02d" % (mi_label, i + 1)
            if cell_loc in max_v_loc:
                border = "border:2px solid #60A5FA;"
            elif cell_loc in min_v_loc:
                border = "border:2px solid #FDE047;"
            else:
                border = "border:none;"
            self._cells[i].setText("C%d\n%.2f" % (i + 1, c.voltage))
            self._cells[i].setStyleSheet(
                "background:" + bg + ";color:" + fg + ";border-radius:3px;"
                "font-family:" + MONO + ";font-size:20px;font-weight:1000;" + border
            )

        # 7 NTC sensors derived from the 14 real cell temperatures (each NTC
        # box shows the average of its adjacent cell pair). v19 used to fill
        # these with independent random noise on every refresh — that's
        # gone now; every number here traces back to real (or simulated)
        # engine data.
        for i, b in enumerate(self._ntcs):
            t = (module.cells[2 * i].temperature + module.cells[2 * i + 1].temperature) / 2.0
            b.setText("T%d\n%.0f°" % (i + 1, t))
            b.setStyleSheet(_ntc_ss(t) + "border-radius:3px;font-family:" + MONO + ";font-size:11px;font-weight:700;")
