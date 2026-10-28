"""ui/keyboard_navigation.py — Five-key directional navigation for the dashboard.

Designed specifically for physical five-button hardware control:
    - UP, DOWN, LEFT, RIGHT, and OK (Enter / Return).

Provides true 2D spatial navigation across all screens, prevents focus traps in
tables and scroll areas, and makes switching between the Driver HUD and Engineer
console seamless and intuitive.
"""

from PyQt5.QtCore import QEvent, QObject, Qt
from PyQt5.QtWidgets import (
    QApplication, QAbstractButton, QComboBox, QDoubleSpinBox,
    QLabel, QLineEdit, QListWidget, QScrollArea, QSlider, QSpinBox,
    QTableWidget, QTreeWidget, QWidget,
)

from ui.cellgrid import SegmentHealthBar
from ui.faultpanel import FaultPanel
from ui.theme import ENGINEER
from ui.widgets import MetricTile

CONTROL_TYPES = (
    QAbstractButton, QComboBox, QSlider, QSpinBox,
    QDoubleSpinBox, QTableWidget, QListWidget, QTreeWidget,
    QLineEdit, QScrollArea, MetricTile, SegmentHealthBar, FaultPanel,
)
ARROWS = (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down)
ENTER_KEYS = (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space)


class FiveKeyNavigation(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.adjusting = False
        app = QApplication.instance()
        if app is not None:
            app.focusChanged.connect(self._on_focus_changed)

    def _on_focus_changed(self, old, new):
        if hasattr(self.window, "update_selector_hud"):
            self.window.update_selector_hud(new)

    def describe_widget(self, widget):
        if widget is None:
            page = getattr(self.window, "stack", None)
            curr = page.currentWidget() if page else None
            pname = type(curr).__name__.replace("Page", "").upper() if curr else "OVERVIEW"
            return (pname, "Use Arrow Keys to navigate")

        name = widget.objectName()
        text = getattr(widget, "text", lambda: "")().strip()

        # 1. Driver HUD buttons
        if name == "driver_feed":
            active = widget.property("active") == "true" or "STOP" in text.upper()
            return ("DRIVER HUD › TELEMETRY", "Press OK: Stop Telemetry Transmission" if active else "Press OK: Start Telemetry Stream")
        if name == "driver_mode":
            return ("DRIVER HUD › CONSOLE", "Press OK: Switch to Engineering Console")
        if name == "mode" or text.startswith("◀"):
            return ("NAVBAR › DRIVER HUD", "Press OK: Return to Driver Screen")

        # 2. Navbar tab buttons
        nav = getattr(self.window, "nav", None)
        if nav and widget in getattr(nav, "_buttons", []):
            tab_names = {
                "OVERVIEW": "Open Pack Overview & Key Metrics",
                "SEGMENTS": "Open Cell Voltages & Temperatures Matrix",
                "TRENDS": "Open Real-time Telemetry Trends",
                "LOGS": "Open Data Recording & Session Logs",
                "SETUP": "Open System Settings & Calibration",
            }
            action = tab_names.get(text, f"Open {text} Page")
            return (f"NAVBAR › {text} TAB", f"Press OK: {action}")

        # 3. Trends Page Channels & Time Windows
        channel_names = {
            "PACK": "Plot Pack Voltage (V)",
            "CURRENT": "Plot Current Draw / Charge (A)",
            "POWER": "Plot Pack Power (kW)",
            "SOC": "Plot State of Charge (%)",
            "TEMP": "Plot Hottest Cell Temp (°C)",
            "ΔV": "Plot Cell Voltage Spread (V)",
            "1m": "Set Chart Window to 1 Minute",
            "5m": "Set Chart Window to 5 Minutes",
            "10m": "Set Chart Window to 10 Minutes",
            "30m": "Set Chart Window to 30 Minutes",
        }
        if name == "pill" and text in channel_names:
            action = channel_names[text]
            group = "TIME WINDOW" if text.endswith("m") else "CHANNEL"
            return (f"TRENDS › {group}: {text}", f"Press OK: {action}")

        # 4. Sliders (e.g. Setup page)
        if isinstance(widget, QSlider):
            parent = widget.parentWidget()
            lbl = "SLIDER"
            if parent:
                for child in parent.findChildren(QLabel):
                    txt = child.text().strip()
                    if txt and not txt.endswith("%") and not txt.endswith("x") and not txt.startswith("1024"):
                        lbl = txt
                        break
            if self.adjusting:
                return (f"SETUP › ADJUSTING {lbl.upper()}", "Use Left/Right to change value  |  Press OK: Lock In")
            return (f"SETUP › {lbl.upper()}", "Press OK to adjust with Arrow Keys")

        # 5. Buttons in Setup / Logs / Driver
        if isinstance(widget, QAbstractButton):
            u_text = text.upper()
            if "DARK" in u_text or "LIGHT" in u_text or "SWITCH" in u_text:
                return ("SETUP › DISPLAY THEME", "Press OK: Toggle Dark / Light Theme")
            if text in ("SM", "MD", "LG", "XL"):
                scale_labels = {"SM": "0.9x Small", "MD": "1.0x Normal", "LG": "1.15x Large", "XL": "1.3x Extra Large"}
                return (f"SETUP › TEXT SCALE ({text})", f"Press OK: Set Font Size to {scale_labels.get(text, text)}")
            if text in ("DRIVER", "ENGINEER"):
                return (f"SETUP › STARTUP MODE ({text})", f"Press OK: Set Default Startup Mode to {text}")
            if "RESTART" in u_text:
                return ("SETUP › SYSTEM", "Press OK: Restart BMS Dashboard")
            if "GO TO DRIVER" in u_text or "DRIVER VIEW" in u_text:
                return ("SETUP › NAVIGATION", "Press OK: Switch to Driver HUD")
            if "SIMULATION" in u_text:
                return ("SETUP › DATA SOURCE", "Press OK: Toggle Synthetic Telemetry Simulation")
            if "VIEW" in u_text:
                return ("LOGS › FILE BROWSER", "Press OK: Inspect Selected CSV Telemetry Log")
            if "EXPORT" in u_text:
                return ("LOGS › FILE BROWSER", "Press OK: Export Selected Log to USB / Disk")
            if "RELOAD" in u_text:
                return ("LOGS › FILE BROWSER", "Press OK: Refresh Session Log List")
            if "CLEAR" in u_text or "DELETE" in u_text:
                return ("LOGS › MAINTENANCE", "Press OK: Delete Selected Log File")
            if "START" in u_text and ("LOG" in u_text or "REC" in u_text or "●" in u_text):
                return ("LOGS › RECORDER", "Press OK: Start Session Recording")
            if "STOP" in u_text and ("LOG" in u_text or "REC" in u_text or "●" in u_text):
                return ("LOGS › RECORDER", "Press OK: Stop Session Recording")
            if "SNAPSHOT" in u_text:
                return ("LOGS › RECORDER", "Press OK: Save Instant CSV Snapshot")
            if "START FEED" in u_text or "STOP FEED" in u_text:
                return ("LOGS › TELEMETRY FEED", f"Press OK: {text}")
            if "BACK" in u_text:
                return ("LOGS › VIEWER", "Press OK: Return to Session Log List")
            if text:
                return (f"SELECTOR › {text}", f"Press OK: Activate {text}")

        # 6. Dropdown Combo Box
        if isinstance(widget, QComboBox):
            curr_text = widget.currentText()
            return (f"SETUP › TYPEFACE ({curr_text})", "Press OK: Open Font Dropdown Menu")

        # 6. ScrollArea / CellGrid
        if isinstance(widget, QScrollArea):
            return ("SEGMENTS › CELL MATRIX", "Use Up/Down/Left/Right to inspect Cell Matrix")

        # 7. Tables (Logs browser & viewer)
        if isinstance(widget, QTableWidget):
            row = widget.currentRow()
            row_info = f"Row {row + 1}" if row >= 0 else "Select Log"
            return (f"LOGS › SESSION TABLE ({row_info})", "Use Up/Down to navigate  |  Press OK: Inspect Details")

        # 8. Metric Tiles (Overview & Driver)
        if isinstance(widget, MetricTile):
            title = ""
            for lbl in widget.findChildren(QLabel):
                if lbl.property("role") == "title":
                    title = lbl.text().strip()
                    break
            val = getattr(widget, "value", None)
            val_text = val.text().strip() if val else ""
            prefix = "DRIVER" if self.window._shells.currentIndex() == 0 else "OVERVIEW"
            if "SPREAD" in title:
                return (f"{prefix} › {title}: {val_text}", "Press OK: Open Cell Voltages & Temperatures Matrix")
            return (f"{prefix} › {title}: {val_text}", f"Press OK: View {title} in Trends Chart")

        # 9. Health Bar & Faults & Special Cards
        if isinstance(widget, SegmentHealthBar):
            return ("OVERVIEW › SEGMENTS HEALTH BAR", "Press OK: Open Cell Voltages & Temperatures Matrix")
        if isinstance(widget, FaultPanel):
            return ("OVERVIEW › ACTIVE FAULTS PANEL", "Press OK: Open Session Logs & Fault Diagnostics")
        if getattr(widget, "objectName", lambda: "")() == "card":
            curr = self.window.stack.currentWidget() if hasattr(self.window, "stack") else None
            if curr and widget is getattr(curr, "charge_card", None):
                return ("OVERVIEW › BATTERY CHARGE CARD", "Press OK: View State of Charge in Trends Chart")
            if curr and widget is getattr(curr, "summary_card", None):
                return ("SEGMENTS › PACK SUMMARY READOUTS", "Use Down arrow to inspect Cell Voltages Matrix")
            if curr and widget is getattr(curr, "temp_card", None):
                return ("SEGMENTS › TEMPERATURE SENSORS MATRIX", "Press OK: View Temperatures in Trends Chart")

        return (f"CURRENT: {text or type(widget).__name__}", "Press OK to select")

    # ── Helpers ────────────────────────────────────────────────────────────
    def _dir_name(self, key):
        return {
            Qt.Key_Up: "up",
            Qt.Key_Down: "down",
            Qt.Key_Left: "left",
            Qt.Key_Right: "right",
        }.get(key)

    def _get_all_nav_buttons(self):
        nav = getattr(self.window, "nav", None)
        if nav is None:
            return []
        if hasattr(nav, "all_buttons"):
            return nav.all_buttons
        driver_btn = getattr(nav, "driver_button", None)
        tabs = getattr(nav, "_buttons", [])
        return ([driver_btn] if driver_btn else []) + list(tabs)

    def _controls(self, root):
        if root is None:
            return []
        from PyQt5.QtWidgets import QFrame
        candidates = []
        if isinstance(root, CONTROL_TYPES) or (isinstance(root, QFrame) and root.focusPolicy() == Qt.StrongFocus):
            candidates.append(root)
        candidates.extend(root.findChildren(CONTROL_TYPES))
        for frame in root.findChildren(QFrame):
            if frame.focusPolicy() == Qt.StrongFocus and frame not in candidates:
                candidates.append(frame)
        controls = []
        for widget in candidates:
            if (widget.window().isVisible() and not widget.isVisible()) or widget.isHidden() or not widget.isEnabled():
                continue
            if isinstance(widget, QLineEdit) and widget.isReadOnly():
                continue
            # Exclude internal dropdown popup views of QComboBox
            curr = widget
            is_combo_popup = False
            while curr is not None:
                if isinstance(curr, QComboBox) or "Combo" in type(curr).__name__:
                    if curr is not widget:
                        is_combo_popup = True
                        break
                curr = curr.parent()
            if is_combo_popup:
                continue
            widget.setFocusPolicy(Qt.StrongFocus)
            controls.append(widget)
        # Unique list preserved in order
        controls = list(dict.fromkeys(controls))
        controls.sort(key=lambda w: (
            w.mapToGlobal(w.rect().center()).y(),
            w.mapToGlobal(w.rect().center()).x(),
        ))
        return controls

    def _get_scroll_target(self, focus):
        if isinstance(focus, QScrollArea):
            return focus
        if focus and isinstance(focus.parent(), QWidget) and isinstance(focus.parent().parent(), QScrollArea):
            return focus.parent().parent()
        return None

    def _find_best_target_2d(self, controls, current, direction):
        if not controls:
            return None
        if current is None or current not in controls:
            return controls[0]

        c_rect = current.rect()
        c_tl = current.mapToGlobal(c_rect.topLeft())
        c_br = current.mapToGlobal(c_rect.bottomRight())
        c_center = current.mapToGlobal(c_rect.center())
        cx, cy = c_center.x(), c_center.y()

        best_target = None
        best_score = float("inf")

        for candidate in controls:
            if candidate is current:
                continue
            cand_rect = candidate.rect()
            cand_tl = candidate.mapToGlobal(cand_rect.topLeft())
            cand_br = candidate.mapToGlobal(cand_rect.bottomRight())
            cand_center = candidate.mapToGlobal(cand_rect.center())
            kx, ky = cand_center.x(), cand_center.y()

            if direction == "right":
                if kx > cx + 4 and cand_br.x() > c_tl.x() + 4:
                    dx = max(0, cand_tl.x() - c_br.x()) if cand_tl.x() >= c_br.x() else (kx - cx)
                    overlap_y = max(0, min(c_br.y(), cand_br.y()) - max(c_tl.y(), cand_tl.y()))
                    dy = 0 if overlap_y > 4 else abs(ky - cy)
                    score = dx + 3.0 * dy
                    if score < best_score:
                        best_score = score
                        best_target = candidate

            elif direction == "left":
                if kx < cx - 4 and cand_tl.x() < c_br.x() - 4:
                    dx = max(0, c_tl.x() - cand_br.x()) if c_tl.x() >= cand_br.x() else (cx - kx)
                    overlap_y = max(0, min(c_br.y(), cand_br.y()) - max(c_tl.y(), cand_tl.y()))
                    dy = 0 if overlap_y > 4 else abs(ky - cy)
                    score = dx + 3.0 * dy
                    if score < best_score:
                        best_score = score
                        best_target = candidate

            elif direction == "down":
                if ky > cy + 4 and cand_br.y() > c_tl.y() + 4:
                    dy = max(0, cand_tl.y() - c_br.y()) if cand_tl.y() >= c_br.y() else (ky - cy)
                    overlap_x = max(0, min(c_br.x(), cand_br.x()) - max(c_tl.x(), cand_tl.x()))
                    dx = 0 if overlap_x > 4 else abs(kx - cx)
                    score = dy + 3.0 * dx
                    if score < best_score:
                        best_score = score
                        best_target = candidate

            elif direction == "up":
                if ky < cy - 4 and cand_tl.y() < c_br.y() - 4:
                    dy = max(0, c_tl.y() - cand_br.y()) if c_tl.y() >= cand_br.y() else (cy - ky)
                    overlap_x = max(0, min(c_br.x(), cand_br.x()) - max(c_tl.x(), cand_tl.x()))
                    dx = 0 if overlap_x > 4 else abs(kx - cx)
                    score = dy + 3.0 * dx
                    if score < best_score:
                        best_score = score
                        best_target = candidate

        return best_target

    def _activate(self, focus, root=None):
        if focus is None:
            return
        if isinstance(focus, QAbstractButton):
            if focus.isEnabled():
                focus.click()
        elif isinstance(focus, QComboBox):
            focus.showPopup()
        elif isinstance(focus, QSlider):
            self.adjusting = not self.adjusting
        elif isinstance(focus, QTableWidget):
            curr = focus
            while curr is not None:
                if hasattr(curr, "_view_selected"):
                    curr._view_selected()
                    return
                curr = curr.parentWidget()
        elif isinstance(focus, (QListWidget, QTreeWidget, QSpinBox, QDoubleSpinBox, QLineEdit)):
            focus.setFocus()
        elif isinstance(focus, MetricTile):
            if self.window._shells.currentIndex() == 0:
                self.window.set_mode(ENGINEER)
            title = ""
            for lbl in focus.findChildren(QLabel):
                if lbl.property("role") == "title":
                    title = lbl.text().strip()
                    break
            if "SPREAD" in title:
                self.window.show_page(1)
            else:
                channel_map = {"PACK": 0, "CURRENT": 1, "POWER": 2, "HOT SPOT": 4, "AVG TEMP": 4, "MAX TEMP": 4}
                ch = channel_map.get(title, 0)
                self.window.show_page(2)
                trends = self.window.stack.currentWidget()
                if hasattr(trends, "_select_channel"):
                    trends._select_channel(ch)
        elif isinstance(focus, SegmentHealthBar):
            self.window.show_page(1)
        elif isinstance(focus, FaultPanel):
            self.window.show_page(3)
        elif getattr(focus, "objectName", lambda: "")() == "card":
            curr = self.window.stack.currentWidget() if hasattr(self.window, "stack") else None
            if curr and focus is getattr(curr, "charge_card", None):
                self.window.show_page(2)
                trends = self.window.stack.currentWidget()
                if hasattr(trends, "_select_channel"):
                    trends._select_channel(3)  # SOC channel
            elif curr and focus is getattr(curr, "temp_card", None):
                self.window.show_page(2)
                trends = self.window.stack.currentWidget()
                if hasattr(trends, "_select_channel"):
                    trends._select_channel(4)  # TEMP channel
            elif curr and focus is getattr(curr, "summary_card", None):
                cell_scroll = getattr(curr, "cell_scroll", None)
                if cell_scroll:
                    cell_scroll.setFocus()

    # ── Event Filter ───────────────────────────────────────────────────────
    def eventFilter(self, watched, event):
        if event.type() != QEvent.KeyPress:
            return False
        key = event.key()
        if key not in ARROWS + ENTER_KEYS:
            return False
        if event.isAutoRepeat() and key in ENTER_KEYS:
            return True

        # Native popup lists (like combobox views) need the arrows and Enter key
        if QApplication.activePopupWidget() is not None:
            return False
        focus = self.window.focusWidget()
        if isinstance(focus, QComboBox) and focus.view().isVisible():
            return False

        # Modals
        modal = QApplication.activeModalWidget()
        if modal is not None:
            if key in ARROWS:
                target = self._find_best_target_2d(self._controls(modal), focus, self._dir_name(key))
                if target:
                    target.setFocus(Qt.TabFocusReason)
                return True
            self._activate(focus, modal)
            return True

        # ── Driver Mode ────────────────────────────────────────────────────
        if self.window._shells.currentIndex() == 0:
            driver = self.window._driver
            if driver is None:
                return False
            controls = self._controls(driver)
            if not controls:
                return False

            if key in ARROWS:
                # If focus is on the ENGINEER button and user presses Right, switch to Engineer mode
                if focus and focus.objectName() in ("driver_mode", "mode") and key == Qt.Key_Right:
                    self.window.set_mode("engineer")
                    return True
                target = self._find_best_target_2d(controls, focus, self._dir_name(key))
                if target:
                    target.setFocus(Qt.TabFocusReason)
                elif controls and focus not in controls:
                    controls[0].setFocus(Qt.TabFocusReason)
                return True

            if key in ENTER_KEYS:
                if focus is None and controls:
                    controls[0].setFocus(Qt.TabFocusReason)
                else:
                    self._activate(focus, driver)
                return True

        # ── Engineer Mode ──────────────────────────────────────────────────
        nav_buttons = self._get_all_nav_buttons()
        on_nav = focus in nav_buttons
        page = self.window.stack.currentWidget()
        page_controls = self._controls(page)

        # 1. Slider adjustment mode
        if self.adjusting and isinstance(focus, QSlider):
            if key in ENTER_KEYS:
                self.adjusting = False
                focus.setToolTip("Press OK to adjust")
                self._on_focus_changed(None, focus)
                return True
            if key in ARROWS:
                step = max(1, focus.singleStep())
                delta = step if key in (Qt.Key_Up, Qt.Key_Right) else -step
                focus.setValue(focus.value() + delta)
                return True

        # 2. Scroll area boundary handling (e.g. CellGrid on Segments page)
        scroll_target = self._get_scroll_target(focus)
        if scroll_target is not None and key in (Qt.Key_Up, Qt.Key_Down):
            bar = scroll_target.verticalScrollBar()
            step = bar.singleStep() or 24
            if key == Qt.Key_Down:
                if bar.value() < bar.maximum():
                    bar.setValue(min(bar.maximum(), bar.value() + step))
                    return True
                # At the bottom boundary: fall through to 2D navigation (e.g. down to bottom navbar)
            elif key == Qt.Key_Up:
                if bar.value() > bar.minimum():
                    bar.setValue(max(bar.minimum(), bar.value() - step))
                    return True
                # At the top boundary: fall through to 2D navigation (e.g. up to top controls)

        # 3. Table boundary handling (e.g. Logs browser and viewer)
        if isinstance(focus, QTableWidget) and key in (Qt.Key_Up, Qt.Key_Down):
            row = focus.currentRow()
            total_rows = focus.rowCount()
            if key == Qt.Key_Down:
                if row < total_rows - 1:
                    focus.selectRow(row + 1)
                    return True
                # At the bottom-most row: fall through to 2D navigation (e.g. down to bottom navbar)
            elif key == Qt.Key_Up:
                if row > 0:
                    focus.selectRow(row - 1)
                    return True
                # At the top row: fall through to 2D navigation (e.g. up to buttons above)

        # 4. On Bottom Navbar
        if on_nav:
            if key in (Qt.Key_Left, Qt.Key_Right):
                idx = nav_buttons.index(focus)
                step = 1 if key == Qt.Key_Right else -1
                next_btn = nav_buttons[(idx + step) % len(nav_buttons)]
                next_btn.setFocus(Qt.OtherFocusReason)
                # If moving between tab buttons, preview/select silently
                if next_btn in self.window.nav._buttons:
                    tab_idx = self.window.nav._buttons.index(next_btn)
                    self.window._keyboard_tab_index = tab_idx
                    self.window.nav.select_silently(tab_idx)
                return True

            if key == Qt.Key_Up:
                # UP from navbar opens the tab (if needed) and moves focus into page controls
                if focus in self.window.nav._buttons:
                    tab_idx = self.window.nav._buttons.index(focus)
                    if self.window._current_index != tab_idx:
                        self.window.show_page(tab_idx)
                curr_page = self.window.stack.currentWidget()
                curr_controls = self._controls(curr_page)
                if curr_controls:
                    target = self._find_best_target_2d(curr_controls, focus, "up")
                    if not target:
                        target = curr_controls[-1]
                    target.setFocus(Qt.TabFocusReason)
                return True

            if key in ENTER_KEYS:
                # OK on driver button switches mode; OK on tab activates page
                driver_btn = getattr(self.window.nav, "driver_button", None)
                if focus == driver_btn or focus == nav_buttons[0] and focus not in self.window.nav._buttons:
                    self.window.set_mode("driver")
                elif focus in self.window.nav._buttons:
                    tab_idx = self.window.nav._buttons.index(focus)
                    self.window._keyboard_tab_index = tab_idx
                    self.window.keyboard_activate_tab()
                return True

        # 5. On Page Controls
        if key in ARROWS:
            direction = self._dir_name(key)
            target = self._find_best_target_2d(page_controls, focus, direction)
            if target:
                target.setFocus(Qt.TabFocusReason)
                return True

            # If moving DOWN and no control below, move smoothly to the navbar
            if key == Qt.Key_Down:
                if nav_buttons:
                    cx = focus.mapToGlobal(focus.rect().center()).x() if focus else 0
                    closest = min(nav_buttons, key=lambda b: abs(b.mapToGlobal(b.rect().center()).x() - cx))
                    closest.setFocus(Qt.TabFocusReason)
                    return True

            # If moving UP and no target, stay on top control
            if key == Qt.Key_Up:
                return True

            # Left/Right fallback within page if no direct geometric target
            if key == Qt.Key_Right and page_controls:
                idx = page_controls.index(focus) if focus in page_controls else -1
                if idx < len(page_controls) - 1:
                    page_controls[idx + 1].setFocus(Qt.TabFocusReason)
                    return True
            elif key == Qt.Key_Left and page_controls:
                idx = page_controls.index(focus) if focus in page_controls else len(page_controls)
                if idx > 0:
                    page_controls[idx - 1].setFocus(Qt.TabFocusReason)
                    return True

            return True

        if key in ENTER_KEYS:
            if focus is None:
                if page_controls:
                    page_controls[0].setFocus(Qt.TabFocusReason)
                elif nav_buttons:
                    nav_buttons[0].setFocus(Qt.TabFocusReason)
                return True
            if isinstance(focus, QSlider):
                self.adjusting = not self.adjusting
                focus.setToolTip(
                    "Adjustment mode: arrows change value; OK finishes"
                    if self.adjusting else "Press OK to adjust"
                )
                self._on_focus_changed(None, focus)
                return True
            else:
                self._activate(focus, page)
            return True

        return False
