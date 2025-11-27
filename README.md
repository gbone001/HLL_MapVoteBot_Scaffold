> **Heads up:** After pulling the latest scaffold changes, reinstall the Python deps (ideally in a fresh virtualenv) with `pip install -r requirements.txt && pip install -r requirements-dev.txt` so the new Discord/test dependencies are available.

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
4. Use `/schedule_set` to add a schedule (e.g., pool=`Warfare Week A`, aps.trigger=`cron`, aps.hour=`18`, aps.minute=`0`, aps.day_of_week=`fri`, mapvote_cooldown=`3`).

## Schedule JSON example
```json
{
  "pool": "Warfare Week A",
  "aps": {
    "trigger": "cron",
    "minute": 0,
    "hour": 18,
    "day_of_week": "fri"
  },
  "mapvote_cooldown": 3,
  "minimum_votes": 5,
  "mapvote_enabled": true,
  "settings": {
    "high_ping_threshold_ms": 180,
    "votekick_enabled": true,
    "votekick_threshold_pairs": [
      [0, 60]
    ],
    "reset_votekick_thresholds": false,
    "autobalance_enabled": true,
    "autobalance_threshold": 4,
    "team_switch_cooldown_minutes": 10,
    "idlekick_duration_minutes": 8
  }
}
```
The example above uses an APS `cron` trigger that fires every Friday at 18:00.

`mapvote_enabled` controls whether an interactive Discord map vote is started for this schedule (`true`) or whether the bot will pick a map immediately and push it to the server (`false`). Cooldown behaviour still applies when `mapvote_enabled` is `false`.

`minimum_votes` sets the minimum number of ballots that must be cast before the vote result is honoured. If the round closes with fewer votes than this threshold, the bot falls back to the random selection logic (same as the "no votes" case) so that a winner is still chosen without favouring a small sample.

`votekick_threshold_pairs` follows the CRCON API shape: each entry is `[player_count, votes_required]`.  
If you prefer to type a quick string (e.g. `"0:60,60:70"`), the bot will coerce it into the pair list automatically when saving schedules.

## Manual server commands
Admins can adjust the same CRCON settings on demand via slash commands:

- `/server_set_high_ping` — Set `high_ping_threshold_ms`.
- `/server_set_votekick_enabled` — Toggle votekick on/off.
- `/server_set_votekick_thresholds` — Update the votekick threshold table (accepts JSON or shorthand `player:votes` pairs).
- `/server_reset_votekick_thresholds` — Restore the server default thresholds.
- `/server_set_autobalance_enabled` — Toggle autobalance.
- `/server_set_autobalance_threshold` — Update the allowed team size difference.
- `/server_set_team_switch_cooldown` — Set `team_switch_cooldown_minutes`.
- `/server_set_idle_autokick_time` — Set `idlekick_duration_minutes`.
- `/mapvote_enabled` — Set the global default for whether scheduled jobs start an interactive Discord map vote (`true`) or immediately pick and push a map (`false`). Updates `config.json` and reloads scheduler jobs.

All commands require Discord administrator permissions and relay directly through the CRCON API.

## In-bot Scheduler
- The bot starts an **AsyncIOScheduler** (AEST/AEDT timezone) and loads all entries from `schedules.json`.
- Jobs can be reloaded automatically on an interval controlled by `scheduler_reload_minutes` in `config.json` (default `60`). Set `0` to disable.
- Admins can use `/schedule_set` to create or update schedule rows without editing files; this also reloads jobs immediately.

## Testing

For the complete testing approach (unit, service, Discord stubs, scheduler, RCON v2, CRCON HTTP client and contract tests, plus CI recommendations), see the Testing Guide:

- docs/TESTING.md
