"""
core/engine.py — the single source of truth for pack state.

Every derived number (pack voltage, per-segment averages, hot spot, cell
extremes, module health) is computed once per tick in _aggregate() and then
read as a plain attribute. Nothing in the UI recomputes over the 98 cells,
and `revision` only advances when the numbers really changed — so an idle
pack costs almost nothing to display.
"""

import time
from collections import deque

from core import config as cfg
from core.faults import FaultTracker
from core.sources import IdleSource, SimulatedSource
from core.stream import TelemetryServer, local_ip


class CellState:
    __slots__ = ("voltage", "temperature")

    def __init__(self):
        self.voltage = cfg.REST_CELL_V
        self.temperature = cfg.REST_CELL_T


class ModuleState:
    __slots__ = ("cells",)

    def __init__(self):
        self.cells = [CellState() for _ in range(cfg.CELLS_PER_SEGMENT)]


class ModuleStats:
    """Per-segment rollup, updated in place (no per-tick allocation)."""

    __slots__ = ("avg_v", "min_v", "max_v", "delta_v", "avg_t", "max_t", "health")

    def __init__(self):
        self.avg_v = self.min_v = self.max_v = cfg.REST_CELL_V
        self.delta_v = 0.0
        self.avg_t = self.max_t = cfg.REST_CELL_T
        self.health = "ok"


