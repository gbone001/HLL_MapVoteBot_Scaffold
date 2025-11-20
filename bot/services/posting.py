import asyncio
import discord
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from discord import Embed

from bot.persistence.repository import Repository
from bot.utils.maps import base_map_code, normalize_cooldowns
from bot.services.voting import determine_winner
from bot.services.game_server_client import GameServerClient
from bot.views import ManagementControlView


logger = logging.getLogger(__name__)


def _empty_last_vote_embed():
    e = Embed(title="Last Vote — Summary", description="No completed votes yet.")
    return e

def _placeholder_vote_embed():
    e = Embed(title="Vote — Next Map", description="No active vote yet.")
    return e

class Posting:
    def __init__(self, repository: Repository, rcon_client: GameServerClient, *, default_mapvote_cooldown: int):
        self.repository = repository
        self.rcon_client = rcon_client
        self.default_mapvote_cooldown = max(0, int(default_mapvote_cooldown))
        self._maps_by_code: Optional[Dict[str, dict]] = None
        self._maps_by_pretty: Optional[Dict[str, dict]] = None
        self._last_status_snapshot: Optional[Dict[str, Any]] = None

    async def _ensure_map_indexes(self) -> None:
        if self._maps_by_code is not None and self._maps_by_pretty is not None:
            return

        maps = await self.repository.load_maps()
        code_index: Dict[str, dict] = {}
        pretty_index: Dict[str, dict] = {}
        for entry in maps:
            if not isinstance(entry, dict):
                continue
            code = str(entry.get("code") or "").strip()
            if code:
                code_index[code.lower()] = entry
            pretty = str(entry.get("prettyName") or "").strip()
            if pretty:
                pretty_index[pretty.lower()] = entry
        self._maps_by_code = code_index
        self._maps_by_pretty = pretty_index

    async def _lookup_map(self, identifier: Optional[str]) -> Optional[dict]:
        if not identifier:
            return None
        await self._ensure_map_indexes()
        ident = identifier.lower()
        entry = (self._maps_by_code or {}).get(ident)
        if entry:
            return entry
        entry = (self._maps_by_pretty or {}).get(ident)
        if entry:
            return entry
        return None

    @staticmethod
    def _coalesce(data: Dict[str, Any], keys: tuple[str, ...], default: Optional[str] = None) -> Optional[str]:
        for key in keys:
            value = data.get(key)
            if value is None:
                continue
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    return stripped
            else:
                return str(value)
        return default

    @staticmethod
    def _format_time_remaining(raw: Any) -> str:
        if raw is None:
            return "Unknown"
        if isinstance(raw, str):
            stripped = raw.strip()
            if not stripped:
                return "Unknown"
            if stripped.replace(":", "").isdigit() and ":" in stripped:
                return stripped
            try:
                total_seconds = int(float(stripped))
            except ValueError:
                return stripped
        else:
            try:
                total_seconds = int(float(raw))
            except (TypeError, ValueError):
                return "Unknown"

        if total_seconds < 0:
            total_seconds = 0
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    async def _fetch_server_status(self) -> Dict[str, Any]:
        snapshot: Dict[str, Any] = {
            "server_name": "Unknown Server",
            "map_label": "Unknown",
            "map_mode": "Unknown",
            "allied": "0",
            "axis": "0",
            "time_remaining": "Unknown",
            "updated_at": datetime.now(timezone.utc),
        }

        try:
            raw = await self.rcon_client.get_public_info()
        except Exception as exc:
            logger.warning("Failed to fetch public info from CRCON: %s", exc)
            return snapshot

        if not isinstance(raw, dict):
            return snapshot
        data = raw.get("result") if isinstance(raw.get("result"), dict) else raw

        server_name = self._coalesce(
            data,
            ("name", "server_name", "hostname", "ServerName"),
            default="Unknown Server",
        )

        map_identifier = self._coalesce(
            data,
            ("current_map", "map", "currentMap", "CurrentMap", "map_code"),
        )

        map_mode = self._coalesce(
            data,
            ("current_gamemode", "currentGameMode", "map_mode", "GameMode"),
            default="Unknown",
        )

        allied = self._coalesce(
            data,
            ("num_allied", "allied_players", "allied", "players_allied", "AlliedCount"),
            default="0",
        )

        axis = self._coalesce(
            data,
            ("num_axis", "axis_players", "axis", "players_axis", "AxisCount"),
            default="0",
        )

        remaining_raw = data.get("time_remaining") or data.get("map_time_remaining") or data.get("timeRemaining")

        map_entry = await self._lookup_map(map_identifier) if map_identifier else None
        map_label = map_entry.get("base") if map_entry else None
        if not map_label:
            map_label = map_entry.get("prettyName") if map_entry else None
        map_label = map_label or (map_identifier or "Unknown")

        if map_entry and map_mode == "Unknown":
            map_mode = map_entry.get("gamemode", "Unknown")

        snapshot.update(
            {
                "server_name": server_name or "Unknown Server",
                "map_label": map_label,
                "map_mode": map_mode or "Unknown",
                "allied": allied or "0",
                "axis": axis or "0",
                "time_remaining": self._format_time_remaining(remaining_raw),
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self._last_status_snapshot = snapshot
        return snapshot

    async def _build_management_embed(self) -> Embed:
        status = await self._fetch_server_status()
        updated_at = status.get("updated_at")
        if isinstance(updated_at, datetime):
            updated_str = updated_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            updated_str = str(updated_at)

        description_lines = [
            "Click the buttons below to manage the map pool schedule and voting",
            "",
            "**Connected Server**",
            f"{status.get('server_name')} | Current Map {status.get('map_label')} (map type: {status.get('map_mode')}) | Allied: {status.get('allied')} | Axis: {status.get('axis')} | Time: {status.get('time_remaining')}",

            f"Updated at {updated_str}",
            "",
            "Buttons stay active across restarts.",
        ]

        embed = Embed(
            title="Hell Let Loose Map Pool Scheduling and Voting",
            description="\n".join(description_lines),
        )
        return embed

    async def update_channel_row(self, guild_id: str, channel_id: str, **fields):
        chans = await self.repository.load_channels()
        row = next((r for r in chans if r.get("guild_id") == guild_id and r.get("channel_id") == channel_id), None)
        if not row:
            row = {
                "guild_id": guild_id,
                "channel_id": channel_id,
                "last_vote_message_id": "0",
                "current_vote_message_id": "0",
                "management_message_id": "0",
                "last_session_id": None,
            }
            chans.append(row)
        row.update(fields)
        await self.repository.save_channels(chans)
        return row

    async def ensure_persistent_messages(self, bot, guild_id: str, channel_id: str):
        chans = await self.repository.load_channels()
        row = next((r for r in chans if r.get("guild_id") == guild_id and r.get("channel_id") == channel_id), None)
        if not row:
            row = {
                "guild_id": guild_id,
                "channel_id": channel_id,
                "last_vote_message_id": "0",
                "current_vote_message_id": "0",
                "management_message_id": "0",
                "last_session_id": None,
            }
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

        management_id = row.get("management_message_id", "0")
        new_management_id = await self.ensure_management_message(
            bot,
            guild_id,
            channel_id,
            existing_message_id=management_id if isinstance(management_id, str) else str(management_id),
        )
        row["management_message_id"] = new_management_id

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

    async def ensure_management_message(
        self,
        bot,
        guild_id: str,
        channel_id: str,
        *,
        existing_message_id: Optional[str] = None,
    ) -> str:
        try:
            channel = bot.get_channel(int(channel_id))
        except Exception:
            channel = None
        if channel is None:
            try:
                channel = await bot.fetch_channel(int(channel_id))
            except Exception as exc:
                logger.error("Unable to resolve channel %s for management message: %s", channel_id, exc)
                raise

        embed = await self._build_management_embed()
        view = ManagementControlView()

        message_id = (existing_message_id or "0") if existing_message_id else "0"
        if message_id and message_id != "0":
            try:
                msg = await channel.fetch_message(int(message_id))
                await msg.edit(embed=embed, view=view)
                return message_id
            except Exception as exc:
                logger.info(
                    "Existing management message %s missing; creating new one (%s)",
                    message_id,
                    exc,
                )

        new_msg = await channel.send(embed=embed, view=view)
        await new_msg.pin()
        return str(new_msg.id)

    async def periodic_management_refresh(
        self,
        bot,
        guild_id: str,
        channel_id: str,
        *,
        interval_seconds: int = 60,
    ) -> None:
        while True:
            try:
                chans = await self.repository.load_channels()
                row = next(
                    (
                        r
                        for r in chans
                        if r.get("guild_id") == guild_id and r.get("channel_id") == channel_id
                    ),
                    None,
                )
                existing_id = str(row.get("management_message_id", "0")) if row else "0"
                new_id = await self.ensure_management_message(
                    bot,
                    guild_id,
                    channel_id,
                    existing_message_id=existing_id,
                )
                if row and new_id != existing_id:
                    row["management_message_id"] = new_id
                    await self.repository.save_channels(chans)
            except Exception as exc:
                logger.warning("Failed to refresh management message: %s", exc)
            await asyncio.sleep(max(15, interval_seconds))

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
        round_cd = r.get("meta", {}).get("mapvote_cooldown", self.default_mapvote_cooldown)
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
        elif detail["reason"] == "below_threshold":
            required = detail.get("required")
            total = detail.get("total")
            lines.append(
                f"\n_Only {total} votes cast (need {required}). Randomly selected **{detail['chosen_label']}**._"
            )
        elif detail["reason"] == "tie":
            lines.append(f"\n_Tie detected. Randomly selected **{detail['chosen_label']}** among: {', '.join(detail['tied_labels'])}._")
        else:
            lines.append(f"\n_Winner by votes: **{detail['chosen_label']}**._")
        e.description = "\n".join(lines)

        refs = await self.ensure_persistent_messages(bot, guild_id, channel_id)
        new_last = await self.edit_last_vote_summary(bot, channel_id, refs["last_vote_message_id"], e)
        if new_last != refs["last_vote_message_id"]:
            await self.update_channel_row(guild_id, channel_id, last_vote_message_id=new_last)
