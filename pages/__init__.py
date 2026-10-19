"""
pages/__init__.py — screen registry.

Every page exposes refresh(engine, recorder) and on_theme_changed(), which is
all main.py needs to know about any of them.
"""

from pages.cells import SegmentDetailsPage
from pages.driver import DriverPage
from pages.logs import LogsPage
from pages.overview import OverviewPage
from pages.setup import SetupPage
from pages.trends import TrendsPage

__all__ = ["DriverPage", "LogsPage", "OverviewPage", "SegmentDetailsPage",
           "SetupPage", "TrendsPage"]
