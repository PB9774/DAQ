"""
core/sources.py — where pack numbers come from.

Each source mutates the engine's cell/vehicle state in place and reports
whether anything actually changed, so the UI can skip work when it hasn't.
Wiring real hardware means adding a CanSource here and nothing else.
"""

import math
import random

from core.config import REST_CELL_V, REST_CELL_T


class IdleSource:
    """No signal. Deterministic rest values that never trigger a fault."""

    name = "NO SIGNAL"
    trustworthy = False
    evaluate_faults = False

    def __init__(self):
        self._applied = False

    def apply(self, engine):
        if self._applied:
            return False
        for module in engine.modules:
            for cell in module.cells:
                cell.voltage = REST_CELL_V
                cell.temperature = REST_CELL_T
        engine.speed = 0.0
        engine.current = 0.0
        engine.soc = 0.0
        self._applied = True
        return True


class SimulatedSource:
    """Plausible test telemetry for bench/UI work. Never a real pack.

    Deliberately calibrated to sit inside the healthy band most of the time —
    one drifting cell and one warm segment give the fault path something to
    show without painting the whole pack red, which would teach the driver to
    ignore the colour.
    """

    name = "SIMULATED"
    trustworthy = False
    evaluate_faults = True

    def __init__(self):
        self._speed_target = 0.0

    def apply(self, engine):
        t = engine.elapsed
        self._speed_target = max(0.0, min(110.0, self._speed_target + random.gauss(0, 1.8)))
        engine.speed = max(0.0, engine.speed + (self._speed_target - engine.speed) * 0.15)

        # Common-mode sag under load, plus a small fixed stagger per segment.
        common = 3.74 - 0.09 * (0.5 + 0.5 * math.sin(t * 0.03))
        for si, module in enumerate(engine.modules):
            base = common + si * 0.003
            for ci, cell in enumerate(module.cells):
                drift = 0.035 if (si == 2 and ci == 6) else 0.0
                cell.voltage = max(3.0, base + random.gauss(0, 0.005) + drift)
                hot = 13.0 if (si == 5 and ci < 4) else 0.0
                cell.temperature = 31.0 + si * 1.2 + random.gauss(0, 0.6) + hot

        engine.current = 35.0 + 28.0 * math.sin(t * 0.08) + random.gauss(0, 2.0)
        engine.soc = max(5.0, 85.0 - t * 0.004)
        return True
