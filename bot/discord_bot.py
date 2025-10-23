
import asyncio
from discord.ext import commands
from utils.persistence import load_json, save_json
from services.channel_msgs import ensure_persistent_messages
from services.game_watch import watch_game_starts
from rounds import start_new_vote
from services.ap_scheduler import VoteScheduler

import discord

class MapVoteBot(commands.Bot):
    async def setup_hook(self):
        cfg = load_json("config.json", {})
        self.cfg = cfg
        self.guild_id = str(cfg.get("guild_id", ""))
        self.vote_channel_id = str(cfg.get("vote_channel_id", ""))

        @self.event
        async def on_ready():
            print(f"Logged in as {self.user} (id={self.user.id})")
            if self.vote_channel_id and self.guild_id:
                await ensure_persistent_messages(self, self.guild_id, self.vote_channel_id)
                # Start watcher
                self.loop.create_task(watch_game_starts(self, self.guild_id, self.vote_channel_id))
                # Start APScheduler
                self.vote_scheduler = VoteScheduler(self, self.guild_id, self.vote_channel_id)
                self.vote_scheduler.start()

        @self.tree.command(name="vote_start", description="Start a map vote now")
        async def vote_start(interaction: discord.Interaction):
            await start_new_vote(self, self.guild_id, self.vote_channel_id)
            await interaction.response.send_message("Started a new vote.", ephemeral=True)

        # /schedule_set to add/update schedules
        @self.tree.command(name="schedule_set", description="Create or update a scheduled vote")
        async def schedule_set(
            interaction: discord.Interaction,
            pool: str,
            cron: str,
            mapvote_cooldown: int | None = None,
            high_ping_threshold_ms: int | None = None,
            votekick_enabled: bool | None = None,
            votekick_threshold: str | None = None,
            votekick_reset: bool | None = None,
            autobalance_enabled: bool | None = None,
            autobalance_threshold: int | None = None,
            team_switch_cooldown_minutes: int | None = None,
            idlekick_duration_minutes: int | None = None,
        ):
            scheds = load_json("schedules.json", [])
            row = next((x for x in scheds if x.get("pool") == pool and x.get("cron") == cron), None)
            if not row:
                row = {"pool": pool, "cron": cron}
                scheds.append(row)
            if mapvote_cooldown is not None:
                row["mapvote_cooldown"] = int(mapvote_cooldown)

            settings = row.setdefault("settings", {})
            def maybe_set(k, v, cast=lambda x: x):
                if v is not None:
                    settings[k] = cast(v)
            maybe_set("high_ping_threshold_ms", high_ping_threshold_ms, int)
            maybe_set("votekick_enabled", votekick_enabled, bool)
            maybe_set("votekick_threshold", votekick_threshold, str)
            maybe_set("votekick_reset", votekick_reset, bool)
            maybe_set("autobalance_enabled", autobalance_enabled, bool)
            maybe_set("autobalance_threshold", autobalance_threshold, int)
            maybe_set("team_switch_cooldown_minutes", team_switch_cooldown_minutes, int)
            maybe_set("idlekick_duration_minutes", idlekick_duration_minutes, int)

            save_json("schedules.json", scheds)
            try:
                self.vote_scheduler.reload_jobs()
            except Exception:
                pass
            await interaction.response.send_message("Schedule saved and jobs reloaded.", ephemeral=True)

        await self.tree.sync()
