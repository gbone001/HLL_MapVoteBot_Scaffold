import json
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from services.crcon_client import CrconClient
from rounds import Rounds
from persistence.repository import Repository
from services.pools import Pools

# TODO This shouldn't be here. Need to inject a config wrapper that can reload the config.
def _load_config():
    path = "config.json"
    with open(path, "r") as f:
        return json.load(f)

class VoteScheduler:
    def __init__(self, bot, repository: Repository, pools: Pools, rounds: Rounds, crcon_client: CrconClient, guild_id: str, channel_id: str):
        # TODO Should not depend on bot.
        self.bot = bot
        self.repository = repository
        self.pools = pools
        self.rounds = rounds
        self.crcon_client = crcon_client
        self.guild_id = guild_id
        self.channel_id = channel_id
        # TODO This shouldn't be hardcoded to some specific timezone.
        self.scheduler = AsyncIOScheduler(timezone="Australia/Sydney")
        self.jobs = []

    async def  _load_schedules(self):
        cfg = _load_config()
        default_cd = cfg.get("mapvote_cooldown", 2)
        scheds = await self.repository.load_schedules()
        for s in scheds:
            s.setdefault("mapvote_cooldown", default_cd)
            s.setdefault("mapvote_enabled", True)
        return scheds

    async def start(self):
        self.scheduler.start()
        await self.reload_jobs()
        try:
            cfg = _load_config()
            interval = int(cfg.get("scheduler_reload_minutes", 60))
        except Exception:
            interval = 60
        if interval and interval > 0:
            self.scheduler.add_job(self.reload_jobs, "interval", minutes=interval, id="reload_jobs")

    def clear_jobs(self):
        for j in list(self.jobs):
            try:
                self.scheduler.remove_job(j.id)
            except Exception:
                pass
        self.jobs.clear()

    async def reload_jobs(self):
        self.clear_jobs()
        scheds = await self._load_schedules()
        for idx, s in enumerate(scheds):
            cron = s.get("cron")
            if not cron:
                continue
            try:
                trigger = CronTrigger.from_crontab(cron, timezone="Australia/Sydney")
            except Exception:
                continue

            # TODO I reckon much of this logic should live in the bot.
            # The scheduler would get a handler injected and call that handler with the respective schedule/settings.
            # The bot (or a service it uses) would then be responsible for applying the settings and starting a vote (if required).
            # This would remove the bidirectional dependency and drastically simplify the scheduler.
            async def job_wrapper(settings=s.get("settings", {}), mv_cd=s.get("mapvote_cooldown"), pool=s.get("pool"), mv_enabled=s.get("mapvote_enabled", True)):
                # Apply server settings regardless
                await self.crcon_client.apply_server_settings(settings or {})

                # If mapvote is enabled, start an interactive vote as before
                if mv_enabled:
                    await self.rounds.start_new_vote(self.bot, self.guild_id, self.channel_id, extra={
                        "mapvote_cooldown": mv_cd,
                        "pool": pool or "default"
                    })
                    return

                # Mapvote disabled: choose a map immediately (random selection respecting cooldowns)
                # Reuse pools.pick_vote_options to get 1 candidate (it already respects cooldowns)
                try:
                    opts = self.pools.pick_vote_options(count=1)
                    if not opts:
                        return
                    chosen = opts[0]["code"]

                    # Push chosen map to server rotation
                    await self.crcon_client.add_map_as_next_rotation(chosen)

                    # Update cooldowns: decrement existing entries and set cooldown for chosen map
                    cds = await self.repository.load_cooldowns()
                    for k in list(cds.keys()):
                        cds[k] = max(0, int(cds.get(k, 0)) - 1)
                    round_cd = mv_cd if mv_cd is not None else _load_config().get("mapvote_cooldown", 2)
                    cds[chosen] = int(round_cd)
                    await self.repository.save_cooldowns(cds)
                except Exception:
                    # keep scheduler resilient; swallowing errors here mirrors existing behavior
                    pass

            j = self.scheduler.add_job(job_wrapper, trigger, id=f"vote_job_{idx}")
            self.jobs.append(j)
