"""
main.py — Accelerons Electric BMS dashboard.

PyQt5 · 1024x600 · Raspberry Pi 4 with the 7" DSI panel.

Two shells share one 10 Hz loop: a driver HUD and the engineer console. Only
the visible page is refreshed, pages are built the first time they are opened,
and nothing re-applies a stylesheet unless a preference actually changed.
"""

import datetime
import os
import sys
import traceback

os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "0")
os.environ.setdefault("DISPLAY", ":0")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

try:
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QCursor, QFont, QKeySequence
    from PyQt5.QtWidgets import (
        QAction, QApplication, QMainWindow, QStackedWidget, QVBoxLayout, QWidget,
    )
except ImportError:
    sys.exit("[BMS] PyQt5 is missing. Run:  bash install.sh")

from core import backlight
from core.config import (
    APP_NAME, APP_VERSION, CRASH_LOG, FULLSCREEN, SCREEN_H, SCREEN_W, TICK_MS,
)
from core.engine import DataEngine
from core.recorder import Recorder
from pages import (
    DriverPage, LogsPage, OverviewPage, SegmentDetailsPage, SetupPage, TrendsPage,
)
from ui.chrome import NavBar, SelectorHUD, StatusStrip
from ui.helpers import restyle_tree
from ui.keyboard_navigation import FiveKeyNavigation
from ui.theme import DRIVER, ENGINEER, TM, stylesheet

PAGE_BUILDERS = (OverviewPage, SegmentDetailsPage, TrendsPage, LogsPage, SetupPage)


def log_crash(context, error):
    """Never let the crash logger be the thing that kills the dashboard."""
    try:
        if os.path.exists(CRASH_LOG) and os.path.getsize(CRASH_LOG) > 1_000_000:
            os.replace(CRASH_LOG, CRASH_LOG + ".1")
        # utf-8 explicitly: tracebacks quote UI strings that carry °C and Δ,
        # which a cp1252 default encoding would raise on — inside the handler.
        with open(CRASH_LOG, "a", encoding="utf-8", errors="replace") as handle:
            handle.write("\n" + "=" * 70 + "\n[%s] %s\n"
                         % (datetime.datetime.now().isoformat(timespec="seconds"), context))
            handle.write("".join(traceback.format_exception(
                type(error), error, error.__traceback__)))
    except Exception:
        pass


def _excepthook(kind, value, tb):
    log_crash("uncaught exception", value)
    traceback.print_exception(kind, value, tb)


