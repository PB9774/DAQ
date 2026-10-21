"""
ui/tokens.py — the design system: palettes, type scale, status colours.

Nothing here touches Qt. Everything the UI draws or styles resolves back to
one of these tokens, which is what keeps the two themes and the seven pages
looking like one instrument instead of seven screens.
"""

PALETTES = {
    "dark": dict(
        BG="#0A0F15", SURFACE="#101720", CARD="#151E28", CARD_HI="#1B2733",
        LINE="#263340", LINE_HI="#344352",
        TEXT="#E7EDF4", TEXT_2="#A3B0BF", TEXT_3="#78889A",
        ACCENT="#6AA7E8", ACCENT_SOFT="#1A2B3D",
        SPEED="#E5A84B", SOC="#43B581", CURRENT="#E17B6C", POWER="#9A8CEB",
        GAUGE_BG="#080C11", GAUGE_TRACK="#202B37", GRAPH_BG="#0A0F15",
        SHADE="#0D131B",
    ),
    "light": dict(
        BG="#F1F4F7", SURFACE="#E9EEF2", CARD="#FFFFFF", CARD_HI="#F7F9FB",
        LINE="#DCE3E9", LINE_HI="#C8D2DC",
        TEXT="#1C2936", TEXT_2="#536476", TEXT_3="#748597",
        ACCENT="#315F8C", ACCENT_SOFT="#E4EDF5",
        SPEED="#A66D23", SOC="#25805A", CURRENT="#BD5747", POWER="#705EAD",
        GAUGE_BG="#121A22", GAUGE_TRACK="#334150", GRAPH_BG="#F1F4F7",
        SHADE="#E3E9EF",
    ),
}

# Status hues are deliberately identical in both themes — a red must read as
# the same red to the driver whichever theme the pit crew left it on.
STATUS_FG = {"ok": "#22C55E", "info": "#3E8CFF", "warn": "#F5A524", "crit": "#FF4D4F"}
STATUS_TINT = {
    "dark": {"ok": "#0B2416", "info": "#0D1C36", "warn": "#2A1C04", "crit": "#2C0B0E"},
    "light": {"ok": "#DCFCE7", "info": "#DBEAFE", "warn": "#FEF3C7", "crit": "#FEE2E2"},
}
STATUS_LABEL = {"ok": "READY", "info": "NOTICE", "warn": "CAUTION", "crit": "STOP"}

FAMILIES = {
    "Inter": "Inter,'Segoe UI Variable','Segoe UI',Ubuntu,Roboto,sans-serif",
    "Roboto": "Roboto,'Segoe UI',Arial,sans-serif",
    "Ubuntu": "Ubuntu,'Segoe UI',Roboto,sans-serif",
    "Mono": "'JetBrains Mono','DejaVu Sans Mono',Consolas,monospace",
}
MONO = "'JetBrains Mono','DejaVu Sans Mono','Roboto Mono',Consolas,monospace"
MONO_QFONT = "JetBrains Mono"

# Type scale for a 1024x600 7-inch panel at arm's length.
TYPE = dict(CAPTION=13, SMALL=15, BODY=17, LEAD=20, TITLE=25, DISPLAY=34, HERO=46)

RADIUS = dict(SM=6, MD=12, LG=16, PILL=18)
GAP = dict(XS=4, SM=8, MD=12, LG=16)