class DataEngine:
    SEGMENTS = cfg.SEGMENTS
    CELLS_PER = cfg.CELLS_PER_SEGMENT

    def __init__(self):
        self.modules = [ModuleState() for _ in range(cfg.SEGMENTS)]
        self.stats = [ModuleStats() for _ in range(cfg.SEGMENTS)]

        self.elapsed = 0.0
        self.speed = 0.0
        self.current = 0.0
        self.soc = 0.0
        self.revision = 0
        self.actual_hz = 0.0

        self.pack_voltage = 0.0
        self.power_kw = 0.0
        self.energy_kwh = 0.0
        self.delta_v = 0.0
        self.vmax = self.vmin = cfg.REST_CELL_V
        self.vmax_location = self.vmin_location = "S1C01"
        self.tmax = self.tmin = self.avg_temperature = cfg.REST_CELL_T
        self.tmax_location = "S1C01"

        self.faults = FaultTracker()
        self.stream = TelemetryServer()
        self._source = IdleSource()
        self._sim = None

        depth = cfg.HISTORY_SECONDS
        self.history = {k: deque(maxlen=depth) for k in
                        ("t", "pack_v", "current", "soc", "avg_t", "tmax", "power", "delta_v")}

        self._hz_count = 0
        self._hz_mark = time.monotonic()
        self._hist_tick = 0
        self._aggregate()

    # ── data source ────────────────────────────────────────────────────────
    @property
    def simulate(self):
        return isinstance(self._source, SimulatedSource)

    def set_simulate(self, on):
        if bool(on) == self.simulate:
            return
        if on:
            self._sim = self._sim or SimulatedSource()
            self._source = self._sim
        else:
            self._source = IdleSource()
        self.faults.clear()

    @property
    def can_ok(self):
        """True only for a real, healthy CAN bus — never for idle or sim."""
        return self._source.trustworthy

    @property
    def sensor_ok(self):
        return self._source.evaluate_faults

    @property
    def source_name(self):
        return self._source.name

    # ── tick ───────────────────────────────────────────────────────────────
    def tick(self):
        self.elapsed += cfg.TICK_MS / 1000.0
        if self._source.apply(self):
            self._aggregate()
            self.revision += 1

        self._hz_count += 1
        now = time.monotonic()
        if now - self._hz_mark >= 1.0:
            self.actual_hz = round(self._hz_count / (now - self._hz_mark), 1)
            self._hz_count = 0
            self._hz_mark = now

        self._hist_tick += 1
        if self._hist_tick >= 10:
            self._hist_tick = 0
            h = self.history
            h["t"].append(self.elapsed)
            h["pack_v"].append(self.pack_voltage)
            h["current"].append(self.current)
            h["soc"].append(self.soc)
            h["avg_t"].append(self.avg_temperature)
            h["tmax"].append(self.tmax)
            h["power"].append(self.power_kw)
            h["delta_v"].append(self.delta_v)

        if self._source.evaluate_faults:
            self.faults.evaluate(self)
        else:
            self.faults.clear()

        self.stream.broadcast(self.snapshot)

    # ── one pass over the pack ─────────────────────────────────────────────
    def _aggregate(self):
        v_sum = t_sum = 0.0
        v_hi, v_lo = -1e9, 1e9
        t_hi, t_lo = -1e9, 1e9
        hot_loc = v_hi_loc = v_lo_loc = "S1C01"

        for si, module in enumerate(self.modules):
            stat = self.stats[si]
            m_vsum = m_tsum = 0.0
            m_vhi, m_vlo, m_thi = -1e9, 1e9, -1e9

            for ci, cell in enumerate(module.cells):
                v, t = cell.voltage, cell.temperature
                m_vsum += v
                m_tsum += t
                if v > m_vhi:
                    m_vhi = v
                if v < m_vlo:
                    m_vlo = v
                if t > m_thi:
                    m_thi = t
                if v > v_hi:
                    v_hi, v_hi_loc = v, "S%dC%02d" % (si + 1, ci + 1)
                if v < v_lo:
                    v_lo, v_lo_loc = v, "S%dC%02d" % (si + 1, ci + 1)
                if t > t_hi:
                    t_hi, hot_loc = t, "S%dC%02d" % (si + 1, ci + 1)
                if t < t_lo:
                    t_lo = t

            n = len(module.cells)
            stat.avg_v = m_vsum / n
            stat.min_v, stat.max_v = m_vlo, m_vhi
            stat.delta_v = m_vhi - m_vlo
            stat.avg_t = m_tsum / n
            stat.max_t = m_thi
            stat.health = _module_health(stat)
            v_sum += m_vsum
            t_sum += m_tsum

        total = cfg.CELLS_TOTAL
        avg_cell_v = v_sum / total
        self.pack_voltage = avg_cell_v * cfg.SERIES_CELLS
        self.delta_v = v_hi - v_lo
        self.vmax, self.vmin = v_hi, v_lo
        self.vmax_location, self.vmin_location = v_hi_loc, v_lo_loc
        self.avg_temperature = t_sum / total
        self.tmax, self.tmin = t_hi, t_lo
        self.tmax_location = hot_loc
        self.power_kw = self.current * self.pack_voltage / 1000.0
        self.energy_kwh = cfg.PACK_NOMINAL_KWH * self.soc / 100.0

    # ── convenience for the UI ─────────────────────────────────────────────
    @property
    def status(self):
        return self.faults.status

    @property
    def fault_count(self):
        return len(self.faults.active)

    @property
    def has_critical(self):
        return self.faults.counts["crit"] > 0

    def local_ip(self):
        return local_ip()

    def snapshot(self):
        return {
            "t": round(self.elapsed, 1),
            "speed": round(self.speed, 1),
            "soc": round(self.soc, 1),
            "pack_v": round(self.pack_voltage, 2),
            "current": round(self.current, 1),
            "power_kw": round(self.power_kw, 2),
            "tmax": round(self.tmax, 1),
            "tmin": round(self.tmin, 1),
            "delta_v": round(self.delta_v, 4),
            "status": self.status,
            "faults": self.fault_count,
            "source": self.source_name,
        }


def _module_health(stat):
    if stat.max_t >= 50 or stat.avg_v > 3.92 or stat.avg_v < 3.20 or stat.delta_v > 0.080:
        return "crit"
    if stat.max_t >= 42 or stat.avg_v > 3.86 or stat.avg_v < 3.35 or stat.delta_v > 0.040:
        return "warn"
    return "ok"
