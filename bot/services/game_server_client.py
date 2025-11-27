from typing import Any, Dict, Optional, Protocol


class GameServerClient(Protocol):
    """Interface for interacting with the game server regardless of transport."""

    async def get_public_info(self) -> Dict[str, Any]:
        """Return publicly exposed server information."""

    async def get_latest_match_start_marker(self) -> Optional[str]:
        """Return a marker that identifies the most recent match/session, if available."""

    async def add_map_as_next_rotation(self, map_code: str) -> bool:
        """Queue the provided map code as the next map in rotation."""

    async def apply_server_settings(self, settings: Dict[str, Any]) -> None:
        """Apply arbitrary server settings provided by the scheduler or commands."""
