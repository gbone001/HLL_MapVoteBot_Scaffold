import asyncio
from services.game_server_client import GameServerClient
from persistence.repository import Repository

# TODO Probably want to change this so you can register handlers for different events, e.g. game start, game end.
class GameStateNotifier:
    def __init__(self, repository: Repository, rcon_client: GameServerClient):
        self.repository = repository
        self.rcon_client = rcon_client
        self.handlers = []

    def add_handler(self, handler):
        self.handlers.append(handler)

    async def watch_game_starts(self, bot, guild_id: str, channel_id: str):
        chans = await self.repository.load_channels()
        row = next((r for r in chans if r.get("guild_id") == guild_id and r.get("channel_id") == channel_id), None)
        if not row:
            return

        while True:
            try:
                session_marker = await self.rcon_client.get_latest_match_start_marker()
                last = row.get("last_session_id")

                if session_marker is None:
                    await asyncio.sleep(25)
                    continue

                if last is None:
                    row["last_session_id"] = session_marker
                    await self.repository.save_channels(chans)
                elif session_marker != last:
                    row["last_session_id"] = session_marker
                    await self.repository.save_channels(chans)
                    for handler in self.handlers:
                        await handler()
            except Exception:
                pass
            await asyncio.sleep(25)
