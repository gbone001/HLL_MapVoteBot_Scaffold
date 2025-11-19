from __future__ import annotations

from typing import Any, List

import pytest
from bot.services.pools import Pools


class StubRepository:
    def __init__(self, maps: List[dict], pools: List[dict], cooldowns: dict[str, Any]):
        self._maps = maps
        self._pools = pools
        self._cooldowns = cooldowns

    async def load_maps(self) -> List[dict]:
        return self._maps

    async def load_pools(self) -> List[dict]:
        return self._pools

    async def load_cooldowns(self) -> dict[str, Any]:
        return self._cooldowns


@pytest.mark.asyncio
async def test_pick_vote_options_prefers_active_pool_and_respects_cooldowns(monkeypatch: pytest.MonkeyPatch):
    maps = [
        {"code": "FOY_WARFARE", "name": "Foy Warfare", "enabled": True},
        {"code": "FOY_NIGHT", "name": "Foy Night", "enabled": True},
        {"code": "UTAH", "name": "Utah", "enabled": True},
    ]
    pools = [
        {"name": "rotation", "maps": ["FOY_WARFARE", "FOY_NIGHT", "UTAH"], "active": True}
    ]
    cooldowns = {"FOY": 2, "UTAH": 0}
    repo = StubRepository(maps, pools, cooldowns)
    service = Pools(repo)

    def fake_sample(population: List[dict], k: int) -> List[dict]:
        return population[:k]

    monkeypatch.setattr("bot.services.pools.random.sample", fake_sample)

    opts = await service.pick_vote_options(count=2)

    assert [o["code"] for o in opts] == ["UTAH", "FOY_WARFARE"]
    assert all("label" in o for o in opts)


@pytest.mark.asyncio
async def test_pick_vote_options_falls_back_to_enabled_maps_when_no_active_pool(monkeypatch: pytest.MonkeyPatch):
    maps = [
        {"code": "SAINT_MERE", "name": "Sainte Mere", "enabled": True},
        {"code": "OMAHA", "name": "Omaha", "enabled": False},
        {"code": "HURTGEN", "name": "Hurtgen", "enabled": True},
    ]
    pools: List[dict] = []
    cooldowns = {"HURTGEN": 0, "SAINT_MERE": 0}
    repo = StubRepository(maps, pools, cooldowns)
    service = Pools(repo)

    def fake_sample(population: List[dict], k: int) -> List[dict]:
        return population[:k]

    monkeypatch.setattr("bot.services.pools.random.sample", fake_sample)

    opts = await service.pick_vote_options(count=2)

    assert [o["code"] for o in opts] == ["SAINT_MERE", "HURTGEN"]
```}