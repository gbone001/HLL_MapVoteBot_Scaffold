<!-- Copilot instructions for contributors/agents working on HLL_MapVoteBot_Scaffold -->
# HLL Map-Vote Bot — Assistant Guidance

This Discord bot orchestrates map votes for Hell Let Loose servers. State lives in JSON under `bot/data/`, and automation hinges on APScheduler plus an RCON/CRCON integration. Use these notes to get productive fast.

## Architecture snapshot
- Entry points: `bot/main.py` (loads env vars, starts `MapVoteBot`), `bot/discord_bot.py` (slash commands, APScheduler bootstrap, game watcher), `docker-compose.yml` (optional local stack).
- Persistence: `bot/utils/persistence.py` (or `persistence/repository.py`) wraps `load_json`/`save_json` with a file lock; never hand-edit files in `bot/data/` from code. Key files include `config.json`, `maps.json`, `pools.json`, `schedules.json`, `votes.json`, `channels.json`, `cooldowns.json`.
- Scheduling: `bot/services/ap_scheduler.py` reads cron-like rows (Australia/Sydney TZ) and calls `bot/rounds.start_new_vote`. Job rows come from `bot/services/schedules.py` and can be modified at runtime via `/schedule_set`.
- Voting lifecycle:
  - `bot/rounds.py` builds vote options through `services/pools.pick_vote_options`, writes `votes.json`, and ensures pinned Discord messages via `services/channel_msgs` + `services/posting`.
  - Closing a round (`services/posting.close_round_and_push`) calls `services/voting.determine_winner`, updates cooldowns, and uses `services/crcon_client.add_map_as_next_rotation` to push the winner server-side.
- Game server integration currently targets HLL RCON v2 (`services/crcon_client`). A CRCON HTTP client layer is planned: keep interfaces injectable so both transports can coexist.

## Discord-specific notes
- Slash commands live in `bot/discord_bot.MapVoteBot`; they assume admin-only usage. `bot/views.py` defines interactive vote buttons; edits must preserve existing component IDs to avoid stale interactions.
- Operational log messages posted to Discord (e.g., confirmations, warnings) must auto-delete after ~20 seconds so channels stay clean; reuse existing helpers or schedule deletions whenever you add new temporary responses.
- Pinned messages act as durable anchors (`Last Vote — Summary`, `Vote — Next Map`). Anytime a pinned message ID changes, call `services/channel_msgs.update_channel_row` to persist the new ID.

## Temporary Discord logs / auto-delete
- Prefer ephemeral responses for slash commands; when you must post into a public channel (e.g., `/schedule_set` confirmations, server setting updates), schedule deletion immediately so channels stay tidy.
- Lean on discord.py’s built-ins: `await channel.send("Saved", delete_after=20)` or `await interaction.followup.send(..., delete_after=20)` so cleanup happens automatically in the background.
- If you already have the message object (e.g., from `followup.send` returning it), call `await message.delete(delay=20)`; no extra tasks or helpers required.

## Game watcher & match detection
- `bot/services/game_watch.py` polls the server every ~25 seconds via `CrconClient.get_latest_match_start_marker`. It caches the last session id inside the relevant `channels.json` row (`last_session_id`) so restarts don’t duplicate work.
- `GameStateNotifier` lets you register handlers; when a new session id appears it awaits each handler (currently wired to `start_new_vote`). Keep handlers lightweight and resilient—exceptions are swallowed, so log internally.
- If you change what constitutes a “new match,” update both the RCON client method and the stored marker format, and migrate existing `channels.json` entries accordingly.

## Testing & tooling
- All testing scaffolding resides under `tests/` (helpers, fixtures, smoke test). See `docs/TESTING.md` for the multi-layer plan (unit/service/Discord/scheduler/RCON/CRCON, contract tests, CI expectations).
- Recommended workflow:
  ```pwsh
  python -m pip install -r requirements-dev.txt
  python -m pytest -q
  ```
  Use Python 3.11+ (3.14 beta will break some deps). Lint/type settings live in `pyproject.toml` (black line length 100, ruff, permissive mypy config).

