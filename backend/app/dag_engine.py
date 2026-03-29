from __future__ import annotations

import asyncio
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from app.enums import ReferralStatus, UserStatus
from app.schemas import GraphResponse, GraphTreeNode


class DAGEngine:
    def __init__(self) -> None:
        self._parent_by_child: dict[str, str] = {}
        self._children_by_parent: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def mutation_lock(self):
        async with self._lock:
            yield

    async def rebuild_from_edges(self, edges: list[tuple[str, str]]) -> None:
        async with self._lock:
            self._parent_by_child = {}
            self._children_by_parent = {}
            for child_id, parent_id in edges:
                self._parent_by_child[child_id] = parent_id
                self._children_by_parent.setdefault(parent_id, set()).add(child_id)

    def has_path_unlocked(self, source: str, target: str) -> bool:
        queue: deque[str] = deque([source])
        visited: set[str] = set()
        while queue:
            node = queue.popleft()
            if node == target:
                return True
            if node in visited:
                continue
            visited.add(node)
            parent = self._parent_by_child.get(node)
            if parent is not None:
                queue.append(parent)
        return False

    async def has_path(self, source: str, target: str) -> bool:
        async with self._lock:
            return self.has_path_unlocked(source, target)

    def add_edge_unlocked(self, child_id: str, parent_id: str) -> None:
        self._parent_by_child[child_id] = parent_id
        self._children_by_parent.setdefault(parent_id, set()).add(child_id)

    async def add_edge(self, child_id: str, parent_id: str) -> None:
        async with self._lock:
            self.add_edge_unlocked(child_id, parent_id)

    def get_ancestors_unlocked(self, user_id: str, depth: int) -> list[str]:
        ancestors: list[str] = []
        current = user_id
        while len(ancestors) < depth:
            parent = self._parent_by_child.get(current)
            if parent is None:
                break
            ancestors.append(parent)
            current = parent
        return ancestors

    async def get_ancestors(self, user_id: str, depth: int) -> list[str]:
        async with self._lock:
            return self.get_ancestors_unlocked(user_id, depth)


dag_engine = DAGEngine()
