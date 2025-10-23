<!-- Copilot instructions for contributors/agents working on HLL_MapVoteBot_Scaffold -->
# HLL Map-Vote Bot — Assistant Guidance

This repository is a lightweight Discord bot that runs scheduled and manual map votes for HLL servers using JSON persistence and an RCON client. The instructions below are focused, actionable guidance to help an AI coding agent be productive immediately.

- Project entrypoints
  - `bot/main.py` — starts the bot (reads `DISCORD_TOKEN` env). Use `python bot/main.py` or `docker compose up` (see `docker-compose.yml`).
  - `bot/discord_bot.py` — defines `MapVoteBot`, commands (`/vote_start`, `/schedule_set`), sets up the APScheduler and game watcher.

- Major components and data flow
  - JSON persistence: `bot/utils/persistence.py` reads/writes files under `bot/data/` (filenames: `config.json`, `maps.json`, `pools.json`, `schedules.json`, `votes.json`, `channels.json`, `cooldowns.json`). Prefer using `load_json`/`save_json` for all state changes.
  - Scheduling: `bot/services/ap_scheduler.py` loads cron-style entries from `schedules.json` (via `services/schedules.py`) and schedules votes. Jobs call `start_new_vote` in `bot/rounds.py`.
  - Voting flow: `bot/rounds.py` builds the vote options using `services/pools.py` (which consults cooldowns and pools), persists a `votes.json` round object, and updates two pinned messages via `services/channel_msgs.py` and `services/posting.py`.
  - Closing a round: `services/posting.py::close_round_and_push` tallies votes using `services/voting.py::determine_winner`, updates cooldowns (`cooldowns.json`) and calls `services/crcon_client.py::add_map_as_next_rotation` to push the winner to the game server.
  - RCON client: `bot/services/crcon_client.py` currently contains stubs for v2 handshake and calls; treat it as a required integration point — changes here affect `game_watch.py`, `ap_scheduler.py` and `posting.py`.

- Key files to reference when making changes
  - `bot/data/config.json` — runtime config (guild_id, vote_channel_id, apscheduler settings). Used by `discord_bot.py` and `ap_scheduler.py`.
  - `bot/services/crcon_client.py` — implement or mock RCON v2 protocol here. Many functions expect `rcon_login` and `rcon_call` to return dictionaries with `maprotation`, `current_map`, and `session` keys.
  - `bot/services/pools.py` and `bot/services/voting.py` — pure logic; safe and recommended places to add tests.
  - `bot/services/channel_msgs.py` and `bot/services/posting.py` — handle Discord message lifecycle (pinning, fetching, editing). Use `ensure_persistent_messages` when starting a vote.

- Conventions and patterns
  - Files under `bot/data/` are authoritative state (JSON). Always use `load_json`/`save_json` to read/write these files so locking and defaults are respected.
  - Timezone and scheduling: APScheduler and time functions use Australia/Sydney (see `bot/utils/time.py` and `ap_scheduler.py`). Respect this timezone when computing schedules or tests.
  - Minimal external dependencies: the RCON client is a stub. Do not assume a working network integration; add a clear mock when running unit tests.
  - Discord interactions: the bot uses discord.py's command tree (`self.tree.command`) and `discord.Interaction`. View objects are returned from `bot/views.py` (vote buttons) — update them carefully to preserve message edit semantics.

- Developer workflows (quick commands)
  - Run locally with a valid token: set env `DISCORD_TOKEN` and run `python bot/main.py` (the code expects the working dir to be project root).
  - Docker: `docker compose up -d` (project includes `docker-compose.yml`).
  - Testing: there are no automated tests in the repo; when adding tests, prefer testing pure functions in `services/` (e.g., `determine_winner`, `pick_vote_options`). Mock `load_json`/`save_json` and `crcon_client`.

- Common changes and safe edit points
  - Implementing RCON v2: modify `bot/services/crcon_client.py`. Keep the same async function signatures (`rcon_login`, `rcon_call`, `add_map_as_next_rotation`, `apply_server_settings`) to avoid touching callers.
  - Adjusting vote options or cooldown logic: change `bot/services/pools.py`; tests can exercise `pick_vote_options` with fake `maps.json`, `pools.json`, and `cooldowns.json` data.
  - Modifying message layout: edit `bot/services/channel_msgs.py` and `bot/services/posting.py::edit_*` functions and `bot/views.py` for interaction views. Remember that pinned messages are used as anchors; if message ids change, call `update_channel_row` to persist them.

- Examples from the code
  - Creating a new vote is done by calling: `await start_new_vote(bot, guild_id, channel_id)` (see `bot/discord_bot.py` and `bot/services/ap_scheduler.py`).
  - Vote close flow: `close_round_and_push` loads `votes.json`, computes winner via `determine_winner`, calls `add_map_as_next_rotation`, updates `cooldowns.json`, then updates pinned summary (see `bot/services/posting.py`).

- Cautionary notes
  - Concurrency: `bot/utils/persistence.py` uses a simple threading.Lock; writes are serialized but there is no transactional semantics. Avoid complex concurrent edits across multiple functions without reading and writing full datasets.
  - Error handling: many I/O operations swallow exceptions (especially in scheduler and game watch loops). When adding features that must be robust, update logging and consider failing jobs loudly.

If anything here is unclear or you'd like me to expand a section (examples for tests, mock patterns for RCON, or a short developer README addition), tell me which section and I'll iterate.
