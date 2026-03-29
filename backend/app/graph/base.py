from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas import GraphResponse


class GraphStore(ABC):
    @abstractmethod
    async def rebuild_from_edges(self, edges: list[tuple[str, str]]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def has_path(self, source: str, target: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def add_edge(self, child_id: str, parent_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_ancestors(self, user_id: str, depth: int) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def build_subgraph(self, user_id: str, depth: int, direction: str) -> GraphResponse:
        raise NotImplementedError
