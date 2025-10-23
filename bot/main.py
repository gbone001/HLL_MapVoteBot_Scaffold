
import asyncio
import os
from discord.ext import commands
from discord_bot import MapVoteBot

async def amain():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN missing")

    import discord
    intents = discord.Intents.default()
    intents.message_content = True

    bot = MapVoteBot(command_prefix="!", intents=intents)
    await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass
