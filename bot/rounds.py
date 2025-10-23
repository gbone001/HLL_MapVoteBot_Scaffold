
import datetime as dt
import discord
from utils.persistence import load_json, save_json
from utils.time import sydney_now, fmt_end
from services.pools import pick_vote_options
from services.posting import edit_current_vote_message
from services.channel_msgs import ensure_persistent_messages, update_channel_row
from views import VoteView

_round_seq = 1
def _next_round_id():
    global _round_seq
    _round_seq += 1
    return _round_seq

async def start_new_vote(bot, guild_id: str, channel_id: str, extra: dict | None = None):
    cfg = load_json("config.json", {})
    extra = extra or {}

    options = pick_vote_options(count=5)

    votes = load_json("votes.json", [])
    rid = _next_round_id()
    ends_at = sydney_now() + dt.timedelta(minutes=cfg.get("vote_duration_minutes", 60))
    round_rec = {
        "id": rid,
        "pool": extra.get("pool", "default"),
        "channel_id": channel_id,
        "started_at": sydney_now().isoformat(),
        "ends_at": ends_at.isoformat(),
        "status": "open",
        "meta": {"mapvote_cooldown": extra.get("mapvote_cooldown", cfg.get("mapvote_cooldown", 2))},
        "options": [{"index": i+1, "map": o["code"], "label": o["label"], "votes": 0} for i, o in enumerate(options)]
    }
    votes.append(round_rec)
    save_json("votes.json", votes)

    embed = discord.Embed(title="Vote — Next Map", description="\n".join([f"**{i+1}. {o['label']}**" for i, o in enumerate(options)]))
    embed.set_footer(text=f"Closes at {fmt_end(ends_at)}")
    view = VoteView(rid, round_rec["options"])

    refs = await ensure_persistent_messages(bot, guild_id, channel_id)
    new_id = await edit_current_vote_message(bot, channel_id, refs["current_vote_message_id"], embed, view)
    if new_id != refs["current_vote_message_id"]:
        update_channel_row(guild_id, channel_id, current_vote_message_id=new_id)
