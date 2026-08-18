"""widgets.py — NavBar · SevenSegDisplay · TelemetryStrip · CriticalAlertOverlay · v20"""
import os
from PyQt5.QtCore    import Qt, QRectF, QPointF, QTimer, pyqtSignal
from PyQt5.QtGui     import QPainter, QColor, QFont, QPolygonF, QLinearGradient, QRadialGradient, QPen,QPixmap
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel,
                              QProgressBar, QSizePolicy, QPushButton, QApplication)
from theme import TM, Color, MONO


# ── Logo ──────────────────────────────────────────────────────────────────────
class LogoWidget(QWidget):
    def __init__(self, height=30, parent=None):
        super().__init__(parent)

        self.setFixedHeight(height)
        self.setFixedWidth(int(height * 9.2))
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Resolve logo relative to this script — works on RPi and any PC
        _base = os.path.dirname(os.path.abspath(__file__))
        self.logo = QPixmap()
        for _name in ("logo1.png", "logo.png", "logo.jpg"):
            _p = os.path.join(_base, "assets", _name)
            if os.path.isfile(_p):
                self.logo = QPixmap(_p).scaled(200, int(height*1.6),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation)
                break

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        if not self.logo.isNull():
            scaled = self.logo.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)

# ── Seven-Segment Display ─────────────────────────────────────────────────────
_DIGIT_SEGS = {
    '0': 'abcdef', '1': 'bc',     '2': 'abdeg',  '3': 'abcdg',
    '4': 'bcfg',   '5': 'acdfg',  '6': 'acdefg', '7': 'abc',
    '8': 'abcdefg','9': 'abcdfg', ' ': '',
}


def _build_segment_polygons(digit_w, digit_h):
    """
    Build 7 segment polygons for one digit cell.
    Segments: a(top), b(top-right), c(bot-right), d(bottom),
              e(bot-left), f(top-left), g(middle)
    """
    thickness = digit_w * 0.18
    gap = thickness * 0.12
    chamfer = thickness * 0.35
    half_h = digit_h / 2.0

    def horizontal_seg(y_top):
        """A horizontal segment at the given y position."""
        t = thickness
        return QPolygonF([
            QPointF(gap + chamfer, y_top + gap),
            QPointF(digit_w - gap - chamfer, y_top + gap),
            QPointF(digit_w - gap, y_top + gap + chamfer),
            QPointF(digit_w - gap, y_top + t - chamfer),
            QPointF(digit_w - gap - chamfer, y_top + t - gap),
            QPointF(gap + chamfer, y_top + t - gap),
            QPointF(gap, y_top + t - chamfer),
            QPointF(gap, y_top + gap + chamfer),
        ])

    def vertical_seg(x_left, y_top, y_bot):
        """A vertical segment between y_top and y_bot at x position."""
        t = thickness
        return QPolygonF([
            QPointF(x_left + chamfer + gap, y_top + gap),
            QPointF(x_left + t - chamfer - gap, y_top + gap),
            QPointF(x_left + t - gap, y_top + chamfer + gap),
            QPointF(x_left + t - gap, y_bot - chamfer - gap),
            QPointF(x_left + t - chamfer - gap, y_bot - gap),
            QPointF(x_left + chamfer + gap, y_bot - gap),
            QPointF(x_left + gap, y_bot - chamfer - gap),
            QPointF(x_left + gap, y_top + chamfer + gap),
        ])

    return {
        'a': horizontal_seg(0),
        'g': horizontal_seg(half_h - thickness / 2),
        'd': horizontal_seg(digit_h - thickness),
        'f': vertical_seg(0, 0, half_h),
        'b': vertical_seg(digit_w - thickness, 0, half_h),
        'e': vertical_seg(0, half_h, digit_h),
        'c': vertical_seg(digit_w - thickness, half_h, digit_h),
    }


def _speed_color(fraction):
    """Interpolate speed colour: green → amber → red based on speed fraction."""
    if fraction <= 0.45:
        return QColor("#22C55E")   # green
    elif fraction <= 0.70:
        t = (fraction - 0.45) / 0.25
        r = int(34 + t * (245 - 34))
        g = int(197 + t * (158 - 197))
        b = int(94 + t * (11 - 94))
        return QColor(r, g, b)
    else:
        t = min(1.0, (fraction - 0.70) / 0.30)
        r = int(245 + t * (239 - 245))
        g = int(158 - t * 90)
        b = int(11 + t * (68 - 11))
        return QColor(r, g, b)


