"""
ui/theme.py — persisted preferences, palette access, and the stylesheet.

The stylesheet is rebuilt only when a preference actually changes (it is
cached against the preference tuple), so switching pages or ticking the
telemetry loop never re-parses QSS.
"""

import json

from core.config import SETTINGS_FILE
from ui.tokens import (
    PALETTES, STATUS_FG, STATUS_TINT, FAMILIES, MONO, TYPE, RADIUS,
)

DRIVER, ENGINEER = "driver", "engineer"


class Prefs:
    """Everything the user can change and expect to survive a restart."""

    def __init__(self):
        self.theme = "dark"
        self.font_scale = 1.0
        self.font_family = "Inter"
        self.brightness = 1.0
        self.contrast = 1.0
        self.mode = DRIVER
        self.load()

    def load(self):
        try:
            with open(SETTINGS_FILE) as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        self.theme = data.get("theme", data.get("name", "dark"))
        self.font_scale = float(data.get("font_scale", data.get("font", 1.0)))
        self.font_family = data.get("font_family", data.get("ff", "Inter"))
        self.brightness = float(data.get("brightness", data.get("bright", 1.0)))
        self.contrast = float(data.get("contrast", 1.0))
        self.mode = DRIVER if data.get("mode", DRIVER) == DRIVER else ENGINEER

    def save(self):
        try:
            with open(SETTINGS_FILE, "w") as handle:
                json.dump({
                    "theme": self.theme, "font_scale": self.font_scale,
                    "font_family": self.font_family, "brightness": self.brightness,
                    "contrast": self.contrast, "mode": self.mode,
                }, handle, indent=2)
        except OSError:
            pass

    # ── derived ────────────────────────────────────────────────────────────
    @property
    def palette(self):
        return PALETTES.get(self.theme, PALETTES["dark"])

    @property
    def family(self):
        return FAMILIES.get(self.font_family, FAMILIES["Inter"])

    @property
    def is_dark(self):
        return self.theme == "dark"

    def size(self, key):
        return int(round(TYPE.get(key, 17) * self.font_scale))

    def toggle_theme(self):
        self.theme = "light" if self.is_dark else "dark"
        self.save()

    def tint(self, status):
        return STATUS_TINT[self.theme if self.theme in STATUS_TINT else "dark"][status]

    def key(self):
        return (self.theme, self.font_scale, self.font_family, round(self.contrast, 2))


TM = Prefs()


class Tok(str):
    """A colour that remembers the token it came from.

    Inline styles are built once at construction time, so a plain hex string
    would still be the *old* theme's hex after a theme switch. Because this is
    a str subclass it interpolates exactly like the hex it holds, while
    helpers.restyle_tree() can re-resolve `.token` against the new palette.
    """

    __slots__ = ("token",)

    def __new__(cls, value, token):
        text = super().__new__(cls, value)
        text.token = token
        return text


class _Colors:
    """Color.CARD / Color.crit — palette keys and status keys in one place."""

    def __getattr__(self, key):
        palette = TM.palette
        if key in palette:
            return Tok(palette[key], key)
        if key in STATUS_FG:
            return Tok(STATUS_FG[key], key)
        raise AttributeError(key)

    @staticmethod
    def status(status):
        return Tok(STATUS_FG.get(status, STATUS_FG["info"]), status)

    @staticmethod
    def tint(status):
        return TM.tint(status)

    def resolve(self, colour):
        """The current-theme value of a colour captured under any theme."""
        token = getattr(colour, "token", None)
        return getattr(self, token) if token else colour


Color = _Colors()


class _Fonts:
    MONO = MONO

    @property
    def FAMILY(self):
        return TM.family

    def __getattr__(self, key):
        return TM.size(key)


Font = _Fonts()

_qss_cache = {}


def stylesheet():
    key = TM.key()
    if key not in _qss_cache:
        _qss_cache.clear()
        _qss_cache[key] = _build_qss()
    return _qss_cache[key]


