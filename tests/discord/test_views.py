from __future__ import annotations

import pytest

from bot.views import VoteButton
from tests.helpers.stub_discord import StubInteraction


class Repo:
    def __init__(self, status: str = "open") -> None:
        self.votes = [
            {
                "id": 7,
                "status": status,
                "ballots": {},
            }
        ]
        self.saved = None

    async def load_votes(self):
        return self.votes

    async def save_votes(self, payload):
        self.saved = payload


@pytest.mark.discord_stub
@pytest.mark.asyncio
async def test_vote_button_records_ballot_and_defers_response():
    repo = Repo(status="open")
    button = VoteButton(repo, round_id=7, index=2, label="Utah")
    interaction = StubInteraction()

    await button.callback(interaction)

    assert repo.votes[0]["ballots"][str(interaction.user.id)] == 2
    assert interaction.response.deferred is True


@pytest.mark.discord_stub
@pytest.mark.asyncio
async def test_vote_button_handles_closed_round():
    repo = Repo(status="closed")
    button = VoteButton(repo, round_id=7, index=1, label="Foy")
    interaction = StubInteraction()

    await button.callback(interaction)

    assert interaction.responses[0]["content"] == "This vote is closed."
    assert interaction.responses[0]["ephemeral"] is True
