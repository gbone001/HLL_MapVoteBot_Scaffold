
import discord
from utils.persistence import load_json, save_json
from services.voting import determine_winner
from services.crcon_client import add_map_as_next_rotation
from services.channel_msgs import ensure_persistent_messages, update_channel_row

async def edit_current_vote_message(bot, channel_id, message_id, embed, view):
    channel = bot.get_channel(int(channel_id))
    try:
        msg = await channel.fetch_message(int(message_id))
        await msg.edit(embed=embed, view=view)
    except Exception:
        new_msg = await channel.send(embed=embed, view=view)
        await new_msg.pin()
        return str(new_msg.id)
    return message_id

async def edit_last_vote_summary(bot, channel_id, message_id, summary_embed):
    channel = bot.get_channel(int(channel_id))
    try:
        msg = await channel.fetch_message(int(message_id))
        await msg.edit(embed=summary_embed, view=None)
    except Exception:
        new_msg = await channel.send(embed=summary_embed)
        await new_msg.pin()
        return str(new_msg.id)
    return message_id

async def close_round_and_push(bot, guild_id, channel_id, round_id: int):
    votes = load_json("votes.json", [])
    r = next((x for x in votes if x.get("id") == round_id), None)
    if not r or r.get("status") != "open":
        return

    ballots = r.get("ballots", {})
    for o in r["options"]:
        o["votes"] = 0
    for uid, idx in ballots.items():
        for o in r["options"]:
            if o["index"] == idx:
                o["votes"] += 1

    winner_map, detail = determine_winner(r, return_detail=True)

    await add_map_as_next_rotation(winner_map)

    cds = load_json("cooldowns.json", {})
    for k, v in list(cds.items()):
        cds[k] = max(0, v - 1)
    round_cd = r.get("meta", {}).get("mapvote_cooldown", load_json("config.json", {}).get("mapvote_cooldown", 2))
    cds[winner_map] = round_cd
    save_json("cooldowns.json", cds)

    r["status"] = "pushed"
    save_json("votes.json", votes)

    e = discord.Embed(title="Last Vote — Summary")
    lines = []
    for opt in r["options"]:
        lines.append(f"• **{opt['label']}** — {opt['votes']} votes")
    if detail["reason"] == "no_votes":
        lines.append(f"\n_No votes cast. Randomly selected **{detail['chosen_label']}**._")
    elif detail["reason"] == "tie":
        lines.append(f"\n_Tie detected. Randomly selected **{detail['chosen_label']}** among: {', '.join(detail['tied_labels'])}._")
    else:
        lines.append(f"\n_Winner by votes: **{detail['chosen_label']}**._")
    e.description = "\n".join(lines)

    refs = await ensure_persistent_messages(bot, guild_id, channel_id)
    new_last = await edit_last_vote_summary(bot, channel_id, refs["last_vote_message_id"], e)
    if new_last != refs["last_vote_message_id"]:
        update_channel_row(guild_id, channel_id, last_vote_message_id=new_last)