## CI / testing expectations
- Before pushing, skim `docs/TESTING.md` for the latest coverage goals, pytest markers, and any notes on how to exercise Discord stubs or CRCON contract suites once they land.
- Default CI run is `pytest -q`; keep it green locally and add targeted tests whenever you touch scheduling, voting, or persistence logic.
- When introducing new fixtures or data files, place them under `tests/fixtures/` and document their purpose in `docs/TESTING.md` so future contributors know how to reuse them.

## Patterns & conventions
- Always respect Australia/Sydney TZ when scheduling or parsing times (`bot/utils/time.py`). Tests should freeze time in that zone.
- Treat CRCON/RCON calls as async I/O. When mocking, follow the dict shapes seen in `crcon_client` (e.g., `{"maprotation": [...]}` or `{"session": ...}`) so downstream consumers keep working.
- Wrap persistence access through helpers to avoid race conditions. The write lock is coarse; batch reads/writes when touching multiple JSON files.
- Discord logging is sparse; prefer raising or returning explicit errors inside command handlers so slash-command responses aren’t silently swallowed.

## CRCON HTTP roadmap
- A `GameServerClient` abstraction is being introduced so both transports (current RCON v2 socket client and upcoming CRCON HTTP client) share the same interface (`get_map_rotation`, `set_next_map`, `add_map_to_rotation`, `broadcast`). Keep new code agnostic by accepting the interface instead of concrete clients.
- The CRCON HTTP client will live under `bot/services/crcon_http_client.py` (planned) and use `httpx.AsyncClient`. Contract tests (see `docs/TESTING.md`) must pin endpoint names/methods by comparing against `/api/get_api_documentation` responses; use `respx` for mocking and store fixtures in `tests/crcon_http/`.
- When adding HTTP behavior, include retries/backoff, auth via Bearer tokens, and explicit exception classes (`CrconAuthError`, `CrconPermissionError`, etc.) so both adapters surface errors consistently. Tests should cover these paths before wiring them into the bot.

## Safe edit points / gotchas
- Logic tweaks (cooldowns, pool selection, tie-break rules) belong in `bot/services/pools.py` and `bot/services/voting.py`. These modules are pure functions—ideal for tests.
- Scheduler tweaks should go through `services/ap_scheduler.py` plus `services/schedules.py`; make sure new fields are persisted in `schedules.json` and exposed via `/schedule_set`.
- When touching `services/posting.py`, remember it chains both Discord edits and game-server calls; keep those operations resilient (log failures, but avoid crashing scheduled jobs).
- If you add new JSON schema, seed reasonable defaults in the corresponding `load_json` call so cold starts don’t crash the bot.

## Persistence schema defaults
- All bot state is JSON-backed via `persistence/repository.py` (or `bot/utils/persistence.py`). When introducing a new field, add the default shape to the relevant `_load_json(..., default)` call so fresh installs create valid files automatically.
- For nested objects (e.g., adding `cooldowns[map_name]["last_played"]`), ensure downstream code tolerates missing keys by using `.get()` with sane fallbacks before writing. Only persist once you’ve verified the default structure.
- If you must migrate existing data (renaming fields, changing types), add a shaping step immediately after `load_*` to coerce legacy data into the new schema, and write it back so future loads hit the normalized format.

## Developer workflows
- Local bot run: set `DISCORD_TOKEN`, ensure `bot/data/config.json` has real IDs, then `python bot/main.py` from repo root (working dir matters for data paths).
- Manual server actions: `/server_*` commands call CRCON immediately; mimic their payload shape if you add new RCON verbs.
- Docker: `docker compose up -d` spins up the bot with env-driven config (see compose file for mount paths).

Feedback welcome—ping if any area (tests, CRCON HTTP client expectations, scheduler norms) needs deeper guidance.
