
# HLL Map-Vote Bot (JSON + RCON v2 + APScheduler)

- JSON persistence (no DB)
- Weekly schedules with per-schedule server settings (in-bot APScheduler only)
- *mapvote_cooldown* to exclude recent winners
- Two pinned messages in the vote channel: **Last Vote — Summary** and **Vote — Next Map**
- Tie/no-vote → random selection
- Close → **AddMapToRotation(MapName, Index)** to queue the voted map as **NEXT**
- Game-start watcher automatically starts a new vote on new matches
- **APScheduler (in-bot only)** reads `schedules.json` and triggers votes automatically; `/schedule_set` can create/edit jobs live

## Quick start
1. Fill `bot/data/config.json` with your IDs and CRCON.
2. `docker compose up -d` (or run `python bot/main.py` in a Python env with requirements installed).
3. Use `/vote_start` for a manual test.
4. Use `/schedule_set` to add a cron schedule (e.g., pool=`Warfare Week A`, cron=`0 18 * * FRI`, mapvote_cooldown=`3`).

## Schedule JSON example
```json
{
  "pool": "Warfare Week A",
  "cron": "0 18 * * FRI",
  "mapvote_cooldown": 3,
  "settings": {
    "high_ping_threshold_ms": 180,
    "votekick_enabled": true,
    "votekick_threshold": "60",
    "votekick_reset": false,
    "autobalance_enabled": true,
    "autobalance_threshold": 4,
    "team_switch_cooldown_minutes": 10,
    "idlekick_duration_minutes": 8
  }
}
```

## In-bot Scheduler
- The bot starts an **AsyncIOScheduler** (AEST/AEDT timezone) and loads all entries from `schedules.json`.
- Jobs can be reloaded automatically on an interval controlled by `scheduler_reload_minutes` in `config.json` (default `60`). Set `0` to disable.
- Admins can use `/schedule_set` to create or update schedule rows without editing files; this also reloads jobs immediately.
