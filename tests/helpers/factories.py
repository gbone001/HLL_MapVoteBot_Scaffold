"""Simple factories for building test data objects.

These can be expanded later to create vote rounds, map pools, cooldown entries, etc.
"""

from __future__ import annotations

from typing import Any, Dict, List


def make_maps(names: List[str]) -> Dict[str, Any]:
    return {"maps": names}


def make_pools(pool_name: str, maps: List[str]) -> Dict[str, Any]:
    return {"pools": {pool_name: maps}}


def make_cooldowns(entries: List[tuple[str, int]]) -> Dict[str, int]:
    return {name: value for name, value in entries}
