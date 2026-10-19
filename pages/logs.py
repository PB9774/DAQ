"""
pages/logs.py — recording, snapshots, the telemetry feed, and the log browser.
"""

import csv

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QMessageBox, QPushButton,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.config import TELEMETRY_PORT
from ui.helpers import card, label, set_ss, set_text
from ui.theme import Color

MAX_VIEW_ROWS = 2000


def _table(headers):
    table = QTableWidget()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.setShowGrid(False)
    return table


class LogsPage(QWidget):
    def __init__(self, engine, recorder, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._recorder = recorder
        self._paths = []
        self._open_path = None
        self._stream_live = None

        self._stack = QStackedWidget()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._stack)
        self._stack.addWidget(self._build_browser())
        self._stack.addWidget(self._build_viewer())
        self.reload()

    # ── browser ────────────────────────────────────────────────────────────
    def _build_browser(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(8, 8, 8, 8)
        column.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self._build_recording(), 1)
        row.addWidget(self._build_streaming(), 1)
        column.addLayout(row)

        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(label("RECORDED FILES", role="title"))
        self._count = label("0 files", role="caption")
        head.addWidget(self._count)
        head.addStretch()
        for text, slot in (("⟳  RELOAD", self.reload), ("VIEW", self._view_selected),
                           ("EXPORT", self._export_selected)):
            button = QPushButton(text)
            button.setObjectName("pill")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(slot)
            head.addWidget(button)
        column.addLayout(head)

        self._files = _table(["FILE", "SIZE", "MODIFIED"])
        self._files.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._files.doubleClicked.connect(self._view_selected)
        column.addWidget(self._files, 1)
        return page

    def _build_recording(self):
        frame, column = card(margins=(12, 8, 12, 8), spacing=6)
        column.addWidget(label("SESSION RECORDING", role="title"))

        self._rec_state = label("○  NOT RECORDING", size="LEAD", weight=700, mono=True)
        column.addWidget(self._rec_state)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._rec_button = QPushButton("●  START")
        self._rec_button.setObjectName("start")
        self._rec_button.setCursor(Qt.PointingHandCursor)
        self._rec_button.clicked.connect(self._toggle_recording)
        row.addWidget(self._rec_button, 1)

        snapshot = QPushButton("SNAPSHOT")
        snapshot.setObjectName("ghost")
        snapshot.setCursor(Qt.PointingHandCursor)
        snapshot.clicked.connect(self.save_snapshot)
        row.addWidget(snapshot, 1)
        column.addLayout(row)
        return frame

    def _build_streaming(self):
        frame, column = card(margins=(12, 8, 12, 8), spacing=6)
        column.addWidget(label("TELEMETRY FEED  ·  CLOSED NETWORK ONLY", role="title"))

        self._stream_state = label("○  FEED OFF", size="LEAD", weight=700, mono=True)
        column.addWidget(self._stream_state)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._stream_button = QPushButton("START FEED")
        self._stream_button.setObjectName("primary")
        self._stream_button.setCursor(Qt.PointingHandCursor)
        self._stream_button.clicked.connect(self._toggle_streaming)
        row.addWidget(self._stream_button, 1)
        self._stream_addr = label("", role="caption", mono=True,
                                  align=Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(self._stream_addr, 1)
        column.addLayout(row)
        return frame

    # ── viewer ─────────────────────────────────────────────────────────────
    def _build_viewer(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(8, 8, 8, 8)
        column.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        back = QPushButton("◀  BACK")
        back.setObjectName("pill")
        back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        head.addWidget(back)
        self._viewer_title = label("", role="header")
        head.addWidget(self._viewer_title, 1)
        self._viewer_note = label("", role="caption", mono=True)
        head.addWidget(self._viewer_note)
        column.addLayout(head)

        self._rows = _table([])
        column.addWidget(self._rows, 1)
        return page

    # ── actions ────────────────────────────────────────────────────────────
    def reload(self):
        entries = self._recorder.list_logs()
        self._paths = [entry[3] for entry in entries]
        table = self._files
        table.setRowCount(len(entries))
        for index, (name, size, when, _path) in enumerate(entries):
            for column, text in enumerate((name, size, when)):
                item = QTableWidgetItem(text)
                if column:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                table.setItem(index, column, item)
        set_text(self._count, "%d file%s" % (len(entries), "" if len(entries) == 1 else "s"))

    def save_snapshot(self):
        try:
            path = self._recorder.save_snapshot()
        except OSError as error:
            QMessageBox.critical(self, "Snapshot failed", str(error))
            return
        self.reload()
        QMessageBox.information(self, "Snapshot saved", path)

    def _toggle_recording(self):
        if self._recorder.is_active:
            self._recorder.stop()
            self.reload()
        else:
            self._recorder.start()
        self._apply_recording_state()

    def _apply_recording_state(self):
        active = self._recorder.is_active
        self._rec_button.setText("■  STOP" if active else "●  START")
        self._rec_button.setObjectName("stop" if active else "start")
        self._rec_button.style().unpolish(self._rec_button)
        self._rec_button.style().polish(self._rec_button)
        set_ss(self._rec_state, "color:%s;font-weight:700;background:transparent;border:none;"
                                % (Color.crit if active else Color.TEXT_3))

    def _toggle_streaming(self):
        stream = self._engine.stream
        if stream.is_active:
            stream.stop()
        else:
            stream.start()
        self._sync_streaming_state(stream.is_active)

    def _sync_streaming_state(self, live):
        if live == self._stream_live:
            return
        self._stream_live = live
        self._stream_button.setText("STOP FEED" if live else "START FEED")
        set_text(self._stream_addr, "tcp  %s:%d" % (self._engine.local_ip(), TELEMETRY_PORT)
                 if live else "")

    def _selected_path(self):
        row = self._files.currentRow()
        return self._paths[row] if 0 <= row < len(self._paths) else None

    def _view_selected(self):
        path = self._selected_path()
        if not path:
            return
        try:
            # Logs written on the Pi are utf-8 (°C in fault text); never let a
            # stray byte from a half-flushed file take the viewer down.
            with open(path, newline="", encoding="utf-8", errors="replace") as handle:
                rows = list(csv.reader(handle))
        except (OSError, csv.Error) as error:
            QMessageBox.warning(self, "Cannot read file", str(error))
            return
        if not rows:
            return

        self._open_path = path
        header, body = rows[0], rows[1:]
        clipped = body[:MAX_VIEW_ROWS]
        table = self._rows
        table.setColumnCount(len(header))
        table.setHorizontalHeaderLabels(header)
        table.setRowCount(len(clipped))
        for r, row in enumerate(clipped):
            for c, value in enumerate(row[:len(header)]):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                table.setItem(r, c, item)
        table.resizeColumnsToContents()

        set_text(self._viewer_title, path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1])
        set_text(self._viewer_note, "%d rows%s" % (len(body),
                 "  ·  showing first %d" % MAX_VIEW_ROWS if len(body) > MAX_VIEW_ROWS else ""))
        self._stack.setCurrentIndex(1)

    def _export_selected(self):
        path = self._selected_path()
        if not path:
            return
        destination = path[:-4] + "_export.csv"
        try:
            self._recorder.export(path, destination)
        except OSError as error:
            QMessageBox.critical(self, "Export failed", str(error))
            return
        self.reload()
        QMessageBox.information(self, "Exported", destination)

    # ── per-tick ───────────────────────────────────────────────────────────
    def refresh(self, engine, recorder=None):
        recorder = recorder or self._recorder
        if recorder.is_active:
            set_text(self._rec_state, "●  RECORDING  %ds  ·  %.1f KB"
                                      % (recorder.duration_s, recorder.file_size_kb))
        else:
            set_text(self._rec_state, "○  NOT RECORDING")

        live = engine.stream.is_active
        set_text(self._stream_state, "●  FEED LIVE" if live else "○  FEED OFF")
        set_ss(self._stream_state, "color:%s;font-weight:700;background:transparent;border:none;"
                                   % (Color.ok if live else Color.TEXT_3))
        self._sync_streaming_state(live)

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_recording_state()
        self.reload()

    def on_theme_changed(self):
        self._apply_recording_state()
