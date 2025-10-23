
import asyncio
from utils.persistence import load_json, save_json
from services.crcon_client import rcon_login, rcon_call
from rounds import start_new_vote

async def watch_game_starts(bot, guild_id: str, channel_id: str):
    chans = load_json("channels.json", [])
    row = next((r for r in chans if r.get("guild_id") == guild_id and r.get("channel_id") == channel_id), None)
    if not row:
        return

    while True:
        try:
            await rcon_login(None, None, None)
            info = await rcon_call("GetServerInformation", {})
            session = (info.get("session") or {})
            session_id = session.get("id")
            phase = session.get("phase")
            last = row.get("last_session_id")

            if last is None:
                row["last_session_id"] = session_id
                save_json("channels.json", chans)
            else:
                if session_id and session_id != last:
                    row["last_session_id"] = session_id
                    save_json("channels.json", chans)
                    await start_new_vote(bot, guild_id, channel_id)
        except Exception:
            pass
        await asyncio.sleep(25)
