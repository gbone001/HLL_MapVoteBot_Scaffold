
from utils.persistence import load_json

def load_schedules():
    cfg = load_json("config.json", {})
    default_cd = cfg.get("mapvote_cooldown", 2)
    scheds = load_json("schedules.json", [])
    for s in scheds:
        s.setdefault("mapvote_cooldown", default_cd)
    return scheds
