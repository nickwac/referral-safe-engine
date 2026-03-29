from __future__ import annotations

import asyncio
from collections import deque

from app.enums import ReferralStatus, UserStatus
from app.graph.base import GraphStore
from app.schemas import GraphNode, GraphResponse, ReferralEdge


class InMemoryGraphStore(GraphStore):
    def __init__(self) -> None:
        self._parent_by_child: dict[str, str] = {}
        self._children_by_parent: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    async def rebuild_from_edges(self, edges: list[tuple[str, str]]) -> None:
        async with self._lock:
            self._parent_by_child = {}
            self._children_by_parent = {}
            for child_id, parent_id in edges:
                self._parent_by_child[child_id] = parent_id
                self._children_by_parent.setdefault(parent_id, set()).add(child_id)

    async def has_path(self, source: str, target: str) -> bool:
        async with self._lock:
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

    async def add_edge(self, child_id: str, parent_id: str) -> None:
        async with self._lock:
            self._parent_by_child[child_id] = parent_id
            self._children_by_parent.setdefault(parent_id, set()).add(child_id)

    async def get_ancestors(self, user_id: str, depth: int) -> list[str]:
        async with self._lock:
            ancestors: list[str] = []
            current = user_id
            while len(ancestors) < depth:
                parent = self._parent_by_child.get(current)
                if parent is None:
                    break
                ancestors.append(parent)
                current = parent
            return ancestors

    async def build_subgraph(self, user_id: str, depth: int, direction: str) -> GraphResponse:
        async with self._lock:
            nodes_seen: set[str] = {user_id}
            edge_models: list[ReferralEdge] = []
            queue: deque[tuple[str, int]] = deque([(user_id, 0)])

            while queue:
                node, level = queue.popleft()
                if level >= depth:
                    continue
                if direction == "ancestors":
                    parent = self._parent_by_child.get(node)
                    if parent is None:
                        continue
                    nodes_seen.add(parent)
                    edge_models.append(ReferralEdge(id=f"{node}:{parent}", child_id=node, parent_id=parent, status=ReferralStatus.ACCEPTED))
                    queue.append((parent, level + 1))
                else:
                    for child in sorted(self._children_by_parent.get(node, set())):
                        nodes_seen.add(child)
                        edge_models.append(ReferralEdge(id=f"{child}:{node}", child_id=child, parent_id=node, status=ReferralStatus.ACCEPTED))
                        queue.append((child, level + 1))

            node_models = [GraphNode(id=node_id, label=node_id, status=UserStatus.ACTIVE) for node_id in sorted(nodes_seen)]
            return GraphResponse(root_user_id=user_id, direction=direction, depth=depth, nodes=node_models, edges=edge_models)
