from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from bot.services.ap_scheduler import VoteScheduler


class StubScheduler:
    def __init__(self):
        self.jobs: List[SimpleNamespace] = []
        self.removed: List[str] = []

    def remove_job(self, job_id: str) -> None:
        self.removed.append(job_id)

    def add_job(self, func, trigger, id: str):
        job = SimpleNamespace(id=id, func=func, trigger=trigger)
        self.jobs.append(job)
        return job


class StubRepository:
    def __init__(self, schedules: List[dict], cooldowns: Dict[str, int] | None = None):
        self._schedules = schedules
        self._cooldowns = cooldowns or {}
        self.saved_cooldowns: Dict[str, int] | None = None

    async def load_schedules(self) -> List[dict]:
        return list(self._schedules)

    async def load_cooldowns(self) -> Dict[str, int]:
        return dict(self._cooldowns)

    async def save_cooldowns(self, payload: Dict[str, int]) -> None:
        self.saved_cooldowns = dict(payload)


class StubPools:
    def __init__(self):
        self.options = [{"code": "FOY", "label": "Foy"}]

    def pick_vote_options(self, count: int = 1):
        return self.options[:count]


class StubRounds:
    def __init__(self):
        self.calls: List[dict] = []

    async def start_new_vote(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})


class StubClient:
    def __init__(self):
        self.applied: List[dict] = []
        self.queued: List[str] = []

    async def apply_server_settings(self, settings: Dict[str, Any]) -> None:
        self.applied.append(settings)

    async def add_map_as_next_rotation(self, map_code: str) -> bool:
        self.queued.append(map_code)
        return True


@pytest.mark.asyncio
async def test_load_schedules_shapes_defaults(monkeypatch: pytest.MonkeyPatch):
    repo = StubRepository(
        schedules=[
            {"cron": "0 0 * * *", "mapvote_cooldown": None, "minimum_votes": "", "mapvote_enabled": True},
            {"cron": "0 0 * * *", "mapvote_enabled": False},
        ]
    )
    scheduler = VoteScheduler(
        bot=object(),
        repository=repo,
        pools=StubPools(),
        rounds=StubRounds(),
        crcon_client=StubClient(),
        guild_id="1",
        channel_id="2",
    )
    scheduler.scheduler = StubScheduler()

    monkeypatch.setattr("bot.services.ap_scheduler._load_config", lambda: {"mapvote_cooldown": 3, "minimum_votes": 2})

    shaped = await scheduler._load_schedules()

    assert shaped[0]["mapvote_cooldown"] == 3
    assert shaped[0]["minimum_votes"] == 0
    assert shaped[1]["mapvote_cooldown"] == 3
    assert shaped[1]["minimum_votes"] == 2


@pytest.mark.asyncio
async def test_reload_jobs_registers_cron_and_runs_mapvote_round(monkeypatch: pytest.MonkeyPatch):
    repo = StubRepository(
        schedules=[
            {
                "cron": "*/5 * * * *",
                "settings": {"high_ping_threshold_ms": 200},
                "mapvote_enabled": True,
                "pool": "default",
                "minimum_votes": 3,
            }
        ]
    )
    pools = StubPools()
    rounds = StubRounds()
    client = StubClient()
    scheduler = VoteScheduler(
        bot="bot",
        repository=repo,
        pools=pools,
        rounds=rounds,
        crcon_client=client,
        guild_id="g",
        channel_id="c",
    )
    stub_scheduler = StubScheduler()
    scheduler.scheduler = stub_scheduler

    monkeypatch.setattr("bot.services.ap_scheduler._load_config", lambda: {"mapvote_cooldown": 2, "minimum_votes": 0})

    await scheduler.reload_jobs()

    assert len(stub_scheduler.jobs) == 1

    job = stub_scheduler.jobs[0]
    await job.func()

    assert client.applied == [{"high_ping_threshold_ms": 200}]
    assert rounds.calls[0]["kwargs"]["extra"]["minimum_votes"] == 3


@pytest.mark.asyncio
async def test_job_wrapper_without_mapvote_queues_next_map(monkeypatch: pytest.MonkeyPatch):
    repo = StubRepository(
        schedules=[
            {
                "cron": "*/10 * * * *",
                "mapvote_enabled": False,
                "pool": "rotation",
                "mapvote_cooldown": None,
            }
        ],
        cooldowns={"FOY": 1},
    )
    pools = StubPools()
    rounds = StubRounds()
    client = StubClient()
    scheduler = VoteScheduler(
        bot="bot",
        repository=repo,
        pools=pools,
        rounds=rounds,
        crcon_client=client,
        guild_id="g",
        channel_id="c",
    )
    scheduler.scheduler = StubScheduler()

    monkeypatch.setattr("bot.services.ap_scheduler._load_config", lambda: {"mapvote_cooldown": 4})

    await scheduler.reload_jobs()
    job = scheduler.scheduler.jobs[0]
    await job.func()

    assert client.queued == ["FOY"]
    assert repo.saved_cooldowns is not None
    assert repo.saved_cooldowns["FOY"] == 4