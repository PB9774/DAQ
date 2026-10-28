# Accelerons Electric — BMS Dashboard

A PyQt5 telemetry dashboard for the Accelerons Electric Formula Student
car's battery pack: 7 segments, 14 cells per segment, 7 temperature
sensors per segment. Built to run on a 1024×600 7" Raspberry Pi display
in the car, and on a laptop for pit-side monitoring and development.

**Version:** v21

---

## Architecture

The app separates telemetry and recording from the Qt interface. A single
engine owns pack state, while the main window updates only the visible screen.

```
main.py       Qt app, screen navigation, and update loop
core/         telemetry engine, data sources, faults, recording, streaming
pages/        driver, overview, segments, trends, logs, and setup screens
ui/           shared gauges, grids, widgets, theme, and navigation
assets/       team logos
```

**Directory layout:**

```
main.py
core/     config.py · engine.py · faults.py · sources.py · recorder.py · stream.py
pages/    driver.py · overview.py · cells.py · trends.py · logs.py · setup.py
ui/       chrome.py · cellgrid.py · faultpanel.py · gauges.py · helpers.py
          theme.py · tokens.py · widgets.py
install.sh
requirements.txt
```

**Why it's built this way:**

- `DataEngine` never imports PyQt — it's pure data/logic, which means the
  fault-detection math could be unit-tested with no GUI involved at all
  (not currently done — see the roadmap below).
- Only the **currently visible** page gets `.refresh()` called each tick.
  This is the main reason the app can run live graphs, a 98-cell grid,
  and a fault panel at 10Hz on a Raspberry Pi without lagging — none of
  that work happens for pages you're not looking at.
- Pages read `DataEngine` through a fixed set of properties
  (`pack_voltage`, `delta_v`, `tmax`, `faults`, etc.) rather than reaching
  into its internals.

---

## Screens

### 1. Engineer Overview (`pages/overview.py`)

- State of charge and remaining energy
- Pack voltage, current, power, cell spread and temperature metrics
- Health summary for all seven segments
- Active faults, ordered by severity

### 2. Segment Details (`pages/cells.py`)

- Cell voltage and temperature grids side by side, grouped by segment
- Highest and lowest cell readings, pack average and off-band count
- Pack-wide temperature maximum, minimum, average and spread

### 3. Trends (`pages/trends.py`)

- Selectable voltage, current, power, SOC, temperature and cell-spread charts
- Adjustable 1 / 5 / 10 / 30 minute window
- Auto-scaled chart and current/minimum/maximum/average values

### 4. Logs (`pages/logs.py`)

- Start/stop CSV recording and save snapshots
- Start/stop the TCP telemetry feed (JSON lines, port 9000)
- Browse, inspect and export recorded CSV files

### 5. Setup (`pages/setup.py`)

- Theme, font scale, typeface and brightness preferences
- Idle/simulated data source and startup mode
- Restart action and system information

---

## Bugs to be fixed

These are open issues in the current codebase — not yet fixed.

1. **Dismissing a critical alert can silence a _different_, later fault.**
   `MainWindow.tick()` tracks dismissal with one flag,
   `self.alert_snoozed`, which only resets to `False` once
   `engine.has_critical` goes back to `False` entirely. If Fault A (crit)
   triggers the full-screen alert and you dismiss it, then Fault B (a
   completely different, unrelated crit fault) appears while A is still
   active, the overlay will **not** reappear — because the flag doesn't
   reset until every critical fault has cleared, not just the one you
   saw. `alert_snoozed` needs to track _which_ fault codes were
   dismissed, not just "was anything dismissed."

2. **Dragging the brightness slider can stutter the UI.**
   `_set_bright()` fires on every single `valueChanged` tick while
   dragging (not just on release), and each call can end up inside
   `_rpi_set_brightness()`'s `subprocess.run(["sudo", "tee", ...],
