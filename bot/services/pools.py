import random
from bot.utils.maps import base_map_code, normalize_cooldowns
from bot.persistence.repository import Repository


class Pools:
    def __init__(self, repository: Repository):
        self.repository = repository

    async def pick_vote_options(self, count=5):
        maps = await self.repository.load_maps()
        pools = await self.repository.load_pools()
        cds = normalize_cooldowns(await self.repository.load_cooldowns())

        pool = next((p for p in pools if p.get("active")), None) or {
            "maps": [m.get("code") for m in maps]
        }

        pool_maps = [
            m for m in maps if m.get("code") in pool["maps"] and m.get("enabled", True)
        ]
        eligible = [
            m for m in pool_maps if int(cds.get(base_map_code(m["code"]), 0)) == 0
        ]

        out = []
        if len(eligible) >= count:
            out = random.sample(eligible, count)
        else:
            need = count - len(eligible)
            cooling = sorted(
                [m for m in pool_maps if int(cds.get(base_map_code(m["code"]), 0)) > 0],
                key=lambda x: cds.get(base_map_code(x["code"]), 0),
            )
            out = eligible + cooling[:need]

        return [{"code": m["code"], "label": m.get("name", m["code"])} for m in out]
