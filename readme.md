# Accelerons Electric — BMS Dashboard

A PyQt5 telemetry dashboard for the Accelerons Electric Formula Student
car's battery pack: 7 segments, 14 cells per segment, 7 temperature
sensors per segment. Built to run on a 1024×600 7" Raspberry Pi display
in the car, and on a laptop for pit-side monitoring and development.

**Version:** v20

---

## Architecture

The codebase is a layered pipeline: one class owns all the data, one
class owns the update loop, and everything else just reads and displays.

```
┌─────────────────────────────────────────────────────────┐
│  ev.py                                                    │
│  DataEngine — owns every number in the app                │
│  Logger     — owns every file written to disk              │
└─────────────────────────────────────────────────────────┘
                          │  .tick() every 100ms
                          ▼
┌─────────────────────────────────────────────────────────┐
│  main.py                                                   │
│  MainWindow — owns the QTimer, the page stack, and the      │
│  nav bar. tick() pulls fresh data from DataEngine and        │
│  hands it to whichever page is currently on screen.           │
└─────────────────────────────────────────────────────────┘
                          │  page.refresh(engine, logger)
                          ▼
┌─────────────────────────────────────────────────────────┐
│  pages/  — six screens, one file each                       │
│  dashboard.py · cells.py · pack.py · analytics.py ·           │
│  storage.py · settings.py                                      │
│                                                                   │
│  pages/common.py — shared pieces used by more than one page       │
│  (_FaultPanel, _SegPanel, color/style helpers)                     │
└─────────────────────────────────────────────────────────┘
                          │  built from
                          ▼
┌─────────────────────────────────────────────────────────┐
│  widgets.py  — general-purpose widgets, not page-specific    │
│  LogoWidget · SevenSegDisplay · TelemetryStrip · NavBar ·      │
│  CriticalAlertOverlay                                            │
│                                                                     │
│  theme.py — palette, font scale, brightness/contrast, QSS builder   │
└─────────────────────────────────────────────────────────┘
```

**Directory layout:**

```
main.py                   Entry point, MainWindow, tick loop, crash isolation
ev.py                     DataEngine (all state + fault detection) and Logger
theme.py                  Dark/light palettes, typography, brightness/contrast
widgets.py                Shared non-page widgets
install.sh                Raspberry Pi setup script
requirements.txt          Dev-machine pip dependencies

pages/
    common.py               Shared widgets used by 2+ pages
    dashboard.py             Page 1
    cells.py                  Page 2
    pack.py                    Page 3
    analytics.py                Page 4
    storage.py                   Page 5
    settings.py                   Page 6

assets/                   Team logo images
logs/                     CSVs, fault log, crash log (all generated at runtime)
```

**Why it's built this way:**
- `DataEngine` never imports PyQt — it's pure data/logic, which means the
  fault-detection math could be unit-tested with no GUI involved at all
  (not currently done — see the roadmap below).
- Only the **currently visible** page gets `.refresh()` called each tick.
  This is the main reason the app can run 5 live graphs, a 98-cell grid,
  and a fault panel at 10Hz on a Raspberry Pi without lagging — none of
  that work happens for pages you're not looking at.
- Pages read `DataEngine` through a fixed set of properties
  (`pack_voltage`, `delta_v`, `tmax`, `active_faults`, etc.) rather than
  reaching into its internals. That boundary is what will make swapping
  simulated data for real CAN data a change to one file (`ev.py`) instead
  of six.

---

## Screens

### 1. Dashboard (`pages/dashboard.py`)
**Motto:** *Everything you need in one glance — nothing you don't.*

**Purpose:** The screen a driver or pit crew member looks at 95% of the
time. Answers "is everything okay right now?" in under a second.

**Features:**
- Live speed on a hand-painted 7-segment display
- State of charge (SOC) as a number + colored bar
- Pack voltage and current
- ΔV — the gap between the highest and lowest cell voltage, the single
  most important pack-health number
