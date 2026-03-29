import pytest

from app.dag_engine import DAGEngine


@pytest.mark.asyncio
async def test_dag_engine_detects_existing_path():
    store = DAGEngine()
    await store.rebuild_from_edges([("child", "parent"), ("parent", "root")])

    assert await store.has_path("child", "root") is True
    assert await store.has_path("root", "child") is False
    assert await store.get_ancestors("child", 3) == ["parent", "root"]


@pytest.mark.asyncio
async def test_dag_engine_atomic_edge_add():
    store = DAGEngine()
    await store.rebuild_from_edges([("a", "root")])

    async with store.mutation_lock():
        assert store.has_path_unlocked("a", "root") is True
        store.add_edge_unlocked("b", "a")

    assert await store.get_ancestors("b", 2) == ["a", "root"]
