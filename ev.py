"""
ev.py — DataEngine · v20

Changes from v19:
  - Random data generation is now OPT-IN. By default the engine sits in an
    idle "no signal" state (safe, deterministic values, CAN status = red).
    Flip DataEngine.set_simulate(True) from the Settings page to generate
    test data — CAN status stays red but switches to "SIMULATED" so nobody
    mistakes it for a live pack.
  - Removed the unused FaultRecord dataclass (dead code — faults are plain
    tuples everywhere, this was never instantiated).
  - Removed the fault-list truncation (`faults[:14]`). All active faults are
    now kept; the fault panel widget is responsible for rendering that
    efficiently (see widgets.py — it only rebuilds when the fault set
    actually changes, not every tick).

Once real CAN hardware is wired in, `_tick_live()` is the place to fill in
python-can + cantools decoding — swap the `self.simulate` flag logic for a
`self.mode` of "idle" / "simulate" / "live" and call the right tick method.
"""

import csv
import datetime
import json
import math
import os
import random
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import List

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
FAULT_LOG = os.path.join(LOG_DIR, "fault_log.csv")
TELEMETRY_PORT = 9000

# Rest-state values used whenever we have no real or simulated signal.
# Safe, nominal numbers — chosen so idle mode never itself triggers a fault.
REST_CELL_VOLTAGE = 3.70
REST_CELL_TEMP = 25.0


@dataclass
class CellState:
    voltage: float = REST_CELL_VOLTAGE
    temperature: float = REST_CELL_TEMP


@dataclass
class ModuleState:
    cells: list = field(default_factory=lambda: [CellState() for _ in range(14)])


