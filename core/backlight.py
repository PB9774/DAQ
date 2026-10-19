"""
core/backlight.py — Raspberry Pi 7" panel brightness.

Silent no-op on any machine without the sysfs node, so the same code runs on
a laptop and on the car.
"""

import os

from core.config import BACKLIGHT_PATHS

_path = None
_probed = False


def device():
    global _path, _probed
    if not _probed:
        _probed = True
        for candidate in BACKLIGHT_PATHS:
            if os.path.exists(candidate):
                _path = candidate
                break
    return _path


def available():
    return device() is not None


def apply(fraction):
    """fraction is 0.0-1.0; the panel takes 0-255. Returns True on success."""
    path = device()
    if not path:
        return False
    level = max(24, min(255, int(round(fraction * 255))))
    try:
        with open(path, "w") as handle:
            handle.write("%d\n" % level)
        return True
    except OSError:
        return False


def set_max():
    return apply(1.0)
