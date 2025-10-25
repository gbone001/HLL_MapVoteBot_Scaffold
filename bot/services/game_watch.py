
import asyncio

from utils.persistence import load_json, save_json
from services.crcon_client import get_latest_match_start_marker, rcon_login
from rounds import start_new_vote

async def watch_game_starts(bot, guild_id: str, channel_id: str):
    chans = load_json("channels.json", [])
    row = next((r for r in chans if r.get("guild_id") == guild_id and r.get("channel_id") == channel_id), None)
    if not row:
        return

    while True:
        try:
            await rcon_login(None, None, None)
            session_marker = await get_latest_match_start_marker()
            last = row.get("last_session_id")

            if session_marker is None:
                await asyncio.sleep(25)
                continue

            if last is None:
                row["last_session_id"] = session_marker
                save_json("channels.json", chans)
            elif session_marker != last:
                row["last_session_id"] = session_marker
                save_json("channels.json", chans)
                await start_new_vote(bot, guild_id, channel_id)
        except Exception:
            pass
        await asyncio.sleep(25)
