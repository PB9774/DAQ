# v19 → v20 Changelog

## 1. Random data removed from everywhere, replaced with an explicit toggle
- `DataEngine` no longer generates random data by default. On every launch
  it starts in **idle mode**: safe, deterministic rest values (3.70V/25°C
  per cell, 0 speed, 0 current), no faults, CAN status = 🔴 **NO SIGNAL**.
- New **Settings → Data Source** card with an Idle / Simulated toggle.
  Switching to Simulated calls `DataEngine.set_simulate(True)` — CAN status
  turns 🟠 **SIMULATED** (still not green — it's still not a real pack).
- Also found and fixed a **second, hidden random source**: `_SegPanel`'s 7
  NTC temperature boxes were independently jittered with `random.gauss()`
  on every refresh, regardless of the engine's data mode. These now derive
  from the real (or simulated) per-cell temperatures instead — averaging
  each adjacent cell pair — so nothing on screen is fabricated outside the
  one explicit toggle.
- Found a **third bug while fixing idle mode**: SOC starts at 0 and the
  idle rest-state didn't set it, so idle mode was falsely showing a
  "SOC CRIT 0%" fault. Fixed — fault detection now only runs when there's
  an actual signal (simulated today, real CAN later); idle mode shows no
  faults at all, which is honest since there's nothing to evaluate.

## 2. apt + pip PyQt5 conflict removed
- `main.py`'s runtime `ensure_package()` (which pip-installed PyQt5 if the
  import failed) is gone. `install.sh` is now the **only** install path —
  apt for PyQt5/numpy, pip only for pyqtgraph. `main.py` now just checks
  the import and fails fast with one clear message pointing at
  `install.sh` if something's missing, instead of trying to fetch packages
  over the network at launch.

## 3. Crash isolation
- The 10Hz `tick()` loop is wrapped in try/except — one bad frame gets
  logged to `logs/crash.log` (with full traceback) and skipped; the timer
  keeps running instead of the whole dashboard dying mid-session.
- A global `sys.excepthook` catches anything outside the tick loop (e.g. a
  bug in a button handler) and logs it the same way.
- Bonus: added `MainWindow.closeEvent()` so an active recording gets
  flushed to disk before the window closes — v19 could lose up to 99
  buffered rows if the app was closed mid-recording.

## 4. Dead code removed (YAGNI pass)
- Deleted `boot_screen.py` — fully built but never imported anywhere.
- Removed the unused `FaultRecord` dataclass from `ev.py` (faults were
  always plain tuples; this was never instantiated).
- Removed unused imports: `QPropertyAnimation`, `QEasingCurve`, `Font`,
  `SEM` in `widgets.py`; an unused local variable in `theme.py`.
- Removed a redundant `import subprocess` inside `_init_rpi_backlight()`
  (already imported where needed).
- Cleared stray leftover debug commentary embedded in `SevenSegDisplay`'s
  paint code.
- Also fixed a genuine bug found while cleaning up: the Dashboard's
  "Save Snapshot" button called `logger.save()`, which never existed —
  clicking it threw `AttributeError`. Added `Logger.save_snapshot()`,
  sharing its row-building logic with `record()` via a new
  `_build_row()` helper (reuse, not duplication).

## 5. Fault list no longer truncated
- `DataEngine._detect_faults()` no longer caps the list at 14
  (`faults[:14]` is gone) — every active fault is kept.
- To keep that performant at 10Hz with potentially 50+ simultaneous
  faults, `_FaultPanel` (now in `pages/common.py`) was rewritten to be
  **incremental**: it keeps one persistent row widget per fault code and
  only adds/removes rows when the *set* of active codes changes; existing
  rows just get their text updated in place instead of the whole panel
  being torn down and rebuilt every 100ms.

## 6. Restart support
- **Settings → System → Restart App Now**: confirms, flushes the logger,
  stops TCP streaming, then re-execs the process (`os.execv`).
- **Crash auto-restart**: `install.sh` now offers (opt-in prompt) to
  install `accelerons-bms.service`, a systemd unit with
  `Restart=on-failure` — if the app crashes on the car's Pi, systemd
  brings it back automatically. Manual runs and the systemd service
  shouldn't run at the same time (noted in the installer's output).