class SevenSegDisplay(QWidget):
    """
    Professional racing-style seven-segment speed display.
    Features: anti-aliased segments, ambient glow, speed-bar gradient,
    scan-line overlay, speed-dependent digit colour, and a "km/h" unit label.
    """
    MAX_SPEED = 120

    def __init__(self, parent=None):
        super().__init__(parent)
        self._speed = 0.0
        self.setMinimumSize(180, 100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAutoFillBackground(False)

    def set_speed(self, value):
        if self._speed != value:
            self._speed = value
            self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)

            W = float(self.width())
            H = float(self.height())
            P = TM.palette
            bg_color = QColor(P.get("SPD_BG", "#070809"))

            # Speed-dependent digit colour
            fraction = min(self._speed / self.MAX_SPEED, 1.0)
            speed_color = _speed_color(fraction)

            # Background
            painter.fillRect(0, 0, int(W), int(H), bg_color)

            # Layout calculations
            pad_x = W * 0.06
            pad_top = H * 0.06
            unit_area_h = H * 0.14
            bar_h = max(3.0, H * 0.03)
            digit_area_h = H - pad_top - unit_area_h - bar_h - H * 0.06

            digit_w = digit_area_h * 0.50
            digit_gap = digit_w * 0.18
            total_digits_w = 3 * digit_w + 2 * digit_gap
            start_x = (W - total_digits_w) / 2.0
            digit_y = pad_top

            # Build segment shapes
            seg_polys = _build_segment_polygons(digit_w, digit_area_h)

            # Dim colour for inactive segments
            dim_color = QColor(
                speed_color.red(), speed_color.green(), speed_color.blue(), 16
            )

            # Glow colour for active segments
            glow_color = QColor(
                speed_color.red(), speed_color.green(), speed_color.blue(), 55
            )

            # Drop shadow beneath digits for depth
            shadow_color = QColor(0, 0, 0, 60)
            shadow_offset = max(1.5, H * 0.008)

            # Draw each digit. speed_str is always exactly 3 chars (":3d"
            # padding) so digit positions stay fixed regardless of value —
            # this is what keeps the display from jittering side to side
            # as the speed number changes width.
            speed_str = f"{int(self._speed):3d}"

            for digit_idx, char in enumerate(speed_str[:3]):
                ox = start_x + digit_idx * (digit_w + digit_gap)
                active_segs = set(_DIGIT_SEGS.get(char, ''))

                for seg_name, poly in seg_polys.items():
                    is_on = seg_name in active_segs

                    # Translate polygon to digit position
                    shifted = QPolygonF([
                        QPointF(pt.x() + ox, pt.y() + digit_y)
                        for pt in poly
                    ])

                    if is_on:
                        # Draw shadow for depth
                        shadow_poly = QPolygonF([
                            QPointF(pt.x() + shadow_offset, pt.y() + shadow_offset)
                            for pt in shifted
                        ])
                        painter.setPen(Qt.NoPen)
                        painter.setBrush(shadow_color)
                        painter.drawPolygon(shadow_poly)

                        # Draw glow behind active segments
                        painter.setPen(QPen(glow_color, 4))
                        painter.setBrush(speed_color)
                        painter.drawPolygon(shifted)
                    else:
                        painter.setPen(Qt.NoPen)
                        painter.setBrush(dim_color)
                        painter.drawPolygon(shifted)

            # Ambient glow behind the digits when speed > 0
            if self._speed > 2:
                glow_intensity = min(35, int(15 + fraction * 20))
                glow_grad = QRadialGradient(W / 2, digit_y + digit_area_h * 0.5, W * 0.45)
                glow_c = QColor(
                    speed_color.red(), speed_color.green(), speed_color.blue(), glow_intensity
                )
                glow_grad.setColorAt(0, glow_c)
                glow_grad.setColorAt(1, QColor(0, 0, 0, 0))
                painter.setPen(Qt.NoPen)
                painter.setBrush(glow_grad)
                painter.drawRect(QRectF(0, 0, W, H * 0.88))

            # Scan-line overlay for authentic instrument feel
            painter.setPen(Qt.NoPen)
            scan_color = QColor(0, 0, 0, 18)
            scan_spacing = max(2, int(H * 0.012))
            y = 0.0
            while y < H:
                painter.fillRect(QRectF(0, y, W, 1), scan_color)
                y += scan_spacing

            # "km/h" label
            unit_y = digit_y + digit_area_h + H * 0.01
            unit_font = QFont("Inter", max(9, int(unit_area_h * 0.55)), QFont.Bold)
            unit_font.setLetterSpacing(QFont.AbsoluteSpacing, 2.0)
            painter.setFont(unit_font)
            unit_color = QColor(
                speed_color.red(), speed_color.green(), speed_color.blue(), 140
            )
            painter.setPen(unit_color)
            painter.drawText(
                QRectF(0, unit_y, W - pad_x, unit_area_h),
                Qt.AlignRight | Qt.AlignVCenter, "km/h"
            )

            # Speed status dot (matches digit colour)
            dot_size = max(6, int(H * 0.05))
            painter.setBrush(speed_color)
            painter.setPen(Qt.NoPen)
            # Draw glow ring around the dot
            dot_glow = QColor(speed_color.red(), speed_color.green(), speed_color.blue(), 50)
            painter.setBrush(dot_glow)
            painter.drawEllipse(
                QPointF(pad_x + dot_size / 2, unit_y + unit_area_h / 2),
                dot_size, dot_size,
            )
            painter.setBrush(speed_color)
            painter.drawEllipse(
                QPointF(pad_x + dot_size / 2, unit_y + unit_area_h / 2),
                dot_size / 2, dot_size / 2,
            )

            # Speed bar at bottom
            bar_y = H - bar_h
            bar_x = pad_x
            bar_max_w = W - pad_x * 2

            # Bar track
            painter.fillRect(
                QRectF(bar_x, bar_y, bar_max_w, bar_h),
                QColor(P.get("BORDER", "#30363D")),
            )

            # Bar fill with gradient
            if fraction > 0:
                bar_grad = QLinearGradient(bar_x, 0, bar_x + bar_max_w, 0)
                bar_grad.setColorAt(0.0, QColor("#22C55E"))
                bar_grad.setColorAt(0.5, QColor("#F59E0B"))
                bar_grad.setColorAt(1.0, QColor("#EF4444"))
                painter.fillRect(
                    QRectF(bar_x, bar_y, bar_max_w * fraction, bar_h),
                    bar_grad,
                )
                # Glowing tip at end of bar
                tip_glow = QRadialGradient(
                    bar_x + bar_max_w * fraction, bar_y + bar_h / 2,
                    bar_h * 3
                )
                tip_c = _speed_color(fraction)
                tip_c.setAlpha(80)
                tip_glow.setColorAt(0, tip_c)
                tip_glow.setColorAt(1, QColor(0, 0, 0, 0))
                painter.setBrush(tip_glow)
                painter.setPen(Qt.NoPen)
                painter.drawRect(QRectF(
                    bar_x + bar_max_w * fraction - bar_h * 3,
                    bar_y - bar_h * 1.5,
                    bar_h * 6, bar_h * 4,
                ))

        finally:
            painter.end()


