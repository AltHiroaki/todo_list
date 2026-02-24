"""Persistent UI state for MainWindow."""

from __future__ import annotations

from dataclasses import dataclass

from app.infrastructure.cache.json_cache import JsonCache
from app.ui.windows.main_window_constants import DEFAULT_EXPANDED_WIDTH, MAX_PANEL_WIDTH, MIN_PANEL_WIDTH


@dataclass(slots=True)
class MainWindowState:
    panel_width: int = DEFAULT_EXPANDED_WIDTH
    pinned: bool = True
    startup_opt_out: bool = False


class MainWindowStateStore:
    """Load/save panel width and user toggles via JSON cache."""

    def __init__(self, cache: JsonCache | None = None):
        self._cache = cache or JsonCache()

    def load(self) -> MainWindowState:
        wrapper = self._cache.load("ui_state")
        if not isinstance(wrapper, dict):
            return MainWindowState()

        payload = wrapper.get("payload")
        if not isinstance(payload, dict):
            return MainWindowState()

        width_raw = payload.get("panel_width", DEFAULT_EXPANDED_WIDTH)
        try:
            width = int(width_raw)
        except (TypeError, ValueError):
            width = DEFAULT_EXPANDED_WIDTH
        width = max(MIN_PANEL_WIDTH, min(MAX_PANEL_WIDTH, width))

        return MainWindowState(
            panel_width=width,
            pinned=bool(payload.get("pinned", True)),
            startup_opt_out=bool(payload.get("startup_opt_out", False)),
        )

    def save(self, state: MainWindowState) -> None:
        self._cache.save(
            "ui_state",
            {
                "panel_width": max(MIN_PANEL_WIDTH, min(MAX_PANEL_WIDTH, int(state.panel_width))),
                "pinned": bool(state.pinned),
                "startup_opt_out": bool(state.startup_opt_out),
            },
        )
