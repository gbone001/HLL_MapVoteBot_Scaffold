import json
import logging
import os
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import aiohttp

logger = logging.getLogger(__name__)

class CrconApiError(RuntimeError):
    """Raised when the CRCON API cannot satisfy a request."""


_CONFIG_CACHE: Optional[Dict[str, Any]] = None

# TODO - this shouldn't be here. Need to inject a config wrapper that can reload it.
def load_config():
    path = "config.json"
    with open(path, "r") as f:
        return json.load(f)

def _crcon_settings() -> Dict[str, Any]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        cfg = load_config()
        _CONFIG_CACHE = cfg.get("crcon") or {}
    return _CONFIG_CACHE

# TODO This should be injected.
def _api_base() -> str:
    base = os.getenv("CRCON_API_BASE") or _crcon_settings().get("api_base") or ""
    base = base.strip()
    if base.endswith("/"):
        base = base[:-1]
    return base

# TODO This should be injected.
def _api_token() -> str:
    return (os.getenv("CRCON_API_TOKEN") or _crcon_settings().get("bearer_token") or "").strip()

# TODO This should be injected.
def _is_dry_run() -> bool:
    env = os.getenv("CRCON_DRY_RUN")
    if env is not None:
        return env.lower() in {"1", "true", "yes", "on"}
    settings = _crcon_settings()
    return bool(settings.get("dryrun"))

# TODO This should be checked upon bootstrap.
def _ensure_api_config() -> None:
    if not _api_base():
        raise CrconApiError("CRCON_API_BASE (or crcon.api_base) is not configured")
    if not _api_token():
        raise CrconApiError("CRCON_API_TOKEN (or crcon.bearer_token) is not configured")


async def _request(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _ensure_api_config()
    base = _api_base()
    token = _api_token()
    url = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
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


async def _get(path: str) -> Dict[str, Any]:
    return await _request("GET", path)


async def _post(path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return await _request("POST", path, payload=payload)


async def rcon_login(host: Optional[str], port: Optional[int], password: Optional[str]) -> bool:  # noqa: ARG001
    """Kept for compatibility with existing call-sites. Validates API config."""
    _ensure_api_config()
    return True


async def get_public_info() -> Dict[str, Any]:
    data = await _get("/api/get_public_info")
    if isinstance(data, dict):
        return data.get("result") or data
    return {}


async def get_map_rotation() -> List[Dict[str, Any]]:
    data = await _get("/api/get_map_rotation")
    if isinstance(data, dict):
        result = data.get("result")
        if isinstance(result, list):
            return result
    return []


async def get_recent_logs(
    actions: Optional[Sequence[str]] = None,
    limit: int = 10_000,
) -> List[Dict[str, Any]]:
    payload: Dict[str, Any] = {
        "end": limit,
        "filter_action": list(actions) if actions else [],
        "filter_player": [],
        "inclusive_filter": "true",
    }
    data = await _post("/api/get_recent_logs", payload)
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


async def get_latest_match_start_marker() -> Optional[str]:
    logs = await get_recent_logs(actions=["MATCH START", "MATCH ENDED"], limit=256)
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


async def set_map_rotation(map_names: Sequence[str]) -> None:
    if not map_names:
        raise ValueError("map_names must contain at least one entry")
    if _is_dry_run():
        logger.info("CRCON dry run enabled; skipping set_map_rotation(%s)", list(map_names))
        return
    await _post("/api/set_map_rotation", {"map_names": list(map_names)})


async def add_map_as_next_rotation(map_code: str) -> bool:
    await set_map_rotation([map_code])
    logger.info("Queued %s as the next map via CRCON API", map_code)
    return True


async def set_max_ping_autokick(ms: int) -> None:
    if ms < 0:
        raise ValueError("max ping must be non-negative")
    await _post("/api/set_max_ping_autokick", {"max_ms": int(ms)})


async def set_votekick_enabled(value: bool) -> None:
    await _post("/api/set_votekick_enabled", {"value": bool(value)})


async def set_votekick_thresholds(pairs: Sequence[Tuple[int, int]]) -> None:
    normalized = _coerce_threshold_pairs(pairs)
    if not normalized:
        raise ValueError("threshold_pairs must contain at least one pair")
    payload_pairs = [[int(p[0]), int(p[1])] for p in normalized]
    await _post("/api/set_votekick_thresholds", {"threshold_pairs": payload_pairs})


async def reset_votekick_thresholds() -> None:
    await _post("/api/reset_votekick_thresholds", {})


async def set_autobalance_enabled(value: bool) -> None:
    await _post("/api/set_autobalance_enabled", {"value": bool(value)})


async def set_autobalance_threshold(diff: int) -> None:
    await _post("/api/set_autobalance_threshold", {"max_diff": int(diff)})


async def set_team_switch_cooldown(minutes: int) -> None:
    if minutes < 0:
        raise ValueError("team switch cooldown must be >= 0")
    await _post("/api/set_team_switch_cooldown", {"minutes": int(minutes)})


async def set_idle_autokick_time(minutes: int) -> None:
    if minutes < 0:
        raise ValueError("idle autokick time must be >= 0")
    await _post("/api/set_idle_autokick_time", {"minutes": int(minutes)})

# TODO This is nasty. Needs refactoring and/or comments.
def _coerce_threshold_pairs(raw: Any) -> List[Tuple[int, int]]:
    if raw is None:
        return []
    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return []
        # Try to parse JSON first (allows "[[0,60],[50,80]]")
        try:
            parsed = json.loads(stripped)
            return _coerce_threshold_pairs(parsed)
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


async def apply_server_settings(settings: Dict[str, Any]) -> None:
    if not settings:
        return

    await rcon_login(None, None, None)

    async def _run(coro, label: str) -> None:
        try:
            await coro
            logger.info("CRCON setting applied: %s", label)
        except Exception as exc:
            raise CrconApiError(f"{label} failed: {exc}") from exc

    if "high_ping_threshold_ms" in settings:
        await _run(
            set_max_ping_autokick(int(settings["high_ping_threshold_ms"])),
            "set_high_ping_threshold",
        )

    if "votekick_enabled" in settings:
        await _run(
            set_votekick_enabled(bool(settings["votekick_enabled"])),
            "set_votekick_enabled",
        )

    if settings.get("reset_votekick_thresholds") or settings.get("votekick_reset"):
        await _run(reset_votekick_thresholds(), "reset_votekick_thresholds")

    threshold_pairs = settings.get("votekick_threshold_pairs")
    if not threshold_pairs and settings.get("votekick_threshold"):
        threshold_pairs = _coerce_threshold_pairs(settings.get("votekick_threshold"))
    if threshold_pairs:
        await _run(
            set_votekick_thresholds(_coerce_threshold_pairs(threshold_pairs)),
            "set_votekick_thresholds",
        )

    if "autobalance_enabled" in settings:
        await _run(
            set_autobalance_enabled(bool(settings["autobalance_enabled"])),
            "set_autobalance_enabled",
        )

    if "autobalance_threshold" in settings:
        await _run(
            set_autobalance_threshold(int(settings["autobalance_threshold"])),
            "set_autobalance_threshold",
        )

    if "team_switch_cooldown_minutes" in settings:
        await _run(
            set_team_switch_cooldown(int(settings["team_switch_cooldown_minutes"])),
            "set_team_switch_cooldown",
        )

    if "idlekick_duration_minutes" in settings:
        await _run(
            set_idle_autokick_time(int(settings["idlekick_duration_minutes"])),
            "set_idle_autokick_time",
        )
