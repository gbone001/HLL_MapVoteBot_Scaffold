import datetime as dt
import discord
from persistence.repository import Repository
from utils.time import sydney_now, fmt_end
from services.pools import Pools
from services.posting import Posting
from views import VoteView

_round_seq = 1


def _next_round_id():
    global _round_seq
    _round_seq += 1
    return _round_seq


class Rounds:
    def __init__(
        self,
        repository: Repository,
        pools: Pools,
        posting: Posting,
        vote_duration_minutes: int,
        mapvote_cooldown: int,
    ):
        self.repository = repository
        self.pools = pools
        self.posting = posting
        self.vote_duration_minutes = vote_duration_minutes
        self.mapvote_cooldown = mapvote_cooldown

    async def start_new_vote(
        self, bot, guild_id: str, channel_id: str, extra: dict | None = None
    ):
        extra = extra or {}

        options = await self.pools.pick_vote_options(count=5)

        votes = await self.repository.load_votes()
        rid = _next_round_id()
        ends_at = sydney_now() + dt.timedelta(minutes=self.vote_duration_minutes)
        round_rec = {
            "id": rid,
            "pool": extra.get("pool", "default"),
            "channel_id": channel_id,
            "started_at": sydney_now().isoformat(),
            "ends_at": ends_at.isoformat(),
            "status": "open",
            "meta": {
                "mapvote_cooldown": extra.get("mapvote_cooldown", self.mapvote_cooldown)
            },
            "options": [
                {"index": i + 1, "map": o["code"], "label": o["label"], "votes": 0}
                for i, o in enumerate(options)
            ],
        }
        votes.append(round_rec)
        await self.repository.save_votes(votes)

        embed = discord.Embed(
            title="Vote — Next Map",
            description="\n".join(
                [f"**{i+1}. {o['label']}**" for i, o in enumerate(options)]
            ),
        )
        embed.set_footer(text=f"Closes at {fmt_end(ends_at)}")
        view = VoteView(self.repository, rid, round_rec["options"])

        refs = await self.posting.ensure_persistent_messages(bot, guild_id, channel_id)
        new_id = await self.posting.edit_current_vote_message(
            bot, channel_id, refs["current_vote_message_id"], embed, view
        )
        if new_id != refs["current_vote_message_id"]:
            await self.posting.update_channel_row(
                guild_id, channel_id, current_vote_message_id=new_id
            )
