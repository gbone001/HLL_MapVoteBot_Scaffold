
from utils.persistence import load_json, save_json
from discord import Embed

def _store(chans):
    save_json("channels.json", chans)

def _load():
    return load_json("channels.json", [])

def update_channel_row(guild_id: str, channel_id: str, **fields):
    chans = _load()
    row = next((r for r in chans if r.get("guild_id") == guild_id and r.get("channel_id") == channel_id), None)
    if not row:
        row = {"guild_id": guild_id, "channel_id": channel_id, "last_vote_message_id": "0", "current_vote_message_id": "0", "last_session_id": None}
        chans.append(row)
    row.update(fields)
    _store(chans)
    return row

async def ensure_persistent_messages(bot, guild_id: str, channel_id: str):
    chans = _load()
    row = next((r for r in chans if r.get("guild_id") == guild_id and r.get("channel_id") == channel_id), None)
    if not row:
        row = {"guild_id": guild_id, "channel_id": channel_id, "last_vote_message_id": "0", "current_vote_message_id": "0", "last_session_id": None}
        chans.append(row)

    channel = bot.get_channel(int(channel_id))

    if row["last_vote_message_id"] == "0":
        m = await channel.send(embed=_empty_last_vote_embed())
        await m.pin()
        row["last_vote_message_id"] = str(m.id)

    if row["current_vote_message_id"] == "0":
        m = await channel.send(embed=_placeholder_vote_embed())
        await m.pin()
        row["current_vote_message_id"] = str(m.id)

    _store(chans)
    return row

def _empty_last_vote_embed():
    e = Embed(title="Last Vote — Summary", description="No completed votes yet.")
    return e

def _placeholder_vote_embed():
    e = Embed(title="Vote — Next Map", description="No active vote yet.")
    return e
