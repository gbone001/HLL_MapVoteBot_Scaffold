# Testing Guide

This guide describes a complete test strategy for the HLL Map‑Vote Bot covering core logic, Discord interactions, the in‑bot scheduler, the in‑game RCON v2 protocol, and the CRCON HTTP API. It aims to keep tests fast and deterministic while catching upstream/API drift early.

## Goals

- Catch regressions in voting, map pool selection, cooldowns, scheduling, and message lifecycle before deployment.
- Verify Discord command handlers and scheduled jobs via isolated async tests.
- Validate integrations through two server backends:
  - RCON v2 (in‑game)
  - CRCON HTTP API (admin/web API)
- Guard against CRCON API drift with contract tests backed by `/api/get_api_documentation`.
- Enforce quality gates (lint, type‑check, coverage) in CI for each PR.

## Test Layers

1) Unit tests (pure logic, fast)
- Target: `bot/services/pools.py`, `bot/services/voting.py`, `bot/utils/maps.py`, `bot/utils/time.py`.
- Validate: deterministic option selection, cooldown expiry, tallying (ties, empty vote), timezone math.
- Tools: `pytest`, `pytest-asyncio`, `freezegun`.

2) Service‑facade tests (logic + persistence boundary)
- Target: `bot/rounds.py`, logic within `bot/services/posting.py` that is independent of Discord HTTP calls.
- Strategy: monkeypatch `load_json`/`save_json` to temp storage and assert round lifecycle, state snapshots, and winner persistence.

3) Discord interaction simulation
- Target: command handlers in `bot/discord_bot.py`, components in `bot/views.py`.
- Provide stubs for `discord.Interaction`, `discord.Message`, `discord.TextChannel` to assert ephemeral responses, embeds, and edited messages.

4) Scheduler & timezone tests
- Target: `bot/services/ap_scheduler.py`.
- Inject a test scheduler, freeze Australia/Sydney time, and assert cron boundaries and job wiring.

5) RCON v2 integration tests (mocked)
- Target: callers that use in‑game RCON flows.
- Mock handshake/session expiry, rotation updates, and malformed payloads to assert resiliency and error handling.

6) CRCON HTTP API client tests (mocked)
- Target: a thin `CrconHttpClient` (to be introduced) using `httpx.AsyncClient`.
- Tools: `respx` for HTTP mocking, `jsonschema` or `pydantic` for response validation.
- Cover:
  - Auth: Bearer token header on all requests; 401/403 handling.
  - Request building: correct GET/POST, JSON body vs query, timeouts.
  - Retry/backoff for 5xx and transient network errors; cap retries and assert behavior.
  - Idempotency policy for any retried “write” operations (documented and tested).
- Edge cases:
  - 401 unauthorized (bad/expired token) → `CrconAuthError`.
  - 403 forbidden (insufficient permissions) → `CrconPermissionError`.
  - 404 endpoint drift; 429 rate limit with `Retry-After`; 5xx with capped retries; request timeouts.

7) CRCON endpoint‑contract tests
- Based on `GET /api/get_api_documentation` (or a frozen fixture), assert that the subset of endpoints this bot relies on exists with the expected HTTP method and argument names.
- Typical endpoints used by the bot:
  - `get_map_rotation` (GET) — read rotation
  - `get_current_map` (GET) — read current map
  - `add_map_to_rotation` (POST) — append/insert next map
  - `set_next_map` (POST) — when available; otherwise emulate via rotation ops
  - Optional: `do_broadcast` (POST) — in‑game announcements
  - Optional: `get_gamestate`, `get_historical_logs` — diagnostics/analytics
- Live mode (optional): if `CRCON_BASE_URL` and `CRCON_API_TOKEN` are set, fetch the live documentation in CI and compare only the subset we use; otherwise use a repository fixture.

8) End‑to‑end orchestrated scenario (mocked)
- Simulate: schedule vote → cast ballots → close round → queue winner.
- Run parametrically against two adapters (RCON v2 and CRCON HTTP) via a unified interface to ensure consistent behavior across backends.