sys.excepthook = _excepthook


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("%s — %s" % (APP_NAME, APP_VERSION))
        self.setFixedSize(SCREEN_W, SCREEN_H)

        self.engine = DataEngine()
        self.recorder = Recorder(self.engine)
        self._pages = {}
        self._driver = None
        self._current_index = 0
        self._keyboard_tab_index = 0

        backlight.set_max()
        self._build()
        self._keyboard_navigation = FiveKeyNavigation(self)
        QApplication.instance().installEventFilter(self._keyboard_navigation)
        self.apply_theme()
        self.set_mode(TM.mode)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.tick)
        self._timer.start(TICK_MS)

    # ── shells ─────────────────────────────────────────────────────────────
    def _build(self):
        self._shells = QStackedWidget()
        self.setCentralWidget(self._shells)

        self._driver_host = QWidget()
        driver_layout = QVBoxLayout(self._driver_host)
        driver_layout.setContentsMargins(0, 0, 0, 0)
        self._shells.addWidget(self._driver_host)

        console = QWidget()
        column = QVBoxLayout(console)
        column.setContentsMargins(10, 8, 10, 0)
        column.setSpacing(8)

        self.strip = StatusStrip()
        column.addWidget(self.strip)

        self.stack = QStackedWidget()
        column.addWidget(self.stack, 1)

        self.selector_hud = SelectorHUD()
        column.addWidget(self.selector_hud)

        self.nav = NavBar()
        self.nav.page_changed.connect(self.show_page)
        self.nav.driver_requested.connect(lambda: self.set_mode(DRIVER))
        column.addWidget(self.nav)
        self._shells.addWidget(console)

        self._shortcut("F1", lambda: self.set_mode(
            ENGINEER if self._shells.currentIndex() == 0 else DRIVER))
        self._shortcut("F11", self._toggle_fullscreen)
        self._shortcut("Ctrl+Q", self.close)

    def _shortcut(self, keys, slot):
        action = QAction(self)
        action.setShortcut(QKeySequence(keys))
        action.triggered.connect(slot)
        self.addAction(action)

    def _toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def _active_modal(self):
        return QApplication.activeModalWidget()

    def keyboard_move_tab(self, delta):
        """Select a tab without opening it; Enter commits the selection."""
        self._keyboard_tab_index = (self._keyboard_tab_index + delta) % len(PAGE_BUILDERS)
        self.nav.select_silently(self._keyboard_tab_index)
        # Force a clear visible focus ring on the selected tab button.
        self.nav._buttons[self._keyboard_tab_index].setFocus(Qt.OtherFocusReason)

    def keyboard_activate_tab(self):
        target_tab = self._keyboard_tab_index
        if self._shells.currentIndex() != 1:
            self._shells.setCurrentIndex(1)
            if TM.mode != ENGINEER:
                TM.mode = ENGINEER
                TM.save()
        self.show_page(target_tab)

    def set_mode_from_keyboard_engineering(self):
        """Driver-mode Right Arrow enters Engineering Mode at the current tab."""
        self.set_mode(ENGINEER)
        self.show_page(self._current_index)

    def update_selector_hud(self, focus_widget):
        if not hasattr(self, "selector_hud") or not hasattr(self, "_keyboard_navigation"):
            return
        loc, action = self._keyboard_navigation.describe_widget(focus_widget)
        self.selector_hud.update_info(loc, action)
        if hasattr(self, "_driver") and self._driver and hasattr(self._driver, "selector_hud"):
            self._driver.selector_hud.update_info(loc, action)

    def set_mode(self, mode):
        if mode == DRIVER:
            if self._driver is None:
                self._driver = DriverPage(self.engine)
                self._driver.engineer_requested.connect(lambda: self.set_mode(ENGINEER))
                self._driver_host.layout().addWidget(self._driver)
            self._shells.setCurrentIndex(0)
            if hasattr(self, "_keyboard_navigation"):
                controls = self._keyboard_navigation._controls(self._driver)
                if controls:
                    controls[0].setFocus(Qt.TabFocusReason)
        else:
            self.show_page(self._current_index)
            self._shells.setCurrentIndex(1)
        if TM.mode != mode:
            TM.mode = mode
            TM.save()
        self.update_selector_hud(self.focusWidget())
        self.refresh_now()

    # ── pages ──────────────────────────────────────────────────────────────
    def show_page(self, index):
        page = self._pages.get(index)
        if page is None:
            page = self._build_page(index)
            self._pages[index] = page
            self.stack.addWidget(page)
        self._current_index = index
        self._keyboard_tab_index = index
        self.stack.setCurrentWidget(page)
        self.nav.select_silently(index)
        self.refresh_now()
        if hasattr(self, "_keyboard_navigation"):
            controls = self._keyboard_navigation._controls(page)
            if controls:
                controls[0].setFocus(Qt.TabFocusReason)
            elif hasattr(self, "nav") and self.nav and hasattr(self.nav, "_buttons") and len(self.nav._buttons) > index:
                self.nav._buttons[index].setFocus(Qt.TabFocusReason)
        self.update_selector_hud(self.focusWidget())

    def _build_page(self, index):
        builder = PAGE_BUILDERS[index]
        if builder is LogsPage:
            return LogsPage(self.engine, self.recorder)
        page = builder(self.engine)
        if builder is SetupPage:
            page.theme_changed.connect(self.apply_theme)
            page.brightness_changed.connect(self.apply_brightness)
            page.mode_changed.connect(self.set_mode)
            page.restart_requested.connect(self.restart)
        return page

    # ── theme ──────────────────────────────────────────────────────────────
    def apply_theme(self):
        self.setStyleSheet(stylesheet())
        restyle_tree(self)
        self.apply_brightness(TM.brightness)
        self.strip.restyle()
        for page in list(self._pages.values()) + ([self._driver] if self._driver else []):
            page.on_theme_changed()
        self.refresh_now()

    def apply_brightness(self, fraction):
        # Real panel first; window opacity is only the desktop fallback.
        if not backlight.apply(fraction):
            self.setWindowOpacity(max(0.45, fraction))

    # ── loop ───────────────────────────────────────────────────────────────
    def tick(self):
        try:
            self.engine.tick()
            self.recorder.record()
            self._refresh_visible()
        except Exception as error:
            log_crash("tick frame", error)

    def refresh_now(self):
        try:
            self._refresh_visible()
        except Exception as error:
            log_crash("forced refresh", error)

    def _refresh_visible(self):
        if self._shells.currentIndex() == 0:
            if self._driver is not None:
                self._driver.refresh(self.engine, self.recorder)
            return
        self.strip.refresh(self.engine, self.recorder)
        page = self.stack.currentWidget()
        if page is not None:
            page.refresh(self.engine, self.recorder)

    # ── shutdown ───────────────────────────────────────────────────────────
    def _cleanup(self):
        try:
            self._timer.stop()
            self.recorder.stop()
            self.engine.stream.stop()
        except Exception as error:
            log_crash("cleanup", error)

    def closeEvent(self, event):
        self._cleanup()
        event.accept()

    def restart(self):
        self._cleanup()
        os.execv(sys.executable, [sys.executable] + sys.argv)


def main():
    QApplication.setAttribute(Qt.AA_DisableHighDpiScaling)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setFont(QFont(TM.font_family, 10))

    window = MainWindow()
    if FULLSCREEN:
        window.setWindowFlags(Qt.FramelessWindowHint)
        window.showFullScreen()
        app.setOverrideCursor(QCursor(Qt.BlankCursor))
    else:
        screen = app.primaryScreen().geometry()
        window.move((screen.width() - SCREEN_W) // 2, (screen.height() - SCREEN_H) // 2)
        window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