def _build_qss():
    p = TM.palette
    sz = TM.size
    ff = TM.family
    bw = max(1, min(3, int(round(TM.contrast * 1.2))))
    r_sm, r_md, r_pill = RADIUS["SM"], RADIUS["MD"], RADIUS["PILL"]
    ok, warn, crit, info = (STATUS_FG[k] for k in ("ok", "warn", "crit", "info"))

    cyan = '#00E5FF' if TM.is_dark else '#0284C7'
    cyan_hi = '#38BDF8' if TM.is_dark else '#0369A1'
    rgba_cyan_subtle = 'rgba(0, 229, 255, 0.12)' if TM.is_dark else 'rgba(2, 132, 199, 0.10)'
    rgba_cyan = 'rgba(0, 229, 255, 0.25)' if TM.is_dark else 'rgba(2, 132, 199, 0.18)'
    rgba_cyan_med = 'rgba(0, 229, 255, 0.35)' if TM.is_dark else 'rgba(2, 132, 199, 0.25)'
    rgba_cyan_strong = 'rgba(0, 229, 255, 0.45)' if TM.is_dark else 'rgba(2, 132, 199, 0.35)'
    text_hi = '#FFFFFF' if TM.is_dark else p['TEXT']
    pad_pill_h = max(8, int(round(14 / TM.font_scale)))
    pad_pill_v = max(4, int(round(6 / TM.font_scale)))

    return f"""
* {{ font-family:{ff}; color:{p['TEXT']}; outline:none; }}
QMainWindow, QWidget {{ background:{p['BG']}; }}
QToolTip {{ background:{p['CARD_HI']}; color:{p['TEXT']}; border:1px solid {p['LINE']}; padding:4px; }}

QScrollArea {{ border:none; background:transparent; }}
QScrollBar:vertical {{ background:transparent; width:8px; margin:2px; }}
QScrollBar::handle:vertical {{ background:{p['LINE_HI']}; border-radius:4px; min-height:32px; }}
QScrollBar::handle:vertical:hover {{ background:{p['ACCENT']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height:0; width:0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background:transparent; }}

QFrame#card       {{ background:{p['CARD']}; border:{bw}px solid {p['LINE']}; border-radius:{r_md}px; }}
QFrame#card_hi    {{ background:{p['CARD_HI']}; border:{bw}px solid {p['LINE_HI']}; border-radius:{r_md}px; }}
QFrame#card_focus {{ background:{p['CARD']}; border:{bw}px solid {p['ACCENT']}; border-radius:{r_md}px; }}
QFrame#flat       {{ background:{p['SURFACE']}; border:none; border-radius:{r_md}px; }}
QFrame#rule       {{ background:{p['LINE']}; border:none; }}

QLabel {{ background:transparent; border:none; color:{p['TEXT']}; font-size:{sz('BODY')}px; }}
QLabel[role="title"]   {{ color:{p['TEXT_2']}; font-size:{sz('CAPTION')}px; font-weight:700; letter-spacing:1.4px; }}
QLabel[role="caption"] {{ color:{p['TEXT_3']}; font-size:{sz('CAPTION')}px; font-weight:600; }}
QLabel[role="unit"]    {{ color:{p['TEXT_3']}; font-size:{sz('SMALL')}px; font-weight:600; }}
QLabel[role="header"]  {{ color:{p['TEXT']}; font-size:{sz('TITLE')}px; font-weight:700; letter-spacing:0.4px; }}
QLabel[role="lead"]    {{ color:{p['TEXT']}; font-size:{sz('LEAD')}px; font-weight:700; }}
QLabel[role="ok"]   {{ color:{ok};   font-weight:700; }}
QLabel[role="warn"] {{ color:{warn}; font-weight:700; }}
QLabel[role="crit"] {{ color:{crit}; font-weight:700; }}
QLabel[role="info"] {{ color:{info}; font-weight:700; }}

QProgressBar {{ background:{p['SURFACE']}; border:none; border-radius:3px; }}
QProgressBar::chunk {{ background:{p['ACCENT']}; border-radius:3px; }}
""" + f"""
QPushButton {{ font-size:{sz('BODY')}px; font-weight:700; }}
QPushButton#primary {{ background:{p['ACCENT']}; color:#FFFFFF; border:none;
    border-radius:{r_md}px; padding:8px 16px; min-height:42px; }}
QPushButton#primary:hover {{ background:{p['TEXT_2']}; color:{p['BG']}; }}
QPushButton#primary:pressed {{ background:{p['ACCENT_SOFT']}; color:{p['ACCENT']}; }}
QPushButton#ghost {{ background:transparent; color:{p['TEXT_2']};
    border:{bw}px solid {p['LINE_HI']}; border-radius:{r_md}px; padding:8px 16px; min-height:40px; }}
QPushButton#ghost:hover {{ border-color:{p['ACCENT']}; color:{p['ACCENT']}; }}
QPushButton#danger {{ background:{crit}; color:#FFFFFF; border:none;
    border-radius:{r_md}px; min-height:44px; }}
QPushButton#start {{ background:{ok}; color:#05130A; border:none;
    border-radius:{r_md}px; min-height:46px; font-weight:800; }}
QPushButton#stop  {{ background:{crit}; color:#FFFFFF; border:none;
    border-radius:{r_md}px; min-height:46px; font-weight:800; }}

QPushButton#pill {{ background:{p['SURFACE']}; color:{p['TEXT_2']};
    border:{bw}px solid {p['LINE']}; border-radius:{r_pill}px;
    padding:{pad_pill_v}px {pad_pill_h}px; min-height:30px; font-size:{sz('SMALL')}px; font-weight:600; }}
QPushButton#pill:hover {{ border-color:{p['ACCENT']}; color:{p['ACCENT']}; }}
QPushButton#pill:checked {{ background:{p['ACCENT']}; color:#FFFFFF; border-color:{p['ACCENT']}; }}
QPushButton#tab {{ background:{p['SURFACE']}; color:{p['TEXT_2']};
    border:{bw}px solid {p['LINE']}; border-radius:{r_sm}px;
    padding:4px 6px; min-height:30px; font-size:{sz('CAPTION')}px;
    font-weight:800; letter-spacing:1px; }}
QPushButton#tab:hover {{ border-color:{p['ACCENT']}; color:{p['ACCENT']}; }}
QPushButton#tab:checked {{ background:{p['ACCENT']}; color:#FFFFFF; border-color:{p['ACCENT']}; }}
QPushButton#driver_feed {{
    background:{p['ACCENT'] if not TM.is_dark else '#1E3A8A'};
    color:#FFFFFF;
    border:2px solid {p['ACCENT'] if not TM.is_dark else '#3B82F6'};
    border-radius:{r_sm + 2}px;
    padding:6px 14px;
    min-height:34px;
    font-size:{sz('SMALL')}px;
    font-weight:800;
    letter-spacing:0.6px;
}}
QPushButton#driver_feed:hover {{
    background:{'#1D4ED8' if not TM.is_dark else '#2563EB'};
    border-color:{'#1E40AF' if not TM.is_dark else '#60A5FA'};
}}
QPushButton#driver_feed[active="true"] {{
    background:{crit};
    color:#FFFFFF;
    border:2px solid {crit};
}}
QPushButton#driver_feed[active="true"]:hover {{
    background:#D32F2F;
    border-color:#B71C1C;
}}

QPushButton#driver_mode {{
    background:{p['CARD'] if not TM.is_dark else '#1E293B'};
    color:{p['TEXT'] if not TM.is_dark else '#F8FAFC'};
    border:2px solid {p['LINE_HI'] if not TM.is_dark else '#64748B'};
    border-radius:{r_sm + 2}px;
    padding:6px 14px;
    min-height:34px;
    font-size:{sz('SMALL')}px;
    font-weight:800;
    letter-spacing:0.6px;
}}
QPushButton#driver_mode:hover {{
    background:{p['SURFACE'] if not TM.is_dark else '#334155'};
    border-color:{p['ACCENT'] if not TM.is_dark else '#94A3B8'};
    color:{p['ACCENT'] if not TM.is_dark else '#FFFFFF'};
}}

QPushButton#mode {{ background:{p['ACCENT_SOFT']}; color:{p['ACCENT']};
    border:{bw}px solid {p['LINE_HI']}; border-radius:{r_pill}px;
    padding:5px 16px; min-height:34px; font-size:{sz('SMALL')}px; font-weight:800; letter-spacing:1px; }}
QPushButton#mode:hover {{ background:{p['ACCENT']}; color:#FFFFFF; }}
QPushButton#link {{ background:transparent; color:{p['ACCENT']}; border:none;
    font-size:{sz('CAPTION')}px; font-weight:700; padding:2px 8px; }}

QWidget#navbar {{ background:{p['SURFACE']}; border-top:{bw}px solid {p['LINE']}; }}
QPushButton#nav {{ background:transparent; border:none; border-top:3px solid transparent;
    color:{p['TEXT_3']}; font-size:{sz('CAPTION')}px; font-weight:700; padding:4px 2px; }}
QPushButton#nav:hover {{ color:{p['TEXT_2']}; }}
QPushButton#nav:checked {{ color:{p['ACCENT']}; border-top-color:{p['ACCENT']};
    background:{p['ACCENT_SOFT']}; }}

QSlider::groove:horizontal {{ background:{p['SURFACE']}; height:6px; border-radius:3px; }}
QSlider::sub-page:horizontal {{ background:{p['ACCENT']}; border-radius:3px; }}
QSlider::handle:horizontal {{ background:{p['TEXT']}; width:22px; height:22px;
    margin:-9px 0; border-radius:11px; border:3px solid {p['ACCENT']}; }}

QComboBox {{ background:{p['CARD_HI']}; color:{p['TEXT']}; border:{bw}px solid {p['LINE_HI']};
    border-radius:{r_sm}px; padding:6px 12px; min-height:32px; font-size:{sz('SMALL')}px; }}
QComboBox::drop-down {{ border:none; width:22px; }}
QComboBox QAbstractItemView {{ background:{p['CARD']}; color:{p['TEXT']};
    border:1px solid {p['LINE_HI']}; selection-background-color:{p['ACCENT']};
    font-size:{sz('SMALL')}px; padding:4px; }}

QTableWidget {{ background:{p['CARD']}; alternate-background-color:{p['CARD_HI']};
    border:none; gridline-color:{p['LINE']}; font-size:{sz('SMALL')}px; }}
QTableWidget::item {{ padding:6px 10px; border:none; }}
QTableWidget::item:selected {{ background:{p['ACCENT_SOFT']}; color:{p['TEXT']}; }}
QHeaderView::section {{ background:{p['SURFACE']}; color:{p['TEXT_2']};
    border:none; border-right:1px solid {p['LINE']}; border-bottom:1px solid {p['LINE']};
    padding:7px 10px; font-size:{sz('CAPTION')}px; font-weight:800; letter-spacing:1px; }}
QMessageBox {{ background:{p['CARD']}; }}
QMessageBox QLabel {{ font-size:{sz('BODY')}px; }}
QMessageBox QPushButton {{ background:{p['SURFACE']}; color:{p['TEXT']};
    border:1px solid {p['LINE_HI']}; border-radius:{r_sm}px; padding:6px 18px; min-width:80px; }}

QFrame#selector_hud {{
    background:{'#0F172A' if not TM.is_dark else '#07101E'};
    border:1.5px solid {cyan};
    border-radius:6px;
}}
QFrame#selector_hud QLabel#hud_title {{
    color:{cyan};
    font-weight:900;
    font-size:{sz('CAPTION')}px;
    letter-spacing:0.8px;
}}
QFrame#selector_hud QLabel#hud_loc {{
    color:{text_hi};
    font-weight:800;
    font-size:{sz('SMALL')}px;
    letter-spacing:0.4px;
}}
QFrame#selector_hud QLabel#hud_div {{
    color:{p['LINE_HI'] if not TM.is_dark else '#334155'};
    font-weight:400;
}}
QFrame#selector_hud QLabel#hud_action_title {{
    color:{'#16A34A' if not TM.is_dark else '#38BDF8'};
    font-weight:900;
    font-size:{sz('CAPTION')}px;
    letter-spacing:0.8px;
}}
QFrame#selector_hud QLabel#hud_action {{
    color:{'#15803D' if not TM.is_dark else '#34D399'};
    font-weight:800;
    font-size:{sz('SMALL')}px;
}}
QFrame#selector_hud QLabel#hud_hint {{
    color:{p['TEXT_3'] if not TM.is_dark else '#64748B'};
    font-size:{sz('SMALL')}px;
    font-weight:700;
}}

/* =========================================================================
   UNIVERSAL HIGH-VISIBILITY SELECTOR BOX (5-KEY HARDWARE NAVIGATION)
   Every single interactive widget/box lights up in bright neon cyan!
   ========================================================================= */
QPushButton:focus,
QComboBox:focus,
QTableWidget:focus,
QListWidget:focus,
QTreeWidget:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QLineEdit:focus,
QScrollArea:focus {{
    border: 3px solid {cyan};
    background-color: {rgba_cyan};
    color: {text_hi};
}}

QPushButton#primary:focus {{
    border: 3px solid {cyan};
    border-radius: {r_md}px;
    background-color: {p['ACCENT']};
    color: #FFFFFF;
    font-weight: 900;
}}

QPushButton#ghost:focus {{
    border: 3px solid {cyan};
    border-radius: {r_md}px;
    background-color: {rgba_cyan};
    color: {cyan};
    font-weight: 800;
}}

QPushButton#danger:focus {{
    border: 3px solid {cyan};
    border-radius: {r_md}px;
    background-color: {crit};
    color: #FFFFFF;
    font-weight: 900;
}}

QPushButton#start:focus {{
    border: 3px solid {cyan};
    border-radius: {r_md}px;
    background-color: {ok};
    color: #05130A;
    font-weight: 900;
}}

QPushButton#stop:focus {{
    border: 3px solid {cyan};
    border-radius: {r_md}px;
    background-color: {crit};
    color: #FFFFFF;
    font-weight: 900;
}}

QPushButton#pill:focus {{
    border: 3px solid {cyan};
    border-radius: {r_pill}px;
    background-color: {rgba_cyan_med};
    color: {text_hi};
    font-weight: 800;
}}

QPushButton#pill:checked:focus {{
    border: 3px solid {cyan};
    border-radius: {r_pill}px;
    background-color: {p['ACCENT']};
    color: #FFFFFF;
    font-weight: 900;
}}

QPushButton#tab:focus {{
    border: 3px solid {cyan};
    border-radius: {r_sm}px;
    background-color: {rgba_cyan};
    color: {cyan};
    font-weight: 900;
}}

QPushButton#tab:checked:focus {{
    border: 3px solid {cyan};
    border-radius: {r_sm}px;
    background-color: {p['ACCENT']};
    color: #FFFFFF;
    font-weight: 900;
}}

QPushButton#nav:focus {{
    border: 3px solid {cyan};
    border-radius: 6px;
    background-color: {rgba_cyan};
    color: {cyan};
    font-weight: 900;
}}

QPushButton#nav:checked:focus {{
    border: 3px solid {cyan};
    border-radius: 6px;
    background-color: {rgba_cyan_strong};
    color: {cyan};
    font-weight: 900;
}}

QPushButton#mode:focus,
QPushButton#driver_mode:focus {{
    border: 3px solid {cyan};
    border-radius: {r_sm + 2}px;
    background-color: {rgba_cyan_med};
    color: {text_hi};
    font-weight: 900;
}}

QPushButton#driver_feed:focus {{
    border: 3px solid {cyan};
    border-radius: {r_sm + 2}px;
    background-color: {rgba_cyan_strong};
    color: #FFFFFF;
    font-weight: 900;
}}

QFrame#card:focus,
MetricTile:focus {{
    border: 3px solid {cyan};
    border-radius: {r_md}px;
    background-color: {rgba_cyan_subtle};
}}

QSlider:focus {{
    border: 2px solid {cyan};
    border-radius: 8px;
    background: {rgba_cyan_subtle};
    padding: 3px;
}}

QSlider:focus::groove:horizontal {{
    background: {cyan};
    height: 6px;
    border-radius: 3px;
}}

QSlider:focus::handle:horizontal {{
    border: 3px solid {cyan};
    background: #FFFFFF;
    width: 24px;
    height: 24px;
    margin: -9px 0;
    border-radius: 12px;
}}

QComboBox:focus {{
    border: 3px solid {cyan};
    border-radius: {r_sm}px;
    background-color: {rgba_cyan_med};
    color: {text_hi};
    font-weight: 800;
}}

QScrollArea#grid_scroll:focus {{
    border: 3px solid {cyan};
    border-radius: 6px;
    background-color: {rgba_cyan_subtle};
}}

QTableWidget:focus {{
    border: 3px solid {cyan};
    border-radius: 6px;
}}

QTableWidget:focus::item:selected {{
    background-color: {rgba_cyan_strong};
    color: {cyan};
    font-weight: 800;
}}
"""