# ── TelemetryStrip ─────────────────────────────────────────────────────────────
class TelemetryStrip(QFrame):
    """Top strip: logo · speed · SOC · fault badge · CAN · record dot · Hz"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card"); self.setFixedHeight(44)
        lay = QHBoxLayout(self); lay.setContentsMargins(8,0,10,0); lay.setSpacing(0)
        self._logo = LogoWidget(height=26); lay.addWidget(self._logo)
        lay.addWidget(self._vdiv())

        # Speed
        sw = QWidget(); sl = QHBoxLayout(sw); sl.setContentsMargins(8,0,8,0); sl.setSpacing(5)
        st = QLabel("SPEED"); st.setProperty("role","title")
        self._spd = QLabel("--"); self._spd.setFixedWidth(46)
        self._spd.setStyleSheet("font-size:20px;font-family:"+MONO+";font-weight:900;background:transparent;border:none;")
        su = QLabel("km/h"); su.setProperty("role","unit")
        for w in (st,self._spd,su): sl.addWidget(w,alignment=Qt.AlignVCenter)
        lay.addWidget(sw); lay.addWidget(self._vdiv())

        # SOC
        sc = QWidget(); sc.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
        so = QHBoxLayout(sc); so.setContentsMargins(8,2,8,2); so.setSpacing(7)
        sct = QLabel("SOC"); sct.setProperty("role","title")
        self._sv = QLabel("--%"); self._sv.setFixedWidth(46)
        self._sv.setStyleSheet("font-size:18px;font-family:"+MONO+";font-weight:900;background:transparent;border:none;")
        self._sbar = QProgressBar(); self._sbar.setRange(0,1000); self._sbar.setTextVisible(False)
        self._sbar.setFixedHeight(7); self._sbar.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        for w in (sct,self._sv): so.addWidget(w,alignment=Qt.AlignVCenter)
        so.addWidget(self._sbar,alignment=Qt.AlignVCenter)
        lay.addWidget(sc); lay.addWidget(self._vdiv())

        # Fault badge
        self._fbadge = QLabel(" OK ")
        self._fbadge.setFixedHeight(22); self._fbadge.setMinimumWidth(36)
        self._fbadge.setAlignment(Qt.AlignCenter)
        self._fbadge.setStyleSheet("background:#16A34A;color:#fff;border-radius:4px;"
                                   "font-size:13px;font-weight:700;padding:0 5px;")
        lay.addWidget(self._fbadge); lay.addWidget(self._vdiv())

        # CAN indicator — red for both NO SIGNAL and SIMULATED; the text
        # is what tells you which. Will turn green once real CAN is wired
        # in and engine.can_ok can actually be True.
        self._can = QLabel("CAN ✗ NO SIGNAL")
        self._can.setStyleSheet("font-size:13px;font-weight:700;color:#EF4444;background:transparent;border:none;padding:0 6px;")
        lay.addWidget(self._can); lay.addWidget(self._vdiv())

        # Recording dot
        self._rec = QLabel("● REC")
        self._rec.setStyleSheet("font-size:13px;font-weight:700;color:#404A5C;background:transparent;border:none;padding:0 6px;")
        lay.addWidget(self._rec); lay.addWidget(self._vdiv())

        # Hz
        self._hz = QLabel("10 Hz")
        self._hz.setStyleSheet("font-size:13px;font-weight:600;color:#8A97B0;background:transparent;border:none;padding:0 6px;")
        lay.addWidget(self._hz)

    def _vdiv(self):
        d = QFrame(); d.setFixedSize(1,22)
        d.setStyleSheet("background:"+Color.BORDER+";"); return d

    def refresh(self, engine, logger=None):
        self._logo.update(); P = TM.palette
        s = engine.speed; soc = engine.soc
        sc = P["SOC_COL"] if soc > 40 else (Color.AMBER_BAR if soc > 20 else Color.RED)
        self._spd.setText("%.0f" % s)
        self._spd.setStyleSheet("color:"+P["SPEED_COL"]+";font-size:20px;font-family:"+MONO+";font-weight:900;background:transparent;border:none;")
        self._sv.setText("%.0f%%" % soc)
        self._sv.setStyleSheet("color:"+sc+";font-size:18px;font-family:"+MONO+";font-weight:900;background:transparent;border:none;")
        self._sbar.setValue(int(soc*10))
        self._sbar.setStyleSheet("QProgressBar{background:"+P["BG_PANEL"]+";border:none;border-radius:2px;}"
                                 "QProgressBar::chunk{background:"+sc+";border-radius:2px;}")
        # Fault badge
        n = engine.fault_count
        if engine.has_critical: fc="#EF4444"; ft=" %d CRIT " % n
        elif n > 0:              fc="#D97706"; ft=" %d WARN " % n
        else:                    fc="#16A34A"; ft=" OK "
        self._fbadge.setText(ft)
        self._fbadge.setStyleSheet("background:"+fc+";color:#fff;border-radius:4px;font-size:13px;font-weight:700;padding:0 5px;")
        # CAN — red for NO SIGNAL and for SIMULATED (both are "not a real
        # live pack"), green reserved for engine.can_ok once real CAN is
        # wired in.
        cc = "#22C55E" if engine.can_ok else "#EF4444"
        self._can.setStyleSheet("font-size:13px;font-weight:700;color:"+cc+";background:transparent;border:none;padding:0 6px;")
        self._can.setText(("CAN ● " if engine.can_ok else "CAN ✗ ") + engine.can_status_text)
        # Recording
        if logger and logger.is_active:
            self._rec.setStyleSheet("font-size:13px;font-weight:700;color:#EF4444;background:transparent;border:none;padding:0 6px;")
            self._rec.setText("● REC")
        else:
            self._rec.setStyleSheet("font-size:13px;font-weight:600;color:#404A5C;background:transparent;border:none;padding:0 6px;")
            self._rec.setText("○ REC")
        # Hz
        self._hz.setText("%.0f Hz" % engine.actual_hz)


# ── NavBar ─────────────────────────────────────────────────────────────────────
class NavBar(QWidget):
    page_changed = pyqtSignal(int)
    # 6 pages: Dash, Cells, Pack, Graphs, Logs, Config  (no timer)
    _TABS = [("⬡","Dash"),("▦","Cells"),("⬡","Pack"),("∿","Graphs"),("🗂","Logs"),("⚙","Config")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("nav_bar"); self.setFixedHeight(58)
        self._btns = []
        lay = QHBoxLayout(self); lay.setContentsMargins(2,2,2,2); lay.setSpacing(0)
        for i,(icon,label) in enumerate(self._TABS):
            b = QPushButton(icon+"\n"+label); b.setObjectName("nav_btn")
            b.setCheckable(True); b.setFlat(True); b.setFont(QFont("Inter",11))
            b.clicked.connect(lambda _,i=i: self._sel(i))
            self._btns.append(b); lay.addWidget(b)
        self._sel(0)

    def _sel(self, idx):
        for i,b in enumerate(self._btns): b.setChecked(i==idx)
        self.page_changed.emit(idx)

    def set_page(self, idx):
        for i,b in enumerate(self._btns): b.setChecked(i==idx)


# ── Critical Alert Overlay ─────────────────────────────────────────────────────
class CriticalAlertOverlay(QWidget):
    """Full-screen red overlay for critical faults. Child of centralWidget."""
    dismissed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hide()
        self._blink = True
        self._blink_timer = QTimer(self); self._blink_timer.setInterval(500)
        self._blink_timer.timeout.connect(self._do_blink)
        self._build()

    def _build(self):
        self.setStyleSheet("background:#1A0000;")
        lay = QVBoxLayout(self); lay.setContentsMargins(40,30,40,30); lay.setSpacing(14)
        lay.addStretch()

        self._icon = QLabel("⚠")
        self._icon.setAlignment(Qt.AlignCenter)
        self._icon.setStyleSheet("font-size:72px;background:transparent;border:none;")
        lay.addWidget(self._icon)

        self._title = QLabel("CRITICAL BATTERY FAULT")
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setStyleSheet("color:#FF4444;font-size:32px;font-weight:900;"
                                  "letter-spacing:4px;background:transparent;border:none;")
        lay.addWidget(self._title)

        self._msg = QLabel("Initialising...")
        self._msg.setAlignment(Qt.AlignCenter)
        self._msg.setWordWrap(True)
        self._msg.setStyleSheet("color:#FFAAAA;font-size:20px;font-family:"+MONO+";"
                                "font-weight:700;background:transparent;border:none;")
        lay.addWidget(self._msg)

        self._loc = QLabel("")
        self._loc.setAlignment(Qt.AlignCenter)
        self._loc.setStyleSheet("color:#FF8888;font-size:17px;font-family:"+MONO+";"
                                "background:transparent;border:none;")
        lay.addWidget(self._loc)

        lay.addSpacing(20)
        btn = QPushButton("   ACKNOWLEDGE — CONTINUE WITH CAUTION   ")
        btn.setObjectName("btn_danger"); btn.setMinimumHeight(52)
        btn.setStyleSheet("background:#7F1D1D;color:#FFAAAA;border:2px solid #EF4444;"
                          "border-radius:8px;font-size:17px;font-weight:700;")
        btn.clicked.connect(self._dismiss); lay.addWidget(btn,alignment=Qt.AlignCenter)

        lay.addStretch()

    def show_faults(self, faults):
        crits = [(c,m,l) for c,m,s,l in faults if s=="crit"]
        if not crits: self.hide_alert(); return
        msgs = " | ".join(m for c,m,l in crits[:3])
        locs = ", ".join(l for c,m,l in crits[:3])
        self._msg.setText(msgs)
        self._loc.setText("Location: " + locs)
        if not self.isVisible():
            self.show(); self.raise_()
            self._blink_timer.start()
            try: QApplication.beep()
            except Exception: pass

    def hide_alert(self):
        self.hide(); self._blink_timer.stop()

    def _do_blink(self):
        self._blink = not self._blink
        bg = "#2A0000" if self._blink else "#1A0000"
        self.setStyleSheet("background:"+bg+";")

    def _dismiss(self):
        self.hide_alert(); self.dismissed.emit()
