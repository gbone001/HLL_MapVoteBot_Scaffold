"""Scriptable RCON (in-game) stub for tests.

Provides a minimal surface to emulate expected calls and responses. Tests can
configure responses by setting attributes or overriding methods.
"""

from __future__ import annotations

from typing import Any, Dict, List


class MockRconClient:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.rotation: list[str] = []
        self.current_map: str = ""

    async def rcon_login(self) -> dict:
        self.calls.append({"method": "rcon_login"})
        return {"session": "mock-session"}

    async def rcon_call(self, command: str, **kwargs: Any) -> dict:
        self.calls.append({"method": "rcon_call", "command": command, "kwargs": kwargs})
        if command == "get_map_rotation":
            return {"maprotation": list(self.rotation)}
        if command == "get_current_map":
            return {"current_map": self.current_map}
        if command == "add_map_to_rotation":
            map_name = kwargs.get("map_name")
            index = kwargs.get("index")
            if not isinstance(map_name, str):
                raise ValueError("map_name must be a string")
            if index is None:
                self.rotation.append(map_name)
            else:
                self.rotation.insert(int(index), map_name)
            return {"ok": True}
        return {"ok": True}