class DataEngine:
    NUM_MODULES = 7
    CELLS_PER = 14
    HIST = 1800

    def __init__(self):
        self.modules = [ModuleState() for _ in range(self.NUM_MODULES)]

        self.speed = 0.0
        self.current = 0.0
        self.soc = 0.0
        self._t = 0.0

        # --- data source state ---
        # simulate=False on every launch, always. This is intentional: the
        # dashboard should never silently start in test mode. The team has
        # to explicitly opt in from the Settings page each session.
        self.simulate = False
        self._spd_target = 0.0

        self._active_faults: List[tuple] = []
        self._prev_fault_codes: set = set()

        self.time_h = deque(maxlen=self.HIST)
        self.voltage_h = deque(maxlen=self.HIST)
        self.current_h = deque(maxlen=self.HIST)
        self.soc_h = deque(maxlen=self.HIST)
        self.temp_h = deque(maxlen=self.HIST)
        self.tmax_h = deque(maxlen=self.HIST)
        self.power_h = deque(maxlen=self.HIST)
        self.dv_h = deque(maxlen=self.HIST)

        # CAN/sensor health is always "no real connection" until real CAN
        # wiring lands — see can_ok / can_status_text below.
        self.sensor_ok = True
        self._hz_count = 0
        self._hz_last = time.monotonic()
        self.actual_hz = 0.0

        self._streaming = False
        self._srv_thread = None
        self._clients: List[socket.socket] = []
        self._cli_lock = threading.Lock()

        self._hist_tick = 0

        # Cached aggregate values (filled by _aggregate() each tick)
        self._pack_v = 0.0
        self._delta_v = 0.0
        self._avg_t = REST_CELL_TEMP
        self._tmax = REST_CELL_TEMP
        self._tmin = REST_CELL_TEMP
        self._tloc = "S1C01"
        self._power = 0.0

        self._apply_rest_state()

    # ─────────────────────────────────────────
    # Data source control
    # ─────────────────────────────────────────
    def set_simulate(self, on: bool):
        """Toggle between idle (no signal) and simulated test data."""
        self.simulate = bool(on)
        if not self.simulate:
            self._apply_rest_state()

    def _apply_rest_state(self):
        """Deterministic, safe idle values — used whenever there's no live
        or simulated signal. Never triggers a fault on its own."""
        for m in self.modules:
            for c in m.cells:
                c.voltage = REST_CELL_VOLTAGE
                c.temperature = REST_CELL_TEMP
        self.speed = 0.0
        self.current = 0.0
        self._spd_target = 0.0

    @property
    def can_ok(self) -> bool:
        # Neither idle nor simulated counts as a real connection. This will
        # become conditional on actual bus health once real CAN is wired in.
        return False

    @property
    def can_status_text(self) -> str:
        return "SIMULATED" if self.simulate else "NO SIGNAL"

    @property
    def has_signal(self) -> bool:
        """True only when there's data worth trusting (i.e. simulated, or
        in future, a real live bus). Idle/no-signal state is not 'data'."""
        return self.simulate

    # ─────────────────────────────────────────
    # Main tick — dispatches to simulate or idle
    # ─────────────────────────────────────────
    def tick(self):
        self._t += 0.1

        if self.simulate:
            self._tick_simulate()
        # else: idle — rest-state values already in place, nothing to do

        self._hz_count += 1
        now = time.monotonic()
        if now - self._hz_last >= 1.0:
            self.actual_hz = round(self._hz_count / (now - self._hz_last), 1)
            self._hz_count = 0
            self._hz_last = now

        # Push history at ~1 Hz to reduce UI graph pressure
        self._hist_tick += 1
        if self._hist_tick >= 10:
            self._hist_tick = 0
            self.time_h.append(self._t)
            self.voltage_h.append(self.pack_voltage)
            self.current_h.append(self.current)
            self.soc_h.append(self.soc)
            self.temp_h.append(self.avg_temperature)
            self.tmax_h.append(self.tmax)
            self.power_h.append(self.power_kw)
            self.dv_h.append(self.delta_v)

        self._aggregate()

        # Fault detection only makes sense when there's an actual signal
        # (simulated today, real CAN in future). In idle/no-signal mode
        # there's nothing to evaluate — showing faults against a rest
        # state we made up ourselves would be actively misleading.
        if self.simulate:
            self._detect_faults()
        else:
            self._active_faults = []
            self._prev_fault_codes = set()

        self._broadcast()

    def _tick_simulate(self):
        """Generates plausible test telemetry. Only runs when the team has
        explicitly enabled simulated data from the Settings page."""
        dt = self._t
        self._spd_target = max(0, min(110, self._spd_target + random.gauss(0, 1.8)))
        self.speed = max(0, self.speed + (self._spd_target - self.speed) * 0.15)

        for mi, m in enumerate(self.modules):
            base_v = 3.62 + 0.18 * math.sin(dt * 0.05 + mi * 0.4)
            for ci, c in enumerate(m.cells):
                noise = random.gauss(0, 0.013)
                outlier = 0.05 if (mi == 2 and ci == 6) else 0.0
                c.voltage = max(3.0, base_v + noise + outlier)

                hot = 14 if (mi == 5 and ci < 4) else 0
                c.temperature = 32 + mi * 1.4 + random.gauss(0, 0.7) + hot

        self.current = 35 + 28 * math.sin(dt * 0.08) + random.gauss(0, 2.0)
        self.soc = max(5.0, 85.0 - dt * 0.004)

    # ─────────────────────────────────────────
    # Aggregation
    # ─────────────────────────────────────────
    def _aggregate(self):
        """Single pass — compute all derived values at once."""
        vsum = 0.0
        vmax = -999.0
        vmin = 999.0
        tmax = -999.0
        tmin = 999.0
        tsum = 0.0
        n = 0
        tloc = "S1C01"

        for mi, m in enumerate(self.modules):
            for ci, c in enumerate(m.cells):
                v = c.voltage
                tp = c.temperature
                vsum += v
                n += 1
                if v > vmax:
                    vmax = v
                if v < vmin:
                    vmin = v
                if tp > tmax:
                    tmax = tp
                    tloc = "S%dC%02d" % (mi + 1, ci + 1)
                if tp < tmin:
                    tmin = tp
                tsum += tp

        self._pack_v = (vsum / n) * 96.0
        self._delta_v = vmax - vmin
        self._avg_t = tsum / n
        self._tmax = tmax
        self._tmin = tmin
        self._tloc = tloc
        self._power = (self.current * self._pack_v) / 1000.0

    @property
    def pack_voltage(self):
        return self._pack_v

    @property
    def delta_v(self):
        return self._delta_v

    @property
    def avg_temperature(self):
        return self._avg_t

    @property
    def tmax(self):
        return self._tmax

    @property
    def tmin(self):
        return self._tmin

    @property
    def tmax_location(self):
        return self._tloc

    @property
    def power_kw(self):
        return self._power

    def mod_avg_v(self, i):
        m = self.modules[i]
        return sum(c.voltage for c in m.cells) / len(m.cells)

    def mod_avg_t(self, i):
        m = self.modules[i]
        return sum(c.temperature for c in m.cells) / len(m.cells)

    def mod_tmax(self, i):
        return max(c.temperature for c in self.modules[i].cells)

    def mod_health(self, i):
        m = self.modules[i]
        vv = [c.voltage for c in m.cells]
        tm = max(c.temperature for c in m.cells)
        dv = max(vv) - min(vv)
        av = sum(vv) / len(vv)
        if tm >= 50 or av > 3.92 or av < 3.20 or dv > 0.080:
            return "crit"
        if tm >= 42 or av > 3.86 or av < 3.35 or dv > 0.040:
            return "warn"
        return "ok"

    def cell_global_extremes(self):
        max_v, min_v, max_loc, min_loc = -999.0, 999.0, "", ""
        for mi, m in enumerate(self.modules):
            for ci, c in enumerate(m.cells):
                loc = "S%dC%02d" % (mi + 1, ci + 1)
                if c.voltage > max_v:
                    max_v = c.voltage
                    max_loc = loc
                if c.voltage < min_v:
                    min_v = c.voltage
                    min_loc = loc
        return max_loc, max_v, min_loc, min_v

    # ─────────────────────────────────────────
    # Fault detection — 3-level: info / warn / crit
    # No truncation: every active fault is kept and exposed via
    # active_faults. The fault panel widget renders these efficiently by
    # only rebuilding when the set of fault codes actually changes.
    # ─────────────────────────────────────────
    def _detect_faults(self):
        faults = []
        dv = self.delta_v
        tm = self.tmax
        s = self.soc

        if dv >= 0.080:
            faults.append(("F01", "DV CRIT %.3fV" % dv, "crit", "PACK"))
        elif dv >= 0.040:
            faults.append(("F01", "DV HIGH %.3fV" % dv, "warn", "PACK"))
        elif dv >= 0.015:
            faults.append(("F01", "DV ELEV %.3fV" % dv, "info", "PACK"))

        if tm >= 55:
            faults.append(("F02", "TEMP CRIT %.0fC" % tm, "crit", self.tmax_location))
        elif tm >= 45:
            faults.append(("F02", "TEMP HIGH %.0fC" % tm, "warn", self.tmax_location))
        elif tm >= 38:
            faults.append(("F02", "TEMP ELEV %.0fC" % tm, "info", self.tmax_location))

        if s <= 10:
            faults.append(("F03", "SOC CRIT %.0f%%" % s, "crit", "PACK"))
        elif s <= 20:
            faults.append(("F03", "SOC LOW %.0f%%" % s, "warn", "PACK"))
        elif s <= 30:
            faults.append(("F03", "SOC INFO %.0f%%" % s, "info", "PACK"))

        for mi, m in enumerate(self.modules):
            for ci, c in enumerate(m.cells):
                loc = "S%dC%02d" % (mi + 1, ci + 1)
                tag = mi * 14 + ci + 1

                if c.voltage > 3.95:
                    faults.append(("OV%02d" % tag, "OVERVLT %.3fV" % c.voltage, "crit", loc))
                elif c.voltage > 3.90:
                    faults.append(("HV%02d" % tag, "HI-V %.3fV" % c.voltage, "warn", loc))
                elif c.voltage < 3.15:
                    faults.append(("UV%02d" % tag, "UNDERVLT %.3fV" % c.voltage, "crit", loc))
                elif c.voltage < 3.35:
                    faults.append(("LV%02d" % tag, "LO-V %.3fV" % c.voltage, "warn", loc))

                if c.temperature >= 55:
                    faults.append(("OT%02d" % tag, "OVERHEAT %.0fC" % c.temperature, "crit", loc))
                elif c.temperature >= 45:
                    faults.append(("HT%02d" % tag, "HOT %.0fC" % c.temperature, "warn", loc))

        new_codes = {f[0] for f in faults}
        for code, msg, sev, loc in faults:
            if code not in self._prev_fault_codes:
                self._write_fault(code, msg, sev, loc)

        self._prev_fault_codes = new_codes
        self._active_faults = faults  # no truncation — full list kept

    def _write_fault(self, code, msg, sev, loc):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        write_header = not os.path.exists(FAULT_LOG)
        with open(FAULT_LOG, "a", newline="") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(["timestamp", "level", "code", "message", "location"])
            w.writerow([ts, sev, code, msg, loc])

    @property
    def active_faults(self):
        return list(self._active_faults)

    @property
    def has_critical(self):
        return any(f[2] == "crit" for f in self._active_faults)

    @property
    def fault_count(self):
        return len(self._active_faults)

    # ─────────────────────────────────────────
    # TCP telemetry streaming
    # ─────────────────────────────────────────
    def start_streaming(self):
        if self._streaming:
            return
        self._streaming = True
        self._srv_thread = threading.Thread(target=self._srv_loop, daemon=True)
        self._srv_thread.start()

    def stop_streaming(self):
        self._streaming = False

    @property
    def is_streaming(self):
        return self._streaming

    def _srv_loop(self):
        try:
            srv = socket.socket()
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("0.0.0.0", TELEMETRY_PORT))
            srv.listen(5)
            srv.settimeout(1.0)
            while self._streaming:
                try:
                    conn, _ = srv.accept()
                    with self._cli_lock:
                        self._clients.append(conn)
                except socket.timeout:
                    pass
            srv.close()
        except Exception:
            pass

    def _broadcast(self):
        with self._cli_lock:
            if not self._clients:
                return
            payload = {
                "t": round(self._t, 1),
                "speed": round(self.speed, 1),
                "soc": round(self.soc, 1),
                "pack_v": round(self.pack_voltage, 2),
                "cur": round(self.current, 1),
                "tmax": round(self.tmax, 1),
                "tmin": round(self.tmin, 1),
                "dv": round(self.delta_v, 4),
                "power": round(self.power_kw, 2),
                "faults": self.fault_count,
                "crit": self.has_critical,
                "simulated": self.simulate,
            }
            data = (json.dumps(payload) + "\n").encode()
            dead = []
            for c in self._clients:
                try:
                    c.sendall(data)
                except Exception:
                    dead.append(c)
            for c in dead:
                self._clients.remove(c)

    def local_ip(self):
        try:
            s = socket.socket()
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"


