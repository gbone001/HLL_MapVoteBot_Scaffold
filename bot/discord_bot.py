
import asyncio
import json
import logging
from discord import app_commands
from discord.ext import commands
from utils.persistence import load_json, save_json
from services.channel_msgs import ensure_persistent_messages
from services.game_watch import watch_game_starts
from rounds import start_new_vote
from services.ap_scheduler import VoteScheduler
from services.crcon_client import apply_server_settings

import discord

logger = logging.getLogger(__name__)

def parse_threshold_pairs_input(raw: str | None):
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    try:
        data = json.loads(stripped)
        if isinstance(data, list):
            pairs = []
            for entry in data:
                if isinstance(entry, (list, tuple)) and len(entry) == 2:
                    pairs.append([int(entry[0]), int(entry[1])])
            if pairs:
                return pairs
    except json.JSONDecodeError:
        pass
    pairs = []
    for chunk in stripped.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" in chunk:
            players, votes = chunk.split(":", 1)
        else:
            players, votes = "0", chunk
        pairs.append([int(players), int(votes)])
    return pairs or None

class MapVoteBot(commands.Bot):
    def __init__(self, guild_id, vote_channel_id):
        self.guild_id = guild_id
        self.vote_channel_id = vote_channel_id

        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="/", intents=intents)

    async def setup_hook(self):
        @self.event
        async def on_ready():
            logger.info(f"Logged in as {self.user} (id={self.user.id})")
            if self.vote_channel_id and self.guild_id:
                await ensure_persistent_messages(self, self.guild_id, self.vote_channel_id)
                # Start watcher
                self.loop.create_task(watch_game_starts(self, self.guild_id, self.vote_channel_id))
                # Start APScheduler
                self.vote_scheduler = VoteScheduler(self, self.guild_id, self.vote_channel_id)
                self.vote_scheduler.start()

        @self.tree.command(name="vote_start", description="Start a map vote now")
        async def vote_start(interaction: discord.Interaction):
            logger.info("Received command: vote_start")
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
            logger.info("Received command: schedule_set")
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
            maybe_set("autobalance_enabled", autobalance_enabled, bool)
            maybe_set("autobalance_threshold", autobalance_threshold, int)
            maybe_set("team_switch_cooldown_minutes", team_switch_cooldown_minutes, int)
            maybe_set("idlekick_duration_minutes", idlekick_duration_minutes, int)

            if votekick_threshold is not None:
                pairs = parse_threshold_pairs_input(votekick_threshold)
                if pairs:
                    settings["votekick_threshold_pairs"] = pairs
                settings.pop("votekick_threshold", None)
            if votekick_reset is not None:
                settings["reset_votekick_thresholds"] = bool(votekick_reset)
                settings.pop("votekick_reset", None)

            save_json("schedules.json", scheds)
            try:
                self.vote_scheduler.reload_jobs()
            except Exception:
                pass
            await interaction.response.send_message("Schedule saved and jobs reloaded.", ephemeral=True)

        async def _run_manual(interaction: discord.Interaction, label: str, payload: dict):
            try:
                await apply_server_settings(payload)
            except Exception as exc:
                await interaction.response.send_message(f"{label} failed: {exc}", ephemeral=True)
            else:
                await interaction.response.send_message(f"{label} updated.", ephemeral=True)

            @self.tree.command(name="mapvote_enabled", description="Set global default for whether scheduled votes start an interactive mapvote")
            @app_commands.describe(value="Enable interactive mapvote (true) or pick map immediately (false)")
            @app_commands.checks.has_permissions(administrator=True)
            async def mapvote_enabled(interaction: discord.Interaction, value: bool):
                logger.info("Received command: mapvote_enabled")
                cfg = load_json("config.json", {})
                cfg["mapvote_enabled"] = bool(value)
                save_json("config.json", cfg)
                try:
                    # reload scheduler jobs if present so new default applies for future schedule loads
                    if hasattr(self, "vote_scheduler"):
                        self.vote_scheduler.reload_jobs()
                except Exception:
                    pass
                await interaction.response.send_message(f"Global mapvote_enabled set to {value}", ephemeral=True)

        @self.tree.command(name="server_set_high_ping", description="Set max ping autokick threshold (milliseconds)")
        @app_commands.describe(ms="Ping threshold in milliseconds before players are kicked automatically")
        @app_commands.checks.has_permissions(administrator=True)
        async def server_set_high_ping(interaction: discord.Interaction, ms: app_commands.Range[int, 0]):
            logger.info("Received command: server_set_high_ping")
            await _run_manual(interaction, "High ping threshold", {"high_ping_threshold_ms": int(ms)})

        @self.tree.command(name="server_set_votekick_enabled", description="Enable or disable votekick on the server")
        @app_commands.describe(value="Enable votekick (true) or disable it (false)")
        @app_commands.checks.has_permissions(administrator=True)
        async def server_set_votekick_enabled(interaction: discord.Interaction, value: bool):
            logger.info("Received command: server_set_votekick_enabled")
            await _run_manual(interaction, "Votekick enabled", {"votekick_enabled": bool(value)})

        @self.tree.command(name="server_set_votekick_thresholds", description="Set the votekick threshold table")
        @app_commands.describe(pairs="JSON or shorthand string (e.g. \"0:60,60:70\")")
        @app_commands.checks.has_permissions(administrator=True)
        async def server_set_votekick_thresholds(interaction: discord.Interaction, pairs: str):
            logger.info("Received command: server_set_votekick_thresholds")
            parsed = parse_threshold_pairs_input(pairs)
            if not parsed:
                await interaction.response.send_message("Could not parse threshold pairs.", ephemeral=True)
                return
            await _run_manual(interaction, "Votekick thresholds", {"votekick_threshold_pairs": parsed})

        @self.tree.command(name="server_reset_votekick_thresholds", description="Reset votekick thresholds to server defaults")
        @app_commands.checks.has_permissions(administrator=True)
        async def server_reset_votekick_thresholds(interaction: discord.Interaction):
            logger.info("Received command: server_reset_votekick_thresholds")
            await _run_manual(interaction, "Reset votekick thresholds", {"reset_votekick_thresholds": True})

        @self.tree.command(name="server_set_autobalance_enabled", description="Turn server autobalance on or off")
        @app_commands.describe(value="Enable autobalance (true) or disable it (false)")
        @app_commands.checks.has_permissions(administrator=True)
        async def server_set_autobalance_enabled(interaction: discord.Interaction, value: bool):
            logger.info("Received command: server_set_autobalance_enabled")
            await _run_manual(interaction, "Autobalance enabled", {"autobalance_enabled": bool(value)})

        @self.tree.command(name="server_set_autobalance_threshold", description="Set the autobalance team size differential")
        @app_commands.describe(diff="Maximum player difference before autobalance triggers")
        @app_commands.checks.has_permissions(administrator=True)
        async def server_set_autobalance_threshold(interaction: discord.Interaction, diff: app_commands.Range[int, 0]):
            logger.info("Received command: server_set_autobalance_threshold")
            await _run_manual(interaction, "Autobalance threshold", {"autobalance_threshold": int(diff)})

        @self.tree.command(name="server_set_team_switch_cooldown", description="Set the team switch cooldown in minutes")
        @app_commands.describe(minutes="Cooldown before players can switch teams again")
        @app_commands.checks.has_permissions(administrator=True)
        async def server_set_team_switch_cooldown(interaction: discord.Interaction, minutes: app_commands.Range[int, 0]):
            logger.info("Received command: server_set_team_switch_cooldown")
            await _run_manual(interaction, "Team switch cooldown", {"team_switch_cooldown_minutes": int(minutes)})

        @self.tree.command(name="server_set_idle_autokick_time", description="Set idle auto-kick duration in minutes")
        @app_commands.describe(minutes="Minutes players can remain idle before being kicked")
        @app_commands.checks.has_permissions(administrator=True)
        async def server_set_idle_autokick_time(interaction: discord.Interaction, minutes: app_commands.Range[int, 0]):
            logger.info("Received command: server_set_idle_autokick_time")
            await _run_manual(interaction, "Idle autokick time", {"idlekick_duration_minutes": int(minutes)})

        await self.tree.sync()
