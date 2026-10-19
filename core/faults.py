"""
core/faults.py — fault rules in one table, plus the tracker that turns them
into an ordered active-fault list and appends new ones to the fault log.
"""

import csv
import datetime
import os
from collections import Counter, namedtuple

from core.config import FAULT_LOG

Fault = namedtuple("Fault", "code msg sev loc")

SEVERITY = {"ok": 0, "info": 1, "warn": 2, "crit": 3}

# Pack-level graded rules, worst threshold first. Limits are compared against
# the engine's own unit; `scale` only exists so a message can read in mV.
# (code, label, format, scale, direction, ((limit, severity, word), ...))
_PACK_RULES = (
    ("F01", "SPREAD", "%.0fmV", 1000.0, "high",
     ((0.080, "crit", "CRIT"), (0.040, "warn", "HIGH"), (0.015, "info", "ELEV"))),
    ("F02", "TEMP", "%.0f°C", 1.0, "high",
     ((55.0, "crit", "CRIT"), (45.0, "warn", "HIGH"), (38.0, "info", "ELEV"))),
    ("F03", "SOC", "%.0f%%", 1.0, "low",
     ((10.0, "crit", "CRIT"), (20.0, "warn", "LOW"), (30.0, "info", "INFO"))),
)

# Per-cell limits. Kept as plain constants so the hot loop stays cheap.
CELL_V_CRIT_HI, CELL_V_WARN_HI = 3.95, 3.90
CELL_V_CRIT_LO, CELL_V_WARN_LO = 3.15, 3.35
CELL_T_CRIT, CELL_T_WARN = 55.0, 45.0


def _graded(value, thresholds, direction):
    for limit, sev, word in thresholds:
        if (value >= limit) if direction == "high" else (value <= limit):
            return sev, word
    return None, None


class FaultTracker:
    """Evaluates the rule table against a snapshot of pack state."""

    def __init__(self):
        self.active = ()
        self.revision = 0
        self.status = "ok"
        self.headline = "ALL SYSTEMS NOMINAL"
        self.counts = {"crit": 0, "warn": 0, "info": 0}
        self._seen = frozenset()

    def clear(self):
        if self.active:
            self.active = ()
            self.status = "ok"
            self.headline = "ALL SYSTEMS NOMINAL"
            self.counts = {"crit": 0, "warn": 0, "info": 0}
            self.revision += 1
        self._seen = frozenset()

    def evaluate(self, engine):
        found = []
        for code, name, fmt, scale, direction, thresholds in _PACK_RULES:
            value = {"F01": engine.delta_v, "F02": engine.tmax, "F03": engine.soc}[code]
            sev, word = _graded(value, thresholds, direction)
            if sev:
                loc = engine.tmax_location if code == "F02" else "PACK"
                found.append(Fault(code, "%s %s %s" % (name, word, fmt % (value * scale)), sev, loc))

        # Skip the 98-cell scan entirely when the pack extremes prove no
        # single cell can be out of limits.
        if (engine.vmax > CELL_V_WARN_HI or engine.vmin < CELL_V_WARN_LO
                or engine.tmax >= CELL_T_WARN):
            found.extend(self._cell_faults(engine))

        self._commit(found)

    @staticmethod
    def _cell_faults(engine):
        out = []
        for si, module in enumerate(engine.modules):
            for ci, cell in enumerate(module.cells):
                loc = "S%dC%02d" % (si + 1, ci + 1)
                tag = si * 14 + ci + 1
                v = cell.voltage
                if v > CELL_V_CRIT_HI:
                    out.append(Fault("OV%02d" % tag, "OVERVLT %.3fV" % v, "crit", loc))
                elif v > CELL_V_WARN_HI:
                    out.append(Fault("HV%02d" % tag, "HI-V %.3fV" % v, "warn", loc))
                elif v < CELL_V_CRIT_LO:
                    out.append(Fault("UV%02d" % tag, "UNDERVLT %.3fV" % v, "crit", loc))
                elif v < CELL_V_WARN_LO:
                    out.append(Fault("LV%02d" % tag, "LO-V %.3fV" % v, "warn", loc))

                t = cell.temperature
                if t >= CELL_T_CRIT:
                    out.append(Fault("OT%02d" % tag, "OVERHEAT %.0f°C" % t, "crit", loc))
                elif t >= CELL_T_WARN:
                    out.append(Fault("HT%02d" % tag, "CELL HOT %.0f°C" % t, "warn", loc))
        return out

    def _commit(self, found):
        found.sort(key=lambda f: -SEVERITY[f.sev])
        codes = frozenset(f.code for f in found)

        for fault in found:
            if fault.code not in self._seen:
                _append_log(fault)

        if codes != self._seen:
            self.revision += 1
        self._seen = codes

        counts = Counter(fault.sev for fault in found)
        self.counts = {severity: counts[severity] for severity in ("crit", "warn", "info")}
        self.active = tuple(found)
        self.status = found[0].sev if found else "ok"
        self.headline = ("%s  ·  %s" % (found[0].msg, found[0].loc)) if found else "ALL SYSTEMS NOMINAL"


def _append_log(fault):
    try:
        new_file = not os.path.exists(FAULT_LOG)
        with open(FAULT_LOG, "a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if new_file:
                writer.writerow(["timestamp", "level", "code", "message", "location"])
            writer.writerow([
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                fault.sev, fault.code, fault.msg, fault.loc,
            ])
    except OSError:
        pass