timeout=2)` fallback path if the udev permission isn't active yet.
   That's a blocking call on the GUI thread, up to 2 seconds long, that
   can fire many times during one slider drag. Should debounce (only
   apply on release, e.g. via `sliderReleased` instead of
   `valueChanged`) or move the write off the GUI thread.

3. **Rapid stop/start of TCP streaming can hit a bind race.**
   `stop_streaming()` just sets `self._streaming = False`; the actual
   server loop only notices and closes its socket on its next `accept()`
   timeout, which can take up to 1 second (`srv.settimeout(1.0)`). If a
   user stops and immediately restarts streaming from the Storage page
   within that window, the new server thread can fail to bind because
   the old one hasn't released the port yet. Needs either a join-with-
   timeout on stop, or disabling the Start button for ~1s after Stop.

4. **Threshold numbers are duplicated with no single source of truth.**
   The exact cutoffs for "this voltage/temperature counts as warn/crit"
   are written independently in three places: `DataEngine._detect_faults()`,
   `DataEngine.mod_health()`, and `pages/common.py`'s `_cell_colors()` /
   `_ntc_ss()`. They agree today, but nothing enforces that — editing one
   without the other two silently makes the fault list disagree with what
   the screen is colored.

5. **No real CAN bus connection.** `DataEngine` currently only supports
   Idle (rest-state) and Simulated modes — there is no code path that
   reads actual pack data. This isn't a small bug, it's the app's central
   remaining gap; everything else is refinement on top of fake data.

---

## Optimization roadmap — making this race-ready

In rough priority order:

1. **Wire in real CAN.** Add a `python-can` + `cantools` based reader
   once a DBC file exists for the BMS/inverter. Run it on a background
   `QThread` (not the GUI thread) so a slow or noisy bus can never stall
   the display — `DataEngine` already has a clean property boundary
   (`pack_voltage`, `delta_v`, etc.) that the rest of the app reads
   through, so this should only require changes inside `ev.py`.

2. **Centralize thresholds into one config.** Pull every warn/crit cutoff
   out of the three files listed in bug #4 above into a single
   `thresholds.py` (or a JSON file editable without touching code). This
   also opens the door to making thresholds tunable from the Settings
   page for different cell chemistries.

3. **Add tests for fault detection.** `DataEngine._detect_faults()` and
   `_aggregate()` don't depend on PyQt at all — they're pure functions of
   state in, fault list out. A small pytest suite (feed it known cell
   voltages/temperatures, assert the right faults come out) would catch
   regressions in genuinely safety-relevant code, and costs very little
   given how decoupled this logic already is from the UI.

4. **Fix the alert-dismissal tracking (bug #1).** Given this is the
   feature responsible for making sure a driver never misses a critical
   warning, it's worth prioritizing above general polish.

5. **Debounce brightness/contrast sliders (bug #2).** Small fix, real
   payoff — nobody should feel the UI stutter while adjusting a slider on
   a race weekend.

6. **Make thresholds and alarm behavior configurable without a rebuild.**
   Once centralized (#2), expose them in Settings so the electrical team
   can calibrate for the actual cell chemistry without redeploying code
   trackside.

7. **Add a lightweight watchdog for tick() duration, not just
   exceptions.** The current crash isolation catches errors but not
   _slowness_ — if a future change (e.g. a slow CAN read) makes one tick
   take 500ms instead of 10ms, nothing currently notices or logs it. A
   simple "warn if a tick takes longer than N ms" check would catch
   performance regressions before they show up as dropped frames on
   track.

8. **Session playback.** The Storage page can open a past CSV as a
   static table but can't replay it through the live dashboard widgets.
   Useful for post-session debrief — "show me what the pack looked like
   at the moment this fault fired" is currently a manual CSV read, not a
   feature.

9. **Basic access control on the TCP telemetry stream.** Right now
   anyone on the same network can connect to port 9000 and read live
   pack data with no authentication. Low risk in a closed pit network,
   but worth a simple shared-token check before this is ever used on
   public event WiFi.

## Five-key hardware navigation (UP, DOWN, LEFT, RIGHT, OK)

The entire dashboard can be operated with five physical buttons (UP, DOWN, LEFT, RIGHT, and OK / Enter):

- **2D Spatial Navigation:** Arrow keys move focus spatially across the screen to the nearest control in that direction. Left/Right moves within rows; Up/Down moves between control tiers and columns.
- **Bottom Navigation Bar:**
  - **Left / Right:** smoothly cycle through `◀ DRIVER` and the five tabs (`OVERVIEW`, `SEGMENTS`, `TRENDS`, `LOGS`, `SETUP`).
  - **OK (Enter):** opens the selected tab (or returns to Driver mode from `◀ DRIVER`) and focuses the page controls.
  - **Up:** immediately activates the tab and moves focus up into the page controls directly above that tab.
- **Scroll Areas & Tables:**
  - In the cell voltage grid, **Up / Down** scrolls the view; reaching the bottom passes focus down to the navbar without getting stuck.
  - In log tables, **Up / Down** navigates rows; pressing Up on row 0 or Down on the last row smoothly exits to adjacent controls.
  - **OK:** on the file browser table opens the selected log file in the viewer.
- **Sliders & Dropdowns:**
  - Highlighting a slider and pressing **OK** enters adjustment mode (Left/Down decreases, Right/Up increases). Pressing **OK** again commits the value.
  - Highlighting a dropdown and pressing **OK** opens its selection popup.
- **Driver Mode:**
  - **Left / Right:** moves between `START TELEMETRY` and `ENGINEER ▶`.
  - **OK:** activates the focused button (toggles telemetry streaming or enters Engineer mode).
  - Pressing **Right** while focused on `ENGINEER ▶` also enters Engineer mode.
