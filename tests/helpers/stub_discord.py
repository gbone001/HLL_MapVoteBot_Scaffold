"""Discord stubs for testing command and view logic without hitting discord.py network layer."""

from __future__ import annotations

from typing import Any, List


class StubUser:
    def __init__(self, id: int = 1234, name: str = "Tester") -> None:
        self.id = id
        self.name = name


class StubChannel:
    def __init__(self) -> None:
        self.sent: List[Any] = []

    async def send(self, content: str = "", **kwargs: Any) -> "StubMessage":
        msg = StubMessage(content=content, channel=self, kwargs=kwargs)
        self.sent.append(msg)
        return msg


class StubMessage:
    def __init__(self, content: str, channel: StubChannel, kwargs: Any) -> None:
        self.content = content
        self.channel = channel
        self.kwargs = kwargs
        self.edits: List[dict] = []

    async def edit(self, content: str | None = None, **kwargs: Any) -> None:
        if content is not None:
            self.content = content
        self.edits.append({"content": content, "kwargs": kwargs})


class StubInteractionResponse:
    def __init__(self, interaction: "StubInteraction") -> None:
        self.interaction = interaction
        self.sent_messages: List[dict] = []
        self.deferred: bool = False

    async def send_message(self, content: str = "", ephemeral: bool = False, **kwargs: Any) -> None:
        payload = {"content": content, "ephemeral": ephemeral, "kwargs": kwargs}
        self.sent_messages.append(payload)
        self.interaction.responses.append(payload)

    async def defer(self) -> None:
        self.deferred = True


class StubInteraction:
    def __init__(self, user: StubUser | None = None, channel: StubChannel | None = None) -> None:
        self.user = user or StubUser()
        self.channel = channel or StubChannel()
        self.responses: List[dict] = []
        self.response = StubInteractionResponse(self)

    async def response_send_message(self, content: str, ephemeral: bool = False, **kwargs: Any) -> None:
        await self.response.send_message(content=content, ephemeral=ephemeral, **kwargs)
