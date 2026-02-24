from __future__ import annotations

import sys
import os


def get_base_path() -> str:
    """Return the runtime root path for both frozen and script execution."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)

    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
