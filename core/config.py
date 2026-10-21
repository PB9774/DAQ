"""
core/config.py — every number that describes THIS car lives here.

Edit this file when the accumulator changes; nothing else needs to know.
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
ASSET_DIR = os.path.join(BASE_DIR, "assets")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
FAULT_LOG = os.path.join(LOG_DIR, "fault_log.csv")
CRASH_LOG = os.path.join(LOG_DIR, "crash.log")

os.makedirs(LOG_DIR, exist_ok=True)

# ── Pack geometry ──────────────────────────────────────────────────────────
SEGMENTS = 7
CELLS_PER_SEGMENT = 14
NTC_PER_SEGMENT = 7
CELLS_TOTAL = SEGMENTS * CELLS_PER_SEGMENT

# Series/parallel layout. Pack voltage = series count x average cell voltage.
SERIES_CELLS = CELLS_TOTAL
PARALLEL_STRINGS = 4          # <-- set to the real string count
CELL_CAPACITY_AH = 5.0        # <-- set to the real cell capacity

# Nominal usable energy, used only for the driver "ENERGY" readout.
NOMINAL_CELL_V = 3.70
PACK_NOMINAL_KWH = SERIES_CELLS * NOMINAL_CELL_V * CELL_CAPACITY_AH * PARALLEL_STRINGS / 1000.0

# Typical energy burnt per endurance lap, for the driver "RANGE" estimate.
ENERGY_PER_LAP_KWH = 0.35     # <-- set from last event's telemetry

# ── Display / loop ─────────────────────────────────────────────────────────
SCREEN_W = 1024
SCREEN_H = 600
FULLSCREEN = False
TICK_MS = 100                 # 10 Hz telemetry loop
HISTORY_SECONDS = 1800        # 30 min of 1 Hz trend samples
SPEED_MAX = 110.0

# ── Idle / rest state (no CAN, no simulation) ──────────────────────────────
REST_CELL_V = 3.70
REST_CELL_T = 25.0

# ── Networking ─────────────────────────────────────────────────────────────
TELEMETRY_PORT = 9000

# ── Backlight (Raspberry Pi 7" DSI panel) ──────────────────────────────────
BACKLIGHT_PATHS = (
    "/sys/class/backlight/rpi_backlight/brightness",
    "/sys/class/backlight/10-0045/brightness",
    "/sys/class/backlight/backlight/brightness",
)

APP_NAME = "Accelerons Electric BMS"
APP_VERSION = "v21"
