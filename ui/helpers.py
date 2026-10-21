"""
ui/helpers.py — the diff-update primitives every page uses.

The rule: a 10 Hz loop may change *values*, never *styles*. setStyleSheet()
forces Qt to re-parse the sheet and re-polish the widget tree, which on a
Pi 4 is orders of magnitude more expensive than setText(). So styles go
through set_ss(), which no-ops when the string is unchanged, and colour
decisions are quantised into a handful of named states first — a cell
drifting 3.71 -> 3.72 V then costs one setText and nothing else.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout, QWidget

from core.faults import CELL_T_CRIT, CELL_T_WARN, CELL_V_WARN_HI, CELL_V_WARN_LO
from ui.theme import Color, TM
from ui.tokens import MONO


def set_ss(widget, style):
    """setStyleSheet, but only when it would actually change something."""
    if getattr(widget, "_ss_cache", None) != style:
        widget.setStyleSheet(style)
        widget._ss_cache = style


def set_text(widget, text):
    if getattr(widget, "_text_cache", None) != text:
        widget.setText(text)
        widget._text_cache = text


def set_value(bar, value):
    value = int(value)
    if bar.value() != value:
        bar.setValue(value)


def mono_width(sample, size="LEAD", pad=10):
    """Width a monospace readout needs, in the *current* text size.

    Reserving pixels instead of characters is what keeps LARGE and HUGE text
    from clipping: every fixed width in the UI is derived from the type scale
    rather than measured once at NORMAL.
    """
    return int(len(sample) * TM.size(size) * 0.62) + pad


def set_mono_width(widget, sample, size="LEAD", pad=10):
    """Reserve room for `sample`, and reserve it again after a type change.

    setFixedWidth() on its own only holds until the driver picks a bigger text
    size: the pixels were computed once at build time. Recording the spec lets
    restyle_tree() re-measure every reservation when the scale moves.
    """
    widget._width_spec = (sample, size, pad)
    widget.setFixedWidth(mono_width(sample, size, pad))


def set_mono_min_width(widget, sample, size="LEAD", pad=10):
    """As set_mono_width, but the widget stays free to grow past the sample."""
    widget._min_width_spec = (sample, size, pad)
    widget.setMinimumWidth(mono_width(sample, size, pad))


def set_scaled_height(widget, size="LEAD", factor=2.0, floor=0):
    """Fix a widget's height as a multiple of one type-scale step."""
    widget._height_spec = (size, factor, floor)
    widget.setFixedHeight(_scaled_height(size, factor, floor))


def set_scaled_width(widget, base, minimum=True):
    """Reserve a width that tracks the type scale.

    A raw setFixedWidth(186) measured at NORMAL clips its own contents once the
    driver picks LARGE/HUGE. `base` is the width that fits at scale 1.0; it is
    re-scaled here and again by restyle_tree() when the scale moves. `minimum`
    keeps the box free to grow (the default) rather than pinning it exactly.
    """
    widget._scaled_width_spec = (base, minimum)
    _apply_scaled_width(widget, base, minimum)


def _apply_scaled_width(widget, base, minimum):
    width = int(round(base * TM.font_scale))
    (widget.setMinimumWidth if minimum else widget.setFixedWidth)(width)


def _scaled_height(size, factor, floor):
    return max(floor, int(round(TM.size(size) * factor)))


def restyle_tree(root):
    """Drop every cached style string and re-apply the ones we can rebuild.

    Inline styles are written once at construction, so after a theme change a
    label would keep the old palette's hex. Anything built by label() or
    numeral() carries the spec that produced it, so it can be re-resolved
    against the new palette here instead of every page restyling by hand.
    Type-derived sizes are re-measured for the same reason.
    """
    for widget in [root] + root.findChildren(QWidget):
        widget._ss_cache = None
        spec = getattr(widget, "_style_spec", None)
        if spec is not None:
            _apply_label_spec(widget, spec)
        spec = getattr(widget, "_numeral_spec", None)
        if spec is not None:
            style_numeral(widget, *spec)
        spec = getattr(widget, "_width_spec", None)
        if spec is not None:
            widget.setFixedWidth(mono_width(*spec))
        spec = getattr(widget, "_min_width_spec", None)
        if spec is not None:
            widget.setMinimumWidth(mono_width(*spec))
        spec = getattr(widget, "_height_spec", None)
        if spec is not None:
            widget.setFixedHeight(_scaled_height(*spec))
        spec = getattr(widget, "_scaled_width_spec", None)
        if spec is not None:
            _apply_scaled_width(widget, *spec)


