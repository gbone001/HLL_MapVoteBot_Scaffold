import discord
import json
from discord import Embed
from persistence.repository import Repository
from utils.maps import base_map_code, normalize_cooldowns
from services.voting import determine_winner
from services.crcon_client import CrconClient


# TODO This shouldn't be here. Need to figure out why config is even loaded below.
def _load_config():
    path = "config.json"
    with open(path, "r") as f:
        return json.load(f)

def _empty_last_vote_embed():
    e = Embed(title="Last Vote — Summary", description="No completed votes yet.")
    return e

def _placeholder_vote_embed():
    e = Embed(title="Vote — Next Map", description="No active vote yet.")
    return e

class Posting:
    def __init__(self, repository: Repository, rcon_client: CrconClient):
        self.repository = repository
        self.rcon_client = rcon_client

    async def update_channel_row(self, guild_id: str, channel_id: str, **fields):
        chans = await self.repository.load_channels()
        row = next((r for r in chans if r.get("guild_id") == guild_id and r.get("channel_id") == channel_id), None)
        if not row:
            row = {"guild_id": guild_id, "channel_id": channel_id, "last_vote_message_id": "0", "current_vote_message_id": "0", "last_session_id": None}
            chans.append(row)
        row.update(fields)
        await self.repository.save_channels(chans)
        return row

    async def ensure_persistent_messages(self, bot, guild_id: str, channel_id: str):
        chans = await self.repository.load_channels()
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

        await self.repository.save_channels(chans)
        return row

    async def edit_current_vote_message(self, bot, channel_id, message_id, embed, view):
        channel = bot.get_channel(int(channel_id))
        try:
            msg = await channel.fetch_message(int(message_id))
            await msg.edit(embed=embed, view=view)
        except Exception:
            new_msg = await channel.send(embed=embed, view=view)
            await new_msg.pin()
            return str(new_msg.id)
        return message_id

    # TODO This does way too much ... needs a closer look.
    async def edit_last_vote_summary(self, bot, channel_id, message_id, summary_embed):
        channel = bot.get_channel(int(channel_id))
        try:
            msg = await channel.fetch_message(int(message_id))
            await msg.edit(embed=summary_embed, view=None)
        except Exception:
            new_msg = await channel.send(embed=summary_embed)
            await new_msg.pin()
            return str(new_msg.id)
        return message_id

    async def close_round_and_push(self, bot, guild_id, channel_id, round_id: int):
        votes = await self.repository.load_votes()
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

        await self.rcon_client.add_map_as_next_rotation(winner_map)

        cooldowns = normalize_cooldowns(await self.repository.load_cooldowns())
        for k in list(cooldowns.keys()):
            cooldowns[k] = max(0, int(cooldowns[k]) - 1)
        round_cd = r.get("meta", {}).get("mapvote_cooldown", _load_config()("config.json", {}).get("mapvote_cooldown", 2))
        cooldowns[base_map_code(winner_map)] = int(round_cd)
        await self.repository.save_cooldowns(cooldowns)

        r["status"] = "pushed"
        await self.repository.save_votes(votes)

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

        refs = await self.ensure_persistent_messages(bot, guild_id, channel_id)
        new_last = await self.edit_last_vote_summary(bot, channel_id, refs["last_vote_message_id"], e)
        if new_last != refs["last_vote_message_id"]:
            await self.update_channel_row(guild_id, channel_id, last_vote_message_id=new_last)
