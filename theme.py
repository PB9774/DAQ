"""theme.py — Dark / Light themes · 1024×600 · 7-inch RPi4 · v20"""
import json, os
_CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

THEMES = {
    "dark": dict(
        BG_BASE="#0A0E14", BG_PANEL="#131920", BG_CARD="#1A2130", BG_CARD2="#1F2740",
        TEXT_PRI="#F0F4FF", TEXT_SEC="#8A97B0", TEXT_DIM="#404A5C", BORDER="#283040",
        ACCENT="#3B82F6", ACCENT2="#F97316", SPEED_COL="#F59E0B", SOC_COL="#22C55E",
        NAV_BG="#0F1420", NAV_SEL="#3B82F6", GRAPH_BG="#0A0E14", SPD_BG="#060810",
    ),
    "light": dict(
        BG_BASE="#F1F5FB", BG_PANEL="#E4EAF5", BG_CARD="#FFFFFF", BG_CARD2="#EDF0F8",
        TEXT_PRI="#0F1623", TEXT_SEC="#3D4B60", TEXT_DIM="#8A97B0", BORDER="#C8D4E8",
        ACCENT="#1D4ED8", ACCENT2="#EA580C", SPEED_COL="#D97706", SOC_COL="#16A34A",
        NAV_BG="#FFFFFF", NAV_SEL="#1D4ED8", GRAPH_BG="#F1F5FB", SPD_BG="#080C14",
    ),
}

# Semantic / status colours (fixed, not theme-dependent)
SEM = dict(
    GREEN="#22C55E",    GREEN_BAR="#4ADE80",
    AMBER="#D97706",    AMBER_BAR="#FCD34D",
    RED="#EF4444",      RED_BAR="#FCA5A5",
    BLUE="#3B82F6",     # info level
    ORANGE="#F97316",
)

_FAMILIES = {
    "Inter":  "Inter,'Segoe UI Variable','Segoe UI',Ubuntu,Roboto,sans-serif",
    "Roboto": "Roboto,'Segoe UI',Arial,sans-serif",
    "Ubuntu": "Ubuntu,'Segoe UI',Roboto,sans-serif",
    "Mono":   "'JetBrains Mono','Fira Code',Consolas,monospace",
}
MONO = "'JetBrains Mono','Fira Code','Cascadia Code','Roboto Mono',Consolas,monospace"

# Base font sizes for 1024×600 7-inch (slightly larger than 800×480)
_BASE = dict(XS=15, SM=16, MD=19, LG=24, XL=36)


class ThemeManager:
    def __init__(self):
        self.name = "dark"; self.font_scale = 1.0; self.brightness = 1.0
        self.contrast = 1.0; self.font_family = "Inter"; self._load()

    def toggle(self): self.name = "light" if self.name == "dark" else "dark"; self.save()
    def save(self):
        try: json.dump({"name":self.name,"font":self.font_scale,"bright":self.brightness,
                        "contrast":self.contrast,"ff":self.font_family},open(_CFG,"w"))
        except Exception: pass
    def _load(self):
        try:
            d=json.load(open(_CFG))
            self.name=d.get("name","dark"); self.font_scale=d.get("font",1.0)
            self.brightness=d.get("bright",1.0); self.contrast=d.get("contrast",1.0)
            self.font_family=d.get("ff","Inter")
        except Exception: pass
    @property
    def palette(self): return THEMES.get(self.name, THEMES["dark"])
    @property
    def family(self): return _FAMILIES.get(self.font_family, _FAMILIES["Inter"])
    def sz(self, k): return int(_BASE.get(k, 13) * self.font_scale)
    def is_dark(self): return self.name == "dark"


TM = ThemeManager()


class _C:
    def __getattr__(self, k): return TM.palette.get(k) or SEM.get(k, "#FF00FF")
Color = _C()
for _k, _v in SEM.items(): setattr(Color, _k, _v)


class _F:
    MONO = MONO
    @property
    def FAMILY(self): return TM.family
    def __getattr__(self, k):
        if k.startswith("SIZE_"): return TM.sz(k[5:])
        raise AttributeError(k)
Font = _F()


