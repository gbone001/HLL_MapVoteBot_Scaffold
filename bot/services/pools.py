
import random
from utils.persistence import load_json

def pick_vote_options(count=5):
    maps = load_json("maps.json", [])
    pools = load_json("pools.json", [])
    cds = load_json("cooldowns.json", {})

    pool = next((p for p in pools if p.get("active")), None) or {"maps": [m.get("code") for m in maps]}

    pool_maps = [m for m in maps if m.get("code") in pool["maps"] and m.get("enabled", True)]
    eligible = [m for m in pool_maps if int(cds.get(m["code"], 0)) == 0]

    out = []
    if len(eligible) >= count:
        out = random.sample(eligible, count)
    else:
        need = count - len(eligible)
        cooling = sorted([m for m in pool_maps if int(cds.get(m["code"], 0)) > 0], key=lambda x: cds.get(x["code"], 0))
        out = eligible + cooling[:need]

    return [{"code": m["code"], "label": m.get("name", m["code"])} for m in out]
