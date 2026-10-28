"""
ui/cellgrid.py — painted pack grids.

The old page put a styled QLabel behind every cell (147 of them) and called
setStyleSheet() on each one ten times a second. These widgets draw the same
information in a single paintEvent, and skip even that when no displayed digit
has changed.
"""

from PyQt5.QtCore import Qt, QRectF, QEvent
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QSizePolicy, QWidget

from core.config import CELLS_PER_SEGMENT, NTC_PER_SEGMENT, SEGMENTS
from ui.helpers import cell_v_status, set_scaled_height, temp_status
from ui.theme import Color, TM
from ui.tokens import MONO_QFONT

_GAP = 4.0
_HEADER = 16.0


def _blend(base, over, amount):
    return QColor(
        int(base.red() + (over.red() - base.red()) * amount),
        int(base.green() + (over.green() - base.green()) * amount),
        int(base.blue() + (over.blue() - base.blue()) * amount),
    )


def _cell_paint(voltage):
    status = cell_v_status(voltage)
    fg = QColor(Color.status(status))
    tint = QColor(Color.tint(status))
    if status == "ok":
        # Inside the healthy band, lean warmer as the cell approaches the top.
        amount = max(0.0, min(1.0, (voltage - 3.55) / 0.35)) * 0.55
        tint = _blend(QColor(Color.CARD_HI), tint, 0.30 + amount)
    return tint, fg


def _temp_paint(temperature):
    status = temp_status(temperature)
    if status == "ok":
        # A flat fill hides the gradient that matters on a thermal page, so
        # healthy sensors still warm towards amber across the working range.
        amount = max(0.0, min(1.0, (temperature - 26.0) / 16.0)) * 0.55
        return _blend(QColor(Color.CARD_HI), QColor(Color.tint("warn")), amount), QColor(Color.TEXT_2)
    return QColor(Color.tint(status)), QColor(Color.status(status))


