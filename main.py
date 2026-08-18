"""
main.py — Accelerons Electric BMS
PyQt5 · 1024×600 · Raspberry Pi 7" · v20

"""

import datetime
import os
import sys
import traceback

# ─────────────────────────────────────────────
# Environment setup (important for Raspberry Pi)
# ─────────────────────────────────────────────
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "0")
os.environ.setdefault("DISPLAY", ":0")
os.environ.setdefault("QT_QUICK_BACKEND", "software")  # faster on RPi (no GL fallback)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
LOG_DIR = os.path.join(BASE_DIR, "logs")
CRASH_LOG = os.path.join(LOG_DIR, "crash.log")
os.makedirs(LOG_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# Dependency check — fails fast with ONE clear message.
# Actual installation is install.sh's job (apt for PyQt5/numpy, pip only
# for pyqtgraph) so there's never a conflicting second install path.
# ─────────────────────────────────────────────
try:
    import PyQt5  # noqa: F401
except ImportError:
    print(
        "[BMS] PyQt5 is not installed. Run install.sh first:\n"
        "      bash install.sh\n"
        "(main.py intentionally does not auto-install packages anymore — "
        "see the module docstring for why.)",
        file=sys.stderr,
    )
    sys.exit(1)

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QCursor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QMessageBox,
)

from theme import TM, get_qss
from ev import DataEngine, Logger
from widgets import NavBar, CriticalAlertOverlay
from pages.dashboard import DashboardPage
from pages.cells import HeatmapPage
from pages.pack import PackDiagramPage
from pages.analytics import AnalyticsPage
from pages.storage import StoragePage
from pages.settings import SettingsPage, APP_VERSION

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
FULLSCREEN = False
WIN_W = 1024
WIN_H = 600


# ─────────────────────────────────────────────
# Crash logging — used by both the tick-loop try/except and the global
# excepthook below, so every uncaught error ends up in one place.
# ─────────────────────────────────────────────
def _log_crash(context: str, exc: BaseException):
    try:
        with open(CRASH_LOG, "a") as f:
            f.write("\n" + "=" * 70 + "\n")
            f.write("[%s] %s\n" % (datetime.datetime.now().isoformat(timespec="seconds"), context))
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    except Exception:
        pass  # logging the crash should never itself crash the app


def _global_excepthook(exc_type, exc_value, exc_tb):
    """Catches anything NOT already caught by the tick-loop try/except
    (e.g. a bug in a button click handler). Logs it and keeps the app
    alive rather than letting Python's default hook tear it down."""
    _log_crash("uncaught exception", exc_value)
    traceback.print_exception(exc_type, exc_value, exc_tb)


sys.excepthook = _global_excepthook