# ── status classification: the single source of truth for colour ───────────
def soc_status(soc):
    if soc <= 10:
        return "crit"
    return "warn" if soc <= 20 else "ok"


def temp_status(t):
    if t >= CELL_T_CRIT - 5:
        return "crit"
    return "warn" if t >= CELL_T_WARN - 3 else "ok"


def dv_status(dv):
    if dv >= 0.080:
        return "crit"
    return "warn" if dv >= 0.040 else "ok"


def cell_v_status(v):
    if v > 3.95 or v < 3.15:
        return "crit"
    return "warn" if (v > CELL_V_WARN_HI or v < CELL_V_WARN_LO) else "ok"


# ── small builders ─────────────────────────────────────────────────────────
def label(text="", role="", align=None, size=None, weight=None, color=None,
          mono=False, spacing=None, wrap=False):
    widget = QLabel(text)
    if role:
        widget.setProperty("role", role)
    if align is not None:
        widget.setAlignment(align)
    if wrap:
        widget.setWordWrap(True)
    spec = (mono, size, weight, color, spacing)
    if any(part for part in spec):
        widget._style_spec = spec
        _apply_label_spec(widget, spec)
    return widget


def _apply_label_spec(widget, spec):
    mono_on, size, weight, color, spacing = spec
    bits = []
    if mono_on:
        bits.append("font-family:" + MONO)
    if size:
        bits.append("font-size:%dpx" % TM.size(size))
    if weight:
        bits.append("font-weight:%d" % weight)
    if color:
        bits.append("color:" + Color.resolve(color))
    if spacing:
        bits.append("letter-spacing:%dpx" % spacing)
    set_ss(widget, ";".join(bits) + ";background:transparent;border:none;")


def card(name="card", margins=(12, 10, 12, 10), spacing=10, vertical=True):
    frame = QFrame()
    frame.setObjectName(name)
    layout = (QVBoxLayout if vertical else QHBoxLayout)(frame)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return frame, layout


def rule(vertical=False, length=22):
    line = QFrame()
    line.setObjectName("rule")
    if vertical:
        line.setFixedSize(1, length)
    else:
        line.setFixedHeight(1)
    return line


def numeral(text="--", size="DISPLAY", color=None,
            align=Qt.AlignRight | Qt.AlignVCenter):
    """A tabular monospace readout — the workhorse of every metric tile."""
    widget = QLabel(text)
    widget.setAlignment(align)
    style_numeral(widget, size, color or Color.TEXT)
    return widget


def style_numeral(widget, size, color):
    widget._numeral_spec = (size, color)
    set_ss(widget, "color:%s;font-family:%s;font-size:%dpx;font-weight:800;"
                   "background:transparent;border:none;"
                   % (Color.resolve(color), MONO, TM.size(size)))


def badge_style(status, size="CAPTION"):
    fg = Color.status(status)
    return ("background:%s;color:%s;border:1px solid %s66;border-radius:6px;"
            "font-size:%dpx;font-weight:800;padding:2px 6px;"
            % (Color.tint(status), fg, fg, TM.size(size)))


def bar_style(color, height=8):
    return ("QProgressBar{background:%s;border:none;border-radius:%dpx;}"
            "QProgressBar::chunk{background:%s;border-radius:%dpx;}"
            % (Color.SURFACE, height // 2, color, height // 2))
