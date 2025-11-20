from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import Any, List

import pytest

from bot.rounds import Rounds


class StubRepository:
    def __init__(self):
        self._votes: List[dict] = []
        self.saved_payload: List[dict] | None = None

    async def load_votes(self) -> List[dict]:
        return list(self._votes)

    async def save_votes(self, votes: List[dict]) -> None:
        self._votes = list(votes)
        self.saved_payload = list(votes)


class StubPools:
    async def pick_vote_options(self, count: int = 5) -> List[dict]:
        return [
            {"code": "FOY", "label": "Foy"},
            {"code": "OMAHA", "label": "Omaha"},
        ][:count]


class StubPosting:
    def __init__(self):
        self.ensure_calls: List[tuple] = []
        self.edits: List[dict] = []
        self.updated_rows: List[dict] = []

    async def ensure_persistent_messages(self, bot, guild_id, channel_id):
        self.ensure_calls.append((bot, guild_id, channel_id))
        return {"current_vote_message_id": "old"}

    async def edit_current_vote_message(self, bot, channel_id, message_id, embed, view):
        self.edits.append({
            "bot": bot,
            "channel_id": channel_id,
            "message_id": message_id,
            "embed": embed,
            "view": view,
        })
        return "new"

    async def update_channel_row(self, guild_id, channel_id, **fields):
        self.updated_rows.append({"guild_id": guild_id, "channel_id": channel_id, **fields})


class StubView:
    def __init__(self, repository, round_id, options):
        self.repository = repository
        self.round_id = round_id
        self.options = options


class StubEmbed:
    def __init__(self, title: str, description: str):
        self.title = title
        self.description = description
        self.footer_text: str | None = None

    def set_footer(self, *, text: str) -> None:
        self.footer_text = text


@pytest.mark.asyncio
async def test_start_new_vote_persists_round_and_updates_messages(monkeypatch: pytest.MonkeyPatch):
    repo = StubRepository()
    pools = StubPools()
    posting = StubPosting()
    rounds = Rounds(
        repository=repo,
        pools=pools,
        posting=posting,
        vote_duration_minutes=5,
        mapvote_cooldown=3,
    )

    fixed = dt.datetime(2024, 1, 1, 12, 0, 0)

    monkeypatch.setattr("bot.rounds._next_round_id", lambda: 42)
    monkeypatch.setattr("bot.rounds.sydney_now", lambda: fixed)
    monkeypatch.setattr("bot.rounds.discord", SimpleNamespace(Embed=StubEmbed))
    monkeypatch.setattr("bot.rounds.VoteView", StubView)

    bot = object()
    await rounds.start_new_vote(bot, guild_id="1", channel_id="2", extra={"minimum_votes": "4"})

    assert repo.saved_payload is not None
    assert repo.saved_payload[0]["id"] == 42
    assert repo.saved_payload[0]["meta"]["minimum_votes"] == 4
    assert repo.saved_payload[0]["options"][0]["label"] == "Foy"

    assert posting.ensure_calls == [(bot, "1", "2")]
    assert posting.updated_rows == [{"guild_id": "1", "channel_id": "2", "current_vote_message_id": "new"}]

    edit = posting.edits[0]
    assert edit["message_id"] == "old"
    assert isinstance(edit["embed"], StubEmbed)
    assert isinstance(edit["view"], StubView)
    assert edit["embed"].footer_text is not None
    assert edit["embed"].footer_text.startswith("Closes at ")
    assert edit["view"].options[0]["label"] == "Foy"
