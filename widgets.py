"""Shared dashboard widgets."""

import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from theme import TM, Color, MONO


class LogoWidget(QWidget):
    def __init__(self, height=30, parent=None):
        super().__init__(parent)
        self.setFixedSize(int(height * 9.2), height)
        self.setAttribute(Qt.WA_TranslucentBackground)

        base = os.path.dirname(os.path.abspath(__file__))
        self.logo = QPixmap()
        for name in ("logo1.png", "logo.png", "logo.jpg"):
            path = os.path.join(base, "assets", name)
            if os.path.isfile(path):
                self.logo = QPixmap(path)
                break

    def paintEvent(self, event):
        if self.logo.isNull():
            return
        from PyQt5.QtGui import QPainter

        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        scaled = self.logo.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter.drawPixmap(
            (self.width() - scaled.width()) // 2,
            (self.height() - scaled.height()) // 2,
            scaled,
        )


class TelemetryStrip(QFrame):
    """Compact live summary shared by the detail pages."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedHeight(48)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 10, 0)
        layout.setSpacing(0)

        self._logo = LogoWidget(height=30)
        layout.addWidget(self._logo)
        layout.addWidget(self._divider())

        speed = QWidget()
        speed_layout = QHBoxLayout(speed)
        speed_layout.setContentsMargins(8, 0, 8, 0)
        speed_layout.setSpacing(5)
        speed_layout.addWidget(self._label("SPEED", "title"))
        self._spd = QLabel("--")
        self._spd.setFixedWidth(52)
        speed_layout.addWidget(self._spd)
        speed_layout.addWidget(self._label("km/h", "unit"))
        layout.addWidget(speed)
        layout.addWidget(self._divider())

        soc = QWidget()
        soc.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        soc_layout = QHBoxLayout(soc)
        soc_layout.setContentsMargins(8, 2, 8, 2)
        soc_layout.setSpacing(7)
        soc_layout.addWidget(self._label("SOC", "title"))
        self._sv = QLabel("--%")
        self._sv.setFixedWidth(52)
        soc_layout.addWidget(self._sv)
        self._sbar = QProgressBar()
        self._sbar.setRange(0, 1000)
        self._sbar.setTextVisible(False)
        self._sbar.setFixedHeight(9)
        self._sbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        soc_layout.addWidget(self._sbar)
        layout.addWidget(soc)
        layout.addWidget(self._divider())

        self._fbadge = QLabel(" OK ")
        self._fbadge.setFixedHeight(26)
        self._fbadge.setMinimumWidth(42)
        self._fbadge.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._fbadge)
        layout.addWidget(self._divider())

        self._can = QLabel("CAN ✗ NO SIGNAL")
        layout.addWidget(self._can)
        layout.addWidget(self._divider())

        self._rec = QLabel("○ REC")
        layout.addWidget(self._rec)
        layout.addWidget(self._divider())

        self._hz = QLabel("10 Hz")
        layout.addWidget(self._hz)
        self._apply_base_styles()

    @staticmethod
    def _label(text, role):
        label = QLabel(text)
        label.setProperty("role", role)
        return label

    @staticmethod
    def _divider():
        divider = QFrame()
        divider.setFixedSize(1, 24)
        divider.setStyleSheet("background:" + Color.BORDER + ";")
        return divider

    def _apply_base_styles(self):
        self._spd.setStyleSheet(
            "font-size:24px;font-family:" + MONO + ";font-weight:900;"
            "background:transparent;border:none;"
        )
        self._sv.setStyleSheet(
            "font-size:22px;font-family:" + MONO + ";font-weight:900;"
            "background:transparent;border:none;"
        )
        self._can.setStyleSheet(
            "font-size:15px;font-weight:700;color:#EF4444;"
            "background:transparent;border:none;padding:0 6px;"
        )
        self._rec.setStyleSheet(
            "font-size:15px;font-weight:700;color:#404A5C;"
            "background:transparent;border:none;padding:0 6px;"
        )
        self._hz.setStyleSheet(
            "font-size:15px;font-weight:600;color:#8A97B0;"
            "background:transparent;border:none;padding:0 6px;"
        )

    def refresh(self, engine, logger=None):
        palette = TM.palette
        soc = engine.soc
        soc_color = palette["SOC_COL"] if soc > 40 else (Color.AMBER_BAR if soc > 20 else Color.RED)
        self._spd.setText("%.0f" % engine.speed)
        self._spd.setStyleSheet(
            "color:" + palette["SPEED_COL"] + ";font-size:24px;font-family:" + MONO + ";"
            "font-weight:900;background:transparent;border:none;"
        )
        self._sv.setText("%.0f%%" % soc)
        self._sv.setStyleSheet(
            "color:" + soc_color + ";font-size:22px;font-family:" + MONO + ";"
            "font-weight:900;background:transparent;border:none;"
        )
        self._sbar.setValue(int(soc * 10))
        self._sbar.setStyleSheet(
            "QProgressBar{background:" + palette["BG_PANEL"] + ";border:none;border-radius:2px;}"
            "QProgressBar::chunk{background:" + soc_color + ";border-radius:2px;}"
        )

        count = engine.fault_count
        if engine.has_critical:
            badge_color, badge_text = "#EF4444", " %d CRIT " % count
        elif count:
            badge_color, badge_text = "#D97706", " %d WARN " % count
        else:
            badge_color, badge_text = "#16A34A", " OK "
        self._fbadge.setText(badge_text)
        self._fbadge.setStyleSheet(
            "background:" + badge_color + ";color:#fff;border-radius:4px;"
            "font-size:15px;font-weight:700;padding:0 5px;"
        )

        can_color = "#22C55E" if engine.can_ok else "#EF4444"
        self._can.setText(("CAN ● " if engine.can_ok else "CAN ✗ ") + engine.can_status_text)
        self._can.setStyleSheet(
            "font-size:15px;font-weight:700;color:" + can_color + ";"
            "background:transparent;border:none;padding:0 6px;"
        )

        if logger and logger.is_active:
            self._rec.setText("● REC")
            self._rec.setStyleSheet(
                "font-size:15px;font-weight:700;color:#EF4444;"
                "background:transparent;border:none;padding:0 6px;"
            )
        else:
            self._rec.setText("○ REC")
            self._rec.setStyleSheet(
                "font-size:15px;font-weight:600;color:#404A5C;"
                "background:transparent;border:none;padding:0 6px;"
            )
        self._hz.setText("%.0f Hz" % engine.actual_hz)


class NavBar(QWidget):
    page_changed = pyqtSignal(int)
    _TABS = [("⬡", "Dash"), ("▦", "Cells"), ("⬡", "Pack"), ("∿", "Graphs"), ("🗂", "Logs"), ("⚙", "Config")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("nav_bar")
        self.setFixedHeight(64)
        self._buttons = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        for index, (icon, label) in enumerate(self._TABS):
            button = QPushButton(icon + "\n" + label)
            button.setObjectName("nav_btn")
            button.setCheckable(True)
            button.setFlat(True)
            button.setFont(QFont("Inter", 16))
            button.clicked.connect(lambda _, i=index: self._select(i))
            self._buttons.append(button)
            layout.addWidget(button, 1)
        self._select(0)

    def _select(self, index):
        for button_index, button in enumerate(self._buttons):
            button.setChecked(button_index == index)
        self.page_changed.emit(index)

    def set_page(self, index):
        for button_index, button in enumerate(self._buttons):
            button.setChecked(button_index == index)
