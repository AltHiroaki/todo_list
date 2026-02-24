"""UI window modules."""

from app.ui.windows.completed_log_window import CompletedLogWindow
from app.ui.windows.main_window_constants import (
    ANIMATION_DURATION_MS,
    DAILY_CHECK_INTERVAL_MS,
    HOVER_EXPAND_DELAY_MS,
    MAX_PANEL_WIDTH,
    MIN_PANEL_WIDTH,
    POLL_INTERVAL_MS,
    RESIZE_MARGIN,
    TOGGLE_EXPANDED_STYLESHEET,
    TOGGLE_HOVER_STYLESHEET,
    TOGGLE_IDLE_STYLESHEET,
    TRIGGER_WIDTH,
    WINDOW_HEIGHT_RATIO,
)
from app.ui.windows.main_window_state_store import MainWindowState, MainWindowStateStore
from app.ui.windows.tray_controller import TrayCallbacks, TrayController

__all__ = [
    "ANIMATION_DURATION_MS",
    "DAILY_CHECK_INTERVAL_MS",
    "HOVER_EXPAND_DELAY_MS",
    "MAX_PANEL_WIDTH",
    "MIN_PANEL_WIDTH",
    "POLL_INTERVAL_MS",
    "RESIZE_MARGIN",
    "TOGGLE_EXPANDED_STYLESHEET",
    "TOGGLE_HOVER_STYLESHEET",
    "TOGGLE_IDLE_STYLESHEET",
    "TRIGGER_WIDTH",
    "WINDOW_HEIGHT_RATIO",
    "CompletedLogWindow",
    "MainWindowState",
    "MainWindowStateStore",
    "TrayCallbacks",
    "TrayController",
]
