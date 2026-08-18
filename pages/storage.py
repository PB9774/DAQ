"""
pages/storage.py — recording, TCP streaming, and log viewer.
Split out of the old monolithic pages.py.
"""

import csv

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QSizePolicy, QScrollArea, QStackedWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox,
)

from theme import MONO
from ev import DataEngine, Logger

from pages.common import _lbl


class StoragePage(QWidget):
    def __init__(self, logger: Logger, engine: DataEngine, parent=None):
        super().__init__(parent)
        self._logger = logger
        self._engine = engine
        self._stack = QStackedWidget()
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)
        self._stack.addWidget(self._list_panel())
        self._stack.addWidget(self._viewer_panel())
        self._refresh()

    def _list_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(6)

        title = QLabel("TELEMETRY  &  LOGS")
        title.setObjectName("page_header")
        lay.addWidget(title)

        rec_f = QFrame()
        rec_f.setObjectName("card")
        rec_f.setFixedHeight(60)
        rl = QHBoxLayout(rec_f)
        rl.setContentsMargins(12, 0, 12, 0)
        rl.setSpacing(10)
        self._rec_status = QLabel("○  Not recording")
        self._rec_status.setStyleSheet("font-size:16px;font-weight:700;color:#404A5C;background:transparent;border:none;")
        self._dur_lbl = QLabel("")
        self._dur_lbl.setStyleSheet("font-size:14px;font-family:" + MONO + ";color:#8A97B0;background:transparent;border:none;")
        self._btn_rec = QPushButton("▶  Start Recording")
        self._btn_rec.setObjectName("btn_start")
        self._btn_rec.setFixedWidth(200)
        self._btn_rec.clicked.connect(self._toggle_recording)
        rl.addWidget(self._rec_status, 1)
        rl.addWidget(self._dur_lbl)
        rl.addWidget(self._btn_rec)
        lay.addWidget(rec_f)

        str_f = QFrame()
        str_f.setObjectName("card")
        str_f.setFixedHeight(60)
        sl = QHBoxLayout(str_f)
        sl.setContentsMargins(12, 0, 12, 0)
        sl.setSpacing(10)
        self._stream_status = QLabel("○  Streaming OFF")
        self._stream_status.setStyleSheet("font-size:16px;font-weight:700;color:#404A5C;background:transparent;border:none;")
        self._ip_lbl = QLabel("")
        self._ip_lbl.setStyleSheet("font-size:14px;font-family:" + MONO + ";color:#8A97B0;background:transparent;border:none;")
        self._btn_stream = QPushButton("⇥  Start Streaming")
        self._btn_stream.setObjectName("btn_primary")
        self._btn_stream.setFixedWidth(200)
        self._btn_stream.clicked.connect(self._toggle_streaming)
        sl.addWidget(self._stream_status, 1)
        sl.addWidget(self._ip_lbl)
        sl.addWidget(self._btn_stream)
        lay.addWidget(str_f)

        list_hdr = QHBoxLayout()
        self._info = QLabel("0 files")
        self._info.setProperty("role", "dim")
        rb = QPushButton("⟳  Refresh")
        rb.setObjectName("btn_pill")
        rb.setFixedHeight(28)
        rb.clicked.connect(self._refresh)
        list_hdr.addWidget(self._info, 1)
        list_hdr.addWidget(rb)
        lay.addLayout(list_hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list_cont = QWidget()
        self._list_lay = QVBoxLayout(self._list_cont)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(4)
        scroll.setWidget(self._list_cont)
        lay.addWidget(scroll, 1)
        return w

    def _viewer_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(6)

        hdr = QHBoxLayout()
        back = QPushButton("← Back")
        back.setObjectName("btn_pill")
        back.setFixedHeight(30)
        back.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        self._vtitle = QLabel("")
        self._vtitle.setProperty("role", "header")
        self._export_btn = QPushButton("⬆ Export")
        self._export_btn.setObjectName("btn_primary")
        self._export_btn.setFixedHeight(30)
        self._export_btn.setFixedWidth(120)
        self._export_btn.clicked.connect(self._do_export)
        hdr.addWidget(back)
        hdr.addSpacing(8)
        hdr.addWidget(self._vtitle, 1)
        hdr.addWidget(self._export_btn)
        lay.addLayout(hdr)

        self._table = QTableWidget()
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self._table, 1)
        self._cur_path = None
        return w

    def _toggle_recording(self):
        if self._logger.is_active:
            self._logger.stop()
            self._btn_rec.setText("▶  Start Recording")
            self._btn_rec.setObjectName("btn_start")
            self._rec_status.setText("○  Not recording")
            self._rec_status.setStyleSheet("font-size:16px;font-weight:700;color:#404A5C;background:transparent;border:none;")
        else:
            self._logger.start()
            self._btn_rec.setText("■  Stop Recording")
            self._btn_rec.setObjectName("btn_stop")
            self._rec_status.setText("● Recording")
            self._rec_status.setStyleSheet("font-size:16px;font-weight:700;color:#EF4444;background:transparent;border:none;")
        self._btn_rec.style().unpolish(self._btn_rec)
        self._btn_rec.style().polish(self._btn_rec)

    def _toggle_streaming(self):
        if self._engine.is_streaming:
            self._engine.stop_streaming()
            self._btn_stream.setText("⇥  Start Streaming")
            self._stream_status.setText("○  Streaming OFF")
            self._stream_status.setStyleSheet("font-size:16px;font-weight:700;color:#404A5C;background:transparent;border:none;")
            self._ip_lbl.setText("")
        else:
            self._engine.start_streaming()
            ip = self._engine.local_ip()
            self._btn_stream.setText("■  Stop Streaming")
            self._stream_status.setText("● Streaming LIVE")
            self._stream_status.setStyleSheet("font-size:16px;font-weight:700;color:#22C55E;background:transparent;border:none;")
            self._ip_lbl.setText("TCP  %s:%d" % (ip, 9000))

    def _refresh(self):
        while self._list_lay.count():
            it = self._list_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        logs = self._logger.list_logs()
        self._info.setText("%d file%s" % (len(logs), "s" if len(logs) != 1 else ""))
        if not logs:
            self._list_lay.addWidget(_lbl("No logs yet.\nStart recording or save a snapshot.", "dim", "font-size:13px;"))

        for name, size, mtime, path in logs:
            row = QFrame()
            row.setObjectName("card")
            row.setFixedHeight(48)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(10, 5, 10, 5)
            rl.setSpacing(8)
            rl.addWidget(_lbl("📄", "", "font-size:15px;background:transparent;border:none;"))
            nm = _lbl(name, "", "font-family:" + MONO + ";font-size:14px;background:transparent;border:none;")
            nm.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            rl.addWidget(nm, 1)
            rl.addWidget(_lbl(size, "dim", "font-size:13px;"))
            rl.addWidget(_lbl(mtime, "dim", "font-family:" + MONO + ";font-size:13px;"))
            vb = QPushButton("View")
            vb.setObjectName("btn_view")
            vb.setFixedSize(50, 26)
            vb.clicked.connect(lambda _, p=path, n=name: self._open(p, n))
            rl.addWidget(vb)
            self._list_lay.addWidget(row)
        self._list_lay.addStretch()

    def _open(self, path, name):
        self._cur_path = path
        self._vtitle.setText(name)
        try:
            with open(path) as f:
                rows = list(csv.reader(f))
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            return
        if not rows:
            return
        self._table.clear()
        self._table.setColumnCount(len(rows[0]))
        self._table.setRowCount(len(rows) - 1)
        self._table.setHorizontalHeaderLabels(rows[0])
        for ri, row in enumerate(rows[1:]):
            for ci, val in enumerate(row):
                self._table.setItem(ri, ci, QTableWidgetItem(val))
        self._stack.setCurrentIndex(1)

    def _do_export(self):
        if not self._cur_path:
            return
        dest = self._cur_path.replace(".csv", "_export.csv")
        try:
            self._logger.export(self._cur_path, dest)
            QMessageBox.information(self, "Exported", "Saved to:\n" + dest)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def showEvent(self, e):
        super().showEvent(e)
        self._refresh()

    def refresh(self, engine, logger=None):
        if logger and logger.is_active:
            self._rec_status.setText("● Recording  %ds  %.1fKB" % (logger.duration_s, logger.file_size_kb))
