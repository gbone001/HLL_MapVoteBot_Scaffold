import logging
import sys
import asyncio
import os

from dotenv import load_dotenv
from config import Config
from discord_bot import create

def load_config():
    path = "config.json"
    return Config(path)

def init_logging(logging_config: dict):
    level = logging_config.get("level") or "INFO"
    file_name = logging_config.get("file") or "app.log"
    logging.basicConfig(filename=file_name, level=level)
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

async def amain():
    load_dotenv()

    config  = load_config()
    init_logging(config.get("logging"))

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN missing")

    bot = create(config)
    await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass
