"""
core/recorder.py — CSV recording, one-shot snapshots, and the log index.
Rows are buffered and flushed in batches so the 10 Hz loop never blocks on
disk I/O; stop() and app shutdown both flush what's left.
"""

import csv
import datetime
import os
import shutil

from core.config import LOG_DIR

HEADER = ["clock", "t_s", "speed", "soc", "pack_v", "current",
          "tmax", "tmin", "avg_t", "delta_v", "power_kw"]
FLUSH_EVERY = 100


class Recorder:
    def __init__(self, engine):
        self._engine = engine
        self._rows = []
        self._started = None
        self._path = None
        self._active = False

    @property
    def is_active(self):
        return self._active

    @property
    def duration_s(self):
        if not self._started:
            return 0
        return int((datetime.datetime.now() - self._started).total_seconds())

    @property
    def file_size_kb(self):
        if not self._path or not os.path.exists(self._path):
            return 0.0
        return os.path.getsize(self._path) / 1024.0

    def start(self):
        self._started = datetime.datetime.now()
        self._path = os.path.join(LOG_DIR, "bms_%s.csv" % self._started.strftime("%Y%m%d_%H%M%S"))
        self._rows = []
        self._active = True

    def stop(self):
        if self._active:
            self._flush()
            self._active = False

    def record(self):
        if not self._active:
            return
        self._rows.append(self._row())
        if len(self._rows) >= FLUSH_EVERY:
            self._flush()

    def save_snapshot(self):
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(LOG_DIR, "snapshot_%s.csv" % stamp)
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADER)
            writer.writerow(self._row())
        return path

    def _row(self):
        e = self._engine
        return [
            datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3],
            round(e.elapsed, 1), round(e.speed, 1), round(e.soc, 1),
            round(e.pack_voltage, 2), round(e.current, 1),
            round(e.tmax, 1), round(e.tmin, 1), round(e.avg_temperature, 1),
            round(e.delta_v, 4), round(e.power_kw, 2),
        ]

    def _flush(self):
        if not self._rows:
            return
        new_file = not os.path.exists(self._path)
        with open(self._path, "a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if new_file:
                writer.writerow(HEADER)
            writer.writerows(self._rows)
        self._rows = []

    @staticmethod
    def list_logs():
        out = []
        try:
            names = sorted(os.listdir(LOG_DIR), reverse=True)
        except OSError:
            return out
        for name in names:
            if not name.endswith(".csv"):
                continue
            path = os.path.join(LOG_DIR, name)
            try:
                size = os.path.getsize(path)
                stamp = datetime.datetime.fromtimestamp(os.path.getmtime(path))
            except OSError:
                continue
            out.append((name, "%.1f KB" % (size / 1024.0), stamp.strftime("%d %b  %H:%M"), path))
        return out

    @staticmethod
    def export(src, dst):
        shutil.copy2(src, dst)