- Highest/lowest temperature in the pack, and exactly which cell
- Per-segment health bars (all 7 segments, color-coded, at a glance)
- Live fault list, worst-first, color-coded by severity
- One-tap "Save Snapshot" button
- Header strip: clock, CAN status, sensor status, recording indicator,
  live tick rate

### 2. Cell Heatmap (`pages/cells.py`)
**Motto:** *No cell hides from view.*

**Purpose:** The zoomed-in screen — when the Dashboard says "something's
off," this is where you find out exactly which cell and by how much.

**Features:**
- All 98 individual cell voltages, color-coded green/yellow/red
- All 49 temperature sensors, color-coded the same way
- The single highest and lowest voltage cell highlighted with a border
- One panel per segment (7 total), each showing its own health badge
- A legend explaining the color coding
- Pack-wide Tmax/Tmin summary at the top

### 3. Pack Diagram (`pages/pack.py`)
**Motto:** *See the whole pack's health without hunting for numbers.*

**Purpose:** A simplified, zoomed-out version of the heatmap — for
quickly comparing all 7 segments against each other rather than staring
at 98 individual numbers.

**Features:**
- 7 segment tiles, laid out to mirror the physical pack
- Switchable coloring mode: by health, by average voltage, or by max
  temperature
- Per-segment average voltage, max temperature, and health badge
- One-line summary at the bottom ("All segments nominal" / "N critical,
  M warning segments")

### 4. Analytics (`pages/analytics.py`)
**Motto:** *Watch the trend, not just the moment.*

**Purpose:** Everything else on the app is "right now" — this screen is
"how did we get here?" Useful for spotting slow drift (e.g. one cell
creeping toward imbalance over a session) that a single glance would
never catch.

**Features:**
- 5 live charts: pack voltage + current (dual axis), SOC, power (kW),
  max cell temperature, and cell voltage imbalance (ΔV)
- Adjustable time window: 1 / 5 / 10 / 20 / 30 minutes
- Auto-scaling Y-axis per chart
- Tab-based switching between charts

### 5. Storage (`pages/storage.py`)
**Motto:** *Nothing recorded is nothing learned.*

**Purpose:** Turns the dashboard from "a screen you watch" into "a
record you can review." Also the bridge to a second machine watching the
same data live.

**Features:**
- Start/stop continuous CSV recording, with live duration + file size
- Start/stop a TCP telemetry stream (JSON lines, port 9000) for a second
  device to tap into live data
- Browse all past recordings and fault logs
- Open any CSV in a built-in table viewer
- Export any log file

### 6. Settings (`pages/settings.py`)
**Motto:** *Make the dashboard work the way your team works.*

**Purpose:** Everything about how the dashboard looks and behaves,
separated from everything about what it's showing — so the team can
tune it for the pit garage, the car, or a teammate's eyes without
touching any other screen.

**Features:**
- Dark / light theme toggle
- Font size (S/M/L) and font family
- Brightness (dims the Raspberry Pi's actual backlight) and contrast
- Data source toggle: Idle (no signal) / Simulated data — the only
  control in the whole app that turns test data on or off
- Manual "Restart App Now" button
- About panel: app name, version, team, department, institution

---

## Bugs to be fixed

These are open issues in the current codebase — not yet fixed.

1. **Dismissing a critical alert can silence a *different*, later fault.**
   `MainWindow.tick()` tracks dismissal with one flag,
   `self.alert_snoozed`, which only resets to `False` once
   `engine.has_critical` goes back to `False` entirely. If Fault A (crit)
   triggers the full-screen alert and you dismiss it, then Fault B (a
   completely different, unrelated crit fault) appears while A is still
   active, the overlay will **not** reappear — because the flag doesn't
   reset until every critical fault has cleared, not just the one you
   saw. `alert_snoozed` needs to track *which* fault codes were
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
   *slowness* — if a future change (e.g. a slow CAN read) makes one tick
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