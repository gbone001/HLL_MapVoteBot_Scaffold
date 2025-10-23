
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from services.schedules import load_schedules
from services.crcon_client import apply_server_settings
from rounds import start_new_vote
from utils.persistence import load_json

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

            async def job_wrapper(settings=s.get("settings", {}), mv_cd=s.get("mapvote_cooldown"), pool=s.get("pool")):
                await apply_server_settings(settings or {})
                await start_new_vote(self.bot, self.guild_id, self.channel_id, extra={
                    "mapvote_cooldown": mv_cd,
                    "pool": pool or "default"
                })

            j = self.scheduler.add_job(job_wrapper, trigger, id=f"vote_job_{idx}")
            self.jobs.append(j)