## 7. Version string fixed
- Was `v19` in file headers but `v1.9` on the Settings → About page.
  Now consistently **v20** everywhere.

## 8. Readability refactor
- Split the 900-line `pages.py` into one file per page under `pages/`:
  `dashboard.py`, `cells.py`, `pack.py`, `analytics.py`, `storage.py`,
  `settings.py`, plus `pages/common.py` for the shared helpers/widgets
  used by more than one page (`_FaultPanel`, `_SegPanel`, style helpers).
- Expanded dense one-liners into multi-line, commented code throughout
  the touched files. No architecture or behavior changes beyond what's
  listed above — same class names, same public methods, same file names
  for `main.py` / `theme.py` / `widgets.py` / `ev.py`.
- Along the way, fixed a real fragility bug in `PackDiagramPage`: v19
  looked up each segment's labels positionally via
  `sw.findChildren(QLabel)[1]/[2]/[3]`, which silently breaks if the
  widget tree ever changes. Each segment tile now holds direct references
  to its own labels instead.

## 9. Refresh-loop performance pass (10 Hz on the Pi)
The dashboard repaints at 10 Hz, and every page's `refresh()` was rebuilding
and **re-applying a stylesheet to almost every visible widget on every
frame** — even when nothing had changed. `QWidget.setStyleSheet()` forces Qt
to re-parse the CSS and repolish the widget subtree, so this was by far the
biggest CPU cost on the Raspberry Pi. On the Cells page that was ~161
`setStyleSheet` calls **per frame** (7 panels × 14 cells + 7 NTC + badges).

- **Memoised UI updates.** New `set_ss()` / `set_text()` helpers in
  `pages/common.py` cache the last value applied to each widget and skip the
  call when it's unchanged. All the hot `refresh()` paths (dashboard, cells,
  pack, the shared `TelemetryStrip`, `_SegPanel`, `_FaultRow`) now go through
  them. Measured on the Cells page: **161 → 0** style re-applies per frame
  when telemetry is steady (idle / pit / cruising), and still ~45 % fewer in
  the worst-case fully-noisy simulation. Pixel output is identical.
- **Single-pass aggregation.** `DataEngine._aggregate()` now computes the
  per-module averages, Tmax and health, plus the global hottest/coldest-cell
  extremes, in the one cell walk it already does each tick. `mod_avg_v()`,
  `mod_avg_t()`, `mod_tmax()`, `mod_health()` and `cell_global_extremes()`
  just read those cached values instead of each re-walking all 98 cells —
  removing ~5 redundant full passes per frame. Verified numerically identical
  to the old per-call implementations across 300 ticks of simulated data.
- **Logo stops repainting.** `LogoWidget` re-ran a `SmoothTransformation`
  rescale of the PNG on every paint, and `TelemetryStrip.refresh()` forced
  that paint 10×/sec. The scaled pixmap is now cached (rebuilt only on
  resize) and the per-tick `update()` is gone — the logo never changes.
- **Analytics re-plots on new data only.** The charts page rebuilt its numpy
  arrays and re-fed pyqtgraph every tick, but history only grows ~1×/sec, so
  9 of every 10 redraws were identical. It now skips the work unless a new
  sample arrived or the time window changed (keyed on the newest sample's
  timestamp, so it keeps working after the history deque fills).

No behaviour, layout, colour, threshold or public-API changes — same class
names and method signatures throughout; this pass is purely about not
repeating work whose result hasn't changed.

## Not changed
Everything not listed above is unchanged: the 3-tier fault thresholds,
the TCP telemetry streaming protocol, the theme/typography/brightness
system, the RPi backlight handling, the analytics charts, and the log
viewer/exporter all work exactly as they did in v19.

## Still open (flagged in the original review, not part of this pass)
- Real CAN bus integration (`python-can` + `cantools`) — `DataEngine` is
  still simulate-or-idle only; wiring in real hardware is the next step.
- Alarm thresholds are still hardcoded in `ev.py` rather than
  user-configurable from the UI.
- No session playback/scrub — `StoragePage` can view a CSV as a static
  table but can't replay it through the live widgets.
