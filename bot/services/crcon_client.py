import aiohttp
import json
import logging
import os
from config import Config
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


logger = logging.getLogger(__name__)

class CrconApiError(RuntimeError):
    """Raised when the CRCON API cannot satisfy a request."""

def create(config: Config):
    api_base = (os.getenv("CRCON_API_BASE") or config.get("crcon").get("api_base") or "").strip()
    if not api_base:
        raise RuntimeError("CRCON_API_BASE (or crcon.api_base) is not configured")

    api_token = (os.getenv("CRCON_API_TOKEN") or config.get("crcon").get("bearer_token") or "").strip()
    if not api_token:
        raise RuntimeError("CRCON_API_TOKEN (or crcon.bearer_token) is not configured")

    dry_run = False
    env = os.getenv("CRCON_DRY_RUN")
    if env is not None:
        dry_run = env.lower().strip() == "true"
    elif config.get("crcon").get("dryrun") is not None:
        dry_run = bool(config.get("crcon").get("dryrun"))

    return CrconClient(api_base, api_token, dry_run)


class CrconClient:
    def __init__(self, api_base: str, bearer_token: str, dry_run: bool):
        if api_base.endswith("/"):
            self.api_base = api_base[:-1]
        else:
            self.api_base = api_base
        self.bearer_token = bearer_token
        self.dry_run = dry_run

    async def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        token = self.bearer_token
        url = f"{self.api_base}{path}" if path.startswith("/") else f"{self.api_base}/{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=15)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(method, url, headers=headers, json=payload) as resp:
                    text = await resp.text()
                    if resp.status >= 400:
                        logger.error("CRCON API %s %s failed (%s): %s", method, path, resp.status, text)
                        raise CrconApiError(f"CRCON API error {resp.status}")
                    if not text:
                        return {}
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return {"raw": text}
        except aiohttp.ClientError as exc:
            logger.error("CRCON API %s %s connection error: %s", method, path, exc)
            raise CrconApiError("CRCON API connection error") from exc


    async def _get(self, path: str) -> Dict[str, Any]:
        return await self._request("GET", path)


    async def _post(self, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await self._request("POST", path, payload=payload)


    async def get_public_info(self) -> Dict[str, Any]:
        data = await self._get("/api/get_public_info")
        if isinstance(data, dict):
            return data.get("result") or data
        return {}


    async def get_map_rotation(self) -> List[Dict[str, Any]]:
        data = await self._get("/api/get_map_rotation")
        if isinstance(data, dict):
            result = data.get("result")
            if isinstance(result, list):
                return result
        return []


    async def get_recent_logs(
        self,
        actions: Optional[Sequence[str]] = None,
        limit: int = 10_000,
    ) -> List[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "end": limit,
            "filter_action": list(actions) if actions else [],
            "filter_player": [],
            "inclusive_filter": "true",
        }
        data = await self._post("/api/get_recent_logs", payload)
        if isinstance(data, dict):
            logs = data.get("result", {}).get("logs", [])
            if isinstance(logs, list):
                normalized: List[Dict[str, Any]] = []
                for entry in logs:
                    if isinstance(entry, dict):
                        normalized.append(entry)
                    else:
                        normalized.append({"message": str(entry)})
                return normalized
        return []


    async def get_latest_match_start_marker(self) -> Optional[str]:
        logs = await self.get_recent_logs(actions=["MATCH START", "MATCH ENDED"], limit=256)
        for entry in logs:
            message = entry.get("message", "") if isinstance(entry, dict) else str(entry)
            if "MATCH START" in message:
                marker = (
                    entry.get("id")
                    or entry.get("log_id")
                    or entry.get("timestamp_ms")
                    or entry.get("timestamp")
                    or message
                )
                return str(marker)
        return None


    async def set_map_rotation(self, map_names: Sequence[str]) -> None:
        if not map_names:
            raise ValueError("map_names must contain at least one entry")
        if self.dry_run:
            logger.info("CRCON dry run enabled; skipping set_map_rotation(%s)", list(map_names))
            return
        await self._post("/api/set_map_rotation", {"map_names": list(map_names)})


    async def add_map_as_next_rotation(self, map_code: str) -> bool:
        await self.set_map_rotation([map_code])
        logger.info("Queued %s as the next map via CRCON API", map_code)
        return True


    async def set_max_ping_autokick(self, ms: int) -> None:
        if ms < 0:
            raise ValueError("max ping must be non-negative")
        await self._post("/api/set_max_ping_autokick", {"max_ms": int(ms)})


    async def set_votekick_enabled(self, value: bool) -> None:
        await self._post("/api/set_votekick_enabled", {"value": bool(value)})


    async def set_votekick_thresholds(self, pairs: Sequence[Tuple[int, int]]) -> None:
        normalized = self._coerce_threshold_pairs(pairs)
        if not normalized:
            raise ValueError("threshold_pairs must contain at least one pair")
        payload_pairs = [[int(p[0]), int(p[1])] for p in normalized]
        await self._post("/api/set_votekick_thresholds", {"threshold_pairs": payload_pairs})


    async def reset_votekick_thresholds(self) -> None:
        await self._post("/api/reset_votekick_thresholds", {})


    async def set_autobalance_enabled(self, value: bool) -> None:
        await self._post("/api/set_autobalance_enabled", {"value": bool(value)})


    async def set_autobalance_threshold(self, diff: int) -> None:
        await self._post("/api/set_autobalance_threshold", {"max_diff": int(diff)})


    async def set_team_switch_cooldown(self, minutes: int) -> None:
        if minutes < 0:
            raise ValueError("team switch cooldown must be >= 0")
        await self._post("/api/set_team_switch_cooldown", {"minutes": int(minutes)})


    async def set_idle_autokick_time(self, minutes: int) -> None:
        if minutes < 0:
            raise ValueError("idle autokick time must be >= 0")
        await self._post("/api/set_idle_autokick_time", {"minutes": int(minutes)})

    # TODO This is nasty. Needs refactoring and/or comments.
    def _coerce_threshold_pairs(self, raw: Any) -> List[Tuple[int, int]]:
        if raw is None:
            return []
        if isinstance(raw, str):
            stripped = raw.strip()
            if not stripped:
                return []
            # Try to parse JSON first (allows "[[0,60],[50,80]]")
            try:
                parsed = json.loads(stripped)
                return self._coerce_threshold_pairs(parsed)
            except json.JSONDecodeError:
                pairs: List[Tuple[int, int]] = []
                for chunk in stripped.split(","):
                    chunk = chunk.strip()
                    if not chunk:
                        continue
                    if ":" in chunk:
                        players, votes = chunk.split(":", 1)
                    else:
                        players, votes = "0", chunk
                    pairs.append((int(players), int(votes)))
                return pairs
        if isinstance(raw, dict):
            pairs: List[Tuple[int, int]] = []
            for players, votes in raw.items():
                pairs.append((int(players), int(votes)))
            return pairs
        if isinstance(raw, Iterable):
            pairs = []
            for item in raw:
                if isinstance(item, dict):
                    if "players" in item and "votes" in item:
                        pairs.append((int(item["players"]), int(item["votes"])))
                    else:
                        raise ValueError(f"Unsupported threshold dict format: {item}")
                elif isinstance(item, (list, tuple)) and len(item) == 2:
                    pairs.append((int(item[0]), int(item[1])))
                else:
                    raise ValueError(f"Unsupported threshold entry: {item}")
            return pairs
        raise ValueError(f"Unsupported threshold_pairs type: {type(raw)}")


    async def apply_server_settings(self, settings: Dict[str, Any]) -> None:
        if not settings:
            return

        async def _run(coro, label: str) -> None:
            try:
                await coro
                logger.info("CRCON setting applied: %s", label)
            except Exception as exc:
                raise CrconApiError(f"{label} failed: {exc}") from exc

        if "high_ping_threshold_ms" in settings:
            await _run(
                self.set_max_ping_autokick(int(settings["high_ping_threshold_ms"])),
                "set_high_ping_threshold",
            )

        if "votekick_enabled" in settings:
            await _run(
                self.set_votekick_enabled(bool(settings["votekick_enabled"])),
                "set_votekick_enabled",
            )

        if settings.get("reset_votekick_thresholds") or settings.get("votekick_reset"):
            await _run(self.reset_votekick_thresholds(), "reset_votekick_thresholds")

        threshold_pairs = settings.get("votekick_threshold_pairs")
        if not threshold_pairs and settings.get("votekick_threshold"):
            threshold_pairs = self._coerce_threshold_pairs(settings.get("votekick_threshold"))
        if threshold_pairs:
            await _run(
                self.set_votekick_thresholds(self._coerce_threshold_pairs(threshold_pairs)),
                "set_votekick_thresholds",
            )

        if "autobalance_enabled" in settings:
            await _run(
                self.set_autobalance_enabled(bool(settings["autobalance_enabled"])),
                "set_autobalance_enabled",
            )

        if "autobalance_threshold" in settings:
            await _run(
                self.set_autobalance_threshold(int(settings["autobalance_threshold"])),
                "set_autobalance_threshold",
            )

        if "team_switch_cooldown_minutes" in settings:
            await _run(
                self.set_team_switch_cooldown(int(settings["team_switch_cooldown_minutes"])),
                "set_team_switch_cooldown",
            )

        if "idlekick_duration_minutes" in settings:
            await _run(
                self.set_idle_autokick_time(int(settings["idlekick_duration_minutes"])),
                "set_idle_autokick_time",
            )