9) Non‑functional and quality gates
- Performance sanity for typical data sizes.
- Static checks: `mypy` (≥ 80% coverage to start).
- Lint/style: `ruff` + `black`.
- Coverage threshold: start at 75%+ and raise to 85%+.

## Unified Client Interface

Introduce a small interface to abstract the server backend and enable adapter‑agnostic tests:

```python
class GameServerClient(Protocol):
    async def get_map_rotation(self) -> list[str]: ...
    async def get_current_map(self) -> str: ...
    async def add_map_to_rotation(
        self,
        map_name: str,
        after_map_name: str | None = None,
        index: int | None = None,
    ) -> str: ...
    async def set_next_map(self, map_name: str) -> str: ...
    async def broadcast(self, message: str) -> None: ...
```

Provide two implementations:
- `RconV2Client(GameServerClient)`
- `CrconHttpClient(GameServerClient)`

Integration and E2E tests parametrize over both to ensure consistent semantics.

## Test Tree (proposed)

```
tests/
  unit/
    test_pools.py
    test_voting.py
    test_time_utils.py
  services/
    test_rounds.py
    test_posting_logic.py
    test_rcon_v2_client.py
  crcon_http/
    test_http_client_auth.py
    test_http_client_requests.py
    test_http_client_errors.py
    test_contract_endpoints.py
  integration/
    test_scheduler.py
    test_vote_flow_parametrized.py  # runs with both adapters
  discord/
    test_commands.py
    test_views.py
  fixtures/
    data_samples/
      maps_basic.json
      pools_basic.json
      schedules_sample.json
    crcon_http/
      get_api_documentation_min.json
  helpers/
    mock_persistence.py
    mock_rcon.py
    stub_discord.py
    factories.py
```

## CRCON HTTP Details

- Base URL: `http://<host>:8010/api/` (server 1), `http://<host>:8011/api/` (server 2), etc.
- Auth: `Authorization: Bearer <django-api-token>` header required.
- Contract source: `GET /api/get_api_documentation` returns endpoint names, args, return types, and allowed methods.
- Client behaviors to test:
  - Per‑request timeout (configurable), JSON content type, connection reuse.
  - Retries with exponential backoff and jitter for transient failures; respect `Retry-After` on 429.
  - Clear exception taxonomy: `CrconAuthError`, `CrconPermissionError`, `CrconRateLimitError`, `CrconServerError`, `CrconTimeoutError`.

## Tooling & Dependencies

- Runtime (when adding the HTTP client): `httpx`
- Dev/test: `pytest`, `pytest-asyncio`, `freezegun`, `respx`, `jsonschema` (or `pydantic`), `pytest-cov`, `mypy`, `ruff`, `black`

Optional: `vcrpy` or `pytest-recording` for golden recordings against a staging CRCON instance.

## CI Pipeline (GitHub Actions)

- Matrix: Python 3.10, 3.11, 3.12
- Steps:
  1. Checkout
  2. Setup Python
  3. Install deps
  4. Lint (`ruff`), format check (`black --check`)
  5. Type check (`mypy`)
  6. Tests (`pytest --cov`)
  7. Upload coverage artifact
- Optional job: Live CRCON contract check behind secrets `CRCON_BASE_URL`, `CRCON_API_TOKEN` (initially non‑blocking).

## Phased Adoption

1. Add DI for server client (unified interface) and persistence root override. Ship unit tests for pools/voting. Introduce mocked `CrconHttpClient` tests and contract fixture.
2. Add parametrized integration tests running against both adapters. Add scheduler tests and Discord stubs.
3. Enable optional live CRCON contract checks in CI. Add concurrency and performance sanity tests. Raise coverage thresholds.

## Assumptions

- CI does not require a live CRCON instance; live tests are optional via secrets.
- Upstream CRCON may evolve; contract tests validate only the subset this bot uses.
- Introducing typing and DI is acceptable prior to broad test coverage.

## Developer Tips

- Prefer testing pure logic in `services/` first; they’re the highest signal and easiest to stabilize.
- Keep HTTP and Discord concerns thin and adapter‑based; this makes them easy to stub and mock.
- When adding new CRCON calls, extend the contract fixture and add spec checks early.
