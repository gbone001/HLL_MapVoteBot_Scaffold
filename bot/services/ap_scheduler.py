
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from services.schedules import load_schedules
from services.crcon_client import apply_server_settings, add_map_as_next_rotation
from rounds import start_new_vote
from utils.persistence import load_json, save_json
from services.pools import pick_vote_options

class VoteScheduler:
    def __init__(self, bot, guild_id: str, channel_id: str):
        self.bot = bot
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.scheduler = AsyncIOScheduler(timezone="Australia/Sydney")
        self.jobs = []

    def start(self):
        self.scheduler.start()
        self.reload_jobs()
        try:
            cfg = load_json("config.json", {})
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

    def reload_jobs(self):
        self.clear_jobs()
        scheds = load_schedules()
        for idx, s in enumerate(scheds):
            cron = s.get("cron")
            if not cron:
                continue
            try:
                trigger = CronTrigger.from_crontab(cron, timezone="Australia/Sydney")
            except Exception:
                continue

            async def job_wrapper(settings=s.get("settings", {}), mv_cd=s.get("mapvote_cooldown"), pool=s.get("pool"), mv_enabled=s.get("mapvote_enabled", True)):
                # Apply server settings regardless
                await apply_server_settings(settings or {})

                # If mapvote is enabled, start an interactive vote as before
                if mv_enabled:
                    await start_new_vote(self.bot, self.guild_id, self.channel_id, extra={
                        "mapvote_cooldown": mv_cd,
                        "pool": pool or "default"
                    })
                    return

                # Mapvote disabled: choose a map immediately (random selection respecting cooldowns)
                # Reuse pools.pick_vote_options to get 1 candidate (it already respects cooldowns)
                try:
                    opts = pick_vote_options(count=1)
                    if not opts:
                        return
                    chosen = opts[0]["code"]

                    # Push chosen map to server rotation
                    await add_map_as_next_rotation(chosen)

                    # Update cooldowns: decrement existing entries and set cooldown for chosen map
                    cds = load_json("cooldowns.json", {})
                    for k in list(cds.keys()):
                        cds[k] = max(0, int(cds.get(k, 0)) - 1)
                    round_cd = mv_cd if mv_cd is not None else load_json("config.json", {}).get("mapvote_cooldown", 2)
                    cds[chosen] = int(round_cd)
                    save_json("cooldowns.json", cds)
                except Exception:
                    # keep scheduler resilient; swallowing errors here mirrors existing behavior
                    pass

            j = self.scheduler.add_job(job_wrapper, trigger, id=f"vote_job_{idx}")
            self.jobs.append(j)