def get_qss() -> str:
    P = TM.palette; sz = TM.sz; ff = TM.family; fm = MONO
    bg=P["BG_BASE"]; card=P["BG_CARD"]; panel=P["BG_PANEL"]; card2=P["BG_CARD2"]
    txt=P["TEXT_PRI"]; sec=P["TEXT_SEC"]; dim=P["TEXT_DIM"]; bdr=P["BORDER"]
    acc=P["ACCENT"]; nav=P["NAV_BG"]; navsel=P["NAV_SEL"]
    g=SEM["GREEN"]; gb=SEM["GREEN_BAR"]; a=SEM["AMBER"]; r=SEM["RED"]
    bl=SEM["BLUE"]
    bw = max(0.5, min(2.0, TM.contrast))

    return f"""
* {{ font-family:{ff}; color:{txt}; }}
QMainWindow, QWidget {{ background:{bg}; }}
QScrollArea {{ border:none; background:transparent; }}
QScrollBar:vertical {{ background:{panel}; width:6px; border-radius:3px; margin:0; }}
QScrollBar::handle:vertical {{ background:{bdr}; border-radius:3px; min-height:24px; }}
QScrollBar::handle:vertical:hover {{ background:{acc}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}

QFrame#card     {{ background:{card};  border:{bw:.1f}px solid {bdr}; border-radius:8px; }}
QFrame#card_lit {{ background:{card};  border:{bw*2:.1f}px solid {acc}; border-radius:8px; }}
QFrame#card_set {{ background:{card};  border:{bw:.1f}px solid {bdr}; border-radius:10px; }}

QLabel                {{ color:{txt}; background:transparent; border:none; }}
QLabel[role="title"]  {{ color:{sec}; font-size:{sz("SM")}px; font-weight:700; letter-spacing:1px; }}
QLabel[role="header"] {{ color:{txt}; font-size:{sz("LG")}px; font-weight:700; }}
QLabel[role="dim"]    {{ color:{dim}; font-size:{sz("SM")}px; }}
QLabel[role="unit"]   {{ color:{dim}; font-size:{sz("SM")}px; }}
QLabel[role="ok"]     {{ color:{g};   font-family:{fm}; font-weight:700; font-size:{sz("SM")}px; }}
QLabel[role="warn"]   {{ color:{a};   font-family:{fm}; font-weight:700; font-size:{sz("SM")}px; }}
QLabel[role="crit"]   {{ color:{r};   font-family:{fm}; font-weight:700; font-size:{sz("SM")}px; }}
QLabel[role="info"]   {{ color:{bl};  font-family:{fm}; font-weight:700; font-size:{sz("SM")}px; }}
QLabel#page_header    {{ color:{txt}; font-size:{sz("LG")}px; font-weight:700; }}

QProgressBar          {{ background:{panel}; border:none; border-radius:3px; }}
QProgressBar::chunk   {{ background:{gb}; border-radius:3px; }}

QPushButton#btn_primary  {{ background:{acc}; color:#fff; border:none; border-radius:7px; padding:7px 16px; font-size:{sz("MD")}px; font-weight:600; min-height:40px; }}
QPushButton#btn_primary:hover {{ background:{acc}cc; }}
QPushButton#btn_danger   {{ background:{r};   color:#fff; border:none; border-radius:7px; font-size:{sz("MD")}px; font-weight:700; min-height:40px; }}
QPushButton#btn_pill     {{ background:{panel}; color:{sec}; border:{bw:.1f}px solid {bdr}; border-radius:18px; padding:3px 12px; font-size:{sz("SM")}px; }}
QPushButton#btn_pill:checked {{ background:{acc}; color:#fff; border-color:{acc}; font-weight:700; }}
QPushButton#btn_pill:hover   {{ border-color:{acc}; color:{acc}; }}
QPushButton#btn_start {{ background:{g};     color:#fff; border:none; border-radius:7px; font-weight:700; font-size:{sz("MD")}px; min-height:42px; }}
QPushButton#btn_stop  {{ background:{r};     color:#fff; border:none; border-radius:7px; font-weight:700; font-size:{sz("MD")}px; min-height:42px; }}
QPushButton#btn_reset {{ background:{panel}; color:{sec}; border:{bw:.1f}px solid {bdr}; border-radius:7px; font-weight:700; font-size:{sz("MD")}px; min-height:42px; }}
QPushButton#btn_toggle {{ background:{panel}; color:{txt}; border:2px solid {bdr}; border-radius:20px; font-size:{sz("SM")}px; font-weight:700; padding:6px 20px; min-height:40px; }}
QPushButton#btn_toggle:hover {{ border-color:{acc}; color:{acc}; }}
QPushButton#btn_view  {{ background:{card2}; color:{acc}; border:1px solid {bdr}; border-radius:5px; padding:2px 6px; font-size:{sz("XS")}px; }}

QWidget#nav_bar              {{ background:{nav}; border-top:1px solid {bdr}; }}
QPushButton#nav_btn          {{ background:transparent; border:none; color:{dim}; font-size:{sz("SM")}px; padding:5px 3px 4px; }}
QPushButton#nav_btn:checked  {{ color:{navsel}; font-weight:700; }}

QSlider::groove:horizontal   {{ background:{panel}; height:6px; border-radius:3px; }}
QSlider::handle:horizontal   {{ background:{acc}; width:18px; height:18px; margin:-6px 0; border-radius:9px; }}
QSlider::sub-page:horizontal {{ background:{acc}; border-radius:3px; }}

QTableWidget {{ background:{card}; border:none; gridline-color:{bdr}; color:{txt}; selection-background-color:{acc}40; }}
QTableWidget::item {{ padding:4px 7px; border:none; color:{txt}; font-size:{sz("SM")}px; }}
QHeaderView::section {{ background:{card2}; color:{sec}; border:1px solid {bdr}; padding:4px 7px; font-size:{sz("SM")}px; font-weight:600; }}

QComboBox {{ background:{card2}; color:{txt}; border:1px solid {bdr}; border-radius:5px; padding:4px 9px; font-size:{sz("SM")}px; }}
QComboBox QAbstractItemView {{ background:{card}; color:{txt}; border:1px solid {bdr}; selection-background-color:{acc}40; font-size:{sz("SM")}px; }}
"""
