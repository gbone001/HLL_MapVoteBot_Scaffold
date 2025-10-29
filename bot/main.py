import json
import logging
import sys
import asyncio
import os

from discord_bot import MapVoteBot

def load_config():
    path = "bot/data/config.json"
    with open(path, "r") as f:
        return json.load(f)

def init_logging(logging_config: dict):
    level = logging_config.get("level") or "INFO"
    file_name = logging_config.get("file") or "app.log"
    logging.basicConfig(filename=file_name, level=level)
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

async def amain():
    config  = load_config()
    init_logging(config.get("logging"))

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN missing")

    bot = MapVoteBot(
        guild_id=config.get("guild_id"),
        vote_channel_id=config.get("vote_channel_id")
    )
    await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass
