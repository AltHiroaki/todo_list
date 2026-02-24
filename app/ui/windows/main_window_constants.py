"""Constants used by the main slide window."""

from __future__ import annotations

TRIGGER_WIDTH = 36
DEFAULT_EXPANDED_WIDTH = 340
MIN_PANEL_WIDTH = 300
MAX_PANEL_WIDTH = 640
RESIZE_MARGIN = 8
ANIMATION_DURATION_MS = 300
WINDOW_HEIGHT_RATIO = 1.0
DAILY_CHECK_INTERVAL_MS = 60_000
POLL_INTERVAL_MS = 60_000
HOVER_EXPAND_DELAY_MS = 140

TOGGLE_IDLE_STYLESHEET = """
    QPushButton#toggleButton {
        background: rgba(139, 92, 246, 0.15);
        color: rgba(255, 255, 255, 0.25);
        border: none;
        border-top-left-radius: 8px;
        border-bottom-left-radius: 8px;
        border-top-right-radius: 0px;
        border-bottom-right-radius: 0px;
        font-size: 13px;
        font-weight: 600;
    }
"""

TOGGLE_HOVER_STYLESHEET = """
    QPushButton#toggleButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #8b5cf6, stop:0.5 #6d28d9, stop:1 #4c1d95);
        color: rgba(255, 255, 255, 0.95);
        border: none;
        border-top-left-radius: 8px;
        border-bottom-left-radius: 8px;
        border-top-right-radius: 0px;
        border-bottom-right-radius: 0px;
        font-size: 14px;
        font-weight: 600;
    }
"""

TOGGLE_EXPANDED_STYLESHEET = """
    QPushButton#toggleButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #8b5cf6, stop:0.5 #6d28d9, stop:1 #4c1d95);
        color: rgba(255, 255, 255, 0.95);
        border: none;
        border-radius: 0px;
        font-size: 14px;
        font-weight: 600;
    }
"""
