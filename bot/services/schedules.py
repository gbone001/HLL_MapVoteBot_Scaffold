
from utils.persistence import load_json

def load_schedules():
    cfg = load_json("config.json", {})
    default_cd = cfg.get("mapvote_cooldown", 2)
    scheds = load_json("schedules.json", [])
    for s in scheds:
        # preserve existing behavior and add a toggle for enabling/disabling interactive mapvote
        s.setdefault("mapvote_cooldown", default_cd)
        s.setdefault("mapvote_enabled", True)
    return scheds
