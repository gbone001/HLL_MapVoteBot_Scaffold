"""Test helper to simulate JSON persistence in a temporary directory.

Future implementation idea:
- Provide a TempDataStore that exposes load_json/save_json shims
  compatible with bot.utils/persistence or repository interfaces, writing
  into a temp root for isolation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class TempDataStore:
    """Lightweight holder for a temp data root used in tests."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    def make_loader(self) -> Callable[[str, Any], Any]:
        def load_json(name: str, default: Any) -> Any:
            p = self.path(name)
            if not p.exists():
                return default
            import json

            return json.loads(p.read_text(encoding="utf-8"))

        return load_json

    def make_saver(self) -> Callable[[str, Any], None]:
        def save_json(name: str, data: Any) -> None:
            p = self.path(name)
            p.parent.mkdir(parents=True, exist_ok=True)
            import json

            p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        return save_json
