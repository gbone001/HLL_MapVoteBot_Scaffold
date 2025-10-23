
import os

HOST = os.getenv("CRCON_HOST", "127.0.0.1")
PORT = int(os.getenv("CRCON_PORT", "7010"))
PASSWORD = os.getenv("CRCON_PASSWORD", "")

async def rcon_login(host, port, password):
    # TODO: implement real v2 handshake (ServerConnect -> Login)
    return True

async def rcon_call(name: str, body: dict):
    # TODO: implement v2 packet framing + XOR body + AuthToken
    # For now, this is a stub that must be replaced with your real client.
    return {}

async def add_map_as_next_rotation(map_code: str):
    await rcon_login(HOST, PORT, PASSWORD)
    info = await rcon_call("GetServerInformation", {})
    rotation = info.get("maprotation") or info.get("mapsequence") or []
    current_map = info.get("current_map")

    try:
        current_idx = rotation.index(current_map) if current_map in rotation else None
    except ValueError:
        current_idx = None

    insert_at = len(rotation) if current_idx is None else min(len(rotation), int(current_idx) + 1)

    if current_idx is not None and insert_at < len(rotation) and rotation[insert_at] == map_code:
        return True

    await rcon_call("AddMapToRotation", {"MapName": map_code, "Index": int(insert_at)})
    try:
        await rcon_call("ServerBroadcast", {"Message": f"Next map set by vote: {map_code}"})
    except Exception:
        pass
    return True

async def apply_server_settings(s: dict):
    if not s:
        return
    await rcon_login(HOST, PORT, PASSWORD)

    if "high_ping_threshold_ms" in s:
        await rcon_call("SetHighPingThreshold", {"HighPingThresholdMs": int(s["high_ping_threshold_ms"])})

    if "votekick_enabled" in s:
        await rcon_call("SetVoteKickEnabled", {"Enable": bool(s["votekick_enabled"])})

    if "votekick_threshold" in s:
        await rcon_call("SetVoteKickThreshold", {"ThresholdValue": str(s["votekick_threshold"])})

    if s.get("votekick_reset"):
        await rcon_call("ResetVoteKickThreshold", {})

    if "autobalance_enabled" in s:
        await rcon_call("SetAutoBalanceEnabled", {"Enable": bool(s["autobalance_enabled"])})

    if "autobalance_threshold" in s:
        await rcon_call("SetAutoBalanceThreshold", {"AutoBalanceThreshold": int(s["autobalance_threshold"])})

    if "team_switch_cooldown_minutes" in s:
        await rcon_call("SetTeamSwitchCooldown", {"TeamSwitchTimer": int(s["team_switch_cooldown_minutes"])})

    if "idlekick_duration_minutes" in s:
        await rcon_call("SetIdleKickDuration", {"IdleTimeoutMinutes": int(s["idlekick_duration_minutes"])})