class _Grid(QWidget):
    """Shared geometry: one column per segment, N rows of boxes, top header."""

    ROWS = 1
    TAG = "C%d"
    HAS_HEADER = True
    BASE_ROW_H = None

    def __init__(self, parent=None, has_header=None):
        super().__init__(parent)
        self._values = ()
        self._marks = (-1, -1)
        self.has_header = self.HAS_HEADER if has_header is None else has_header
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.update_geometry()

    def update_geometry(self):
        header_h = _HEADER if self.has_header else 0.0
        if self.BASE_ROW_H is not None:
            row_h = int(round(self.BASE_ROW_H * TM.font_scale))
            self.setMinimumHeight(int(header_h + self.ROWS * row_h + _GAP * (self.ROWS - 1)))
        else:
            self.setMinimumHeight(int(header_h + self.ROWS * 18))

    def paintEvent(self, _event):
        if not self._values:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        header_h = _HEADER if self.has_header else 0.0
        box_w = (self.width() - _GAP * (SEGMENTS - 1)) / SEGMENTS
        if self.BASE_ROW_H is not None:
            min_row_h = int(round(self.BASE_ROW_H * TM.font_scale))
            avail = self.height() - header_h - _GAP * (self.ROWS - 1)
            box_h = max(min_row_h, avail / self.ROWS)
        else:
            box_h = (self.height() - header_h - _GAP * (self.ROWS - 1)) / self.ROWS

        tag_font = QFont(MONO_QFONT)
        tag_font.setStyleHint(QFont.Monospace)
        tag_font.setFamilies(["JetBrains Mono", "DejaVu Sans Mono", "Consolas", "monospace"])
        tag_font.setPixelSize(max(8, min(10, int(box_h * 0.40))))
        value_font = QFont(MONO_QFONT)
        value_font.setStyleHint(QFont.Monospace)
        value_font.setFamilies(["JetBrains Mono", "DejaVu Sans Mono", "Consolas", "monospace"])
        value_font.setPixelSize(max(10, min(13, int(box_h * 0.48))))
        value_font.setBold(True)

        if self.has_header:
            painter.setFont(tag_font)
            painter.setPen(QPen(QColor(Color.TEXT_3)))
            for segment in range(SEGMENTS):
                head = QRectF(segment * (box_w + _GAP), 0, box_w, _HEADER)
                painter.drawText(head, Qt.AlignCenter, "SEG %d" % (segment + 1))

        for index, value in enumerate(self._values):
            segment, row = divmod(index, self.ROWS)
            box = QRectF(segment * (box_w + _GAP), header_h + row * (box_h + _GAP), box_w, box_h)
            bg, fg = self.paint_for(value)
            self._draw_box(painter, box, bg, fg, index)
            self._draw_text(painter, box, tag_font, value_font, fg,
                            self.TAG % (row + 1), self.format(value))

        if self.hasFocus():
            cyan = QColor("#00E5FF" if TM.is_dark else "#0284C7")
            painter.setPen(QPen(cyan, 3.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 6, 6)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.update()

    def _draw_box(self, painter, box, bg, fg, index):
        high, low = self._marks
        painter.setBrush(bg)
        if index == high:
            painter.setPen(QPen(QColor(Color.ACCENT), 2))
        elif index == low:
            painter.setPen(QPen(QColor(Color.SPEED), 2))
        else:
            edge = QColor(fg)
            edge.setAlpha(70)
            painter.setPen(QPen(edge, 1))
        painter.drawRoundedRect(box, 4, 4)

    @staticmethod
    def _draw_text(painter, box, tag_font, value_font, fg, tag, value):
        faded = QColor(fg)
        faded.setAlpha(160)
        painter.setPen(QPen(faded))
        painter.setFont(tag_font)
        painter.drawText(box.adjusted(4, 0, -4, 0), Qt.AlignLeft | Qt.AlignVCenter, tag)
        painter.setPen(QPen(fg))
        painter.setFont(value_font)
        painter.drawText(box.adjusted(4, 0, -4, 0), Qt.AlignRight | Qt.AlignVCenter, value)


class SegmentHeader(QWidget):
    """Pinned column header for segment grids."""

    def __init__(self, scroll_area=None, parent=None):
        super().__init__(parent)
        self.scroll_area = scroll_area
        self.setFixedHeight(int(_HEADER))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if scroll_area is not None:
            scroll_area.viewport().installEventFilter(self)

    def eventFilter(self, watched, event):
        if self.scroll_area and watched == self.scroll_area.viewport():
            if event.type() == QEvent.Resize:
                self.update()
        return super().eventFilter(watched, event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        vw = self.scroll_area.viewport().width() if self.scroll_area else self.width()
        box_w = (vw - _GAP * (SEGMENTS - 1)) / SEGMENTS

        tag_font = QFont(MONO_QFONT)
        tag_font.setStyleHint(QFont.Monospace)
        tag_font.setFamilies(["JetBrains Mono", "DejaVu Sans Mono", "Consolas", "monospace"])
        tag_font.setPixelSize(10)
        painter.setFont(tag_font)
        painter.setPen(QPen(QColor(Color.TEXT_3)))
        for segment in range(SEGMENTS):
            head = QRectF(segment * (box_w + _GAP), 0, box_w, _HEADER)
            painter.drawText(head, Qt.AlignCenter, "SEG %d" % (segment + 1))


class CellGrid(_Grid):
    """All 98 cell voltages: segments across, cells down."""

    ROWS = CELLS_PER_SEGMENT
    TAG = "C%02d"
    BASE_ROW_H = None
    HAS_HEADER = False

    def set_data(self, engine):
        values = tuple(round(cell.voltage, 3)
                       for module in engine.modules for cell in module.cells)
        marks = (self._locate(engine.vmax_location), self._locate(engine.vmin_location))
        if values == self._values and marks == self._marks:
            return
        self._values, self._marks = values, marks
        self.update()

    @staticmethod
    def _locate(location):
        try:
            segment = int(location[1:location.index("C")]) - 1
            cell = int(location[location.index("C") + 1:]) - 1
        except (ValueError, IndexError):
            return -1
        return segment * CELLS_PER_SEGMENT + cell

    paint_for = staticmethod(_cell_paint)

    @staticmethod
    def format(value):
        return "%.3f" % value


class TempGrid(_Grid):
    """All 49 NTCs: segments across, sensors down."""

    ROWS = NTC_PER_SEGMENT
    TAG = "T%d"

    def set_data(self, engine):
        values = tuple(
            round((module.cells[2 * i].temperature + module.cells[2 * i + 1].temperature) / 2.0, 1)
            for module in engine.modules for i in range(NTC_PER_SEGMENT)
        )
        if values == self._values:
            return
        self._values = values
        self.update()

    paint_for = staticmethod(_temp_paint)

    @staticmethod
    def format(value):
        return "%.0f°" % value


class SegmentHealthBar(QWidget):
    """Seven chips: segment tag, average volts, hot spot, tinted by health."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = ()
        set_scaled_height(self, "SMALL", 3.2, 48)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_data(self, stats):
        rows = tuple((s.health, round(s.avg_v, 3), round(s.max_t), round(s.delta_v, 3))
                     for s in stats)
        if rows == self._rows:
            return
        self._rows = rows
        self.update()

    def paintEvent(self, _event):
        if not self._rows:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        count = len(self._rows)
        width = (self.width() - _GAP * (count - 1)) / count
        height = float(self.height())

        tag_font = QFont(MONO_QFONT)
        tag_font.setPixelSize(max(10, int(height * 0.20)))
        tag_font.setBold(True)
        value_font = QFont(MONO_QFONT)
        value_font.setPixelSize(max(12, int(height * 0.27)))
        value_font.setBold(True)

        for index, (health, avg_v, max_t, delta_v) in enumerate(self._rows):
            box = QRectF(index * (width + _GAP), 0.0, width, height - 1)
            fg = QColor(Color.status(health))
            painter.setBrush(QColor(Color.CARD_HI) if health == "ok"
                             else QColor(Color.tint(health)))
            edge = QColor(fg)
            edge.setAlpha(110 if health == "ok" else 220)
            painter.setPen(QPen(edge, 1.5))
            painter.drawRoundedRect(box, 6, 6)

            painter.setFont(tag_font)
            painter.setPen(QPen(QColor(Color.TEXT_3)))
            painter.drawText(box.adjusted(8, 4, -8, 0), Qt.AlignLeft | Qt.AlignTop,
                             "SEG %d" % (index + 1))
            painter.drawText(box.adjusted(8, 4, -8, 0), Qt.AlignRight | Qt.AlignTop,
                             "%d°C" % max_t)
            painter.setFont(value_font)
            painter.setPen(QPen(QColor(Color.TEXT) if health == "ok" else fg))
            painter.drawText(box.adjusted(8, 0, -8, -3), Qt.AlignLeft | Qt.AlignBottom,
                             "%.3f V" % avg_v)
            painter.setFont(tag_font)
            painter.setPen(QPen(QColor(Color.TEXT_2)))
            painter.drawText(box.adjusted(8, 0, -8, -4), Qt.AlignRight | Qt.AlignBottom,
                             "Δ %.0f mV" % (delta_v * 1000))

        if self.hasFocus():
            cyan = QColor("#00E5FF" if TM.is_dark else "#0284C7")
            painter.setPen(QPen(cyan, 3.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.update()
