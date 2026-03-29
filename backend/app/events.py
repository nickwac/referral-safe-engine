from __future__ import annotations

import asyncio


class EventHub:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    async def publish(self, payload: dict) -> None:
        for queue in list(self._subscribers):
            await queue.put(payload)

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)


event_hub = EventHub()
