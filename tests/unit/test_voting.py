from __future__ import annotations

import pytest

from bot.services import voting


@pytest.fixture(autouse=True)
def deterministic_choice(monkeypatch: pytest.MonkeyPatch):
    def fake_choice(options):
        return options[0]

    monkeypatch.setattr(voting.random, "choice", fake_choice)


def test_determine_winner_no_votes_returns_random_option_with_detail():
    round_data = {
        "options": [
            {"map": "FOY", "label": "Foy", "votes": 0},
            {"map": "OMAHA", "label": "Omaha", "votes": 0},
        ]
    }

    winner, detail = voting.determine_winner(round_data, return_detail=True)

    assert winner == "FOY"
    assert detail["reason"] == "no_votes"
    assert detail["chosen_label"] == "Foy"


def test_determine_winner_enforces_minimum_votes_before_random(monkeypatch: pytest.MonkeyPatch):
    round_data = {
        "options": [
            {"map": "FOY", "label": "Foy", "votes": 2},
            {"map": "OMAHA", "label": "Omaha", "votes": 0},
        ],
        "meta": {"minimum_votes": 10},
    }

    winner, detail = voting.determine_winner(round_data, return_detail=True)

    assert winner == "FOY"
    assert detail["reason"] == "below_threshold"
    assert detail["required"] == 10
    assert detail["total"] == 2


def test_determine_winner_breaks_ties_randomly(monkeypatch: pytest.MonkeyPatch):
    round_data = {
        "options": [
            {"map": "FOY", "label": "Foy", "votes": 5},
            {"map": "OMAHA", "label": "Omaha", "votes": 5},
            {"map": "UTAH", "label": "Utah", "votes": 1},
        ]
    }

    winner, detail = voting.determine_winner(round_data, return_detail=True)

    assert winner == "FOY"
    assert detail["reason"] == "tie"
    assert detail["tied_labels"] == ["Foy", "Omaha"]


def test_determine_winner_picks_highest_vote_when_unique():
    round_data = {
        "options": [
            {"map": "OMAHA", "label": "Omaha", "votes": 7},
            {"map": "FOY", "label": "Foy", "votes": 3},
        ]
    }

    winner, detail = voting.determine_winner(round_data, return_detail=True)

    assert winner == "OMAHA"
    assert detail["reason"] == "highest"
    assert detail["chosen_label"] == "Omaha"