class Logger:
    HDR = ["time", "t_s", "speed", "soc", "pack_v", "current", "tmax", "tmin", "avg_t", "dv", "power_kw"]

    def __init__(self, engine: DataEngine):
        self._e = engine
        self._rows = []
        self._start = None
        self._active = False
        self._path = None

    def start(self):
        self._start = datetime.datetime.now()
        self._path = os.path.join(LOG_DIR, "bms_%s.csv" % self._start.strftime("%Y%m%d_%H%M%S"))
        self._rows = []
        self._active = True

    def stop(self):
        if self._active:
            self._flush()
            self._active = False

    def _build_row(self):
        """One row in the standard log format, built from current engine
        state. Shared by record() (continuous logging) and save_snapshot()
        (one-shot manual save) so there's a single source of truth for the
        row layout."""
        e = self._e
        return [
            datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3],
            round(e._t, 1), round(e.speed, 1), round(e.soc, 1), round(e.pack_voltage, 2),
            round(e.current, 1), round(e.tmax, 1), round(e.tmin, 1), round(e.avg_temperature, 1),
            round(e.delta_v, 4), round(e.power_kw, 2),
        ]

    def record(self):
        if not self._active:
            return
        self._rows.append(self._build_row())
        if len(self._rows) >= 100:
            self._flush()

    def save_snapshot(self) -> str:
        """One-shot manual save (the Dashboard page's 'Save Snapshot'
        button) — independent of start()/stop() continuous recording.
        Writes a single-row CSV and returns its path.

        v20 fix: this method didn't exist in v19 even though the UI called
        `logger.save()` — clicking Save Snapshot threw an AttributeError.
        """
        ts = datetime.datetime.now()
        path = os.path.join(LOG_DIR, "snapshot_%s.csv" % ts.strftime("%Y%m%d_%H%M%S"))
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(self.HDR)
            w.writerow(self._build_row())
        return path

    def _flush(self):
        """Write any buffered rows to disk. Safe to call repeatedly —
        also called from MainWindow.closeEvent() so nothing is lost if the
        app is closed mid-recording."""
        if not self._rows:
            return
        write_header = not os.path.exists(self._path)
        with open(self._path, "a", newline="") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(self.HDR)
            w.writerows(self._rows)
        self._rows = []

    @property
    def is_active(self):
        return self._active

    @property
    def duration_s(self):
        if not self._start:
            return 0
        return int((datetime.datetime.now() - self._start).total_seconds())

    @property
    def file_size_kb(self):
        if not self._path or not os.path.exists(self._path):
            return 0.0
        return os.path.getsize(self._path) / 1024.0

    def list_logs(self):
        out = []
        try:
            for fn in sorted(os.listdir(LOG_DIR), reverse=True):
                if not fn.endswith(".csv"):
                    continue
                p = os.path.join(LOG_DIR, fn)
                sz = os.path.getsize(p)
                mt = datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%m/%d %H:%M")
                out.append((fn, "%.1fKB" % (sz / 1024), mt, p))
        except Exception:
            pass
        return out

    def export(self, src, dst):
        import shutil
        shutil.copy2(src, dst)