# ─────────────────────────────────────────────
# RPi display init
# ─────────────────────────────────────────────
def _init_rpi_backlight():
    """Set backlight to maximum on launch. Silent no-op on non-RPi."""
    import subprocess  # local import: only ever needed on RPi hardware

    candidates = [
        "/sys/class/backlight/rpi_backlight/brightness",
        "/sys/class/backlight/10-0045/brightness",
        "/sys/class/backlight/backlight/brightness",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                open(path, "w").write("255\n")
            except PermissionError:
                try:
                    subprocess.run(["sudo", "tee", path], input=b"255\n", capture_output=True, timeout=2)
                except Exception:
                    pass
            return


# ─────────────────────────────────────────────
# Main Window
# ─────────────────────────────────────────────
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Accelerons Electric — BMS Monitor " + APP_VERSION)
        self.setFixedSize(WIN_W, WIN_H)

        self.engine = DataEngine()
        self.logger = Logger(self.engine)

        self.current_page = 0
        self.alert_snoozed = False

        _init_rpi_backlight()
        self.build_ui()
        self.apply_theme()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(100)  # 10 Hz

    # ─────────────────────────────────────────
    # UI Construction
    # ─────────────────────────────────────────
    def build_ui(self):
        container = QWidget()
        self.setCentralWidget(container)

        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()

        self.dashboard = DashboardPage(save_cb=self.save_snapshot, logger=self.logger)
        self.heatmap = HeatmapPage(self.engine)
        self.pack = PackDiagramPage(self.engine)
        self.analytics = AnalyticsPage(self.engine)
        self.storage = StoragePage(self.logger, self.engine)
        self.settings = SettingsPage(engine=self.engine)

        self.settings.theme_changed.connect(self.apply_theme)
        self.settings.restart_requested.connect(self.restart_app)

        self.pages = [
            self.dashboard, self.heatmap, self.pack,
            self.analytics, self.storage, self.settings,
        ]
        for page in self.pages:
            self.stack.addWidget(page)

        self.navbar = NavBar()
        self.navbar.page_changed.connect(self.on_nav)

        root.addWidget(self.stack, 1)
        root.addWidget(self.navbar)

        self.alert_overlay = CriticalAlertOverlay(parent=container)
        self.alert_overlay.setGeometry(0, 0, WIN_W, WIN_H)
        self.alert_overlay.dismissed.connect(self.on_alert_dismissed)

    # ─────────────────────────────────────────
    # Navigation
    # ─────────────────────────────────────────
    def on_nav(self, index):
        self.current_page = index
        self.stack.setCurrentIndex(index)

    # ─────────────────────────────────────────
    # Theme
    # ─────────────────────────────────────────
    def apply_theme(self):
        self.setStyleSheet(get_qss())
        self.setWindowOpacity(TM.brightness)
        self.dashboard.logo_widget.update()
        self.dashboard._gauge.update()
        self.analytics.update_graph_theme()

    # ─────────────────────────────────────────
    # Main Update Loop — crash-isolated (v20)
    # ─────────────────────────────────────────
    def tick(self):
        try:
            self.engine.tick()
            self.logger.record()

            page = self.pages[self.current_page]
            page.refresh(self.engine, self.logger)

            if self.engine.has_critical and not self.alert_snoozed:
                self.alert_overlay.show_faults(self.engine.active_faults)
                self.alert_overlay.raise_()
            elif not self.engine.has_critical:
                self.alert_snoozed = False
                self.alert_overlay.hide_alert()

        except Exception as e:
            # One bad frame must never take the whole dashboard down mid
            # session. Log it, skip this frame, keep the 10Hz timer going.
            _log_crash("tick() frame error", e)

    # ─────────────────────────────────────────
    # Alert handling
    # ─────────────────────────────────────────
    def on_alert_dismissed(self):
        self.alert_snoozed = True

    # ─────────────────────────────────────────
    # Save snapshot
    # ─────────────────────────────────────────
    def save_snapshot(self):
        try:
            path = self.logger.save_snapshot()
            QMessageBox.information(self, "Saved", "Snapshot saved:\n" + path)
            self.storage._refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # ─────────────────────────────────────────
    # Shutdown / restart (v20)
    # ─────────────────────────────────────────
    def closeEvent(self, event):
        """Make sure nothing is lost if the app is closed mid-session."""
        try:
            self.logger.stop()  # flushes any buffered rows
            self.engine.stop_streaming()
        except Exception as e:
            _log_crash("closeEvent cleanup error", e)
        event.accept()

    def restart_app(self):
        """Manual restart from the Settings page: flush/stop cleanly, then
        re-exec the current process with the same interpreter and argv.
        Crash-triggered restarts are handled separately by the systemd
        service (see install.sh) — this is only for the in-app button."""
        try:
            self.logger.stop()
            self.engine.stop_streaming()
        except Exception as e:
            _log_crash("restart_app cleanup error", e)
        os.execv(sys.executable, [sys.executable] + sys.argv)


# ─────────────────────────────────────────────
# Application Entry
# ─────────────────────────────────────────────
def main():
    QApplication.setAttribute(Qt.AA_DisableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, False)
    app = QApplication(sys.argv)

    app.setApplicationName("Accelerons Electric BMS")
    app.setFont(QFont("Inter", 11))

    window = MainWindow()

    if FULLSCREEN:
        window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        window.showFullScreen()
        app.setOverrideCursor(QCursor(Qt.BlankCursor))
    else:
        screen = app.primaryScreen().geometry()
        window.move((screen.width() - WIN_W) // 2, (screen.height() - WIN_H) // 2)
        window.show()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
