import json
import os
from threading import Lock

DATA_DIR = "bot/data"
_lock = Lock()


def _load_json(filename, default):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(path, "w") as f:
            json.dump(default, f, indent=2)
        return default
    with open(path, "r") as f:
        return json.load(f)


def _save_json(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with _lock:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


class Repository:
    async def load_channels(self):
        return _load_json("channels.json", [])

    async def save_channels(self, channels):
        _save_json("channels.json", channels)

    async def load_schedules(self):
        return _load_json("schedules.json", [])

    async def save_schedules(self, schedules):
        _save_json("schedules.json", schedules)

    async def load_votes(self):
        return _load_json("votes.json", [])

    async def save_votes(self, votes):
        return _save_json("votes.json", votes)

    async def load_cooldowns(self):
        return _load_json("cooldowns.json", {})

    async def save_cooldowns(self, cooldowns):
        _save_json("cooldowns.json", cooldowns)

    async def load_maps(self):
        return _load_json("maps.json", [])

    async def load_pools(self):
        return _load_json("pools.json", [])
