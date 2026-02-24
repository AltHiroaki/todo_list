from __future__ import annotations

import json
import os
from datetime import datetime

from app.utils import get_base_path


class JsonCache:
    def __init__(self, cache_dir: str | None = None):
        base = get_base_path()
        self.cache_dir = cache_dir or os.path.join(base, "data", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def save(self, name: str, payload: dict) -> None:
        path = self._path(name)
        wrapper = {
            "cached_at": datetime.utcnow().isoformat() + "Z",
            "payload": payload,
        }
        with open(path, "w", encoding="utf-8") as file:
            json.dump(wrapper, file, ensure_ascii=False, indent=2)

    def load(self, name: str) -> dict | None:
        path = self._path(name)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as file:
                wrapper = json.load(file)
            return wrapper
        except (OSError, json.JSONDecodeError):
            return None

    def _path(self, name: str) -> str:
        safe_name = name.replace("/", "_")
        return os.path.join(self.cache_dir, f"{safe_name}.json")

